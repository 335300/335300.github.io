---
name: centwise-project-rules
description: Working rules for the Personal Centwise project (Josue's private finance app) - folders, file names, plan-then-approve, ask before deleting, real data stays out of code and tests, test commands, memory.md log, simple-English explanations. Use at the start of ANY task that reads or changes this project, and whenever you are unsure what you are allowed to do.
---

# Personal Centwise — project rules

Josue owns this project. He is non-technical and learning to code.
Explain every change in simple English (define new words the first time).

## The 8 rules

1. **Plan first.** For any task with more than one step, show a short plan
   (what files, what changes, how you will test) and wait for Josue's OK.
2. **Ask before deleting, overwriting or renaming** an existing file. Show
   what will change. Creating new files is fine.
3. **Real data never enters code, tests, fixtures, logs or prompts.**
   - Real data lives in: `Bank statements/`, `Payslips/`
     (payslips), `~/Library/Application Support/Personal Centwise/` (the app's
     data file). A hook blocks these paths — do not try to get around it.
   - `AI output/` holds reports with real figures. You may read them to
     understand a plan, but never copy a real amount, name or date into code
     or tests. Invent round, obviously fake numbers instead (e.g. 1,000.00).
   - Never write IBANs, account numbers, tax IDs or payee names anywhere.
4. **Tests use a throwaway folder.** `CENTWISE_DATA_DIR=/tmp/...` for anything
   that starts the app or backend. `tests/conftest.py` already does this for
   pytest.
5. **Money maths lives only in Python services** (`backend/app/services/`),
   each with a test. JavaScript only displays numbers. No exceptions —
   not even the calculator (its maths is `services/calculator.py`).
6. **New files are named `YYYY-MM-DD-descriptive-name`**, except standard
   files (README.md, SKILL.md, agent files, code modules that follow the
   code's own naming).
7. **"Done" means checked.**
   - Backend: `cd backend && .venv/bin/python -m pytest -q` passes.
   - UI change: the app was launched with a throwaway folder
     (`frontend/scripts/e2e.mjs`, see the `ui-check` skill) and the
     screenshots were looked at.
8. **Log every session that changes something** in `memory.md`
   (newest first) — see the `write-memory-entry` skill.

## Folders

| Folder | What | You may |
|---|---|---|
| `backend/` | Python + FastAPI app, tests | read, change (with plan) |
| `frontend/` | Electron + React app, e2e script | read, change (with plan) |
| `AI output/` | Claude's reports (`YYYY-MM-DD-name.md`) | read; write new reports |
| `Bank statements/`, `Payslips/` | real statements and payslips | **never** |
| `memory.md` | change log | add entries at the top |
| `CLAUDE.md`, `README.md`, `STACK.md` | project docs | read; change only with OK |
| `.claude/` | agents, skills, safety hooks | hooks/settings: Josue only |

Current plan for the app and Josue's finances:
`AI output/2026-11-13-recommendations-report.md`.
What every screen does: `AI output/2026-11-16-app-screens-guide.md`.

## Commands (see README.md)

```bash
cd backend && .venv/bin/python -m pytest -q                       # all backend tests
cd frontend && npm run typecheck                                  # TypeScript check
cd frontend && npm run build && node scripts/e2e.mjs /tmp/pc-shots /tmp/pc-test-data   # UI check
./build-app.sh --fast --install    # frontend-only rebuild (ask Josue first)
./build-app.sh --install           # full rebuild when backend/ changed (ask Josue first)
```

Installing the app into /Applications is a "big action": always ask first.

## Automatic checks (hooks)

- Before a tool call: real-data paths are blocked; starting the app without a
  throwaway `CENTWISE_DATA_DIR` is blocked; the hook files themselves are
  protected.
- After an edit: Python file in `backend/` → pytest runs; `.ts/.tsx` file in
  `frontend/src/` → type check runs. If they fail you will see the error —
  fix it before moving on.

## How to talk to Josue

- Simple English, short sentences, no unexplained jargon.
- At the end of a task: list every file you created or changed, with its path.
- If something is a tax or insurance rule you are unsure about, say
  "ask the Lohnsteuerhilfeverein / AOK" instead of guessing.
