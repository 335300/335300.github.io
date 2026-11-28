# Centwise Final Project

*Every cent, spent wisely.* The final-project edition of Personal Centwise, a local finance app
for one person (Personal) and a couple's shared account (Joint): where you stand this month,
where you will be at the end of the year, and whether the savings goals are on track.

Everything runs on this Mac. No AI features inside the app, nothing is sent anywhere. It comes
with a **made-up sample year** (January–November 2026), so every screen has something to show.

## What is in this folder

| | |
| --- | --- |
| `backend/`, `frontend/` | The app: Python/FastAPI calculations and tests, Electron + React screens |
| `sample-data/` | The sample data: `data.json` (Personal) and `joint/data.json` (Joint) |
| `backend/scripts/2026-11-28-make-sample-data.py` | Makes the sample data again, through the app's own API |
| `.claude/` | The Claude Code agents, skills and hooks used to build the app — see [.claude/README.md](.claude/README.md) |
| `CLAUDE.md` | The rules every Claude session and agent follows in this project |
| `AI output/` | The screens guide the agents keep current |
| `Designs/`, `STACK.md` | UI design mock-ups and the technical stack |
| `memory.md` | Change log |

## Sample data

All figures are invented. **Personal** (Josu): a working-student job at 22 €/h (20 h a week in
lecture periods, 32 h in the breaks) with payslips and the income calendar; student health
insurance, phone, subscriptions, Deutschlandticket, food and leisure; a semester-fee sinking fund
(paid from the fund in August), an emergency fund, a laptop goal (bought in September) and a trip
goal; a plot of land paid in monthly instalments in guaraníes; an ETF savings plan from June;
recurring bills, payee rules, a Tagesgeld and an ETF depot on the Net worth tab, and a monthly
Transfer to Joint. **Joint** (Josu and Isa): rent, utilities, internet, groceries, household and
eating out; the money "From Josu" and "From Isa" split by the fair share (about 40 / 60); a shared
holiday goal; two shared costs paid privately and one settle-up.

```bash
./run-sample.sh          # open the app on a fresh copy of the sample data
./run-sample.sh --new    # make the sample data again first (same figures every time)
```

`run-sample.sh` works on a copy in a temporary folder, so `sample-data/` never changes. The
first `./build-app.sh --install` also copies the sample data into the installed app's data
folder (only if that folder is empty).

## What it does

| Tab | |
| --- | --- |
| **Overview** | Liquidity, balance, cash in, cash out, what you kept and the wealth you built in a month; where your money is (liquid, saved for goals, invested); the emergency-fund tile (months of essential costs covered, with a red / amber / green word); bills due in the next 30 days with "money ready"; categories that are unusual this month; in the Joint profile, the fair-share calculator and the settle-up balance; where the income went (fixed costs, variable costs, investment, savings) against a planning guide, with one click to distribute the savings to goals; investment plans and goals; each cost category against its usual month; budget vs real; costs and cash flow over the last twelve months |
| **Transactions** | Add one transaction or paste many from a spreadsheet (left), search, filter and edit the list (right); manage categories — each expense category is a fixed cost, a variable cost or an investment, and can be marked essential; import a Sparkasse CSV-CAMT (V8) statement file with a duplicate check and a preview; payee rules that set the category on import, with suggestions; mark a transaction one-off; recurring bills with automatic detection; Transfer to Joint (Personal profile); mark categories tax-relevant (§) and save the yearly tax export as CSV, with a commute estimate |
| **Forecast** | Rolling 12-month projection (across the year end; one line per graduation scenario), the working-student income calendar (hours, gross, net learned from payslips, when pay arrives), investment plans, savings goals (pace and status), the 12-month budget plan with each category's usual month |
| **Net worth** | What you own minus what you owe, in euros: the tracked account, other accounts kept by hand (Tagesgeld, ETF depot, cash, EUR or PYG), the land as an asset and its remaining instalments as a debt, using an exchange rate you enter; what each transfer to Paraguay really cost |
| **Settings** | Encrypted backup of both profiles (password, AES-256-GCM), verify a backup against its check sheet, restore one (a safety copy of the current data is kept), and export all transactions (CSV) or the whole data file (JSON) |

