"""Constants and filesystem locations.

Everything that would otherwise be hardcoded across the app lives here, so that
changing the currency, the starter categories, or where data is stored is a
one-file edit.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Centwise Final Project"

MONTHS: list[str] = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTHS_SHORT: list[str] = [m[:3] for m in MONTHS]

CURRENCY = "EUR"
CURRENCY_SYMBOL = "€"

#: 2 — adds investment plans, the "investment" category kind and
#: ``Transaction.installments``.
#: 3 — adds the income calendar (``AppData.income_plan``), payee rules,
#: ``Category.essential``, ``SavingsGoal.emergency_fund`` and the bank-import
#: fields ``Transaction.payee`` / ``bank_ref``.
#: 4 — adds one-off transactions, sinking funds (repeating goals and
#: withdrawals), recurring bills, and the Joint links (``Transaction.link_id``,
#: fair share, shared costs, settlements). Older files load unchanged (every
#: new field has a default).
#: 5 — adds tax-relevant categories and the commute line, accounts and
#: exchange rates for net worth, the land's market value, and the foreign
#: amount of a payment. Older files load unchanged and are saved as 5.
#: 8 — adds the usual pay day of the income calendar (``IncomeSettings.pay_day``,
#: default 0 = last working day) for the Calendar tab. Older files load unchanged.
#: 9 — adds budget boxes typed by hand over a figure that fills itself
#: (``YearBudgets.manual``), hours typed per month and vacations in the income
#: calendar (``IncomeSettings.hours_typed``, ``vacations``). Older files load unchanged.
#: 10 — adds month-end net worth snapshots (``AppData.net_worth_snapshots``,
#: default empty) for "Net worth over 12 months". Older files load unchanged.
SCHEMA_VERSION = 10

#: "Net worth over 12 months": how many month-end bars the chart shows.
NET_WORTH_HISTORY_MONTHS = 12

#: How many timestamped copies of data.json to keep alongside the live file.
BACKUP_RETENTION = 20

#: A budget line turns amber ("heads-up") once this share of it is used, and
#: red only once it is actually exceeded. Owner's choice: 80%.
BUDGET_WARNING_PCT = 80.0

#: Planning ranges shown next to the monthly distribution of income, as a share
#: of income in percent: (minimum, maximum), ``None`` = no limit on that side.
#: A widely used rule of thumb (fixed 50–60, investing 10+, saving 5–10,
#: free spending 20–35) — a guide to compare against, not a rule.
DISTRIBUTION_GUIDE: dict[str, tuple[float | None, float | None]] = {
    "fixed": (50.0, 60.0),
    "variable": (20.0, 35.0),
    "investment": (10.0, None),
    "savings": (5.0, None),
}

#: German payroll rules for a working student (Werkstudent), by tax year.
#: Income tax: the § 32a EStG tariff (Grundtabelle, tax class 1) —
#:   zone 1 up to ``gfb``: 0; zone 2 up to ``z2``: (a2·y + b2)·y, y = (zvE − gfb) / 10 000;
#:   zone 3 up to ``z3``: (a3·z + b3)·z + c3, z = (zvE − z2) / 10 000;
#:   zone 4 up to ``z4``: 0.42·zvE − c4; above: 0.45·zvE − c5.
#: ``soli_free``: yearly income tax below which no solidarity surcharge is due.
#: ``pension``: total pension insurance rate (employee pays half), on monthly pay up to ``pension_cap``.
#: ``midi_low`` / ``midi_high``: the Übergangsbereich (reduced employee pension share).
#: A year not listed uses the latest listed one (2027 is still a draft law, so it
#: uses 2026 until the final values are known).
PAYROLL_RULES: dict[int, dict[str, float]] = {
    2025: {
        "gfb": 12096, "z2": 17443, "a2": 932.30, "b2": 1400,
        "z3": 68480, "a3": 176.64, "b3": 2397, "c3": 1015.13,
        "z4": 277825, "c4": 10911.92, "c5": 19246.67,
        "soli_free": 19950, "pension": 18.6, "pension_cap": 8050, "midi_low": 556, "midi_high": 2000,
    },
    2026: {
        "gfb": 12348, "z2": 17799, "a2": 914.51, "b2": 1400,
        "z3": 69878, "a3": 173.10, "b3": 2397, "c3": 1034.87,
        "z4": 277825, "c4": 11135.63, "c5": 19470.38,
        "soli_free": 20350, "pension": 18.6, "pension_cap": 8450, "midi_low": 603, "midi_high": 2000,
    },
}
#: Work-related expenses allowance (Arbeitnehmer-Pauschbetrag) and the lump sum
#: for special expenses (Sonderausgaben-Pauschbetrag), per year.
EMPLOYEE_ALLOWANCE = 1230
SPECIAL_EXPENSES_ALLOWANCE = 36
#: A working student in a semester break may work over 20 hours a week for at
#: most this many weeks in 12 months, or full social insurance becomes due.
WERKSTUDENT_MAX_LONG_WEEKS = 26

#: How many months the Overview's cost history shows, and the windows used for
#: the "usual" figures a month is compared against.
HISTORY_MONTHS = 12
BASELINE_MONTHS = 6
SHORT_BASELINE_MONTHS = 3

#: The rolling forecast always looks this many months ahead.
FORECAST_MONTHS = 12
#: Recorded months shown before the forecast starts, for context.
FORECAST_CONTEXT_MONTHS = 3
#: At most this many graduation scenarios (each one is a line on the chart).
MAX_SCENARIOS = 3

# --- Forecast ranges (services/forecast_ranges.py), added 2026-11-19 ---
#: The spread is learned from at most this many finished months of "kept" …
RANGE_HISTORY_MONTHS = 24
#: … and needs at least this many; with fewer the screens hide the bands.
RANGE_MIN_HISTORY_MONTHS = 6
#: Normal-distribution factors: half of all outcomes lie within ±0.6745 sigma,
#: eight in ten within ±1.2816 sigma (standard z-scores).
RANGE_Z50 = 0.6745
RANGE_Z80 = 1.2816
#: "Stay above" figure: rounded down to 100 € below 5 000 €, to 500 € from there (approved plan, 2026-11-19).
RANGE_FLOOR_SWITCH = 5000
RANGE_FLOOR_SMALL_STEP = 100
RANGE_FLOOR_BIG_STEP = 500
#: "Most likely balance: about …" is rounded to the nearest 50 €.
RANGE_ABOUT_STEP = 50
#: The Overview's forecast card shows this many months.
OVERVIEW_FORECAST_MONTHS = 6

#: Bank import: an existing transaction counts as the same movement when the
#: amount is equal and the dates are at most this many days apart.
DUPLICATE_DAYS = 3
#: Category given to imported rows that no payee rule matched.
UNCATEGORISED = "Uncategorised"
#: Biggest statement file the import accepts.
IMPORT_MAX_BYTES = 5_000_000
#: A payee rule with "book next month" moves a payment made on this day of the
#: month or later to the 1st of the following month (salary, rent).
LATE_PAYMENT_DAY = 25
#: A rule is suggested after the same payee got the same category this often.
RULE_SUGGESTION_MIN = 2

#: Emergency-fund tile: months covered below the first number are "too thin"
#: (red), below the second "building" (amber), otherwise "healthy" (green).
EMERGENCY_THRESHOLDS: tuple[float, float] = (1.0, 3.0)

#: KPI tiles: a figure counts as "about the same as usual" while it is less
#: than this many euros, or less than this % of the usual figure (whichever is
#: bigger), away from the usual month. Example: usual cash in 2,000 -> within
#: 40 € is "about the same"; usual kept 300 -> within 10 €. Owner's choice
#: proposed for the new Overview (2026-11-19).
SAME_AS_USUAL_EUR = 10.0
SAME_AS_USUAL_PCT = 2.0

#: "Unusual this month": a category at least this many times its usual month…
UNUSUAL_FACTOR = 1.5
#: …and at least this many euros above it.
UNUSUAL_MIN_EUR = 30.0

#: Recurring bills. Rhythms in months, with the gaps (in days) between two
#: payments that count as that rhythm when bills are detected.
BILL_RHYTHMS: dict[int, tuple[int, int]] = {1: (25, 35), 3: (80, 100), 6: (165, 200), 12: (340, 390)}
#: A payment this many days around a due date pays that bill.
BILL_MATCH_DAYS = 7
#: Amounts may differ this much (share of the bill) and still be the same bill.
BILL_AMOUNT_TOLERANCE = 0.10
#: A bill is suggested after this many payments.
BILL_MIN_PAYMENTS = 3
#: The Overview lists bills due within this many days.
UPCOMING_DAYS = 30

#: Income calendar "usual pay day": 0 = the last working day of the month;
#: -1 = the working day before it (e.g. last working day Mon 30 Nov 2026 ->
#: paid Fri 27 Nov); 1-31 = that day of the month, moved back to the Friday
#: before on a weekend. Public holidays are not looked at.
PAY_DAY_LAST_WORKING_DAY = 0
PAY_DAY_BEFORE_LAST_WORKING_DAY = -1
#: The default: how Josu's salary is paid (his correction, 18 Nov 2026).
DEFAULT_PAY_DAY = PAY_DAY_BEFORE_LAST_WORKING_DAY
#: Calendar tab: the longest window of money dates one request may ask for.
MONEY_DATES_MAX_DAYS = 400
#: iPhone sync: the app's own calendars in iCloud, one per profile (Josu's
#: choice, 18 Nov 2026: titles only, no amounts — iCloud Calendar is not
#: end-to-end encrypted).
OWN_CALENDARS: dict[str, str] = {"personal": "Centwise Final Project", "joint": "Centwise Final Project Joint"}
#: iPhone sync: money dates from today this many days ahead (about 6 months).
CALENDAR_SYNC_DAYS = 183

#: "Transfer to Joint": the expense category on the Personal side. Its budget
#: follows the owner's part of the Joint plan (services/joint.py).
TRANSFER_PERSONAL_CATEGORY = "Transfer to Joint"
#: On the Joint side each person's money arrives as income "From <name>".
JOINT_CONTRIBUTION_PREFIX = "From "
#: The Joint Overview's money-in vs spent chart: this many months.
JOINT_HISTORY_MONTHS = 6

#: Tax export: Entfernungspauschale per km (one way, per office day), 2026.
#: An estimate for the tax return, not tax advice.
COMMUTE_RATE_PER_KM = 0.38

#: Encrypted backups: shortest password accepted, and the scrypt cost
#: (2**16 = 64 MB of memory per try, which makes guessing slow).
BACKUP_MIN_PASSWORD = 10
BACKUP_SCRYPT_N = 2**16
#: Biggest backup file the app reads back.
BACKUP_MAX_BYTES = 50_000_000

#: Currencies an account or a foreign payment can be in.
CURRENCIES = ("EUR", "PYG")

#: Offered on the first-run setup card. Editable afterwards like any category.
STARTER_CATEGORIES: dict[str, list[tuple[str, str]]] = {
    "expense": [
        ("Rent", "fixed"),
        ("Insurance", "fixed"),
        ("Phone & Internet", "fixed"),
        ("Subscriptions", "fixed"),
        ("Groceries", "variable"),
        ("Eating out", "variable"),
        ("Transport", "variable"),
        ("Shopping", "variable"),
        ("Leisure", "variable"),
        ("Health", "variable"),
    ],
    "income": [
        ("Salary", "variable"),
        ("Other income", "variable"),
    ],
}


def data_dir() -> Path:
    """Folder holding ``data.json``, ``backups/`` and ``app-state.json``.

    Overridable with ``CENTWISE_DATA_DIR`` — the test suite uses this so tests
    never touch the real data. This is deliberately a different folder from the
    course app ("Centwise"), so the two never share a file.
    """
    override = os.environ.get("CENTWISE_DATA_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library" / "Application Support" / APP_NAME


#: The profiles this app offers, in header order: id -> label.
#: Each one is a separate database (own transactions, categories, budgets, goals).
PROFILES: dict[str, str] = {
    "personal": "Personal",
    "joint": "Joint",
}
DEFAULT_PROFILE = "personal"
#: The shared profile. Its first person ("a") is the owner of Personal.
JOINT_PROFILE = "joint"


def profile_dir(profile: str) -> Path:
    """Folder holding one profile's ``data.json`` and ``backups/``.

    Personal lives at the root (where it always has); every other profile gets
    its own sub-folder, so two profiles can never share a file.
    """
    if profile not in PROFILES:
        raise ValueError(f"Unknown profile {profile!r}")
    if profile == DEFAULT_PROFILE:
        return data_dir()
    return data_dir() / profile


def data_file(profile: str = DEFAULT_PROFILE) -> Path:
    return profile_dir(profile) / "data.json"


def app_state_file() -> Path:
    """Last open profile + display preferences (no financial data in it)."""
    return data_dir() / "app-state.json"
