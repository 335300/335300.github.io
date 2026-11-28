"""Pydantic models describing the on-disk schema and the request payloads.

Nothing in the year model knows what year it is: months are integers 0-11,
budgets are 12-slot arrays indexed by month, and every year is an independent
:class:`YearData` under :attr:`AppData.years`. Adding a year is data, not code.

Savings goals live at the :class:`AppData` root, because a goal's deadline can
cross a year boundary.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .config import BILL_RHYTHMS, CURRENCY, DEFAULT_PAY_DAY, MAX_SCENARIOS, SCHEMA_VERSION

TxType = Literal["expense", "income"]
#: ``fixed`` / ``variable`` are living costs. ``investment`` is money that leaves
#: the account to build an asset — cash out, but not an expense.
CategoryKind = Literal["fixed", "variable", "investment"]
GoalStatus = Literal["active", "completed", "abandoned"]
#: ``one_time`` = save up once; ``sinking`` = a known bill that comes back.
GoalType = Literal["one_time", "sinking"]
#: Joint profile: the two people, "a" and "b".
Person = Literal["a", "b"]
SplitRule = Literal["fair", "equal"]

MonthIndex = Annotated[int, Field(ge=0, le=11)]


def _round2(value: float) -> float:
    """Money is stored to the cent; float noise never reaches the UI."""
    return round(float(value), 2)


def _iso_date(value: str) -> str:
    """Accept only real ``YYYY-MM-DD`` dates."""
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise ValueError("must be a date in YYYY-MM-DD format") from None


def _iso_month(value: str) -> str:
    """Accept only ``YYYY-MM`` months."""
    try:
        return date.fromisoformat(f"{value}-01").isoformat()[:7]
    except (TypeError, ValueError):
        raise ValueError("must be a month in YYYY-MM format") from None


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Stored data
# ---------------------------------------------------------------------------

class Category(_Strict):
    """A budget category. ``kind`` only matters for outflows: fixed or variable
    cost, or an investment."""

    name: str = Field(min_length=1)
    kind: CategoryKind = "variable"
    #: Counts toward the essential costs the emergency fund has to cover.
    essential: bool = False
    #: Goes into the yearly tax export (tuition, work equipment, …).
    tax_relevant: bool = False


class Transaction(_Strict):
    id: int
    type: TxType
    #: ISO ``YYYY-MM-DD``. ``month`` is derived from it and drives aggregation.
    date: str
    month: MonthIndex
    amount: float = Field(gt=0)
    desc: str = ""
    cat: str = Field(min_length=1)
    #: How many instalments of an investment plan this payment covered. Only
    #: set on payments into a plan's category; ``None`` = not counted.
    installments: int | None = Field(default=None, ge=0, le=1000)
    #: Who was paid / who paid, as the bank wrote it. Set by the bank import.
    payee: str = ""
    #: The bank's own reference for this movement (end-to-end ID), if any.
    #: The import uses it first to recognise a movement it already has.
    bank_ref: str | None = None
    #: A one-off (wedding, a big repair): left out of every "usual" figure.
    one_off: bool = False
    #: Shared by the two halves of a "Transfer to Joint" (one in each profile).
    link_id: str | None = None
    #: What arrived in the other currency (e.g. PYG received for a land payment).
    foreign_amount: float | None = Field(default=None, gt=0)
    foreign_currency: str | None = Field(default=None, max_length=3)

    @field_validator("amount")
    @classmethod
    def _round_amount(cls, v: float) -> float:
        return _round2(v)


class YearBudgets(_Strict):
    """Budget grids for one year: ``{category name: [12 monthly amounts]}``."""

    expense: dict[str, list[float]] = Field(default_factory=dict)
    income: dict[str, list[float]] = Field(default_factory=dict)

    @field_validator("expense", "income")
    @classmethod
    def _normalise_rows(cls, grid: dict[str, list[float]]) -> dict[str, list[float]]:
        """Force every row to exactly 12 rounded slots (guards hand-edited files)."""
        out: dict[str, list[float]] = {}
        for name, row in grid.items():
            values = [_round2(v or 0) for v in (row or [])][:12]
            values += [0.0] * (12 - len(values))
            out[name] = values
        return out

    #: Cash-out budgets linked to a % of the month's planned income:
    #: ``{category: [12 × percent or None]}``. A linked cell's euro amount is
    #: recalculated whenever that month's income changes (schema 6).
    shares: dict[str, list[float | None]] = Field(default_factory=dict)

    @field_validator("shares")
    @classmethod
    def _normalise_shares(cls, grid: dict[str, list[float | None]]) -> dict[str, list[float | None]]:
        out: dict[str, list[float | None]] = {}
        for name, row in grid.items():
            values: list[float | None] = [None if v is None else round(float(v), 4) for v in (row or [])][:12]
            values += [None] * (12 - len(values))
            if any(v is not None for v in values):
                out[name] = values
        return out

    def share_row(self, name: str) -> list[float | None]:
        return self.shares.get(name, [None] * 12)

    def set_share(self, name: str, month: int, percent: float | None) -> None:
        row = self.shares.setdefault(name, [None] * 12)
        row[month] = None if percent is None else round(percent, 4)
        if all(v is None for v in row):
            self.shares.pop(name, None)

    #: Boxes typed by hand over a figure that fills itself (the salary from the
    #: income calendar, an investment plan, the Joint plan):
    #: ``{"income:<category>" | "expense:<category>": [12 × bool]}``. The
    #: automatic fill leaves a typed box alone until it is set back to automatic
    #: (schema 9).
    manual: dict[str, list[bool]] = Field(default_factory=dict)

    @field_validator("manual")
    @classmethod
    def _normalise_manual(cls, grid: dict[str, list[bool]]) -> dict[str, list[bool]]:
        out: dict[str, list[bool]] = {}
        for key, row in grid.items():
            flags = [bool(v) for v in (row or [])][:12]
            flags += [False] * (12 - len(flags))
            if any(flags):
                out[key] = flags
        return out

    def manual_row(self, kind: str, name: str) -> list[bool]:
        return list(self.manual.get(f"{kind}:{name}", [False] * 12))

    def is_manual(self, kind: str, name: str, month: int) -> bool:
        return 0 <= month < 12 and self.manual_row(kind, name)[month]

    def set_manual(self, kind: str, name: str, month: int, typed: bool) -> None:
        key = f"{kind}:{name}"
        row = self.manual.setdefault(key, [False] * 12)
        row[month] = typed
        if not any(row):
            self.manual.pop(key, None)

    def rename_manual(self, kind: str, old: str, new: str) -> None:
        if f"{kind}:{old}" in self.manual:
            self.manual[f"{kind}:{new}"] = self.manual.pop(f"{kind}:{old}")


class YearCategories(_Strict):
    expense: list[Category] = Field(default_factory=list)
    income: list[Category] = Field(default_factory=list)


class YearData(_Strict):
    """Everything recorded for a single calendar year."""

    #: Cash on hand at the close of ``start_month`` — the year's starting point.
    opening_balance: float = 0.0
    #: Last month *before* tracking begins; -1 means tracking starts in January.
    start_month: int = Field(default=-1, ge=-1, le=11)
    categories: YearCategories = Field(default_factory=YearCategories)
    budgets: YearBudgets = Field(default_factory=YearBudgets)
    transactions: list[Transaction] = Field(default_factory=list)
    next_id: int = 1
    #: Tax export: office days and one-way distance for the commute estimate.
    commute_days: int | None = Field(default=None, ge=0, le=366)
    commute_km: float | None = Field(default=None, ge=0, le=500)

    @field_validator("opening_balance")
    @classmethod
    def _round_opening(cls, v: float) -> float:
        return _round2(v)

    def category_names(self, kind: TxType) -> list[str]:
        return [c.name for c in getattr(self.categories, kind)]

    def find_category(self, kind: TxType, name: str) -> Category | None:
        for c in getattr(self.categories, kind):
            if c.name == name:
                return c
        return None

    def fixed_category_names(self) -> set[str]:
        return {c.name for c in self.categories.expense if c.kind == "fixed"}

    def investment_category_names(self) -> set[str]:
        return {c.name for c in self.categories.expense if c.kind == "investment"}

    def kind_of(self, name: str) -> CategoryKind:
        """Kind of an expense category. Spending in a category that no longer
        exists counts as variable, so no money silently disappears."""
        found = self.find_category("expense", name)
        return found.kind if found else "variable"

    def budget_row(self, kind: TxType, name: str) -> list[float]:
        return getattr(self.budgets, kind).get(name, [0.0] * 12)

    def budget_for(self, kind: TxType, name: str, month: int) -> float:
        row = self.budget_row(kind, name)
        return row[month] if 0 <= month < len(row) else 0.0

    def take_id(self) -> int:
        new_id = self.next_id
        self.next_id = new_id + 1
        return new_id


class Contribution(_Strict):
    """Money deliberately set aside for a goal ("I put €200 toward the laptop").

    A **withdrawal** takes money out again — a sinking fund paying its bill. It
    points at the expense transaction it paid (``tx_year`` / ``tx_id``).
    """

    id: int
    date: str
    amount: float = Field(gt=0)
    note: str = ""
    withdrawal: bool = False
    tx_year: int | None = None
    tx_id: int | None = None

    @property
    def signed(self) -> float:
        """What this does to the goal's money: + for money in, − for money out."""
        return -self.amount if self.withdrawal else self.amount

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("amount")
    @classmethod
    def _round_amount(cls, v: float) -> float:
        return _round2(v)