### How money is named

- **Cash in** — all income of a month. **Cash out** — everything that left the account.
- Cash out is either a **cost** (fixed or variable — money consumed) or an **investment** (money that
  builds an asset, such as the instalments of a plot of land). The kind is set per category.
- **Kept** — cash in minus cash out: what stayed in the account. **Wealth built** — kept plus invested.
- **Goals** earmark part of the balance; the money stays in the account.
- **Liquidity** — the balance minus what is saved for goals: the money you can use freely.
  Investments are not in it; they already left the account. The Overview also says how many
  typical months of costs it covers.
- **Income calendar** — hourly rate, lecture periods and hours per week. Each weekday is a lecture
  or a break day; net pay uses the ratio from the payslip with the most similar gross. Graduation
  scenarios stop the student job on their end date and switch health insurance to the employee rate.
- **Bank import** — Sparkasse online banking → Umsätze → choose the period → Export → *CSV-CAMT V8*.
  A row is a duplicate when the bank reference matches, or the amount matches, the date is within
  3 days and the payee is similar. Nothing is saved before the preview.
- **Usual figures** use the median (the middle value) of the months before and leave out
  transactions marked **one-off**.
- A **sinking fund** is a goal that repeats (e.g. €220 every semester). "Pay from fund" records the
  bill and takes the money out of the fund, so the liquidity does not drop.
- **Transfer to Joint** is the only action that writes to both profiles: an expense in Personal and
  the matching income in Joint, linked. Shared costs paid from a personal account are kept in a
  separate Joint list for settling up; they do not change the Joint balance.
- **Backups** are encrypted with your password; it is not stored anywhere, so a forgotten password
  means the backup cannot be opened. "Verify" decrypts a backup in memory and re-calculates every
  total. The CSV and JSON exports are *not* encrypted.
- An **investment plan** follows an asset paid in instalments: every payment recorded in its
  category says how many instalments it covered.

A small **calculator** button sits in the bottom-right corner of every tab. It keeps what you
typed while you change tab, and works with exact decimals (`0.1 + 0.2` is `0.3`).

Two profiles, switched in the header: **Personal** (one person's own money) and **Joint** (a
couple's shared finances). Each has its own transactions, categories, budgets and goals; nothing
is shared or combined between them.

## Getting started (macOS, Apple Silicon)

Needs Python 3.11–3.13 and Node.js 20+.

```bash
./setup.sh                    # Python environment (backend/requirements.txt) + npm packages, runs the tests
./run-sample.sh               # run from source on the sample data
./build-app.sh --install      # → /Applications/Centwise Final Project.app (starts with the sample data)
```

## Development

```bash
cd backend && .venv/bin/python -m pytest -q        # backend tests
cd backend && .venv/bin/python -m app --port 8137  # backend alone; API docs at /docs
./build-app.sh --fast --install                    # frontend-only rebuild
# UI check against a throwaway data folder (never the real one):
cd frontend && npm run build && node scripts/e2e.mjs /tmp/shots /tmp/pc-test-data
```

## Where data lives

- Installed app — Personal: `~/Library/Application Support/Centwise Final Project/data.json`
- Installed app — Joint: `~/Library/Application Support/Centwise Final Project/joint/data.json`
- Each keeps its last 20 versions in a `backups/` folder next to it. Quit the app before
  editing a file by hand.
- This is a separate folder from Personal Centwise (`.../Personal Centwise/`) and the course
  app (`.../Centwise/`). They never share data, and this copy has its own iCloud calendars.

Centwise Final Project is a planning tool, not financial advice. Forecasts are estimates.
