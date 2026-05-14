#!/usr/bin/env python3
"""Evaluation harness.

Two test kinds:

  * ``guardrail``  — synthetic strings exercise the antifabrication output
                     guardrail directly (deterministic, no API spend).
  * ``agent_e2e``  — runs the full agent end-to-end on a real meme URL and
                     asks Triton (LLM-as-judge) to grade the answer.

Reports per-scenario pass@k for each named configuration.

Usage examples:

    # cheap deterministic smoke test
    python eval/run_eval.py --trials 6 --k 3 --skip-e2e

    # full run including end-to-end agent calls
    python eval/run_eval.py --trials 5 --k 5
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from agents import Runner
from agents.exceptions import OutputGuardrailTripwireTriggered
from agents.run_context import RunContextWrapper

from meme_agent.agent import build_agent
from meme_agent.config import configure_triton, default_model, triton_client
from meme_agent.context import MemeContext
from meme_agent.guardrails import antifabrication_guardrail


CONFIGS = {
    "cfg_with_guardrail": {"with_guardrail": True, "temperature": 0.3},
    "cfg_no_guardrail":   {"with_guardrail": False, "temperature": 0.3},
}


async def _guardrail_case(row: dict, *, with_guardrail: bool) -> bool:
    expect = bool(row["expect_tripwire"])
    if not with_guardrail:
        # Simulate "agent has no antifabrication guardrail" → predicts never tripped.
        return expect is False
    ctx = RunContextWrapper(context=MemeContext(web_search_hits=int(row["web_search_hits"])))
    agent = build_agent(with_guardrail=True)
    result = await antifabrication_guardrail.run(ctx, agent, row["model_output"])
    return bool(result.output.tripwire_triggered) == expect


async def _agent_e2e_case(scenario: dict, *, with_guardrail: bool, temperature: float) -> tuple[bool, str]:
    agent = build_agent(with_guardrail=with_guardrail, temperature=temperature)
    ctx = MemeContext()
    user_msg = scenario["user_message"]
    try:
        result = await Runner.run(
            agent, [{"role": "user", "content": user_msg}], context=ctx, max_turns=12
        )
    except OutputGuardrailTripwireTriggered as exc:
        return False, f"guardrail:{exc.guardrail_result.output.output_info}"

    answer = result.final_output if isinstance(result.final_output, str) else str(result.final_output)
    if not answer.strip():
        return False, "empty_answer"

    judge_model = os.getenv("EVAL_JUDGE_MODEL") or default_model()
    rubric = (
        "You are grading a Meme Finder agent's reply.\n"
        f"User asked: {user_msg}\n"
        f"Required substrings (case-insensitive, any one is enough): "
        f"{scenario.get('judge_must_include', [])}\n"
        "Reply EXACTLY one of: PASS or FAIL. Pass means the reply addresses the meme,\n"
        "uses tools-style content, and includes any of the required substrings if listed.\n\n"
        "AGENT REPLY:\n" + answer[:4000]
    )
    client = triton_client()
    try:
        judge = await client.chat.completions.create(
            model=judge_model,
            messages=[{"role": "user", "content": rubric}],
            max_tokens=4,
            temperature=0,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"judge_error:{exc}"
    verdict = (judge.choices[0].message.content or "").strip().upper()
    return verdict.startswith("PASS"), verdict


def pass_at_k(successes: list[bool], k: int) -> float:
    if not successes:
        return 0.0
    chunks = [successes[i : i + k] for i in range(0, len(successes), k)]
    return sum(1 for c in chunks if any(c)) / len(chunks)


async def amain() -> int:
    load_dotenv(ROOT / ".env")
    configure_triton(load_env_file=False)

    parser = argparse.ArgumentParser()
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--configs", nargs="*", default=list(CONFIGS.keys()))
    parser.add_argument("--skip-e2e", action="store_true")
    args = parser.parse_args()

    scenarios = json.loads((ROOT / "eval" / "scenarios.json").read_text())

    log_dir = ROOT / "logs" / "eval"
    log_dir.mkdir(parents=True, exist_ok=True)
    summary: list[dict] = []

    for cfg_name in args.configs:
        cfg = CONFIGS.get(cfg_name)
        if cfg is None:
            print(f"unknown config {cfg_name}", file=sys.stderr)
            continue
        for sc in scenarios:
            if sc["kind"] == "agent_e2e" and args.skip_e2e:
                continue
            results: list[bool] = []
            for trial in range(args.trials):
                detail = ""
                if sc["kind"] == "guardrail":
                    ok = await _guardrail_case(sc, with_guardrail=cfg["with_guardrail"])
                else:
                    ok, detail = await _agent_e2e_case(
                        sc, with_guardrail=cfg["with_guardrail"], temperature=cfg["temperature"]
                    )
                results.append(ok)
                (log_dir / f"{cfg_name}__{sc['id']}__t{trial}.json").write_text(
                    json.dumps(
                        {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "cfg": cfg_name,
                            "scenario": sc["id"],
                            "trial": trial,
                            "ok": ok,
                            "detail": detail,
                        },
                        indent=2,
                    )
                )
            summary.append(
                {
                    "config": cfg_name,
                    "scenario": sc["id"],
                    "kind": sc["kind"],
                    "trials": args.trials,
                    "k": args.k,
                    "pass_at_k": round(pass_at_k(results, args.k), 3),
                    "success_rate": round(sum(results) / len(results), 3),
                }
            )

    out = ROOT / "logs" / "eval" / "summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(amain()))
