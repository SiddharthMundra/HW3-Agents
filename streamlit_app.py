"""Meme Finder — Streamlit front-end.

Landing page is INTENTIONALLY just one search bar (per project requirements).
After the user submits the first query the app routes to a results view that
hosts a multi-turn chat with the agent.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from agents import Runner
from agents.exceptions import AgentsException, OutputGuardrailTripwireTriggered

from meme_agent.agent import build_agent
from meme_agent.config import active_backend, configure_agents, default_model
from meme_agent.context import MemeContext

load_dotenv(override=True)

LOG_PATH = Path("logs/runs.jsonl")

SAMPLE_PROMPTS = [
    "Explain the Distracted Boyfriend meme",
    "Slow walking Peter from Family Guy — what's the meme?",
    "https://upload.wikimedia.org/wikipedia/en/5/5f/Original_Doge_meme.jpg",
    "What's the deal with the Surprised Pikachu meme?",
]


def _inject_css() -> None:
    """Caramel-brown theme. Hides Streamlit chrome (menu, footer, deploy button)."""
    st.markdown(
        """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap');

  :root {
    --mf-cream:    #FBF6EE;
    --mf-cream-2:  #F5EBD9;
    --mf-caramel:  #B7763A;
    --mf-caramel-2:#8A4F1C;
    --mf-mocha:    #5A3217;
    --mf-espresso: #3A1F0E;
    --mf-line:     #E5D6BC;
  }

  html, body, .stApp, [class*="css"] {
    font-family: 'Inter', system-ui, sans-serif;
    color: var(--mf-espresso);
  }
  .stApp {
    background:
      radial-gradient(1200px 600px at 80% -10%, #F0DDB6 0%, transparent 60%),
      radial-gradient(900px  500px at -10% 110%, #EBC892 0%, transparent 55%),
      var(--mf-cream);
  }

  /* Hide Streamlit chrome */
  #MainMenu, footer { visibility: hidden !important; }
  [data-testid="stToolbar"],
  [data-testid="stDeployButton"],
  [data-testid="stStatusWidget"],
  [data-testid="stDecoration"] { display: none !important; }
  header[data-testid="stHeader"] { background: transparent; height: 0; }
  div[data-testid="stSidebar"] { display: none !important; }

  .block-container { padding-top: 2rem !important; padding-bottom: 3rem !important; max-width: 880px; }

  /* ---------- LANDING ---------- */
  .landing-wrap {
    min-height: 70vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1.0rem;
    text-align: center;
    animation: fadein 600ms ease-out;
  }
  @keyframes fadein { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }

  .landing-eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.32em;
    font-size: 0.72rem;
    color: var(--mf-caramel-2);
    font-weight: 600;
  }
  .landing-title {
    font-family: 'Fraunces', serif;
    font-size: clamp(3rem, 7vw, 5rem);
    font-weight: 600;
    letter-spacing: -0.03em;
    line-height: 1.0;
    color: var(--mf-mocha);
    margin: 0;
  }
  .landing-title em {
    font-style: italic;
    color: var(--mf-caramel-2);
    font-weight: 500;
  }
  .landing-sub {
    color: #6E4D2A;
    font-size: 1.02rem;
    margin: 0 0 0.6rem 0;
    max-width: 38rem;
    line-height: 1.55;
  }

  body[data-mf-page="landing"] [data-testid="stTextInput"] {
    width: 100%;
    max-width: 640px;
    margin: 0 auto;
  }
  body[data-mf-page="landing"] [data-testid="stTextInput"] label { display: none; }
  body[data-mf-page="landing"] [data-testid="stTextInput"] input {
    border-radius: 999px !important;
    padding: 1.05rem 1.4rem !important;
    font-size: 1.05rem !important;
    border: 1px solid var(--mf-line) !important;
    background: #fffdf8 !important;
    color: var(--mf-espresso) !important;
    box-shadow: 0 16px 38px rgba(90, 50, 23, 0.12) !important;
  }
  body[data-mf-page="landing"] [data-testid="stTextInput"] input:focus {
    border-color: var(--mf-caramel) !important;
    box-shadow: 0 16px 38px rgba(138, 79, 28, 0.22),
                0 0 0 4px rgba(183, 118, 58, 0.18) !important;
    outline: none !important;
  }

  /* Sample prompt chips */
  body[data-mf-page="landing"] .stButton > button {
    background: rgba(255, 253, 248, 0.85) !important;
    color: var(--mf-mocha) !important;
    border: 1px solid var(--mf-line) !important;
    border-radius: 999px !important;
    padding: 0.45rem 0.95rem !important;
    font-weight: 500 !important;
    font-size: 0.85rem !important;
    box-shadow: 0 4px 10px rgba(90, 50, 23, 0.06) !important;
    transition: all 140ms ease !important;
  }
  body[data-mf-page="landing"] .stButton > button:hover {
    background: var(--mf-cream-2) !important;
    border-color: var(--mf-caramel) !important;
    color: var(--mf-caramel-2) !important;
    transform: translateY(-1px);
  }

  /* Primary submit button (caramel) */
  [data-testid="stFormSubmitButton"] button,
  body[data-mf-page="results"] .stButton > button {
    background: linear-gradient(180deg, var(--mf-caramel) 0%, var(--mf-caramel-2) 100%) !important;
    color: #fffdf8 !important;
    border: 1px solid var(--mf-caramel-2) !important;
    border-radius: 999px !important;
    padding: 0.7rem 1.2rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.01em !important;
    box-shadow: 0 10px 22px rgba(138, 79, 28, 0.25) !important;
    transition: transform 120ms ease, box-shadow 120ms ease !important;
  }
  [data-testid="stFormSubmitButton"] button:hover,
  body[data-mf-page="results"] .stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 14px 26px rgba(138, 79, 28, 0.32) !important;
  }

  /* ---------- RESULTS ---------- */
  .results-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.9rem 1.1rem;
    margin-bottom: 1rem;
    background: rgba(255, 253, 248, 0.85);
    border: 1px solid var(--mf-line);
    border-radius: 16px;
    backdrop-filter: blur(8px);
  }
  .results-brand {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 1.35rem;
    color: var(--mf-mocha);
    letter-spacing: -0.01em;
  }
  .results-brand em { color: var(--mf-caramel-2); font-style: italic; font-weight: 500; }
  .results-meta { font-size: 0.78rem; color: #6E4D2A; }
  .results-meta code {
    background: var(--mf-cream-2);
    color: var(--mf-mocha);
    padding: 1px 6px;
    border-radius: 6px;
  }

  /* Toggle accent */
  [data-baseweb="toggle"] [role="switch"][aria-checked="true"] > div {
    background: var(--mf-caramel) !important;
  }

  /* Chat bubbles */
  .stChatMessage {
    border-radius: 16px !important;
    border: 1px solid var(--mf-line) !important;
    background: #fffdf8 !important;
    box-shadow: 0 6px 18px rgba(90, 50, 23, 0.06) !important;
  }
  .stChatMessage [data-testid="stChatMessageAvatarUser"] {
    background: var(--mf-caramel) !important;
  }
  .stChatMessage [data-testid="stChatMessageAvatarAssistant"] {
    background: var(--mf-mocha) !important;
  }

  /* Tool activity expander */
  .stChatMessage details {
    background: var(--mf-cream-2);
    border: 1px dashed var(--mf-line);
    border-radius: 10px;
    padding: 0.4rem 0.7rem;
    margin-top: 0.6rem;
    font-size: 0.84rem;
    color: var(--mf-mocha);
  }
  .stChatMessage details summary {
    cursor: pointer;
    color: var(--mf-caramel-2);
    font-weight: 600;
  }
  .stChatMessage details ul { margin: 0.4rem 0 0 1rem; padding: 0; }

  /* Chat input */
  [data-testid="stChatInput"] textarea {
    background: #fffdf8 !important;
    border: 1px solid var(--mf-line) !important;
    color: var(--mf-espresso) !important;
  }
  [data-testid="stChatInput"] textarea:focus {
    border-color: var(--mf-caramel) !important;
    box-shadow: 0 0 0 3px rgba(183, 118, 58, 0.18) !important;
  }

  .stSpinner > div > div { border-top-color: var(--mf-caramel) !important; }
  a, a:visited { color: var(--mf-caramel-2); }
</style>
        """,
        unsafe_allow_html=True,
    )


def _set_body_attr(page: str) -> None:
    st.markdown(
        f"<script>document.body.setAttribute('data-mf-page', '{page}');</script>",
        unsafe_allow_html=True,
    )


def _append_log(payload: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, default=str) + "\n")


async def _run_turn(input_items: list, ctx: MemeContext, *, with_guardrail: bool):
    agent = build_agent(with_guardrail=with_guardrail)
    return await Runner.run(agent, input_items, context=ctx, max_turns=14)


def _activity_html(activity: list[str]) -> str:
    if not activity:
        return ""
    items = "".join(f"<li>{a}</li>" for a in activity)
    return (
        f"<details><summary>🔧 What the agent did ({len(activity)} steps)</summary>"
        f"<ul>{items}</ul></details>"
    )


def _execute_turn(prompt: str, *, allow_disk: bool, with_guardrail: bool) -> str:
    st.session_state.sdk_items.append({"role": "user", "content": prompt})
    st.session_state.chat.append({"role": "user", "content": prompt, "activity": []})

    ctx = MemeContext(user_allows_disk_write=allow_disk)
    answer = ""
    error_detail = None
    try:
        with st.spinner("Researching the meme…"):
            result = asyncio.run(
                _run_turn(st.session_state.sdk_items, ctx, with_guardrail=with_guardrail)
            )
        out = result.final_output
        answer = out if isinstance(out, str) else str(out)
        st.session_state.sdk_items = result.to_input_list()
    except OutputGuardrailTripwireTriggered as exc:
        info = str(exc.guardrail_result.output.output_info)
        answer = (
            "**🛑 Guardrail blocked a fabricated origin claim.**\n\n"
            f"_Reason:_ {info}\n\n"
            "I tried to make a definitive claim without web evidence. Try a more "
            "specific question, or accept that the exact origin is uncertain."
        )
        error_detail = info
        st.session_state.sdk_items.pop()
    except AgentsException as exc:
        answer = f"**Agent error:** `{exc}`"
        error_detail = str(exc)
        st.session_state.sdk_items.pop()
    except Exception as exc:  # noqa: BLE001
        answer = f"**Unexpected error:** `{exc}`"
        error_detail = str(exc)
        st.session_state.sdk_items.pop()

    st.session_state.chat.append(
        {"role": "assistant", "content": answer, "activity": list(ctx.activity)}
    )
    _append_log(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "model": default_model(),
            "with_guardrail": with_guardrail,
            "allow_disk": allow_disk,
            "user_preview": prompt[:500],
            "activity": ctx.activity,
            "error": error_detail,
        }
    )
    return answer


def _landing() -> None:
    _set_body_attr("landing")
    st.markdown(
        """
<div class="landing-wrap">
  <div class="landing-eyebrow">CSE 190 · Agents Project</div>
  <h1 class="landing-title">Meme <em>Finder</em></h1>
  <p class="landing-sub">Paste a meme URL or describe one — the agent reads the image, searches the web, and explains where it came from, what people use it for, and why it's funny.</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("landing_search", clear_on_submit=False):
        query = st.text_input(
            label="search",
            placeholder="Paste a meme URL or describe a meme…",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Search", use_container_width=True)

    chip_cols = st.columns(len(SAMPLE_PROMPTS))
    for i, sample in enumerate(SAMPLE_PROMPTS):
        with chip_cols[i]:
            label = sample if len(sample) < 32 else sample[:30] + "…"
            if st.button(label, key=f"chip_{i}", help=sample, use_container_width=True):
                st.session_state.pending_prompt = sample
                st.session_state.page = "results"
                st.rerun()

    if submitted and query.strip():
        st.session_state.pending_prompt = query.strip()
        st.session_state.page = "results"
        st.rerun()


def _results() -> None:
    _set_body_attr("results")

    backend = active_backend()
    backend_label = "OpenAI" if backend.name == "openai" else "TritonAI"

    st.markdown(
        f"""
<div class="results-bar">
  <div>
    <div class="results-brand">Meme <em>Finder</em></div>
    <div class="results-meta">Model <code>{default_model()}</code> · {backend_label}</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns([1, 1])
    with cols[0]:
        st.toggle(
            "Allow saving reports",
            key="allow_disk",
            help="Enables the save_report tool (the confirmation-tier guardrail).",
        )
    with cols[1]:
        if st.button("New search", use_container_width=True):
            st.session_state.page = "landing"
            st.session_state.sdk_items = []
            st.session_state.chat = []
            st.rerun()

    pending = st.session_state.pop("pending_prompt", None)
    if pending:
        _execute_turn(
            pending,
            allow_disk=st.session_state.get("allow_disk", False),
            with_guardrail=True,
        )

    for msg in st.session_state.chat:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("activity"):
                st.markdown(_activity_html(msg["activity"]), unsafe_allow_html=True)

    follow_up = st.chat_input("Follow up — ask another question or share another meme URL…")
    if follow_up:
        _execute_turn(
            follow_up,
            allow_disk=st.session_state.get("allow_disk", False),
            with_guardrail=True,
        )
        st.rerun()


def main() -> None:
    st.set_page_config(
        page_title="Meme Finder",
        page_icon="🟤",
        layout="centered",
        initial_sidebar_state="collapsed",
        menu_items={},
    )
    _inject_css()

    try:
        configure_agents(load_env_file=True)
    except Exception as exc:  # noqa: BLE001
        st.error(str(exc))
        st.stop()

    st.session_state.setdefault("page", "landing")
    st.session_state.setdefault("sdk_items", [])
    st.session_state.setdefault("chat", [])
    st.session_state.setdefault("allow_disk", False)

    if st.session_state.page == "landing":
        _landing()
    else:
        _results()


if __name__ == "__main__":
    main()
