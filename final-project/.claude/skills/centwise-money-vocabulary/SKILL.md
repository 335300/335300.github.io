---
name: centwise-money-vocabulary
description: The exact money words used in Personal Centwise code and screens - cash in, cash out, costs (fixed/variable), investments, kept, wealth built, liquidity, earmarking for goals, sinking funds, usual (median) figures, one-off, essential, fair share, Transfer to Joint. Use whenever you name, explain, display, test or check any money figure in this app, so every agent uses the same meaning.
---

# Centwise money vocabulary

Use these words exactly. Do not invent synonyms in code, UI text or reports.

## Core flows (per month)

| Word | Meaning | Note |
|---|---|---|
| **Cash in** | All income of the month | Salary, gifts, "From <name>" in Joint |
| **Cash out** | Everything that left the account | = costs + investments |
| **Costs** | Money consumed | Category kind `fixed` or `variable` |
| **Fixed cost** | Same-ish every month | Rent, insurance, phone |
| **Variable cost** | Changes month to month | Groceries, eating out |
| **Investment** | Money that builds an asset | Category kind `investment` (e.g. land instalments). It is cash out, but **not** a cost |
| **Kept / savings** | Cash in − cash out | What stayed in the account |
| **Wealth built** | Kept + invested | Kept money plus the asset part |

## Balance words

| Word | Meaning |
|---|---|
| **Balance** | Money in the tracked account (opening balance + all movements) |
| **Earmarked / saved for goals** | Goal contributions. The money **stays in the account**; it is only labelled. Never cash out |
| **Liquidity (free to use)** | Balance − money saved for goals. Investments are never part of it (they already left) |

## Goals

- **Savings goal (one-time):** target amount + deadline. Status: `met`,
  `on_track`, `behind` (with `shortfall` per month), `overdue`, `completed`,
  `abandoned`.
- **Sinking fund:** a goal that repeats (e.g. a fee every 6 months).
  "Pay from fund" records the bill as a real expense AND takes the same amount
  out of the fund, so liquidity does not drop.
- **Emergency fund:** the goal marked "This is my emergency fund". The tile
  shows how many months of **essential** costs it covers: red < 1,
  amber 1–3, green ≥ 3.
- **Spent in forecast:** a goal that is bought on its deadline (the money
  leaves the account that month).

## Comparison words

- **Usual** = the **median** (middle value) of the months **before** the one
  shown. Months after it never count. Transactions marked **one-off** are left
  out.
- **Unusual this month** = at least 1.5 × usual and at least €30 above it.
- **Budget status:** amber ("heads-up") at 80 % used, red when exceeded.
- **Essential** (🛡) = a category that counts for the emergency fund.
- **Tax-relevant** (§) = a category that goes into the yearly tax export.

## Income words

- **Income calendar:** hourly rate × hours; lecture days vs break days;
  pay may arrive 0 or 1 month after the work; net pay is learned from
  payslips (or the German payroll rules).
- **Graduation scenario:** a line in the forecast where the student job stops
  on a given end date.
- **Rolling forecast:** always the next 12 months, across the year end.

## Joint words

- **Personal / Joint profiles:** two separate databases, never combined.
- **Transfer to Joint:** the only action that writes to both: an expense
  "Transfer to Joint" in Personal and a linked income "From <name>" in Joint.
- **Fair share:** each person's part of Joint costs, by income (50/50 until
  both incomes are entered).
- **Settle up:** shared costs paid from a personal account, balanced once.
- Joint screens use plain English for Isa (Josue's partner).

## Net worth words

- **Net worth** = what you own − what you owe, in euros.
- The land = an **asset** (market value if entered, else contract price);
  remaining instalments = a **debt**. PYG amounts use the exchange rate
  Josue entered.
- **Exchange cost** = what a transfer abroad really cost compared to the
  rate entered for that day.

## Rules that follow from the words

- Goal contributions are never counted as cash out.
- Investments are cash out but never costs, and never part of liquidity.
- A "usual" figure never looks at the month itself or later months.
