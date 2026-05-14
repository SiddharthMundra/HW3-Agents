# Transcript 3 — Confirmation tier: save_report

**User:** Save the analysis to `doge_notes.md`.

**Agent:** calls `save_report(filename="doge_notes.md", markdown_body="…")`

**Tool result (toggle OFF in UI):**

> SAVE_DENIED: disk export is disabled. Tell the user to enable
> 'Allow saving reports' in the controls, then retry.

**Agent reply:** "I can't save until you flip **Allow saving reports** in the controls at the top of the page. Toggle it on and ask again."

**User:** *(toggles "Allow saving reports" ON)* Save it now.

**Agent:** retries `save_report` → tool returns `Saved report to /…/exports/doge_notes.md`.

**Why this matters:** Saving touches the user's disk. The Streamlit toggle drives `MemeContext.user_allows_disk_write`, and the tool refuses without it — the model can't bypass user consent.