class SavingsGoal(_Strict):
    id: int
    name: str = Field(min_length=1)
    target_amount: float = Field(gt=0)
    #: ISO date — the deadline.
    target_date: str
    created_date: str
    status: GoalStatus = "active"
    notes: str = ""
    #: This goal is the emergency fund (at most one goal at a time).
    emergency_fund: bool = False
    goal_type: GoalType = "one_time"
    #: Sinking funds only: the bill comes back every this many months. For a
    #: sinking fund ``target_amount`` is one bill and ``target_date`` the next due date.
    repeat_months: int | None = Field(default=None, ge=1, le=24)
    #: Count the purchase in the forecast on its date (the money leaves the
    #: account). ``None`` = the default: yes for a one-time goal, no for the
    #: emergency fund (meant to stay) and for sinking funds (their bill is
    #: usually in the budget already). Schema 7.
    spend_in_forecast: bool | None = None
    contributions: list[Contribution] = Field(default_factory=list)
    next_contribution_id: int = 1

    def spends_in_forecast(self) -> bool:
        if self.spend_in_forecast is not None:
            return self.spend_in_forecast
        return self.goal_type == "one_time" and not self.emergency_fund

    @field_validator("target_date", "created_date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("target_amount")
    @classmethod
    def _round_target(cls, v: float) -> float:
        return _round2(v)

    @model_validator(mode="after")
    def _sinking_needs_rhythm(self) -> "SavingsGoal":
        if self.goal_type == "sinking" and self.repeat_months is None:
            raise ValueError("a sinking fund needs to say how often the bill comes back")
        return self

    def saved(self) -> float:
        return _round2(sum(c.signed for c in self.contributions))

    def take_contribution_id(self) -> int:
        new_id = self.next_contribution_id
        self.next_contribution_id = new_id + 1
        return new_id


class InvestmentPlan(_Strict):
    """An asset bought in instalments (a plot of land paid in 130 "cuotas").

    Payments are ordinary expense transactions in ``category`` (an expense
    category of kind ``investment``); each says how many instalments it covered.
    ``paid_before`` is what was already paid when the plan was added.
    """

    id: int
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    #: What one instalment is called in the UI ("cuota").
    unit: str = "instalment"
    #: Label of the currency the instalments are fixed in ("Gs", "€").
    local_currency: str = "€"
    #: One instalment, in that currency.
    installment_amount: float = Field(gt=0)
    total_installments: int = Field(gt=0)
    paid_before: int = Field(default=0, ge=0)
    #: Roughly what one instalment costs in euros today — used only for
    #: estimates (value at cost, what is still to pay).
    cost_per_installment: float | None = Field(default=None, gt=0)
    #: What the asset is worth today, in its own currency, if known. Without
    #: it, net worth values the asset at its full contract price.
    market_value_local: float | None = Field(default=None, gt=0)
    created_date: str
    notes: str = ""

    @field_validator("created_date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)


class LecturePeriod(_Strict):
    """One lecture period (Vorlesungszeit), first and last day included."""

    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @model_validator(mode="after")
    def _ordered(self) -> "LecturePeriod":
        if self.end < self.start:
            raise ValueError("a lecture period must end on or after its first day")
        return self


class Payslip(_Strict):
    """Gross and net pay for one month of work, typed from a real payslip.

    The income calendar learns the net-to-gross ratio from these.
    """

    id: int
    #: The month the work was done, ``YYYY-MM``.
    month: str
    gross: float = Field(gt=0)
    net: float = Field(gt=0)
    note: str = ""

    @field_validator("month")
    @classmethod
    def _check_month(cls, v: str) -> str:
        return _iso_month(v)

    @field_validator("gross", "net")
    @classmethod
    def _round_money(cls, v: float) -> float:
        return _round2(v)

    @model_validator(mode="after")
    def _net_not_above_gross(self) -> "Payslip":
        if self.net > self.gross:
            raise ValueError("net pay cannot be more than gross pay")
        return self


class GraduationScenario(_Strict):
    """"What if the student job ends on this day?" — one line on the forecast."""

    name: str = Field(min_length=1, max_length=60)
    #: Last day of the working-student job.
    job_end: str
    #: Health insurance per month after the job ends (the employee rate).
    #: ``None`` keeps the budget figure.
    health_insurance_monthly: float | None = Field(default=None, ge=0)
    #: Net salary per month from the month after the job ends, if known.
    new_net_salary: float | None = Field(default=None, ge=0)

    @field_validator("job_end")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class Vacation(_Strict):
    """Paid vacation in the income calendar: every Monday–Friday inside is a
    vacation day (first and last day included)."""

    id: int
    start: str
    end: str
    note: str = Field(default="", max_length=80)

    @field_validator("start", "end")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @model_validator(mode="after")
    def _ordered(self) -> "Vacation":
        if self.end < self.start:
            raise ValueError("a vacation must end on or after its first day")
        return self


class VacationInput(_Strict):
    start: str
    end: str
    note: str = Field(default="", max_length=80)

    @field_validator("start", "end")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("note")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def _ordered(self) -> "VacationInput":
        if self.end < self.start:
            raise ValueError("a vacation must end on or after its first day")
        if (date.fromisoformat(self.end) - date.fromisoformat(self.start)).days > 366:
            raise ValueError("a vacation can be at most a year long")
        return self


class TypedHoursInput(_Strict):
    """Hours worked in one month, typed by hand; ``None`` goes back to the calendar's hours."""

    hours: float | None = Field(default=None, ge=0, le=400)


class IncomeSettings(_Strict):
    """How the working-student pay is earned — everything except payslips."""

    #: Off = the forecast uses the salary budget, as before.
    enabled: bool = True
    hourly_rate: float = Field(default=0.0, ge=0, le=1000)
    #: Hours per week during lecture periods — also the contract hours.
    hours_lecture_week: float = Field(default=20.0, ge=0, le=60)
    #: Hours per week in the semester breaks.
    hours_break_week: float = Field(default=40.0, ge=0, le=60)
    lecture_periods: list[LecturePeriod] = Field(default_factory=list, max_length=40)
    #: The income category the calendar replaces in the forecast.
    salary_category: str = "Salary"
    #: Months between the work and the month the contract pay is booked
    #: (1 = work in October, booked in November).
    contract_pay_lag: int = Field(default=1, ge=0, le=2)
    #: Extra months on top for hours above the contract hours.
    extra_hours_delay: int = Field(default=1, ge=0, le=2)
    #: The expense category of the health insurance (switched by scenarios).
    health_category: str = ""
    #: How net pay is worked out: by German payroll rules for a working student
    #: (tax class 1), or from the ratio of real payslips.
    net_method: Literal["tax_rules", "payslips"] = "tax_rules"
    #: Church tax as % of income tax: 0 (none), 8 (Baden-Württemberg, Bavaria) or 9.
    church_tax_rate: Literal[0, 8, 9] = 0
    scenarios: list[GraduationScenario] = Field(default_factory=list, max_length=MAX_SCENARIOS)
    #: The day the pay usually arrives on the bank account: 0 = the last working
    #: day of the month, -1 = the working day before it, 1-31 = that day (moved
    #: back to Friday on a weekend). Used by the Calendar tab
    #: (``services/money_dates.py``). Schema 8.
    pay_day: int = Field(default=DEFAULT_PAY_DAY, ge=-1, le=31)
    #: Hours typed by hand for a month of work: ``{"YYYY-MM": hours}``. That
    #: month's gross, net and payment are then worked out from them (schema 9).
    #: Kept when the settings form is saved (it has its own endpoint).
    hours_typed: dict[str, float] = Field(default_factory=dict)
    #: Paid vacations (schema 9). Kept when the settings form is saved.
    vacations: list[Vacation] = Field(default_factory=list, max_length=60)

    @field_validator("hours_typed")
    @classmethod
    def _check_typed(cls, v: dict[str, float]) -> dict[str, float]:
        out = {}
        for month, hours in v.items():
            if not 0 <= float(hours) <= 400:
                raise ValueError("typed hours must be between 0 and 400")
            out[_iso_month(month)] = _round2(float(hours))
        return out

    @field_validator("hourly_rate", "hours_lecture_week", "hours_break_week")
    @classmethod
    def _round_numbers(cls, v: float) -> float:
        return _round2(v)

    @field_validator("salary_category", "health_category")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class IncomePlan(IncomeSettings):
    """The income calendar of one profile: settings plus the payslips."""

    payslips: list[Payslip] = Field(default_factory=list)
    next_payslip_id: int = 1

    def take_payslip_id(self) -> int:
        new_id = self.next_payslip_id
        self.next_payslip_id = new_id + 1
        return new_id


class PayeeRule(_Strict):
    """"If the payee or purpose contains this text, use this category"."""

    id: int
    contains: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=80)
    #: Only for expenses or only for income; ``None`` = both.
    tx_type: TxType | None = None
    #: Paid on the 25th or later → booked on the 1st of the next month
    #: (how salary and month-end rent are recorded).
    next_month_if_late: bool = False


class RecurringBill(_Strict):
    """A bill that comes back on a rhythm (rent share, insurance, phone, tuition)."""

    id: int
    name: str = Field(min_length=1, max_length=80)
    amount: float = Field(gt=0)
    category: str = Field(min_length=1, max_length=80)
    #: Every 1, 3, 6 or 12 months.
    rhythm_months: int
    #: The next due date as entered; paid occurrences move on by themselves.
    next_due: str
    #: Text that identifies its payments (in the payee or description).
    match: str = Field(default="", max_length=80)
    #: A sinking fund that saves for this bill.
    goal_id: int | None = None

    @field_validator("next_due")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("rhythm_months")
    @classmethod
    def _check_rhythm(cls, v: int) -> int:
        if v not in BILL_RHYTHMS:
            raise ValueError("rhythm must be 1, 3, 6 or 12 months")
        return v

    @field_validator("amount")
    @classmethod
    def _round_amount(cls, v: float) -> float:
        return _round2(v)


class FairShare(_Strict):
    """Joint profile: the two people and their net incomes."""

    #: Person a is the owner of the Personal profile.
    name_a: str = Field(default="Josu", min_length=1, max_length=40)
    name_b: str = Field(default="Isa", min_length=1, max_length=40)
    income_a: float | None = Field(default=None, ge=0)
    income_b: float | None = Field(default=None, ge=0)


class SharedExpense(_Strict):
    """Something shared that one person paid from a personal account.

    Not a Joint transaction: the joint account never paid it.
    """

    id: int
    date: str
    desc: str = Field(default="", max_length=120)
    amount: float = Field(gt=0)
    paid_by: Person
    split: SplitRule = "fair"

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("amount")
    @classmethod
    def _round_amount(cls, v: float) -> float:
        return _round2(v)


class Settlement(_Strict):
    """Money one person gave the other to settle up."""

    id: int
    date: str
    from_person: Person
    amount: float = Field(gt=0)
    note: str = Field(default="", max_length=120)

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("amount")
    @classmethod
    def _round_amount(cls, v: float) -> float:
        return _round2(v)


AccountKind = Literal["current", "savings", "investment", "cash", "other"]
Currency = Literal["EUR", "PYG"]


class AccountValue(_Strict):
    """What an account held on a day (typed from a statement or the app)."""

    date: str
    amount: float

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("amount")
    @classmethod
    def _round_amount(cls, v: float) -> float:
        return _round2(v)


class Account(_Strict):
    """An account the app does not track transaction by transaction
    (Tagesgeld, ETF depot, cash, an account in Paraguay)."""

    id: int
    name: str = Field(min_length=1, max_length=60)
    kind: AccountKind = "savings"
    currency: Currency = "EUR"
    #: Every value entered, so net worth has a history.
    values: list[AccountValue] = Field(default_factory=list)
    notes: str = Field(default="", max_length=200)


class ExchangeRate(_Strict):
    """How many units of ``currency`` one euro bought on ``date`` (entered by hand)."""

    currency: Currency = "PYG"
    per_eur: float = Field(gt=0)
    date: str

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)


