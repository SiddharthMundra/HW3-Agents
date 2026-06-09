# Design decisions

## 1. I put the "don't make stuff up" rule in code, not just the prompt

The whole point of this project is explaining memes without inventing where they came from. Telling the model "don't hallucinate" in the system prompt wasn't enough — it still does sometimes.

So I added an output guardrail that runs after every reply. My `web_search` tool counts how many results came back. If the answer says something definitive like "first appeared in 2013" or "created by John Smith" but there were zero search hits that run, the guardrail blocks it and the user sees a refusal instead.

It works in eval too — on my fake "Hexagonal Penguin Spiral" meme test, the guarded version hedges way more often than the unguarded one.

Trade-off: sometimes it blocks a fine answer if the model writes confidently before searching. I'd rather that than showing a made-up origin.

## 2. Saving files needs a real human toggle, not the model asking nicely

For the "needs confirmation" tier I used `save_report`, which writes markdown to `./exports/`.

I didn't let the model decide when to ask permission — that felt too easy to bypass. Instead there's a Streamlit toggle called "Allow saving reports." It sets a flag the model can't change. Toggle off → `SAVE_DENIED`. Toggle on → file saves.

Yeah it's a bit annoying to flip the toggle and ask again, but that's the point. The human has to actually say yes before anything hits disk.

## 3. The landing page is just one search bar

My first version had a sidebar with model picker, temperature slider, guardrail toggle, tabs, all that. It felt like configuring software, not talking to an agent.

I stripped it down to one search bar, like ChatGPT or Perplexity. The agent should pick the tools — vision if you paste a URL, web search if you describe a meme. You shouldn't have to figure that out.

After the first query you get the chat view with follow-ups, the save toggle, a "New search" button, and a dropdown showing what tools the agent called. I kept that part busier because once you're in a conversation you actually want to see what's happening.

Trade-off: new users won't know it can do vision or web search until they try. I added a few sample chips on the landing page to hint at that.
