"""Income calendar: what a working student earns each month, and when it arrives.

How a month is worked out:

1. Every weekday (Monday–Friday) of the month is a **lecture day** when it lies
   in one of the lecture periods, otherwise a **break day**. Days after the
   job's last day are not worked. Public holidays are paid in Germany, so they
   count like any other weekday.
2. A lecture day has ``hours_lecture_week / 5`` hours, a break day
   ``hours_break_week / 5``. The lecture-week hours are the **contract hours**;
   anything above them on a break day is **extra hours**. Half months (a period
   that starts or ends mid-month) fall out of this on their own.
3. Gross = hours × hourly rate.
4. Net = gross minus what German payroll takes off a working student in tax
   class 1 — income tax, solidarity surcharge, church tax, pension insurance
   (see :mod:`german_payroll`). Each month on its own: a full-time month keeps a
   smaller share than a 20-hour month. Or, if chosen, gross × the ratio learned
   from real payslips (see :func:`net_ratio`).
5. Contract pay is booked ``contract_pay_lag`` months after the work; extra
   hours another ``extra_hours_delay`` months later.

Months are handled as ``(year, month)`` with ``month`` 0–11, like the rest of
the app. Pure functions only — nothing here reads the clock or the disk.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from ..config import MONTHS, MONTHS_SHORT, WERKSTUDENT_MAX_LONG_WEEKS
from ..models import IncomeSettings, LecturePeriod, Payslip
from . import german_payroll

YM = tuple[int, int]


def _round2(v: float) -> float:
    return round(v, 2)


# ---------------------------------------------------------------------------
# Month arithmetic
# ---------------------------------------------------------------------------

def ym_index(ym: YM) -> int:
    return ym[0] * 12 + ym[1]


def ym_from_index(i: int) -> YM:
    return divmod(i, 12)


def ym_add(ym: YM, months: int) -> YM:
    return ym_from_index(ym_index(ym) + months)


def ym_label(ym: YM) -> str:
    return f"{MONTHS_SHORT[ym[1]]} {str(ym[0])[2:]}"


def ym_name(ym: YM) -> str:
    return f"{MONTHS[ym[1]]} {ym[0]}"


def ym_key(ym: YM) -> str:
    return f"{ym[0]}-{ym[1] + 1:02d}"


def ym_of(d: date) -> YM:
    return d.year, d.month - 1


# ---------------------------------------------------------------------------
# Days and hours
# ---------------------------------------------------------------------------

def is_lecture_day(day: date, periods: list[LecturePeriod]) -> bool:
    iso = day.isoformat()
    return any(p.start <= iso <= p.end for p in periods)


def _weekdays(ym: YM) -> int:
    """Monday–Friday in a month (public holidays count, as everywhere here)."""
    year, month = ym
    first = date(year, month + 1, 1)
    return sum(1 for i in range(calendar.monthrange(year, month + 1)[1]) if (first + timedelta(days=i)).weekday() < 5)


def _on_vacation(day: date, settings: IncomeSettings) -> bool:
    iso = day.isoformat()
    return any(v.start <= iso <= v.end for v in settings.vacations)


def work_month(settings: IncomeSettings, ym: YM, job_end: date | None = None,
               payslips: list[Payslip] | None = None) -> dict[str, Any]:
    """Hours and gross pay for one month of work.

    - **Vacation days** (Monday–Friday inside a vacation) are not worked. Each
      is paid at the average of the 3 months before: their gross (a payslip's
      gross where one is entered, else this calendar's) ÷ their Monday–Friday
      days. Vacation pay is part of the contract pay.
    - **Typed hours** (``hours_typed``) replace the month's worked hours. The
      contract hours stay as the calendar works them out; typed hours above
      them are extra hours, fewer are all contract hours.
    """
    return _work_month(settings, ym, job_end, payslips or [], {})


def _work_month(settings: IncomeSettings, ym: YM, job_end: date | None, payslips: list[Payslip],
                cache: dict[YM, dict[str, Any]]) -> dict[str, Any]:
    if ym in cache:
        return cache[ym]
    year, month = ym
    lecture_days = break_days = vacation_days = 0
    first = date(year, month + 1, 1)
    for offset in range(calendar.monthrange(year, month + 1)[1]):
        day = first + timedelta(days=offset)
        if day.weekday() >= 5 or (job_end is not None and day > job_end):
            continue
        if _on_vacation(day, settings):
            vacation_days += 1
        elif is_lecture_day(day, settings.lecture_periods):
            lecture_days += 1
        else:
            break_days += 1

    lecture_per_day = settings.hours_lecture_week / 5
    break_per_day = settings.hours_break_week / 5
    contract_per_day = settings.hours_lecture_week / 5
    hours_lecture = lecture_days * lecture_per_day
    hours_break = break_days * break_per_day
    # The contract hours of a break day are paid like any day; only what goes
    # beyond them is "extra" (and may be paid later).
    hours_contract = hours_lecture + break_days * min(break_per_day, contract_per_day)
    hours_extra = break_days * max(0.0, break_per_day - contract_per_day)
    hours_auto = hours_lecture + hours_break
    typed = settings.hours_typed.get(ym_key(ym))
    if typed is not None:
        hours_extra = max(0.0, typed - hours_contract)
        hours_contract = min(typed, hours_contract)
    rate = settings.hourly_rate

    vacation_pay = 0.0
    vacation_rate = None
    if vacation_days:
        total, days = 0.0, 0
        for back in (1, 2, 3):
            before = ym_add(ym, -back)
            slip = next((p for p in payslips if p.month == ym_key(before)), None)
            total += slip.gross if slip else _work_month(settings, before, job_end, payslips, cache)["gross"]
            days += _weekdays(before)
        if days:
            vacation_rate = _round2(total / days)
            vacation_pay = _round2(total * vacation_days / days)

    if lecture_days and break_days:
        kind = "mixed"
    elif lecture_days:
        kind = "lecture"
    elif break_days:
        kind = "break"
    else:
        kind = "none"

    row = {
        "year": year,
        "month": month,
        "key": ym_key(ym),
        "label": ym_label(ym),
        "month_name": ym_name(ym),
        "kind": kind,
        "lecture_days": lecture_days,
        "break_days": break_days,
        "vacation_days": vacation_days,
        "hours": _round2(hours_contract + hours_extra),
        "hours_auto": _round2(hours_auto),
        "hours_typed": typed is not None,
        "hours_contract": _round2(hours_contract),
        "hours_extra": _round2(hours_extra),
        "vacation_rate": vacation_rate,
        "vacation_pay": vacation_pay,
        "gross_contract": _round2(hours_contract * rate + vacation_pay),
        "gross_extra": _round2(hours_extra * rate),
        "gross": _round2((hours_contract + hours_extra) * rate + vacation_pay),
    }
    cache[ym] = row
    return row


# ---------------------------------------------------------------------------
# Net from gross
# ---------------------------------------------------------------------------

def net_ratio(payslips: list[Payslip], gross: float) -> float | None:
    """Share of ``gross`` that is left as net pay, learned from payslips.

    A full-time month keeps a smaller share than a 20-hour month (more tax), so
    one ratio does not fit all months. The ratio of the payslip with the most
    similar gross is used; between two payslips the two ratios are blended in
    proportion to where ``gross`` lies between them. Payslips with the same
    gross are averaged. ``None`` when no payslip is entered yet.
    """
    if not payslips:
        return None
    by_gross: dict[float, list[float]] = {}
    for p in payslips:
        by_gross.setdefault(p.gross, []).append(p.net / p.gross)
    points = sorted((g, sum(r) / len(r)) for g, r in by_gross.items())
    if gross <= points[0][0]:
        return points[0][1]
    if gross >= points[-1][0]:
        return points[-1][1]
    for (g1, r1), (g2, r2) in zip(points, points[1:]):
        if g1 <= gross <= g2:
            share = (gross - g1) / (g2 - g1)
            return r1 + (r2 - r1) * share
    return points[-1][1]  # pragma: no cover - the loop always returns


def uses_tax_rules(settings: IncomeSettings) -> bool:
    return settings.net_method == "tax_rules"


def has_net(settings: IncomeSettings, payslips: list[Payslip]) -> bool:
    """Whether net pay can be worked out: always with the tax rules, else once a payslip exists."""
    return uses_tax_rules(settings) or bool(payslips)


_NO_NET = {
    "net_ratio": None, "net": None, "net_contract": None, "net_extra": None,
    "income_tax": None, "pension": None, "deducted_pct": None, "rules_year": None,
}


def with_net(row: dict[str, Any], payslips: list[Payslip], settings: IncomeSettings) -> dict[str, Any]:
    """Add net pay (whole month, contract part, extra part) to a work month.

    With the tax rules the month also gets ``income_tax`` (income tax +
    solidarity surcharge + church tax), ``pension`` and ``deducted_pct``.
    The contract and extra parts keep the month's net share between them.
    """
    breakdown: dict[str, Any] | None = None
    if uses_tax_rules(settings):
        breakdown = german_payroll.month_net(row["gross"], row["year"], settings.church_tax_rate)
        ratio = breakdown["net"] / row["gross"] if row["gross"] else 1.0
    else:
        ratio = net_ratio(payslips, row["gross"])
        if ratio is None:
            return {**row, **_NO_NET}
    net_contract = _round2(row["gross_contract"] * ratio)
    net_extra = _round2(row["gross_extra"] * ratio)
    out = {
        **row,
        **_NO_NET,
        "net_ratio": round(ratio, 4),
        "net": _round2(net_contract + net_extra),
        "net_contract": net_contract,
        "net_extra": net_extra,
        "deducted_pct": _round2((1 - ratio) * 100) if row["gross"] else 0.0,
    }
    if breakdown is not None:
        out["income_tax"] = _round2(breakdown["income_tax"] + breakdown["solidarity"] + breakdown["church_tax"])
        out["pension"] = breakdown["pension"]
        out["deducted_pct"] = breakdown["deducted_pct"]
        out["rules_year"] = breakdown["rules_year"]
    return out


def payslip_checks(settings: IncomeSettings, payslips: list[Payslip]) -> list[dict[str, Any]]:
    """Each payslip next to what the tax rules give for the same gross.

    A small difference is normal (meal allowances, one-off payments); a large
    one means the rules miss something on your payslip.
    """
    out = []
    for p in payslips:
        year = int(p.month[:4])
        rules = german_payroll.month_net(p.gross, year, settings.church_tax_rate)
        out.append(
            {
                "id": p.id,
                "month": p.month,
                "gross": p.gross,
                "net": p.net,
                "rules_net": rules["net"],
                "difference": _round2(p.net - rules["net"]),
            }
        )
    return out


def refund_estimate(settings: IncomeSettings, today: YM) -> dict[str, Any] | None:
    """What the tax return may give back for one calendar year if the job runs
    as the calendar says: the current year until June, then the next one.
    Every month of that year is worked out from the calendar."""
    if not uses_tax_rules(settings) or settings.hourly_rate <= 0:
        return None
    year = today[0] if today[1] <= 5 else today[0] + 1
    grosses = [work_month(settings, (year, m))["gross"] for m in range(12)]
    return german_payroll.yearly_refund(grosses, year, settings.church_tax_rate)


def long_weeks(settings: IncomeSettings, first: YM, count: int) -> float:
    """Weeks with more than 20 hours of work in the window (semester breaks)."""
    if settings.hours_break_week <= 20:
        return 0.0
    days = sum(work_month(settings, ym_add(first, i))["break_days"] for i in range(count))
    return round(days / 5, 1)


# ---------------------------------------------------------------------------
# When the money arrives
# ---------------------------------------------------------------------------

def paid_by_month(
    settings: IncomeSettings,
    payslips: list[Payslip],
    first: YM,
    count: int,
    job_end: date | None = None,
    new_net_salary: float | None = None,
) -> dict[YM, float]:
    """Net pay booked in each of ``count`` months starting at ``first``.

    Pay for work done before ``first`` that arrives inside the window is
    included, so the first months are not empty. ``new_net_salary`` (a job after
    graduation) starts with the first full month after ``job_end`` and is booked
    with the same contract-pay lag. Empty when no payslip is entered (no net).
    """
    if not has_net(settings, payslips):
        return {}
    lag = settings.contract_pay_lag
    extra_lag = lag + settings.extra_hours_delay
    out: dict[YM, float] = {ym_add(first, i): 0.0 for i in range(count)}
    new_job_from = ym_add(ym_of(job_end), 1) if job_end is not None else None

    for i in range(-extra_lag, count):
        work = ym_add(first, i)
        row = with_net(work_month(settings, work, job_end, payslips), payslips, settings)
        contract = row["net_contract"] or 0.0
        extra = row["net_extra"] or 0.0
        if new_job_from is not None and new_net_salary and ym_index(work) >= ym_index(new_job_from):
            contract += new_net_salary
        for amount, delay in ((contract, lag), (extra, extra_lag)):
            target = ym_add(work, delay)
            if target in out:
                out[target] += amount
    return {ym: _round2(v) for ym, v in out.items()}


def calendar_view(
    settings: IncomeSettings,
    payslips: list[Payslip],
    first: YM,
    count: int,
    scenario_ends: list[tuple[str, date]] | None = None,
) -> dict[str, Any]:
    """The income calendar card: one row per month of work, plus when it arrives.

    Rows assume the job goes on; each scenario's last month is flagged so the
    card can mark where the student job would end.
    """
    paid = paid_by_month(settings, payslips, first, count)
    ends = scenario_ends or []
    rows = []
    for i in range(count):
        ym = ym_add(first, i)
        row = with_net(work_month(settings, ym, payslips=payslips), payslips, settings)
        row["received"] = paid.get(ym) if has_net(settings, payslips) else None
        row["contract_paid_in"] = ym_label(ym_add(ym, settings.contract_pay_lag))
        row["extra_paid_in"] = (
            ym_label(ym_add(ym, settings.contract_pay_lag + settings.extra_hours_delay))
            if row["hours_extra"] else None
        )
        row["job_ends"] = [name for name, end in ends if ym_of(end) == ym]
        rows.append(row)

    nets = [r["net"] for r in rows if r["net"] is not None]
    last_period = max((p.end for p in settings.lecture_periods), default=None)
    window_end = ym_key(ym_add(first, count - 1))
    warnings: list[str] = []
    if not has_net(settings, payslips):
        warnings.append("no_payslips")
    weeks = long_weeks(settings, first, count)
    if weeks > WERKSTUDENT_MAX_LONG_WEEKS:
        warnings.append("werkstudent_26_weeks")
    if not settings.lecture_periods:
        warnings.append("no_lecture_periods")
    elif last_period is not None and last_period[:7] < window_end:
        warnings.append("lecture_periods_end_early")
    if settings.hourly_rate <= 0:
        warnings.append("no_hourly_rate")

    return {
        "rows": rows,
        "total_gross": _round2(sum(r["gross"] for r in rows)),
        "total_net": _round2(sum(nets)) if has_net(settings, payslips) else None,
        "average_net": _round2(sum(nets) / len(nets)) if nets else None,
        "lecture_periods_until": last_period,
        "warnings": warnings,
        "net_method": settings.net_method,
        "long_weeks": weeks,
        "payslip_checks": payslip_checks(settings, payslips),
        "refund": refund_estimate(settings, first),
    }