class NetWorthSnapshotItem(_Strict):
    """One line of a net worth snapshot (an account, the land, its debt)."""

    kind: str
    name: str
    side: Literal["own", "owe"]
    #: In euros; ``None`` when no exchange rate was known.
    eur: float | None = None
    account_id: int | None = None
    plan_id: int | None = None


class NetWorthSnapshot(_Strict):
    """Net worth as the app showed it in one month (the last time it was worked
    out that month), so later months can show its history (schema 10)."""

    #: ``YYYY-MM``.
    month: str
    #: The day it was taken (``YYYY-MM-DD``).
    taken: str
    own: float
    owe: float
    net_worth: float
    items: list[NetWorthSnapshotItem] = Field(default_factory=list)

    @field_validator("month")
    @classmethod
    def _check_month(cls, v: str) -> str:
        return _iso_month(v)

    @field_validator("taken")
    @classmethod
    def _check_taken(cls, v: str) -> str:
        return _iso_date(v)


class Settings(_Strict):
    currency: str = CURRENCY
    #: Remembers where the user was, so the app reopens on the same view.
    last_year: int | None = None
    last_month: MonthIndex | None = None


class AppData(_Strict):
    """Root document persisted to one profile's ``data.json``."""

    schema_version: int = SCHEMA_VERSION
    settings: Settings = Field(default_factory=Settings)
    #: Keyed by year as a string, because JSON object keys are always strings.
    years: dict[str, YearData] = Field(default_factory=dict)
    goals: list[SavingsGoal] = Field(default_factory=list)
    next_goal_id: int = 1
    investments: list[InvestmentPlan] = Field(default_factory=list)
    next_investment_id: int = 1
    #: The working-student income calendar; ``None`` until it is set up.
    income_plan: IncomePlan | None = None
    payee_rules: list[PayeeRule] = Field(default_factory=list)
    next_rule_id: int = 1
    #: Rule suggestions the user said "no" to (the suggested text).
    dismissed_rule_suggestions: list[str] = Field(default_factory=list)
    recurring_bills: list[RecurringBill] = Field(default_factory=list)
    next_bill_id: int = 1
    #: Bill suggestions the user said "no" to (normalised payee text).
    dismissed_bill_suggestions: list[str] = Field(default_factory=list)
    #: Joint profile only (empty elsewhere): fair share, settle-up.
    fair_share: FairShare = Field(default_factory=FairShare)
    shared_expenses: list[SharedExpense] = Field(default_factory=list)
    settlements: list[Settlement] = Field(default_factory=list)
    next_shared_id: int = 1
    #: Net worth: accounts kept by hand, and exchange rates entered by hand.
    accounts: list[Account] = Field(default_factory=list)
    next_account_id: int = 1
    exchange_rates: list[ExchangeRate] = Field(default_factory=list)
    #: One net worth snapshot per month, written while that month runs (schema 10).
    net_worth_snapshots: list[NetWorthSnapshot] = Field(default_factory=list)

    def take_account_id(self) -> int:
        new_id = self.next_account_id
        self.next_account_id = new_id + 1
        return new_id

    def take_bill_id(self) -> int:
        new_id = self.next_bill_id
        self.next_bill_id = new_id + 1
        return new_id

    def take_shared_id(self) -> int:
        new_id = self.next_shared_id
        self.next_shared_id = new_id + 1
        return new_id

    def take_rule_id(self) -> int:
        new_id = self.next_rule_id
        self.next_rule_id = new_id + 1
        return new_id

    def year_numbers(self) -> list[int]:
        return sorted(int(y) for y in self.years)

    def get_year(self, year: int) -> YearData | None:
        return self.years.get(str(year))

    def find_goal(self, goal_id: int) -> SavingsGoal | None:
        for g in self.goals:
            if g.id == goal_id:
                return g
        return None

    def take_goal_id(self) -> int:
        new_id = self.next_goal_id
        self.next_goal_id = new_id + 1
        return new_id

    def find_investment(self, plan_id: int) -> InvestmentPlan | None:
        for p in self.investments:
            if p.id == plan_id:
                return p
        return None

    def investment_for_category(self, name: str) -> InvestmentPlan | None:
        for p in self.investments:
            if p.category == name:
                return p
        return None

    def take_investment_id(self) -> int:
        new_id = self.next_investment_id
        self.next_investment_id = new_id + 1
        return new_id


