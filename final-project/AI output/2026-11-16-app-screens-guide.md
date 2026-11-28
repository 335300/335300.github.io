# Personal Centwise — what each screen does

A reference for when a screen is not obvious. The app itself keeps only titles, numbers and
warnings; the explanations that used to sit in grey under the titles are collected here.

Written 2026-11-16, updated 2026-11-19 for the new look. Screens are described in the order they appear.

---

## The money words

| Word | Means |
| --- | --- |
| **Cash in** | Income: everything that came into the account. |
| **Cash out** | Everything that left: **costs** (fixed + variable) and **investments**. |
| **Fixed cost** | Hard to change in the short term: rent, insurance, contracts. |
| **Variable cost** | Follows your choices: food, going out, shopping. |
| **Investment** | Money that builds an asset (the land). It is cash out, but not an expense. |
| **Kept / savings** | Cash in − cash out. |
| **Wealth built** | Kept + invested. |
| **Balance** | What is in the account. |
| **Earmarked** | Part of the balance saved for a goal. The money stays in the account. |
| **Liquidity** | Balance − money saved for goals: what you can use freely. Investments are never part of it. |
| **Usual month** | The middle value (median) of the months *before* the one shown, with one-off transactions left out. A month still in progress is never compared with itself. |
| **One-off** | A transaction you tick as unusual (a wedding, a big repair, a double salary). It is left out of every "usual" figure. |

---

## The header

- **Tabs** — Personal: Overview, Transactions, Calendar, Forecast, Net worth, Settings. Joint: Overview,
  Transactions, Calendar, Forecast only. Opening Joint while on Net worth or Settings lands on its Overview.
- **Month** (Overview only) and **Year** — the period shown. The month also sets the month on the
  Transactions tab. "+ Start 2027" creates the next year, copying categories and budgets from the latest one.
- **Profile** — Personal or Joint. Two separate data files; switching never mixes them. The tab you
  are on stays open.
- **Calculator** (round button, bottom right) — a pocket calculator that stays as it is when you change
  tab. The sums are done by the backend, not by the screen.
- **Keyboard shortcuts** — ⌘1–⌘6 open the tabs in header order (Personal shows the hint next to each
  tab name; Joint has four tabs and no hints). ⌘K opens or closes the calculator. ⌘N "Add transaction":
  the screen on show opens its add window; if it has none, the Transactions tab opens it. On
  Transactions, ⌘F jumps to the search box and ⌘↵ saves the Quick entry rows. Esc closes a window or a
  "Delete?" question. Settings lists them all.
- **Look** — the bar stays at the top while the page scrolls. Joint has bigger tabs and menus, and all
  text there is at least 14px. **Light / Dark / Match Mac** is chosen in Settings → Appearance (the
  same for both profiles; charts change colour with it).
- **How numbers are written** — German style everywhere: `1.234,56 €` (the € after the number),
  a real minus sign for money going out (`−500,00 €`), `71%`, dates as `19.11.2026` (or `19.11.` when
  the year is clear), guaraníes as `1.600.000 Gs`. Big headline tiles show whole euros (`1.234 €`).
  When typing, both `12,50` and `12.50` work.

---

## Personal → Overview

*(New layout 2026-11-19.)* Where you stand in the month picked in the header. Top part first, then
"More detail" further down.

### Worth a look (banner at the top)
Only for the month that is running now. It names the one variable budget that needs a look —
**Over budget**, **On pace to go over** (at this speed it will be over by month end) or **Close to
limit** (80 % used) — with the amounts in one sentence. When another variable budget has room, the
button **Move … from …** shifts that much budget over in one click (you can undo it for a few seconds);
**Adjust budget** opens the plan. When nothing needs a look it says **All on track**.

### Tiles
- **Kept this month**, **Liquidity**, **Wealth built** — the three big tiles, in whole euros. Under
  Kept and Wealth built: how much more or less that is than your **usual month** (one-offs left out)
  and the share of cash in. Under Liquidity: how many months of costs it covers, or a warning when
  goals hold more than the account has. ⓘ explains each.
