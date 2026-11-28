# The Claude Code setup of Centwise Final Project

This folder is the AI development team that built and checks the app: the same
agents, skills and safety hooks used in Personal Centwise, copied unchanged.
Claude Code loads them automatically when it is started in the project folder.

## How the pieces fit together

```
            you (plan → approve)
                    │
          main Claude Code session ── reads CLAUDE.md, uses the skills
                    │  hands work to …
   ┌────────────────┼──────────────────────────────┐
 builders         checkers (read-only, independent) yearly upkeep
 backend-service- calc-verifier  (blind maths check) rules-updater
   engineer       ui-reviewer    (screens)
 frontend-        rules-privacy-reviewer (rules + privacy, last step)
   engineer
                    │
   hooks run on every tool call: block real data · limit each agent's files ·
   run the tests / type check after every edit
```

## Agents (`agents/`)

| Agent | Role | Can change | Model |
| --- | --- | --- | --- |
| `backend-service-engineer` | Python calculations, FastAPI routes, data model, tests written first | `backend/`, the two TS API files, `memory.md` | same as session |
| `frontend-engineer` | Screens, cards, charts; shows numbers the API sends, never computes them | `frontend/`, the screens guide, `memory.md` | same as session |
| `calc-verifier` | "Blind" checker: recomputes a result from the written rules without reading the service code or its tests, compares to the cent | nothing in the code (cannot even read `backend/app/services`) | Opus |
| `ui-reviewer` | Runs the e2e UI check, looks at screenshots, checks design and wording | nothing (read-only) | Sonnet |
| `rules-privacy-reviewer` | Checks a finished change against `CLAUDE.md` and for real data in code/tests | nothing (read-only) | Sonnet |
| `rules-updater` | Keeps the yearly German payroll and tax values current from official sources | `backend/app/config.py`, tests, skills, `memory.md`, `AI output/` | Opus |

Usual order for a change: plan → builder → `calc-verifier` (money) and/or
`ui-reviewer` (screens) → `rules-privacy-reviewer` → `memory.md` entry.

## Skills (`skills/`)

Knowledge and step-by-step recipes the agents load (listed in each agent's `skills:`).

| Skill | What it gives |
| --- | --- |
| `centwise-project-rules` | Folders, file names, plan-then-approve, privacy, test commands |
| `centwise-architecture-map` | Which layer a change belongs in, data flow, where each feature lives |
| `centwise-money-vocabulary` | The exact meaning of cash in/out, kept, liquidity, earmarking … |
| `centwise-design-system` | Colour tokens, shared components, chart and wording rules |
| `german-werkstudent-payroll` | Working-student payroll rules 2025–2027 with sources (`reference/`) and a checker script |
| `add-backend-feature` | Recipe: service + tests first → route → model → types |
| `add-ui-card` | Recipe: build a card or screen that only formats API numbers |
| `ui-check` | Run `frontend/scripts/e2e.mjs` on a throwaway folder and review the screenshots |
| `verify-numbers` | Blind check with `run_service.py` and `compare.py` |
| `write-memory-entry` | The house format for the `memory.md` change log |

## Hooks (`hooks/`, wired in `settings.json` and in the agent files)

| Hook | When | What it does |
| --- | --- | --- |
| `block_real_data.py` | before every Read/Edit/Write/Grep/Glob/Bash | Blocks the real-data folders (statements, payslips, the real apps' data folders), starting the app without a throwaway `CENTWISE_DATA_DIR`, and changes to the hooks themselves |
| `agent_guard.py` | before an agent's tool calls | Limits where each agent may write (`--write`) and what it may not read (`--no-read`, keeps the verifier blind) |
| `after_edit.py` | after every edit | Runs the backend tests (Python change) or the type check (TypeScript change) and reports failures straight back |

## Differences from the original project

- The agents were written for Personal Centwise and still use that name, and
  the names Josu and Isa (also built into the app's Joint screens).
- The real-data folders and most of `AI output/` are not part of this copy.
  `AI output/` only holds the screens guide the frontend agents keep current.
  `AI output/2026-11-13-recommendations-report.md`, named in
  `centwise-project-rules`, is not included (it has real figures).
- This copy runs on the made-up data in `sample-data/` (see the main README).