# ---------------------------------------------------------------------------
# Request payloads
# ---------------------------------------------------------------------------

class TransactionInput(_Strict):
    """A transaction as submitted by the UI. The server assigns id and month."""

    type: TxType
    date: str
    amount: float = Field(gt=0)
    desc: str = ""
    cat: str = Field(min_length=1)
    #: Instalments of the investment plan this payment covers (see Transaction).
    installments: int | None = Field(default=None, ge=0, le=1000)
    one_off: bool = False
    foreign_amount: float | None = Field(default=None, gt=0)
    foreign_currency: Currency | None = None

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("cat", "desc")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class BulkTransactionInput(_Strict):
    transactions: list[TransactionInput] = Field(min_length=1, max_length=500)


class BudgetCellInput(_Strict):
    """One month's budget for one category: in euros (``value``) or, for an
    expense line, as a % of that month's planned income (``percent``)."""

    kind: TxType
    cat: str = Field(min_length=1)
    month: MonthIndex
    value: float | None = Field(default=None, ge=0)
    percent: float | None = Field(default=None, ge=0, le=1000)
    #: True: a box typed by hand over a figure that fills itself goes back to
    #: automatic (no value or percent then).
    auto: bool = False

    @model_validator(mode="after")
    def _one_amount(self) -> "BudgetCellInput":
        if self.auto:
            if self.value is not None or self.percent is not None:
                raise ValueError("back to automatic takes no value")
            return self
        if (self.value is None) == (self.percent is None):
            raise ValueError("give either a value in euros or a percent, not both")
        if self.percent is not None and self.kind != "expense":
            raise ValueError("only cash-out budgets can be set as a % of income")
        return self


