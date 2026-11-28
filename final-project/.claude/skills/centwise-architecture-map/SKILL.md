---
name: centwise-architecture-map
description: Map of the Personal Centwise code - which layer a change belongs in (Python service, FastAPI route, Pydantic model and schema_version, React page/card, chart, colour token), how data flows from the JSON file to the screen, how storage, profiles, auth and tests work, and the file of each feature. Use before planning or reviewing ANY code change, or when you need to find where a feature lives.
---

# Personal Centwise — architecture map

## The flow of a number

```
data.json  ->  storage.py (Repository)  ->  api/<area>.py (route)  ->  services/<x>.py (pure maths)
                                                   |
React page  <-  api/queries.ts (TanStack Query)  <-  window.api bridge (preload.js -> main.js -> 127.0.0.1)
```

- The page **never** computes a business number and **never** calls `fetch`.
  It only displays what the backend returns.
- Electron (`frontend/main.js`) starts the Python backend on a random
  127.0.0.1 port with a one-shot token (`CENTWISE_TOKEN`), and proxies every
  `/api/...` call (IPC). The page cannot reach the network (CSP `connect-src 'none'`).

## Where a change belongs

| You are changing… | Put it in | Also |
|---|---|---|
| How a number is calculated | `backend/app/services/<x>.py` (pure function) | a test in `backend/tests/` |
| What an endpoint returns / accepts | `backend/app/api/<area>.py` (routing + validation only) | API test in `tests/test_api.py` or the area test |
| A setting / constant / yearly value | `backend/app/config.py` | test that uses it |
| The on-disk data shape | `backend/app/models.py` | bump `SCHEMA_VERSION` in `config.py`; new fields need defaults |
| Request/response types on the page | `frontend/src/lib/types.ts` | match the backend shape exactly |
| A data hook (read/mutation) | `frontend/src/api/queries.ts` | mutations invalidate all queries |
| A page or card | `frontend/src/pages/<tab>/` | e2e check in `scripts/e2e.mjs` |
| A shared UI part | `frontend/src/components/ui/` | reuse before creating new |
| A chart | `frontend/src/components/charts/` | Recharts; colours via `lib/theme.ts` |
| Colours, spacing | `frontend/src/index.css` tokens, `tailwind.config.js` | never raw hex in components |
| Number/date formatting only | `frontend/src/lib/format.ts` | formatting is allowed in JS; maths is not |
| UI-only state (tab, month) | `frontend/src/lib/store.ts` (Zustand) | never money data |

## Backend rules

- **Services are pure:** they take model objects (and `today` when time
  matters), return plain dicts, do no I/O, hold no state, never read the clock.
  The clock lives in `api/deps.py → get_today()` (tests override it).
- **Money arithmetic:** follow the existing service's style (the payroll
  service uses `round(x, 2)` and floor-to-cent helpers; the calculator uses
  `Decimal`). Never round in the route.
- **Storage:** one JSON file per profile, atomic writes, 20 rotating backups
  (`storage.py`). Older files load because every new field has a default;
  they are saved under the current `SCHEMA_VERSION` (now 7). A file with a
  newer schema is refused. There is no separate migration step — **a new
  field must have a default**; if old data needs converting, do it in a
  Pydantic validator and test it with an old-shape JSON.
- **Profiles:** `personal` (data folder root) and `joint` (`joint/`
  sub-folder). `store.repo()` = open profile. Only `services/joint.py`
  touches both (`api/deps.py → sync_joint_links`).
- **Auth:** every router is guarded by `require_token`; with no
  `CENTWISE_TOKEN` (tests, dev) auth is off.
- **Data folder:** `config.data_dir()` → `CENTWISE_DATA_DIR` or
  `~/Library/Application Support/Personal Centwise`. Always set the env var
  in dev and tests.

## Data shape (models.py)

