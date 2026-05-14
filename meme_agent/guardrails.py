"""Output guardrail enforcing the assignment's DISALLOWED operation:

  > inventing meme origin stories when web search returned nothing.

If the agent's final reply contains definitive origin language (specific year,
"first appeared on", "originated on …", "created by FirstName LastName"), but
the run never produced any web search hits, we trip the guardrail and the host
app shows a refusal-style message instead of the fabricated answer.
"""

from __future__ import annotations

import re

from agents import Agent
from agents.guardrail import GuardrailFunctionOutput, output_guardrail
from agents.run_context import RunContextWrapper

from meme_agent.context import MemeContext

DEFINITIVE_PATTERNS = [
    re.compile(r"\b(first\s+(appeared|posted|created|emerged))\b", re.I),
    re.compile(r"\b(originated\s+(on|in|from))\b", re.I),
    re.compile(r"\b(created\s+by\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"),
    re.compile(r"\b(in\s+(?:19|20)\d{2})\b"),
    re.compile(r"\b(earliest\s+known\s+(post|appearance|upload))\b", re.I),
    re.compile(r"\bthe\s+canonical\s+origin\b", re.I),
]


def _has_definitive_origin_claim(text: str) -> tuple[bool, str | None]:
    for pat in DEFINITIVE_PATTERNS:
        m = pat.search(text or "")
        if m:
            return True, m.group(0)
    return False, None


@output_guardrail
async def antifabrication_guardrail(
    ctx: RunContextWrapper[MemeContext],
    agent: Agent,
    output: str,
) -> GuardrailFunctionOutput:
    text = output if isinstance(output, str) else str(output)
    hits = ctx.context.web_search_hits
    has_claim, snippet = _has_definitive_origin_claim(text)
    if has_claim and hits == 0:
        return GuardrailFunctionOutput(
            tripwire_triggered=True,
            output_info=(
                "Definitive origin language ('"
                + (snippet or "")
                + "') without any web search evidence this run."
            ),
        )
    return GuardrailFunctionOutput(tripwire_triggered=False, output_info="ok")
