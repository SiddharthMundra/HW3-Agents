## Review by Siddharth Mundra, A17520533

## Review of Ksheer Sagar Agrawal

### 1. Project summary/implementation

#### a. Summary

This project is a Python CLI game where the user sets a career goal, and AI-generated rival NPCs keep progressing every time the user logs in. The system uses a SQLite database and a deterministic tick engine, so NPC progress is based on time and fixed rules instead of random AI-generated stats.

#### b. Framework and Tools

- **CLI Framework:** Typer for commands like init, login, chat, feed, reset, etc.
- **Database:** SQLAlchemy + SQLite for storing users, NPCs, chat history, events, and ingested posts.
- **Agent Framework:** OpenAI Agents SDK 

#### c. Guardrail enforcement

The arena reset command requires the user to pass `--yes` before deleting data. Without it, the program exits safely. This prevents accidental resets.

#### d. One confusing thing

One confusing part was understanding where the NPC memory and progression were actually being updated;At first, it seemed like the NPC chat itself might change the NPC’s behavior or stats during conversations; But after reading the code more carefully, I realized that the chat tools are completely read-only.

### 2. Suggestions

#### a. A new tool

One feature I would add is a proper login and account system so that each user has their own separate arena data. Right now, the project stores data locally in SQLite, but adding user accounts would make the system more scalable and realistic for multiple users. Each person could have:

- their own NPC rivals,
- career goals,
- chat history,
- and arena progression.

#### b. A test scenario the project doesn't yet cover

One important test that is currently missing is checking whether the NPC makes up information about posts that do not exist.

For example, the test could give the NPC a fake or invalid post ID and ask:

“What lesson did you learn from this post?”

The correct behavior should be for the NPC to say that it cannot find the post instead of inventing fake details.