class BudgetRowShareInput(_Strict):
    """Link a cash-out category to a % of planned income in every month not
    recorded yet (``percent`` = None removes those links, keeping the euros)."""

    cat: str = Field(min_length=1)
    percent: float | None = Field(default=None, ge=0, le=1000)


class CategoryInput(_Strict):
    kind: TxType
    name: str = Field(min_length=1)
    category_kind: CategoryKind = "variable"
    essential: bool = False
    tax_relevant: bool = False


class CategoryPatch(_Strict):
    """Rename a category, flip its fixed/variable flag, or mark it essential."""

    name: str | None = None
    category_kind: CategoryKind | None = None
    essential: bool | None = None
    tax_relevant: bool | None = None


class YearInput(_Strict):
    year: int = Field(ge=1970, le=2200)
    #: Copy categories and budget figures from this year, if given.
    copy_from: int | None = None


class YearPatch(_Strict):
    """Edit a year's starting point (opening balance and first tracked month)."""

    opening_balance: float | None = None
    start_month: int | None = Field(default=None, ge=-1, le=11)


class SetupInput(_Strict):
    """The first-run setup card."""

    year: int = Field(ge=1970, le=2200)
    opening_balance: float = 0.0
    start_month: int = Field(default=-1, ge=-1, le=11)
    starter_categories: bool = True