`AppData` (one per profile): `settings`, `years: {"2026": YearData}`, `goals`,
`investments`, `income_plan` (`IncomePlan`: settings, lecture periods,
payslips, graduation scenarios), `payee_rules`, `recurring_bills`,
`fair_share`, `shared_expenses`, `settlements`, `accounts`, `exchange_rates`,
plus `next_*_id` counters and dismissed suggestions.
`YearData`: `opening_balance`, `start_month`, `categories` (expense/income,
each with `kind`, `essential`, `tax_relevant`), `budgets` (12 values per category),
`transactions` (`Transaction`: id, type, date, month 0–11, amount, cat, desc,
payee, bank_ref, one_off, installments, link_id, foreign_amount, foreign_currency). `amount` is always positive; `type` (income/expense) gives the direction.
**Months are 0–11 inside the code.**

## Feature → files

| Feature | Service | Route | Main UI |
|---|---|---|---|
| Overview tiles, budget vs real, trends | `dashboard.py`, `cashflow.py`, `aggregation.py` | `views.py` `/dashboard` | `pages/overview/OverviewPage.tsx` |
| Where income went, distribute savings | `cashflow.distribution`, `goals.allocation` | `distribution.py` | `DistributionCard.tsx`, `DistributeModal.tsx` |
| Emergency fund tile | `emergency.py` | in dashboard | `EmergencyFundTile.tsx` |
| Transactions, day totals | `aggregation.day_totals` | `transactions.py` | `pages/transactions/*` |
| Bank import (CSV-CAMT V8) | `bank_import.py`, `payee_rules.py` | `imports.py`, `rules.py` | `ImportModal.tsx`, `PayeeRulesCard.tsx` |
| Recurring bills, bills calendar | `recurring.py`, `dates.py` | `recurring.py` | `RecurringBillsCard.tsx`, `BillsGoalsCalendar.tsx` |
| Budget plan, % links | `budget_links.py`, `cashflow.budget_*` | `budgets.py` | `BudgetGrid.tsx`, `VariableSharePanel.tsx`, `AllocationPanel.tsx` |
| Income calendar, payslips | `income_calendar.py`, `german_payroll.py` | `income.py` | `IncomeCalendarCard.tsx`, `IncomeSettingsModal.tsx` |
| Rolling forecast, scenarios | `rolling_forecast.py`, `goal_forecast.py`, `projection.py` | `income.py` `/forecast`, `views.py` `/projection` | `RollingTable.tsx`, `RollingForecastChart.tsx` |
| Goals, sinking funds | `goals.py`, `sinking.py` | `goals.py` | `GoalsPanel.tsx`, `GoalCard.tsx` |
| Investment plans (land) | `investments.py` | `investments.py` | `InvestmentsPanel.tsx`, `InvestmentCard.tsx` |
| Net worth, EUR/PYG | `net_worth.py` | `net_worth.py` | `pages/networth/NetWorthPage.tsx` |
| Joint: transfer, fair share, settle-up | `joint.py` | `joint.py` | `JointOverview.tsx`, `JointForecast.tsx`, `TransferModal.tsx` |
| Tax export, commute | `tax_export.py`, `csv_format.py` | `tax.py` | `TaxExportModal.tsx` |
| Backup, export | `backup.py`, `export.py` | `data_safety.py` | `pages/settings/SettingsPage.tsx` |
| Calculator | `calculator.py` | `calculator.py` | `components/Calculator.tsx` |

## Tests

- `backend/tests/` — ~400 pytest tests. `conftest.py` points every test at a
  temp data folder and offers small hand-checkable fixtures (`year`, `data`,
  `tx(...)`). Expected figures are worked out by hand in the docstring
  (see `test_german_payroll.py`) — copy that style.
- `backend/tests/fixtures/` — synthetic files only (e.g. the fake Sparkasse CSV).
- `frontend/scripts/e2e.mjs` — Playwright drives the built Electron app on a
  throwaway folder (~42 checks), saves screenshots, fails on console errors.

## Build

`./build-app.sh` = icon → PyInstaller backend → Vite page → electron-builder.
`--fast` reuses the frozen backend (frontend-only changes).
Any change under `backend/` needs the full build. Ask Josue before installing.