- **Balance**, **Cash in**, **Cash out** — the smaller tiles, exact to the cent, each compared with
  the usual month; under them what the month started with, what was planned (left out when nothing
  is planned), or the costs / invested split.

### Budget vs real
One bar per **variable** budget: the bar is what was spent against the budget, the small │ mark is
your usual month. Colours always come with words: **On track · … left**, **Close to limit** (amber,
from 80 %), **Over by …** (red), **No budget set**. The line at the bottom sums the variable budgets
and the days left. **Table** shows every budget (fixed, variable, investments) as numbers. If
something is over budget: check whether it was a one-off, or raise that budget in the Forecast tab.

### Forecast · next 6 months
The balance for the coming six months: solid = recorded, dashed = most likely, shaded = the 50 % and
80 % ranges (when there is enough history). The sentence says "In 8 of 10 likely futures you stay
above …" and the most likely balance, so the chart itself does not repeat that number at its right
edge. **Open forecast** goes to the Forecast tab.

### Right column
**Savings goals** (progress of each goal), **Upcoming bills** (next 14 days and whether the money is
there), **Invested this month**.

### Recent transactions
The month's latest movements; **All transactions** opens the Transactions tab.

### More detail
The cards below the "More detail" line are the ones the Overview always had.

### Where the money went
The month's living costs only (investments are not an expense). The ring splits fixed and variable
costs. Each category is compared with its **usual month** (the middle value of the months before,
one-offs left out): the arrow shows up or down, "new" means it had no usual amount yet.
**Unusual this month** lists categories at least 1.5 × their usual month and €30 more. If one was a
one-off, tick "One-off" on that transaction (Transactions tab) and it stops counting there.

### Fixed and variable costs over time
Bars: what each of the last twelve months cost. Dashed line: the 3-month average of variable costs —
the direction, without single months jumping around. The two boxes compare this month with the
usual month and give the 3- and 6-month averages, the typical month (median) and "last 3 months vs
the 3 before". All of these use the months *before* the one shown.

### Cash in vs cash out
The last twelve months. Green: cash in. Cash out is stacked: living costs below, investments on top.

### Where your money is
Everything you own, by how freely you can use it: **liquidity** (in the account, free to use),
**goals** (in the account, earmarked) and **investments** (already an asset, valued at what it cost
you — hence the ≈). "All together" is balance plus investments. A warning appears when goals hold
more than the account has (part of that saving has already been spent).

### Emergency fund
How many months of **essential** costs your emergency savings cover. Under 1 is too thin, 3 or more is
healthy. It needs: a goal marked "This is my emergency fund" (Forecast → goal), and essential
categories marked with the shield (Transactions → Categories). The categories counted are listed.