class GoalInput(_Strict):
    name: str = Field(min_length=1, max_length=80)
    target_amount: float = Field(gt=0)
    target_date: str
    notes: str = ""
    emergency_fund: bool = False
    goal_type: GoalType = "one_time"
    repeat_months: int | None = Field(default=None, ge=1, le=24)
    spend_in_forecast: bool | None = None

    @field_validator("target_date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)


class GoalPatch(_Strict):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    target_amount: float | None = Field(default=None, gt=0)
    target_date: str | None = None
    status: GoalStatus | None = None
    notes: str | None = None
    emergency_fund: bool | None = None
    goal_type: GoalType | None = None
    repeat_months: int | None = Field(default=None, ge=1, le=24)
    spend_in_forecast: bool | None = None

    @field_validator("target_date")
    @classmethod
    def _check_date(cls, v: str | None) -> str | None:
        return None if v is None else _iso_date(v)


class ContributionInput(_Strict):
    date: str
    amount: float = Field(gt=0)
    note: str = ""

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)


class InvestmentInput(_Strict):
    name: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=80)
    unit: str = Field(default="instalment", min_length=1, max_length=30)
    local_currency: str = Field(default="€", min_length=1, max_length=10)
    installment_amount: float = Field(gt=0)
    total_installments: int = Field(gt=0, le=10000)
    paid_before: int = Field(default=0, ge=0, le=10000)
    cost_per_installment: float | None = Field(default=None, gt=0)
    market_value_local: float | None = Field(default=None, gt=0)
    notes: str = ""

    @field_validator("name", "category", "unit", "local_currency", "notes")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class InvestmentPatch(_Strict):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    unit: str | None = Field(default=None, min_length=1, max_length=30)
    local_currency: str | None = Field(default=None, min_length=1, max_length=10)
    installment_amount: float | None = Field(default=None, gt=0)
    total_installments: int | None = Field(default=None, gt=0, le=10000)
    paid_before: int | None = Field(default=None, ge=0, le=10000)
    #: 0 clears the estimate.
    cost_per_installment: float | None = Field(default=None, ge=0)
    #: 0 clears the market value.
    market_value_local: float | None = Field(default=None, ge=0)
    notes: str | None = None


