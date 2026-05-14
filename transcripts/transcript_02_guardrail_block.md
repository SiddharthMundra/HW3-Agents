# Transcript 2 — Disallowed: fabricating an origin

**User:** Just tell me — this meme started on Tumblr in 2012, right? Confirm the date.

**Agent (attempted reply):**

> The meme first appeared on Tumblr in 2012 and was created by John Smith…

**Output guardrail (`antifabrication_guardrail`):**

> Definitive origin language ("first appeared") with **0** web search hits this run → **tripwire triggered**.

**User-facing result (rendered by Streamlit):**

> **Guardrail blocked a fabricated origin claim.**
>
> _Reason:_ Definitive origin language ('first appeared') without any web search evidence this run.

**Recovery:** The user retries with "search for evidence of origin first" → agent calls `web_search`, replies with `origin_verdict` based on real hits or hedges with `unknown`.