### Upcoming bills & savings goals *(fold with the arrow)*
*(Changed 2026-11-17: replaces "Upcoming 30 days" and the Overview's "Savings goals" card.)*
- **Calendar** (left) — starts at the month picked in the header; ‹ › move to other months, also
  years ahead. Each day shows the recurring bills due and a **flag** on each goal's deadline. Click a
  day to see its bills in words. Bill states: **Money ready** (a bill linked to a sinking fund when the
  fund holds enough; the others when your liquidity covers them and the bills before them), **Short**
  (by how much), **Overdue**, **Paid** (a matching payment was found), **Planned** (more than 30 days
  ahead — too far to judge on today's money). Above the calendar: what is still due in the month and
  what was already paid.
- **Savings goals** (right) — each goal's progress, deadline and the monthly pace it needs. The line
  under the list compares what all open goals need a month with what the forecast expects you to keep.

### Where your income went *(fold with the arrow)*
Every euro that came in this month, by the job it got: fixed costs, variable costs, investment,
goals, and what has no job yet. The chips compare each share with a common rule of thumb (In range /
Above / Below) — something to compare against, not a rule. When part of the month's savings has no
job, "Distribute to goals" proposes how to share it among your goals.

Sits on the left half of the row, next to **Investments**.

### Investments *(fold with the arrow)*
Right half of the row. Each plan (the land): instalments paid and left, built so far, last instalment.

---

## Personal → Transactions

*(New layout 2026-11-19.)*

- **Top line** — the month (or "All of 2026") and how many transactions are shown. Buttons:
  **Categories**, **Transfer to Joint**, **Tax export**, **Import CSV** and **Add transaction** (⌘N).
- **Add transaction** — opens a window: type, date, amount, category, description. A new category
  name is created as a variable category. For the land: "cuotas covered" counts toward the plan (0 for
  a payment that is not an instalment), and "Gs received" lets the Net worth tab show what the
  transfer really cost. **One-off** leaves it out of every "usual" figure. Editing a record that is
  part of a Transfer to Joint also changes its other half in Joint. The window stays open to add
  several; Esc closes it.
- **Filter bar** — search (⌘F), All types / Cash out / Cash in, month (or All months), category, and
  **Table | Calendar** (the app remembers your choice).
- **Quick entry** *(fold with the arrow)* — a small grid: date, description, category, cash in or out,
  amount. Tab moves on, Enter adds a row, **Save N rows** (or ⌘↵) saves them all together — or none if
  one row is wrong (the wrong box says why). **Paste from a spreadsheet** fills the rows from copied
  lines (`date; type; amount; category; description`).
- **Table** — grouped by day, each day with its cash in and cash out. Pencil = edit, × = delete (it
  asks "Delete?" in the row; a short note at the bottom confirms it). Tick rows to change their
  category or delete them together. Keyboard: ↑↓ move, Space selects, Enter edits, ⌫ deletes (asks
  first). The bottom line shows the totals of what is listed.
- **Calendar** — one month; ‹ › change the month. Each day shows its first three movements and, when
  there are several, the day's totals (green = in). Click a day to see all its movements below and
  edit or delete them; the **+** on a day (mouse over it) or **Add on this day** adds one with that date.
- "linked · Personal ↔ Joint" marks a Transfer to Joint: deleting it deletes the other half too.
- **Categories** (button, opens a window) — every expense category is a fixed cost, a variable cost or
  an investment; this drives the split on the Overview. The **shield** marks an essential cost
  (emergency fund); **§** marks a tax-relevant one (tax export). A category in use cannot be deleted —
  rename it instead (the history moves with it).
- **Transfer to Joint** — saves an expense "Transfer to Joint" here and the matching income
  "From Josu" in Joint, linked.
- **Tax export** — the year's tax-relevant transactions plus a commuting estimate, as a file.
- **Import CSV** — reads a Sparkasse CSV, shows a preview (duplicates skipped, categories from the
  payee rules), then saves.
- **Recurring bills** (right column) — bills that come back. A paid one moves to its next due date by
  itself (a matching payment within 7 days and 10 % of the amount). **+ Add bill** opens the form.
  Suggestions ("… looks like a monthly bill") appear above after 3 similar payments.
- **Payee rules** (right column) — when a CSV is imported, a row whose payee or purpose contains the
  text gets that category. **+ Add rule** opens the form; the app suggests rules from repeated payees.

---

## Calendar (Personal and Joint)

*Added 2026-11-18.* Your Apple Calendar and the money dates in one place.

- **Allow calendar access** — the first time, one button asks macOS for access to Apple Calendar
  (macOS shows its own question; you can switch it off later in System Settings → Privacy & Security
  → Calendars). Until then the money dates still show. The app only reads your own calendars and never
  changes them (it writes only into its own two "Centwise" calendars, if you switch on Money dates on
  your iPhone in Settings), and the events are not saved in the app's data.
- **Month calendar** — opens on this month; ‹ › move between months. Each day
  shows its money dates and its events: a coloured dot = the event's calendar (its colour from Apple
  Calendar), then the time and the title. A light blue line on top of a day = lecture period (from the
  income calendar). Up to four entries per day, then "+N more". Click a day to see everything on it.
  Clicking the chosen day again keeps its panel open (× closes it). **Events / Money** switch either
  off. Above the calendar three tiles: **Still to pay** in the month (bills and Transfer to Joint not
  done, overdue included), **Money expected**, and **Free to use** (with a warning when it does not
  cover every bill of the next 30 days).
- **Status words** — every money date has an icon and a word: **Still to pay**, **Paid**, **Overdue**,
  **Money expected**, **Arrived**, **To send** (Transfer to Joint).
- **Money dates** — only these, never everyday card payments:
  - **salary** on the day it usually arrives (pay day in the income calendar settings: the working day
    before the last working day — the default, how you are paid —, the last working day, or a day of
    the month, moved to the Friday before on a weekend) — "Expected", or "Received" once it is booked.
    A pay at the end of a month is the **next month's** salary (Fri 27 Nov shows December's figure),
    the way you book it (dated the 1st);
  - **Transfer to Joint** on the working day after the pay arrives — "To send", "Sent", or "Not sent
    yet" when the day has passed;
  - your **recurring bills** (monthly, and those every 3, 6 or 12 months) — "Due", "Paid on …",
    "Overdue";
  - **savings-goal deadlines** — "Goal deadline", "Goal reached", "Goal date passed".
  In Joint: the shared bills, shared goals, and **"From Josu" / "From Isa"** on the same day as the
  transfer.
