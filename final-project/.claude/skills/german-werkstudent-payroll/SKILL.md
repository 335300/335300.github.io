---
name: german-werkstudent-payroll
description: German working-student (Werkstudent) payroll rules and yearly values for 2025-2027 - Werkstudentenprivileg (20-hour and 26-week rules), pension insurance and the midijob range (Uebergangsbereich), wage tax tariff (para. 32a EStG) and allowances, Vorsorgepauschale since 2026, solidarity surcharge, student health insurance (KVdS) - each with status (final/draft) and sources, mapped to PAYROLL_RULES in config.py. Use when building, testing, verifying or explaining net pay, payslip checks, refund estimates, the income calendar, or the January rules update.
---

# German Werkstudent payroll (verified on 2026-11-17)

Source of the values: the deep research report of 17 Nov 2026 (official
sources first; see `reference/sources.md`). Machine-readable copy:
`reference/values.json`.

## Golden rules

- **Never compute money in your head.** The answer comes from
  `backend/app/services/german_payroll.py` (via a test or
  `.claude/skills/verify-numbers/scripts/run_service.py`). This skill gives
  rules and values, not answers.
- Every value has a **status**: FINAL, PROVISIONAL, CABINET (approved by the
  cabinet, parliament vote pending), DRAFT, OPEN, DEPENDS. Only mark a value
  FINAL when it is quoted from a law gazette (BGBl), an official BMF
  Programmablaufplan (PAP), a ministry notice, or a health fund /
  Minijob-Zentrale notice.
- When unsure: "ask the Lohnsteuerhilfeverein / AOK". This is planning help,
  not tax advice.

## Who this covers

An enrolled student who works next to studying. **Werkstudentenprivileg:** in
the job they pay **only pension insurance** (no health, care or unemployment
insurance through the employer) while studying stays the main activity:
- at most **20 hours/week in lecture periods** (all jobs together);
- more hours are fine in semester breaks, evenings, weekends — but at most
  **26 weeks in 12 months above 20 h** (`WERKSTUDENT_MAX_LONG_WEEKS`, checked
  by `income_calendar.long_weeks`).
- Health and care insurance are paid by the student (KVdS) — a personal cost,
  not a payroll deduction.

## How the app computes one month (`german_payroll.month_net`)

1. **Pension (employee share = half of the total rate):**
   - gross ≤ `midi_low` (mini-job): 3.6 % of gross;
   - `midi_low` < gross ≤ `midi_high` (Übergangsbereich): reduced base
     `midi_high / (midi_high − midi_low) × (gross − midi_low)` × 9.3 %;
   - gross > `midi_high`: 9.3 % of gross, at most `pension_cap`.
   Factor F is **not needed** for the employee share (it changes the
   employer side). Break months above €2,000 pay the full 9.3 %.
2. **Wage tax (Lohnsteuer), tax class I (IV after marriage = same withholding):**
   yearly wage = gross × 12 − employee allowance (`EMPLOYEE_ALLOWANCE`, max the
   wage) − special-expenses allowance (36) − yearly pension (rounded up)
   → § 32a tariff (whole euros, rounded down) → ÷ 12, floored to the cent.
3. **Vorsorgepauschale since 2026:** no minimum amount anymore (BMF letter
   14 Aug 2025). Only insurance that goes through payroll counts — for a
   Werkstudent only pension. **The app already does this** (it subtracts only
   the pension). Real KVdS payments are claimed in the tax return.
4. **Solidarity surcharge:** 5.5 % of the yearly tax, only above `soli_free`
   (with the 11.9 % phase-in). A Werkstudent does not reach it.
5. **Church tax:** optional rate (8 % / 9 % of the tax).
6. **Refund (`yearly_refund`):** each month is taxed as if paid all year, so
   uneven months (full-time breaks) over-withhold; the tariff on the real year
   total is lower → refund. The estimate is a floor (other deductions raise it).

## Values

