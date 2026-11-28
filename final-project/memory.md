# memory.md — change log for Centwise Final Project

Record every change to this project here: the app, the sample data, the reports in `AI output/`,
the `.claude/` setup, and decisions that affect them. Newest entries go at the top. One entry per
session.

Format:

```
## YYYY-MM-DD — short title
- What changed (files, features, numbers)
- Why (the decision or new fact behind it)
- Checks
- Open points / next step
```

Privacy: never write account numbers, IBANs, tax IDs or other identifiers here. This project
holds only made-up data.

The history before this copy (2026-10-21 to 2026-11-20) is in `memory.md` of Personal Centwise.
It is not copied here because it talks about real figures.

---

## 2026-11-28 — Final project created from Personal Centwise, with sample data

- **What changed:**
  - New folder `AI Projects/Final project`: a copy of Personal Centwise (`backend/`, `frontend/`,
    `assets/`, `Designs/`, `.claude/`, `CLAUDE.md`, `README.md`, `STACK.md`, `setup.sh`,
    `build-app.sh`). Not copied: bank statements, payslips, the original `AI output/` reports and
    `memory.md` (real figures), the essay, git history and build output.
  - Own identity, so it can never touch the real app: `APP_NAME = "Centwise Final Project"` (data
    in `~/Library/Application Support/Centwise Final Project/`), app id
    `io.centwise.final-project`, backend `centwise-final-project-backend`, own iCloud calendar
    names (`OWN_CALENDARS`), own build cache. Two tests updated to the new names.
  - **Sample data:** `backend/scripts/2026-11-28-make-sample-data.py` builds an invented year
    (Jan–Nov 2026) for Personal and Joint through the app's own API (TestClient, fixed random
    seed, "today" = 28 Nov 2026). Result in `sample-data/`. Past months get their plan as typed
    budgets (Salary, Transfer to Joint, From Josu / From Isa), because the app fills those itself
    only for months not recorded yet.
  - New `tests/test_sample_data.py` (2 tests): the generator fills both profiles, the files load
    under the current schema, the 11 Transfer to Joint links match, repeat runs give the same
    transactions, and existing data needs `--force`.
  - `run-sample.sh` opens the app on a fresh temp copy of `sample-data/`. `setup.sh` makes the
    sample data if it is missing; the first `build-app.sh --install` copies it into the installed
    app's (empty) data folder. `.gitignore` keeps `sample-data/` in git.
  - `backend/requirements.txt` with pinned versions; `setup.sh` now installs from it (the old
    list missed `cryptography` and the Apple calendar packages).
  - `AI output/2026-11-16-app-screens-guide.md` copied for the frontend agents, with its example
    amounts changed to neutral ones.
  - `.claude/README.md` explains the 6 agents, 10 skills and 3 hooks. The agents, skills, hooks
    and `settings.json` themselves are copied unchanged.
  - `frontend/scripts/2026-11-28-sample-screens.mjs`: screenshots of every tab in both profiles
    on the sample data.
- **Why:** Josu wanted a copy for the final project with sample data and the agents used to build it.
- **Checks:** pytest 547 passed (545 old + 2 new); `tsc` clean; e2e 52/52, console clean;
  sample screens script: all 10 tabs (6 Personal, 4 Joint) load with no console errors.
  Screenshots looked at and saved in `screenshots/2026-11-28-sample-data/`.
- **Open points:** the agents and skills still say "Personal Centwise" and mention the real-data
  folders; that is how they were used, so they were left as they are. In the Joint sample,
  November ends with less free money than December's bills (the holiday goal holds 1.100 €),
  so the Joint Overview shows "Not enough yet" — a real-looking warning, kept on purpose.
  No git repository yet; the installed app was not built (`./build-app.sh --install`).