- **Next 14 days** — the same, as a list from today, with what is still to pay and the money expected
  in those 14 days.
- **Joint** — opens with one sentence for Isa ("Our shared account · November" / "2 bills left this
  month — 250 € in total.") and whether there is enough money for them, then the month, **Still to
  pay** and **Money expected** (the transfers from Josu and Isa).
- One payment pays only one bill: when two bills look alike (same category, similar amount, close
  dates), the closest match gets the payment and the other stays unpaid.

---

## Personal → Forecast

*(New layout 2026-11-19.)* The next 12 months, from the month after the last recorded one. Recorded
months use your real transactions; later months use your budget plan and (when set up) the income
calendar. An estimate for planning, not financial advice.

- **Top line** — "Next 12 months · first to last month · from N months of history" and the starting
  point ("tracking starts January 2026 with …"). **Change** opens a small dialog for the opening
  balance and the first tracked month. **Income settings** opens the income calendar settings;
  **Add goal** opens the new-goal form.
- **Tiles** — balance at the end of the 12 months (one per graduation scenario), the lowest point,
  "free to use · lowest" (balance minus goal savings) and "expected per month" (what a month keeps on
  average, before goal purchases — the figure goals are checked against). Each tile has an ⓘ.
- **Projected balance** — solid line: recorded. Dashed line(s): planned, one per scenario, after
  living costs, investments and the goals you buy on their date (flags). Dotted line: free to use.
  **Shaded bands** (when there are at least 6 finished months of history): the 50 % range (darker)
  and the 80 % range (lighter) — how far the real balance may drift, from how much your months
  usually wobble. The sentence above the chart says "In 8 of 10 likely futures you stay above … through
  …" and the most likely end balance. "Include goal purchases" switches goal purchases off to compare.
  The **status line** under the chart says what matters: *Below zero* (a month drops under zero),
  *Heads-up* (a goal is not covered on its date, goals need more than the account holds, or your open
  goals together need more than you keep), or *On track* with the tightest month.
- **Month by month** — always on screen: the 12 months as a table in whole euros (hover a number for
  the cents): cash in, costs, investments, kept, the balance (one column per scenario) and "8 in 10
  between" (the 80 % range). A goal bought that month shows as a chip with a flag under the month name.
  The last row shows what the 12 planned months keep in total and the end balance.
- **Savings goals** (right of the table) — a target and a deadline. Each goal: saved of target, bar,
  status (On track / Behind / Overdue / Goal reached …), date and months left, the % saved, then the
  pace check, the forecast check, and actions (contributions, Add money, Pay from fund for sinking
  funds, the ··· menu: edit, complete, stop, delete). One-time goals are spent on their date (unless
  unticked); the emergency fund and sinking funds are kept. A **sinking fund** is a bill that comes back
  (e.g. a semester fee): "Pay from fund" records the bill and starts the next round. The eye button
  shows "Savings · not assigned yet": this year's savings (income minus expenses of the recorded
  months) minus money added to active goals this year; completed or stopped goals give their money back.
