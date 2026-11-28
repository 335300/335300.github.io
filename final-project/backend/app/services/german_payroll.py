"""Net pay of a German working student (Werkstudent), tax class 1.

What comes off a month's gross pay:

1. **Pension insurance** — the only social insurance a working student pays
   (the "Werkstudentenprivileg" frees them from health, care and unemployment
   insurance). The employee pays half the rate (9.3 % of 18.6 %).
   Between ``midi_low`` and ``midi_high`` (the *Übergangsbereich*) the employee
   share is taken from a reduced base: ``high / (high − low) × (gross − low)``.
   Up to ``midi_low`` (a mini-job) the employee pays 3.6 % of gross.
2. **Income tax withheld (Lohnsteuer)** — the month is treated as if it were
   paid all year: yearly wage = gross × 12, minus the work allowance
   (1 230 €), the special-expenses lump sum (36 €) and the pension
   contributions (*Vorsorgepauschale*; a working student's own health insurance
   is not withheld by the employer, so it is not part of it). The § 32a tariff
   gives the yearly tax (whole euros, rounded down); a twelfth of it, rounded
   down to the cent, is withheld.
3. **Solidarity surcharge** — 5.5 % of the tax, only above a yearly free limit
   (with the 11.9 % phase-in above it).
4. **Church tax** — optional, a share of the income tax (8 % or 9 %).

Because a full-time month is taxed as if it lasted all year, more tax is
withheld than is owed over a year with lecture months; :func:`yearly_refund`
estimates what the tax return gives back.

Pure functions; all yearly values live in ``config.PAYROLL_RULES``.
"""

from __future__ import annotations

import math
from typing import Any

from ..config import EMPLOYEE_ALLOWANCE, PAYROLL_RULES, SPECIAL_EXPENSES_ALLOWANCE

MINIJOB_PENSION_PCT = 3.6


def _round2(v: float) -> float:
    return round(v + 0.0, 2)


def _floor_cents(v: float) -> float:
    return math.floor(round(v * 100, 6)) / 100


def rules_for(year: int) -> tuple[dict[str, float], int]:
    """The payroll values for ``year`` and the year they belong to.

    A year after the last listed one uses the latest values (a year before the
    first uses the earliest), so the forecast never runs out of rules.
    """
    known = sorted(PAYROLL_RULES)
    pick = max((y for y in known if y <= year), default=known[0])
    return PAYROLL_RULES[pick], pick


def income_tax(taxable: float, rules: dict[str, float]) -> int:
    """Yearly income tax for a taxable income (§ 32a EStG, Grundtabelle), whole euros."""
    x = math.floor(max(taxable, 0.0))
    if x <= rules["gfb"]:
        tax = 0.0
    elif x <= rules["z2"]:
        y = (x - rules["gfb"]) / 10_000
        tax = (rules["a2"] * y + rules["b2"]) * y
    elif x <= rules["z3"]:
        z = (x - rules["z2"]) / 10_000
        tax = (rules["a3"] * z + rules["b3"]) * z + rules["c3"]
    elif x <= rules["z4"]:
        tax = 0.42 * x - rules["c4"]
    else:
        tax = 0.45 * x - rules["c5"]
    return math.floor(tax + 1e-9)


def solidarity(yearly_tax: float, rules: dict[str, float]) -> float:
    """Yearly solidarity surcharge on a yearly income tax."""
    if yearly_tax <= rules["soli_free"]:
        return 0.0
    return _round2(min(yearly_tax * 0.055, (yearly_tax - rules["soli_free"]) * 0.119))


def pension_share(gross: float, rules: dict[str, float]) -> float:
    """The employee's pension insurance for one month."""
    half = rules["pension"] / 2 / 100
    low, high = rules["midi_low"], rules["midi_high"]
    if gross <= 0:
        return 0.0
    if gross <= low:
        return _round2(gross * MINIJOB_PENSION_PCT / 100)
    if gross <= high:
        base = high / (high - low) * (gross - low)
        return _round2(base * half)
    return _round2(min(gross, rules["pension_cap"]) * half)


def _taxable(yearly_wage: float, yearly_pension: float) -> float:
    allowance = min(EMPLOYEE_ALLOWANCE, yearly_wage)
    return yearly_wage - allowance - SPECIAL_EXPENSES_ALLOWANCE - math.ceil(yearly_pension - 1e-9)


def month_net(gross: float, year: int, church_tax_rate: float = 0.0) -> dict[str, Any]:
    """Everything that comes off one month's gross pay, and what is left.

    Returns ``gross``, ``income_tax``, ``solidarity``, ``church_tax``,
    ``pension``, ``deductions``, ``net``, ``deducted_pct`` (share of gross)
    and ``rules_year`` (the tax year whose values were used).
    """
    rules, rules_year = rules_for(year)
    gross = _round2(max(gross, 0.0))
    pension = pension_share(gross, rules)
    yearly_tax = income_tax(_taxable(gross * 12, pension * 12), rules)
    tax = _floor_cents(yearly_tax / 12)
    soli = _floor_cents(solidarity(yearly_tax, rules) / 12)
    church = _floor_cents(tax * church_tax_rate / 100)
    deductions = _round2(tax + soli + church + pension)
    return {
        "gross": gross,
        "income_tax": tax,
        "solidarity": soli,
        "church_tax": church,
        "pension": pension,
        "deductions": deductions,
        "net": _round2(gross - deductions),
        "deducted_pct": _round2(deductions / gross * 100) if gross else 0.0,
        "rules_year": rules_year,
    }


def yearly_refund(months: list[float], year: int, church_tax_rate: float = 0.0) -> dict[str, Any]:
    """Estimate the tax return for a year of monthly gross pay.

    Withheld = the twelve monthly withholdings. Owed = the tariff on the real
    yearly income (gross − allowances − pension paid). The difference comes back
    (a negative refund would be paid in). Other deductible costs — your own
    health insurance, travel to work, study costs — would raise the refund, so
    this is a floor, not a promise.
    """
    rules, rules_year = rules_for(year)
    per_month = [month_net(g, year, church_tax_rate) for g in months]
    gross = _round2(sum(m["gross"] for m in per_month))
    pension = _round2(sum(m["pension"] for m in per_month))
    withheld = _round2(sum(m["income_tax"] + m["solidarity"] + m["church_tax"] for m in per_month))
    owed_tax = income_tax(_taxable(gross, pension), rules)
    owed = _round2(owed_tax + solidarity(owed_tax, rules) + owed_tax * church_tax_rate / 100)
    return {
        "year": year,
        "rules_year": rules_year,
        "gross": gross,
        "pension": pension,
        "withheld": withheld,
        "owed": owed,
        "refund": _round2(withheld - owed),
    }
