---
name: ui-check
description: Check the Personal Centwise screens for real - build the page, run the Playwright end-to-end script (frontend/scripts/e2e.mjs) on a throwaway data folder, read the PASS/FAIL lines and console result, look at the screenshots, and review them against the design and wording rules. Use after any frontend change, before saying a UI task is done, and when reviewing someone else's UI change.
---

# UI check

## Run it

```bash
bash .claude/skills/ui-check/scripts/run_ui_check.sh            # build + e2e
bash .claude/skills/ui-check/scripts/run_ui_check.sh --no-build # e2e on the last build
```

The script makes fresh folders `/tmp/pc-shots-<time>` (screenshots, `e2e.log`,
`console.txt`) and `/tmp/pc-test-data-<time>` (throwaway data). It prints
`Checks: X passed, Y failed`, the console result and the screenshot folder.

What e2e does: launches the built Electron app with `CENTWISE_DATA_DIR` set
to the throwaway folder, goes through every write flow (setup, transactions,
bulk paste, budgets, goals, import, backup…) with fake data, checks what the
screen shows (~42 checks), saves numbered screenshots, and fails on console
errors or warnings.

**Never** pass a real folder: `e2e.mjs` deletes its data folder at the start.

## Read the result

1. All checks PASS and console "(clean)"? If not, read the `FAIL` line
   (it names the check and the line in `e2e.mjs`) and the `fail-N.png` shot.
2. Look at the screenshots that belong to the change (Read the PNG files).
   Use this checklist:

| Look for | Rule |
|---|---|
| Text or numbers cut off, overlapping, wrapping badly at 1360 px | fix layout |
| Money columns line up | `num` class, `fmtMoney` |
| Every status has an icon **and** a word | never colour alone |
| Colours match meaning (teal savings, violet investments, red bad, amber heads-up, gold only for celebration) | design system |
| Personal screens: no grey explanation paragraphs | writing rules |
| Joint screens: plain English for Isa, no jargon | writing rules |
| Empty cards show a helpful empty message | `EmptyState` |
| Fold arrows fold and reopen; side-by-side cards are half width each | layout |
| Numbers on screen look plausible for the fake data the test entered | numbers come from API |

3. If the change added a feature, there must be a **new e2e check** for it.
4. If a screen changed, `AI output/2026-11-16-app-screens-guide.md` must match.

## Report

```markdown
# UI check — YYYY-MM-DD — <change>
e2e: X/Y passed, console: clean | <errors>
Screenshots looked at: 12-overview.png, …
| screen | finding | rule | severity (must fix / nice to have) |
Verdict: PASS | FAIL
```

## Notes

- `npm run build` runs `tsc --noEmit` first; type errors stop the build.
- The run takes a few minutes; run once at the end, not after every small edit
  (the type-check hook covers small edits).
- Screenshots contain only fake test data, so they are safe to look at.