- **Investments** (under the goals) — assets you pay for in instalments (the land). Their payments are
  cash out, not an expense — you are building something. The plan's category budget fills itself with
  one instalment a month until the last one.
- **Income calendar** — your pay follows the semester: fewer hours in lecture periods, more in the
  breaks. Net pay follows German payroll rules for a working student, tax class 1 (a full-time month
  loses a bigger share to income tax), or is learned from your payslips. **Italic rows are expected**;
  upright rows are months with a real payslip. Settings: hourly rate, hours, lecture periods, when pay
  is booked, the day the pay arrives (the working day before the last one — how you are paid —, the
  last working day, or a day of the month; used by the Calendar tab), graduation scenarios. The salary
  budget of months not recorded yet follows the calendar.
  - **Hours** — each month's hours box can be typed in: gross, net, tax and when it arrives are then
    worked out from your hours (the contract hours stay; anything above them is extra hours). A typed
    month gets ↺, which goes back to the hours from your lecture periods.
  - **Vacation** — "Add vacation" (first day, last day, note). Every Monday–Friday inside is a vacation
    day: not worked, paid at the average of the 3 months before (their gross — a payslip's gross where
    you entered one — ÷ their working days, × vacation days). It is paid and taxed with that month's
    normal pay; the month shows "N vacation days · €…".
  - **Tax return** — each full-time month is taxed as if you earned that all year, so more is withheld
    than you owe. Your own health insurance, travel and study costs count too and make the refund
    bigger. An estimate, not tax advice; not added to the forecast.
  - **Payslips** — type gross and net pay for one month of work. With the tax rules, the app checks
    them against the rules: a small difference is normal (meal allowance, one-off payments); a big one
    means your payslip has something the rules do not know. With "net pay from payslips", a lecture
    month and a full-time month teach the app the most.
- **Plan by month** — what you plan to earn, spend and invest each month. Edits update the forecast and
  goals straight away. The forecast above also uses your real spending history, so it is a little more
  careful than the plan.
  - *The table* — type a number and press Tab (or click away) to save. **Euros / Share of income**
    (top right) switches what the cells show. In the euro view you can also type e.g. `30%` into a
    cell. **Teal** amounts follow a % of the month's income; typing euros into one removes the link.
    **Grey italic** cells are filled in for you (salary from the income calendar, the land instalment,
    the "Transfer to Joint" row) — an icon next to the name says which. You can type over them too: the
    typed amount stays (the automatic fill leaves it alone) and is used everywhere — forecast, Kept,
    Calendar tab, iPhone. A typed box shows **↺** on a light grey background; click ↺ to go back to the
    automatic figure. Greyed month names are recorded: the forecast uses what you actually spent there,
    so changing them only affects budget vs real.
  - *Planned kept* — budgeted income minus all budgeted cash out; *Actually kept* — what really
    happened in recorded months.
  - *Share of planned income* — each job's part of that month's planned income.
  - *Planned split of income* (under the table) — each job's share of the income you plan to earn
    (fixed, variable, investment, savings), for the year or one month (click a month bar). Savings are
    what the plan leaves over.
  - *Variable costs by % of income* (under the table) — drag a slider to give a variable cost a share of
    each month's income. It applies to every coming month and the euros follow that month's income.
    Fixed costs and the investment keep their euro amounts.