| key (PAYROLL_RULES / config) | 2026 | 2027 | status 2027 | source |
|---|---|---|---|---|
| minimum wage / hour (context) | 13.90 | 14.60 | FINAL (MiLoV5) | Minijob-Zentrale |
| `midi_low` (= Minijob limit) | 603 | 633 | FINAL | AOK; § 8 (1a), § 20 (2) SGB IV |
| `midi_high` | 2000 | 2000 | FINAL | § 20 (2) SGB IV |
| factor F (employer side, not in app) | 0.6619 | 0.7683 | PROVISIONAL | AOK "voraussichtlich" |
| `pension` (total rate %) | 18.6 | 18.6 | EXPECTED | DRV, Haufe |
| `pension_cap` (BBG pension, month) | 8450 | 8850 | CABINET 2026-10-07, Bundesrat pending | BMAS, DRV |
| `gfb` (Grundfreibetrag) | 12348 | 12564 | DRAFT (EStReformG 2027) | Haufe 2026-09-21 |
| `z3` (end of zone 3; 42 % starts at z3+1) | 69878 | 70599 | DRAFT | Haufe (42 % from 70,600) |
| `z2`, `a2`, `b2`, `a3`, `b3`, `c3`, `z4`, `c4`, `c5` | see values.json | from final PAP 2027 | OPEN | BMF PAP |
| `soli_free` (single, yearly tax) | 20350 | from final PAP 2027 | OPEN | lohndirekt |
| `EMPLOYEE_ALLOWANCE` | 1230 | 1430 | DRAFT | Haufe, IHK Heilbronn |
| `SPECIAL_EXPENSES_ALLOWANCE` | 36 | 36 | FINAL (no change announced) | § 10c EStG |
| `COMMUTE_RATE_PER_KM` (tax export) | 0.38 | 0.38 | FINAL, no end date | BMF LStH 2026 Anhang 14 |
| KVdS health base / month (context) | 87.38 + fund top-up | 87.38; ~93.51 from summer semester 2027 if the BAföG reform passes | DEPENDS | Haufe, DSW, lohn-info |
| KVdS care, childless 23+ (context) | 35.91 | 35.91 until base changes | DEPENDS | health fund tables |
| family insurance income limit (context) | 565 | 590 | PLANNED | Studis Online |

2025 values are in `values.json` (all FINAL, used by tests).

## Vacation pay and typed hours (income calendar, added 2026-11-18)

- **Vacation pay (Urlaubsentgelt), Josu's rule:** pay for a vacation day =
  (gross of the 3 calendar months before ÷ Monday–Friday days in them) ×
  vacation days. A month with a payslip uses the payslip's gross, otherwise
  the calendar's gross (including that month's own vacation pay, so it
  chains). Vacation pay is contract pay: it is paid with the contract lag and
  taxed with the month (`income_calendar.work_month`).
- **Legal note:** §11 BUrlG averages the last 13 weeks and leaves out pay for
  overtime. The app keeps extra (break) hours in the average, because Josu's
  break hours are agreed hours, not overtime (his choice). Revisit if his
  contract treats them as overtime.
- **Typed hours** (`hours_typed`): contract hours stay as the calendar works
  them out; typed hours above them are extra hours, fewer are all contract.

## Known gaps in the app (for the rules-updater)

1. `EMPLOYEE_ALLOWANCE` is one number, not per year → 2027 needs a per-year
   value (1,430 draft) — move it into `PAYROLL_RULES[year]` with a test.
2. No status / `verified_on` / `source` next to the values → add them so the
   UI can show a small "draft value" label.
3. 2027 is not in `PAYROLL_RULES` yet; the app falls back to 2026 (correct
   until the final PAP 2027 exists).
4. KVdS cost is not modelled (it is a personal cost category); the graduation
   switch to employee payroll needs a new `german_employee_payroll` service.
5. A warning when a month leaves the midijob range would help explain payslips.

## Refresh schedule

- **January:** final PAP 2027 (all tariff coefficients, `soli_free`), law
  status of EStReformG 2027, factor F → update table, values.json and
  `verified_on`; run `scripts/check_rules.py`.
- **Late November:** Bundesrat vote on the 2027 social-insurance values (BBG).
- **April and October:** KVdS values for the new semester.
- After any Bundestag/Bundesrat vote on the tax reform or the care reform.

## Files

- `reference/values.json` — every value with status and source (2025–2027)
- `reference/sources.md` — links for each value
- `scripts/check_rules.py` — compares `config.PAYROLL_RULES` with values.json:
  `python3 .claude/skills/german-werkstudent-payroll/scripts/check_rules.py`

## Test prompts (to check this skill works)

1. "Is €2,100 in a break month inside the midijob range?" → No, > €2,000: full 9.3 %.
2. "Add the 2027 payroll values now." → Only FINAL ones may be marked final; the
   tariff coefficients are OPEN until the final PAP; propose a plan, ask Josue.
3. "Why did the user get more tax withheld in September?" → full-time month taxed
   as if all year; refund later; numbers only from the service.
4. "Does the app include health insurance in the Vorsorgepauschale?" → No, only
   pension, which matches the 2026 rule for a Werkstudent.
5. "Can the user work 25 h in a lecture week?" → No (20-hour rule); explain the risk.
