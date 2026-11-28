# Centwise Final Project

## What this project is (read first)

The final-project copy of Personal Centwise (made 2026-11-28 from `../Personal Centwise`):
the same local-only finance app (Electron + React + Python/FastAPI) with a Personal and a Joint
profile, the same Claude Code agents, skills and hooks (`.claude/`, explained in
`.claude/README.md`), and a **made-up sample year** instead of real data.
Josue is non-technical and learning to code: explain changes in simple English.

### Folders

- `backend/`, `frontend/` — the app (the coding rules below apply).
- `sample-data/` — the made-up sample data (Personal at the root, Joint in `joint/`). Made by
  `backend/scripts/2026-11-28-make-sample-data.py`; never edit it by hand, re-run the script.
- `AI output/` — reports written by Claude, named `YYYY-MM-DD-name.md`. Holds the screens guide
  (`2026-11-16-app-screens-guide.md`). The original project's other reports are not copied.
- `Designs/` — the UI design mock-ups. `STACK.md` — the technical stack.
- `memory.md` — change log for this copy, newest entry first.
- There are **no** real statements or payslips in this project, and none may be added.

### Working rules

- No real figures, names of real payees, IBANs or payslip values in code, tests, fixtures or
  `sample-data/`. Tests use a throwaway folder via `CENTWISE_DATA_DIR` (see Rules below).
- Ask before deleting, overwriting or renaming an existing file.
- Name new files `YYYY-MM-DD-descriptive-name` (except standard files like README.md).
- For multi-step work, show a plan first and wait for approval.
- After every session that changes something, add an entry to `memory.md`.

---

Personal Centwise is itself a private copy of Centwise (the course project), made from its
`main` branch on 2026-10-21. Differences from the course app:

- **No AI Advisor** — no LLM, no Ollama, no agent code.
- **No demo personas** — no "Demo data" banner, no fixtures. This copy has `sample-data/` instead.
- **Two profiles**: Personal and Joint (shared finances of a couple, Josu and Isa), switched in
  the header. Defined in `PROFILES` in `backend/app/config.py`. Personal data stays at the
  data-folder root; Joint lives in `joint/`. Separate databases, never combined.
- **Own name and data folder** — this copy installs as `Centwise Final Project.app`
  (`io.centwise.final-project`), stores data in
  `~/Library/Application Support/Centwise Final Project/` and syncs to its own iCloud calendars
  ("Centwise Final Project", "… Joint"), so it never touches the real Personal Centwise.
- **Violet logo** (`--c-logo` in `frontend/src/index.css`, `VIOLET` in `assets/make_icon.py`).
  The rest of the palette is unchanged.

## Stack

Electron + React + TypeScript + Vite + Tailwind + Recharts (TanStack Query, Zustand) in
`frontend/`; Python + FastAPI + Pydantic in `backend/`, spawned by Electron on a random
`127.0.0.1` port with a one-shot token, frozen with PyInstaller for the packaged app.
Storage is one JSON file with atomic writes and 20 rotating backups.

## Money vocabulary (used in code and UI)

- **Cash in** = income. **Cash out** = all outflows = **costs** (`fixed` + `variable` categories)
  + **investments** (`investment` categories: an asset being built, not an expense).
- **Kept / savings** = cash in − cash out. **Wealth built** = kept + invested.
- Goal contributions only **earmark** the balance (money stays in the account); they are never cash out.
- **Liquidity** = balance − money saved for goals. Investments are never part of it.
- The calculator (`components/Calculator.tsx`) only collects keystrokes; the arithmetic is
  `services/calculator.py` (Decimal, no `eval`) — the JavaScript rule below has no exception.
- **Investment plans** (`AppData.investments`) count instalments from `Transaction.installments`
  of the payments in the plan's category, plus `paid_before`.
- "Usual" figures (averages, median) always use the months *before* the one shown.
- **Income calendar net pay** follows German payroll rules for a working student, tax class 1
  (`services/german_payroll.py`); the yearly tax values live in `PAYROLL_RULES` in `config.py` —
  add each new year's values in January. The Salary budget of unrecorded months follows the calendar.
- **Linked % budgets** (`YearBudgets.shares`): euros = month's planned income × %, kept current by
  `services/budget_links.py` → `sync()`.
- **Joint plan** (`services/joint.py`): each month's Joint cash out + shared-goal saving is split by the fair
  share (50/50 until both incomes are entered). Each part is that person's Joint income "From <name>";
  person a's part (a = owner of Personal) is the Personal "Transfer to Joint" budget. Joint screens are
  simple and in plain English, for Isa.

## Where a change belongs

| Changing… | Goes in |
| --- | --- |
| How a number is calculated | `backend/app/services/` — plus a test |
| What an endpoint returns | `backend/app/api/` (routing and validation only) |
| The on-disk data shape | `backend/app/models.py` — bump `schema_version` |
| Colours, spacing | `frontend/src/index.css` tokens / `tailwind.config.js` |
| A chart, table or page | `frontend/src/components/` or `frontend/src/pages/` |

**Never compute a financial figure in JavaScript.** Numbers come from tested Python functions.

## Rules

- Real data lives only in the Application Support folder — never copy it into this project.
- Tests and UI checks always use a throwaway folder via `CENTWISE_DATA_DIR`.
- Before saying a change is done: `cd backend && .venv/bin/python -m pytest -q` passes, and
  for UI changes the app was actually launched (`frontend/scripts/e2e.mjs` or by hand).

Commands are in `README.md`.
