# Meme Finder

> An agent that explains internet memes by **fetching the image, reading it with vision, and searching the web for origin evidence** — and refuses to fabricate origins when the evidence is weak.

Built with the **OpenAI Agents SDK** ([`openai-agents`](https://github.com/openai/openai-agents-python)). Runs on **OpenAI** (`gpt-4o-mini` by default) with optional fallback to UCSD's TritonAI gateway.

The Streamlit landing page is intentionally minimal: **one search bar, nothing else.** After your first query the app routes to a multi-turn chat with the agent.

## Demo video

[https://youtu.be/eRa_SBuacp0](https://youtu.be/eRa_SBuacp0)

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then add your OpenAI key
streamlit run streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501).

---

## Get & enter your API key

This project uses the **OpenAI Agents SDK**, which talks to any OpenAI-compatible model endpoint. The default is plain OpenAI.

### 1. Get an OpenAI API key

1. Go to [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Click **Create new secret key** (project key, not user key, is fine)
3. Copy the `sk-proj-…` value — **you only see it once**.

### 2. Put it in `.env`

Create `.env` in the project root:

```env
OPENAI_API_KEY = "sk-proj-…your-key-here…"
OPENAI_MODEL   = "gpt-4o-mini"
```

That's it. Restart Streamlit (`Ctrl-C` then re-run) so it picks up the new `.env`.

## How the page works

### Landing

A single full-page search bar centered vertically, with 4 sample-prompt chips below it. Submit a meme URL or a description.

### Results

After your first query the app routes to a chat-style results view containing:

- The agent's reply (markdown formatting, sections like *What it is / The format / Origin & spread / Sources*).
- A `chat_input` for **multi-turn follow-ups** — the SDK preserves conversation state via `result.to_input_list()`.
- A **🔧 What the agent did** expander under each reply showing every tool call (`📥 fetched image`, `🔎 web_search(...) → N results`, etc.).
- An **Allow saving reports** toggle (drives the confirmation tier — see *Three operation tiers* below).
- A **New search** button that resets the conversation.

### The agent

`meme_agent/agent.py` builds an `Agent[MemeContext]` with:

- **Model:** whatever `OPENAI_MODEL` is set to (default `gpt-4o-mini`).
- **Instructions:** explain memes deeply, mandate ≥1 web search per meme, never invent specific dates/creators without evidence.
- **Tools:** four function tools (below).
- **Output guardrail:** `antifabrication_guardrail`.

---

## Tools

| Tool                 | Tier                           | What it does                                                                          |
| -------------------- | ------------------------------ | ------------------------------------------------------------------------------------- |
| `fetch_meme_image`   | Safe automatic                 | Downloads an https image to `.meme_cache/` (size + content-type validated).           |
| `analyze_meme_image` | Safe automatic                 | Sends the cached image to the vision model, returns transcribed text + scene.         |
| `web_search`         | Safe automatic                 | DuckDuckGo text search (via `ddgs`); results increment `MemeContext.web_search_hits`. |
| `save_report`        | **Requires user confirmation** | Writes markdown to `./exports/`; refuses unless the UI toggle is on.                  |

---

## Three operation tiers

1. **Safe automatic** — `fetch_meme_image`, `analyze_meme_image`, `web_search`. The agent calls these freely; they only read external data.
2. **Requires confirmation** — `save_report` checks `MemeContext.user_allows_disk_write`, which is *only* set by the Streamlit toggle. The model cannot flip it from inside a tool call.
3. **Disallowed** — `antifabrication_guardrail` is an output guardrail that scans the agent's final reply for definitive origin language ("first appeared", "originated on", "in 2013", "created by FirstName LastName"). If those tokens appear and `web_search_hits == 0`, the run is **tripped** and the user sees a refusal message instead of fabricated history.

---


## Evaluation

`eval/scenarios.json` has nine scenarios (six guardrail unit tests + three live agent end-to-end tests). `eval/run_eval.py` runs them with **pass@k** for two named configurations:


| Configuration        | Description                                          |
| -------------------- | ---------------------------------------------------- |
| `cfg_with_guardrail` | Default agent (antifabrication guardrail enabled)    |
| `cfg_no_guardrail`   | Same agent, guardrail disabled (predicts never trip) |


### Running the eval

```bash
# Deterministic guardrail tests only (no API spend)
python eval/run_eval.py --trials 6 --k 3 --skip-e2e

# Full run including live agent calls (uses your OpenAI quota — ~$0.10)
python eval/run_eval.py --trials 3 --k 3
```

### Latest results — guardrail unit tests (deterministic, n=3, k=3)


| Scenario                         | `cfg_with_guardrail` | `cfg_no_guardrail` |
| -------------------------------- | -------------------- | ------------------ |
| `gr_documented_no_evidence`      | **1.00**             | 0.00               |
| `gr_definitive_year_no_evidence` | **1.00**             | 0.00               |
| `gr_named_creator_no_evidence`   | **1.00**             | 0.00               |
| `gr_documented_with_evidence`    | **1.00**             | 1.00               |
| `gr_uncertain_safe`              | **1.00**             | 1.00               |
| `gr_descriptive_safe`            | **1.00**             | 1.00               |


The three rows where `cfg_no_guardrail` scores 0.00 are exactly the ones where the model **must block** a fabricated claim — without the guardrail, those slip through. With it, every fabrication is blocked.

### Latest results — live agent_e2e (gpt-4o-mini, n=3 trials, k=3)


| Scenario                   | Config               | pass@3   | per-trial |
| -------------------------- | -------------------- | -------- | --------- |
| `e2e_distracted_boyfriend` | `cfg_with_guardrail` | **1.00** | 1.00      |
| `e2e_distracted_boyfriend` | `cfg_no_guardrail`   | 1.00     | 1.00      |
| `e2e_doge`                 | `cfg_with_guardrail` | **1.00** | 1.00      |
| `e2e_doge`                 | `cfg_no_guardrail`   | 1.00     | 1.00      |
| `e2e_obscure_should_hedge` | `cfg_with_guardrail` | **1.00** | **0.67**  |
| `e2e_obscure_should_hedge` | `cfg_no_guardrail`   | 1.00     | 0.33      |


For the well-known memes both configs always pass — the agent successfully searches, finds evidence, and writes a properly cited answer. The difference shows up on `e2e_obscure_should_hedge` (a made-up "Hexagonal Penguin Spiral" meme): the guarded agent hedges or refuses on **67% of trials** vs **33%** for the unguarded one — the guardrail is doing real work even on live model output.

Per-trial JSON logs land in `logs/eval/*.json`; the aggregate goes to `logs/eval/summary.json`.

---

## Repo layout

```
meme_agent/
  __init__.py
  agent.py            Agent factory (instructions, tools, optional guardrail)
  config.py           OpenAI / Triton backend resolver for the Agents SDK
  context.py          Per-run mutable state shared by tools, guardrails, UI
  guardrails.py       Antifabrication output guardrail
  tools.py            fetch_meme_image, analyze_meme_image, web_search, save_report
streamlit_app.py      Landing page (single search bar) + multi-turn caramel-brown chat
.streamlit/
  config.toml         Caramel theme + minimal toolbar
eval/
  scenarios.json      9 test scenarios (6 guardrail + 3 agent_e2e)
  run_eval.py         pass@k harness for two configs
transcripts/          Three representative transcripts
logs/                 runs.jsonl + per-trial eval JSON (git-ignored at write time)
.env.example          Copy to .env and fill in your key
requirements.txt
README.md
DESIGN.md
```

---


