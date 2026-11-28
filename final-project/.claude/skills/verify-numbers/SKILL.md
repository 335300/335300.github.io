---
name: verify-numbers
description: Blind check of a Personal Centwise money calculation - recompute the expected result from the written rules on a synthetic fixture, get the service's real answer with run_service.py (without reading the service code), compare field by field with compare.py, and write a PASS/FAIL report. Use after any change in backend/app/services/, before a release, or when a number on screen looks wrong.
---

# Verify numbers (blind recomputation)

"Blind" means: you work out the expected answer **from the rules**, not from
the code. Then you compare. If you read the code first, you would copy its
mistakes.

## Never

- Never open `backend/app/services/<the service you check>.py` or its test.
  (`--signature` shows the function's inputs and docstring — that is enough.)
- Never use real data. Fixtures are synthetic, with round fake numbers,
  saved in `/tmp/pc-verify/` (or reuse `backend/tests/fixtures/`).
- Never "fix" the service yourself. You report; the backend-service-engineer fixes.

## Steps

1. **Know the rule.** Read the rule text: the task description, the relevant
   knowledge skill (`german-werkstudent-payroll`, `centwise-money-vocabulary`),
   `CLAUDE.md` money vocabulary. Write the rule down in your own words.
2. **See the inputs:**
   ```bash
   backend/.venv/bin/python .claude/skills/verify-numbers/scripts/run_service.py <module.function> --signature
   ```
3. **Make a synthetic fixture** (only if the function needs model objects) in
   `/tmp/pc-verify/`. Keep it tiny and hand-checkable (2–5 transactions,
   round numbers). Months inside the code are 0–11.
4. **Compute the expected result yourself** with a small Python script in
   `/tmp/pc-verify/expected.py` using `decimal.Decimal`, following the rule
   step by step (comment each step). Save `/tmp/pc-verify/expected.json` with
   only the fields you can derive from the rules.
5. **Get the service's answer:**
   ```bash
   backend/.venv/bin/python .claude/skills/verify-numbers/scripts/run_service.py <module.function> \
     --args '<json>' --out /tmp/pc-verify/actual.json
   ```
   Special args: `{"$date": "2026-10-21"}`, `{"$appdata": "/tmp/pc-verify/data.json"}`,
   `{"$model": "YearData", "file": "/tmp/pc-verify/year.json"}`.
6. **Compare:**
   ```bash
   python3 .claude/skills/verify-numbers/scripts/compare.py /tmp/pc-verify/expected.json /tmp/pc-verify/actual.json
   ```
   Tolerance: **€0.01** for exact figures (default). Only forecasts and
   estimates may use `--pct 1` — say why.
7. **Test several cases**: a normal case, each boundary (e.g. exactly at
   `midi_low`, `midi_high`, a zone edge), zero, and one tricky case
   (year change, one-off transaction, a month with no data).
8. **Report** (the main session saves it as
   `AI output/YYYY-MM-DD-verify-<service>.md`):

```markdown
# Verify <module.function> — YYYY-MM-DD
Result: PASS | FAIL (x of y fields)
## Rules used
1. …
## Cases
| case | inputs | field | expected | service | diff | result |
## Problems found
- … (or "none")
## Unclear rules
- … (DRAFT values, rules not written down — say so instead of guessing)
```

## Good to know

- Rounding in the payroll service: tax is whole euros rounded down per year,
  then a twelfth floored to the cent; other amounts round to 2 decimals. If your
  result is 1 cent off, check rounding before calling it a bug — and report it.
- `compare.py` only checks the fields you put in `expected.json`.