---

## Personal → Net worth

*(New layout 2026-11-19.)* Everything you own minus what you still owe, in euros. Guaraníes are
converted with the exchange rate you enter (shown in the top line).

- **Tiles** — **Net worth** (with how much more or less than at the end of last month), **You own**,
  **You owe** (instalments still to pay) and **Held in guaraníes** (that part moves with the rate).
- **Net worth over 12 months** — one bar per month-end. The solid part of each bar is the net worth
  (the number on top); the light cap above it is what you still owe; the whole bar is what you own.
  Diagonal stripes plus the word "estimated" mark estimated months (for example before an account value
  was entered). If net worth is below zero in any month, the chart shows plain "what you own" bars with
  net worth as a line instead. *(Changed 2026-11-19.)*
  The sentence above says how much it went up or down and how much of that came from what you saved.
- **What makes it up** — every item on the "own" and "owe" side: the account, other accounts, the land
  as an asset and the instalments still owed, in its own currency and in euros. One total row:
  **Net worth**, with the change since last month-end.
- **Exchange rate** — guaraníes per euro, typed from Monito, your bank or Western Union, with the date.
  "1 € = 8.000 Gs · saved 01.11." shows the one in use; earlier rates are listed under it.
- **Other accounts** — accounts the app does not follow transaction by transaction (Tagesgeld, ETF
  depot, cash), in **Euro (€)** or **Guaraní (Gs)**. Update their value now and then. **Delete…**
  (mouse over the account) asks first: **Keep** or **Delete**.
- **What your transfers really cost** — for payments where you entered what arrived in guaraníes: the
  rate you got against the rate of that day, and the cost in euros; the line on top says what the last
  transfer lost.

---

## Personal → Settings

*(New layout 2026-11-19.)* Keep your data safe, and take it with you. The **Data safe** bar on top
reminds you that 20 automatic backups are kept on this Mac and shows the data folder.

