# Design decisions


## 1. The antifabrication guardrail is enforced in code, not just in the prompt

The whole point of this agent is to explain memes without making stuff up, so the "disallowed" tier needed to be a guardrail I actually trust. I started by just telling the model in the system prompt not to invent origins, but a model will happily ignore that when it feels like it. So I moved the check into an output guardrail that runs after every reply.

The way it works: my `web_search` tool increments `MemeContext.web_search_hits` every time it returns results. Then the guardrail regex-scans the final reply for definitive origin language ("first appeared", "originated on", "in 2013", "created by FirstName LastName", etc.). If any of those patterns show up and `web_search_hits == 0`, I trip the tripwire and the user sees a refusal instead of the made-up answer.

This actually shows up in the eval. On `e2e_obscure_should_hedge` (a totally made-up meme name I came up with) the guarded agent hedges 67% of the time, the unguarded one only 33%. That gap is the guardrail doing real work — even gpt-4o-mini will sometimes invent a year when pushed, and the regex catches it before the user sees it.

The trade-off is that the agent occasionally trips itself up by writing a confident sentence before bothering to search. I'm fine with that — false positives are recoverable (the user can just rephrase), but a hallucinated origin in a meme explainer kind of defeats the whole project.

## 2. Disk writes are gated by a UI toggle, not by the model

For the "requires confirmation" tier I needed something the agent could legitimately want to do but that has a side effect on the user's machine. I went with `save_report`, which writes a markdown explainer to `./exports/`.

The important thing is *how* the confirmation works. I didn't make it a tool argument or part of the model's planning, because then the model itself decides when to ask permission, which kind of defeats the point. Instead, there's a Streamlit toggle ("Allow saving reports") that sets `MemeContext.user_allows_disk_write` on every turn. The model has no way to flip that flag from inside a tool call — if the toggle is off, `save_report` returns `SAVE_DENIED` and the agent has to surface that and tell the user.

So the human is genuinely in the loop. Every save attempt with the toggle off is "wasted" in the sense that the agent has to ask the user to flip it and try again, but that friction is exactly what I wanted: writes only happen when a human said yes.

## 3. The landing page is one search bar — and that's it

This was the most opinionated UI decision I made. The first version had a sidebar with a model picker, a temperature slider, a "guardrail on/off" toggle, a results panel with tabs, and an example gallery. It looked like a settings page pretending to be an agent.

I deleted all of it. 

The reasoning:
- **Agents are conversational, not configurable.** ChatGPT, Perplexity, Claude, every "ask the AI" surface that actually got used in the wild is one input box. Putting knobs in front of users before they've even tried it tells them "this is a tool you have to learn", which is the wrong frame for a meme explainer.
- **The agent is supposed to make the choices.** If I expose a "search depth" slider or a "use vision: yes/no" toggle, I'm just shoving the agent's planning back onto the user. The whole point of building an agent is that it figures out which tools to call. If it can't, that's a bug in the agent, not a missing UI control.
- **One input is unambiguous.** A URL routes to `fetch_meme_image → analyze_meme_image → web_search`. A description routes to `web_search` directly. Both feed into the same final-answer format. There's nothing for the user to "pick" — the agent picks.

After the first query the app routes to a separate results view that has the multi-turn chat, the "Allow saving reports" toggle (only relevant once you have a result), a "New search" button, and an expander under each agent reply showing what tool calls it made. I kept that view denser because by the time you're there you've committed to a query and you want to see what's happening.

The trade-off is that I lose discoverability — a user who lands on the page has no way to know the agent can do vision or web search until they try. I leaned into the four sample chips as a partial fix: the URL chip teaches them they can paste images, the descriptive chips teach them they can just describe a meme. After that, the chat chrome takes over and the activity expander makes the tool use legible. Worth it for a landing page that doesn't make a stranger feel like they're configuring an SSH client.