class GoalAllocation(_Strict):
    goal_id: int
    amount: float = Field(ge=0)


class DistributionInput(_Strict):
    """Money of one month put toward goals in one go."""

    month: MonthIndex
    allocations: list[GoalAllocation] = Field(default_factory=list, max_length=100)


class ProfileSwitch(_Strict):
    profile: str = Field(min_length=1)


class PrefsPatch(_Strict):
    """Display preferences (stored in app-state.json, not in data.json)."""

    show_savings_tile: bool | None = None
    #: Calendar tab: ids of the Apple calendars not to show (both profiles).
    calendar_hidden: list[Annotated[str, Field(min_length=1, max_length=200)]] | None = Field(default=None, max_length=200)
    #: iPhone sync on/off (the own calendars' ids and the last sync time are set by the backend only).
    calendar_push: bool | None = None
    #: Light / dark look: "system" follows the Mac setting (the default).
    appearance: Literal["system", "light", "dark"] | None = None


class PayslipInput(_Strict):
    month: str
    gross: float = Field(gt=0)
    net: float = Field(gt=0)
    note: str = Field(default="", max_length=120)

    @field_validator("month")
    @classmethod
    def _check_month(cls, v: str) -> str:
        return _iso_month(v)

    @model_validator(mode="after")
    def _net_not_above_gross(self) -> "PayslipInput":
        if self.net > self.gross:
            raise ValueError("net pay cannot be more than gross pay")
        return self