- **Appearance** — **Light**, **Dark** or **Match Mac** (follows the Mac's own setting). Saved, and the
  same for Personal and Joint. "Motion" shows whether the Mac's "Reduce motion" is on.
- **Make an encrypted backup** — both profiles in one file, each kept separate inside, locked with
  your password (AES-256-GCM). There is no way to open it without the password.
- **Verify or restore a backup** — "Verify" opens the backup in memory, re-calculates every total and
  compares it with the check sheet inside; it changes nothing. A good backup shows **All totals
  match**. "Restore this backup…" asks first, keeps your current files as a safety copy, then replaces
  the data with the backup.
- **Export everything** — your data in open formats (transactions as CSV, the whole data file as
  JSON), so you are never locked in. Only the profile that is open now. These two files are not
  encrypted.
- The app also keeps 20 automatic backups of each profile's file in its data folder.
- **Apple Calendar** — access (allowed or not, with the button to allow it) and the calendars the
  Calendar tab shows (tick or untick). One choice for Personal and Joint.
  - **Money dates on your iPhone** — when ticked, the app keeps two calendars of its own in iCloud,
    **“Centwise”** (Personal) and **“Centwise Joint”**, with the money dates of the next 6 months as
    all-day entries: bill and goal names, never amounts (“Rent due”, “Salary arrives”, “Transfer to Joint”,
    “Money from Isa”, “Goal deadline: …”; a tick when done). They show on the iPhone, iPad and Watch.
    The app updates them when it opens and 3 seconds after any change; **Sync now** does it at
    once (it then shows how many entries were added, changed and removed). It only changes its own entries — something you add there by hand, and past entries, stay.
    Reminders: your calendar's default alert for all-day entries (Calendar → Settings → Alerts).
    These two calendars never show as event calendars in the Calendar tab.
  - **Remove the Centwise calendars…** — asks first (**Delete them** / **Cancel**), then deletes the two calendars (also from the
    iPhone) and switches the sending off. Your own calendars are not touched.
- **Keyboard shortcuts** — the list of shortcuts that work (see The header).

---

## Joint (the shared view with Isa)

Joint is kept simple and in plain English for Isa. Its screens keep their short explanations.

**How the money works.** Every month the Joint plan's costs, plus what it saves for shared goals,
is split between Josu and Isa — half and half until both net incomes are entered, then by income.
Each person's part is their planned income in Joint: **"From Josu"** and **"From Isa"**, so the
contributions cancel the costs. Josu's part also appears by itself in Personal as the
**"Transfer to Joint"** budget (locked). When Josu uses "Transfer to Joint", the money lands in Joint
as "From Josu". Isa's money is recorded in Joint as income "From Isa".

- **Overview** — *(new layout 2026-11-19)* one big sentence ("This month we kept 200 €.") and how it
  compares with a usual month; three tiles: **In our shared account**, **Spent together this month**,
  **Bills still to pay**; a **Worth a look** note when a budget needs a look; **Looking ahead** (where
  the shared account is heading) and **Coming up** (bills soon, and whether the money is there); the
  latest payments; **Who pays what** (how we split, this month's plan, "So far we put in …", and each
  person's part and how much they have paid in); **What we spent on** (bars that fill up to the planned
  amount); the last months (put in vs spent); **Our goals**; **Between us** — **How we split** ("Each of us
  pays a part of the shared costs, in proportion to what we earn. Until both incomes are filled in, we
  split 50/50.", with labelled fields for each name and net income per month), and
  **Settle up** for something one of us paid for both from a personal account.
- **Transactions** — *(new layout 2026-11-19)* "Everything we paid together" in the month picked on the
  Overview: three tiles (money in, money out compared with usual, left in the account), a search box and
  "Show everything / only money in / only money out", then the list by day with who paid. **Add a
  payment** opens the form in a window. **More tools** holds adding several at once, importing a bank
  file, categories, tax export, recurring bills and payee rules (no Transfer button).
- **Calendar** — "Our shared account" and one sentence about the bills left this month; then our shared
  dates: shared bills, the money each of us puts in ("From Josu", "From Isa") and our goals, next to the
  same calendar events as in Personal.
- **Forecast** — *(new layout 2026-11-19)* a headline sentence ("Our plan works: about … in our shared
  account by …", or a warning if it would drop below zero), "In 8 of 10 likely futures our shared
  account stays above … until …" (when there is enough history); tiles (together each month with each
  person's part, our costs, for our goals, our pot at the end); **Money in our shared account** (today's
  balance, the most likely path dashed, the expected range shaded); **Month by month** (we put in — with
  Josu's and Isa's part —, we spend, for our goals, in our pot after; "We buy: …" when a goal is bought);
  **What we pay each month** (the plan's categories for the first coming month and the total);
  **We buy** (shared goals, with what it takes a month and each person's part); **Our plan** in euros
  (the "From …" rows fill themselves); the starting point with **Change**.

---

## Symbols

| Symbol | Means |
| --- | --- |
| 🛡 shield (Categories) | Essential cost — counts for the emergency fund. |
| § (Categories) | Tax-relevant — goes into the tax export. |
| Calendar icon (plan row) | Follows the income calendar. |
| Building icon (plan row) | Follows an investment plan. |
| People icon (plan row) | Follows the Joint plan. |
| ↺ (in a budget or hours box) | Typed by hand over an automatic figure; click to go back to automatic. |
| Palm tree (income calendar) | Vacation days in that month, with their pay. |
| Arrow next to a card title | Folds the card away; the app remembers it. |
| Flag (forecast charts) | A goal is bought that month. |
| "linked" (transaction) | One half of a Transfer to Joint. |
