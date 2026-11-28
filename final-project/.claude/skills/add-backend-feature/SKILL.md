---
name: add-backend-feature
description: Step-by-step recipe to add or change backend logic in Personal Centwise - plan, pure Python service with hand-checked tests first, FastAPI route, Pydantic model change with defaults and SCHEMA_VERSION bump, TypeScript types, full pytest run, blind verification and a memory.md entry. Use whenever a task adds or changes a calculation, an endpoint, a stored field, or a yearly rule value.
---

# Add or change a backend feature

Load first: `centwise-project-rules`, `centwise-architecture-map`,
`centwise-money-vocabulary` (and a domain skill such as
`german-werkstudent-payroll` when the feature touches it).

## 1. Plan (wait for OK)

Write a short plan for Josue in simple English:
- What the feature does, in one or two sentences.
- Files: service, route, model, config, tests, frontend types (if the API changes).
- Does the stored data shape change? (then: `SCHEMA_VERSION` bump)
- How you will test it, with one hand-worked example.
- Anything you are unsure about (a rule, a number) → ask instead of guessing.

**Stop and wait for Josue's OK.**

## 2. Write the test first

In `backend/tests/test_<area>.py` (new file `test_<feature>.py` if none fits):
- Use the `conftest.py` fixtures (`year`, `data`, `tx(...)`, `TODAY`).
- Put the hand calculation in the docstring, like `test_german_payroll.py`:
  ```python
  def test_full_time_month_2026():
      """3 500 € in 2026: pension 9.3 % = 325.50. Yearly: 42 000 − 1 230 − 36 − 3 906 = 36 828 …"""
  ```
- Cover: normal case, each boundary, zero/empty, year change, one-off
  transactions excluded from "usual" figures, Personal vs Joint if relevant.
- Fake round numbers only. Never real amounts, names or dates from Josue's data.

## 3. The service (pure function)

`backend/app/services/<x>.py`:
- Inputs: model objects and plain values; **`today` is a parameter** — never
  `date.today()` inside a service.
- Output: a plain `dict` (or list of dicts) with clear keys; money as numbers
  rounded the way the module already rounds.
- No file access, no global state, no imports from `api/`.
- Constants go into `config.py` with a comment (what, unit, source/owner's choice).
- Docstring in simple English: what it returns and the rule behind it.

## 4. The route (if the screen needs it)

`backend/app/api/<area>.py`: routing and validation only.
- Use `Depends(get_repository)` (or `get_synced_repository` for plans and
  forecasts), `Depends(get_today)`.
- Input models (`…Input`) live in `models.py`; errors via `not_found`,
  `conflict`, `bad_request` from `deps.py`.
- After a change: `repo.save()`. If budgets follow income or plans, call
  `budget_links.sync(repo.data, today)` like the existing routes do.
- A new router module must be added to the list in `app.py`.

## 5. Stored data changes

- New fields in `models.py` **must have defaults** so old files still load.
- Bump `SCHEMA_VERSION` in `config.py` and add a comment line saying what the
  new version adds.
- If old values must be converted: a Pydantic validator + a test that loads an
  old-shape JSON.
- Remind Josue: before installing, keep a copy of his data file (he did this
  as `pre-schema-7-…json` last time).

## 6. Frontend types

If the response shape changed: update `frontend/src/lib/types.ts` and the hook
in `frontend/src/api/queries.ts`. The UI itself → hand over to the
frontend-engineer (`add-ui-card`).

## 7. Check

- `cd backend && .venv/bin/python -m pytest -q` → all pass (the hook also runs
  `-x -q` after each edit).
- Ask for a blind check (`calc-verifier` / `verify-numbers`) when a money
  figure is new or its rule changed.
- `cd frontend && npm run typecheck` if types changed.

## 8. Finish

- `write-memory-entry`.
- Tell Josue in simple English: what changed, which files, test count, what
  is left (e.g. "the UI part is next", "needs a full build to install").