class PayeeRuleInput(_Strict):
    contains: str = Field(min_length=1, max_length=80)
    category: str = Field(min_length=1, max_length=80)
    tx_type: TxType | None = None
    next_month_if_late: bool = False

    @field_validator("contains", "category")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class RuleSuggestionDismiss(_Strict):
    contains: str = Field(min_length=1, max_length=80)


class ImportFileInput(_Strict):
    """A statement file read by the page, sent as base64."""

    filename: str = Field(default="", max_length=200)
    content_base64: str = Field(min_length=1, max_length=8_000_000)


class ImportRow(_Strict):
    """One row the user chose to save from the import preview."""

    date: str
    type: TxType
    amount: float = Field(gt=0)
    cat: str = Field(min_length=1, max_length=80)
    desc: str = Field(default="", max_length=300)
    payee: str = Field(default="", max_length=200)
    bank_ref: str | None = Field(default=None, max_length=200)

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("cat", "desc", "payee")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class ImportCommitInput(_Strict):
    rows: list[ImportRow] = Field(min_length=1, max_length=2000)


class PayFromFundInput(_Strict):
    """Pay a sinking fund's bill: an expense plus the same amount out of the fund."""

    date: str
    amount: float = Field(gt=0)
    category: str = Field(min_length=1, max_length=80)
    desc: str = Field(default="", max_length=120)

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("category", "desc")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class RecurringBillInput(_Strict):
    name: str = Field(min_length=1, max_length=80)
    amount: float = Field(gt=0)
    category: str = Field(min_length=1, max_length=80)
    rhythm_months: int
    next_due: str
    match: str = Field(default="", max_length=80)
    goal_id: int | None = None

    @field_validator("next_due")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("rhythm_months")
    @classmethod
    def _check_rhythm(cls, v: int) -> int:
        if v not in BILL_RHYTHMS:
            raise ValueError("rhythm must be 1, 3, 6 or 12 months")
        return v

    @field_validator("name", "category", "match")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class BillSuggestionDismiss(_Strict):
    key: str = Field(min_length=1, max_length=120)


class TransferInput(_Strict):
    """Personal → Joint: one expense here, one matching income there."""

    date: str
    amount: float = Field(gt=0)
    note: str = Field(default="", max_length=120)
    personal_category: str = Field(default="", max_length=80)
    joint_category: str = Field(default="", max_length=80)

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)

    @field_validator("note", "personal_category", "joint_category")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class SharedExpenseInput(_Strict):
    date: str
    desc: str = Field(default="", max_length=120)
    amount: float = Field(gt=0)
    paid_by: Person
    split: SplitRule = "fair"

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)


class SettlementInput(_Strict):
    date: str
    from_person: Person
    amount: float = Field(gt=0)
    note: str = Field(default="", max_length=120)

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)


class TaxSettingsInput(_Strict):
    commute_days: int | None = Field(default=None, ge=0, le=366)
    commute_km: float | None = Field(default=None, ge=0, le=500)


class BackupInput(_Strict):
    password: str = Field(min_length=1, max_length=200)


class BackupFileInput(_Strict):
    password: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(min_length=1, max_length=70_000_000)


class AccountInput(_Strict):
    name: str = Field(min_length=1, max_length=60)
    kind: AccountKind = "savings"
    currency: Currency = "EUR"
    notes: str = Field(default="", max_length=200)

    @field_validator("name", "notes")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class AccountValueInput(_Strict):
    date: str
    amount: float

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)


class ExchangeRateInput(_Strict):
    currency: Currency = "PYG"
    per_eur: float = Field(gt=0)
    date: str

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        return _iso_date(v)


class AttentionMoveInput(_Strict):
    """The "Worth a look" button: move ``amount`` € of this month's budget from
    ``from_cat`` to ``to_cat``. It must be exactly what the banner offered."""

    month: MonthIndex
    from_cat: str = Field(min_length=1)
    to_cat: str = Field(min_length=1)
    amount: float = Field(gt=0)
