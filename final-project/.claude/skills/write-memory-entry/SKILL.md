---
name: write-memory-entry
description: Write the change-log entry in Personal Centwise memory.md in the house format (newest first, one entry per session, What changed / Why / Checks / Open points, no private identifiers), inserted safely without retyping the file. Use at the end of every session that changed the app, the reports in AI output/, the .claude setup, or a decision about them.
---

# Write a memory.md entry

`memory.md` (project root) is the change log for the whole project. Newest
entry at the **top**, directly under the `---` line that follows the format
block. **One entry per session.** If today already has an entry for the same
work, add a "**Later the same day — …**" bullet to it instead.

## Format

```markdown
## YYYY-MM-DD — short title

- **What changed:** files, features, numbers (code paths in backticks).
- **Why:** the decision or new fact behind it ("Josu's request", a rule change…).
- **Checks:** pytest result (e.g. "pytest 401 passed"), e2e result
  ("e2e.mjs 42/42, console clean"), screenshots looked at, build done or not.
- **Open points / next step:** what is left, what needs Josue's OK.
```

Use the bold labels the recent entries use (`**Backend:**`, `**Checks:**`,
`**Installed:**`…) when they fit better. Keep each bullet short.

## Privacy

Never write account numbers, IBANs, tax IDs, payee names or other identifiers.
Real amounts only when they are already Josue's decision in a report (e.g. a
budget he chose); never copy amounts from statements or payslips.

## Insert it safely

Do not retype the whole file. Insert with a small script (read → insert →
write), so nothing else changes:

```bash
python3 - <<'PY'
from pathlib import Path
p = Path("memory.md")
text = p.read_text(encoding="utf-8")
entry = """## YYYY-MM-DD — title

- **What changed:** …
- **Why:** …
- **Checks:** …
- **Open points:** …

"""
marker = "\n---\n\n"
i = text.index(marker) + len(marker)   # first '---' after the format block
p.write_text(text[:i] + entry + text[i:], encoding="utf-8")
PY
```

Then show Josue the new entry (the first ~15 lines of the file).
