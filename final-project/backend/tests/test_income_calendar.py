"""Income calendar: hours, gross, net from payslips, and when pay arrives.

Made-up settings, easy to check by hand: €20/hour, 20 h/week in lectures
(4 h a day, also the contract hours) and 40 h/week in breaks (8 h a day).
Lecture periods: 1 Oct 2026 – 15 Jan 2027 and 15 Mar – 9 Jul 2027.
Payslips: gross 1,000 → net 900 (ratio 0.9); gross 3,000 → net 2,100 (0.7).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models import IncomeSettings, LecturePeriod, Payslip, Vacation
from app.services import income_calendar as ic


@pytest.fixture
def settings() -> IncomeSettings:
    return IncomeSettings(
        hourly_rate=20,
        hours_lecture_week=20,
        hours_break_week=40,
        lecture_periods=[
            LecturePeriod(start="2026-10-01", end="2027-01-15"),
            LecturePeriod(start="2027-03-15", end="2027-07-09"),
        ],
        contract_pay_lag=1,
        extra_hours_delay=1,
        net_method="payslips",
    )


@pytest.fixture
def payslips() -> list[Payslip]:
    return [
        Payslip(id=1, month="2026-10", gross=1000, net=900),
        Payslip(id=2, month="2026-09", gross=3000, net=2100),
    ]


def test_full_break_month(settings):
    # February 2027: 20 weekdays, all in the break -> 8 h each.
    row = ic.work_month(settings, (2027, 1))
    assert row["kind"] == "break"
    assert (row["lecture_days"], row["break_days"]) == (0, 20)
    assert row["hours"] == 160 and row["hours_contract"] == 80 and row["hours_extra"] == 80
    assert row["gross"] == 3200 and row["gross_contract"] == 1600 and row["gross_extra"] == 800 * 2


def test_full_lecture_month(settings):
    # April 2027: 22 weekdays, all lecture days -> 88 h, no extra hours.
    row = ic.work_month(settings, (2027, 3))
    assert row["kind"] == "lecture"
    assert row["hours"] == 88 and row["hours_extra"] == 0 and row["gross"] == 1760


def test_half_month_is_split_by_day(settings):
    # January 2027: 11 lecture weekdays (to the 15th), then 10 break weekdays.
    row = ic.work_month(settings, (2027, 0))
    assert row["kind"] == "mixed"
    assert (row["lecture_days"], row["break_days"]) == (11, 10)
    assert row["hours"] == 11 * 4 + 10 * 8 == 124
    assert row["gross"] == 2480
    assert row["hours_contract"] == 11 * 4 + 10 * 4 and row["hours_extra"] == 40


def test_weekends_are_never_worked(settings):
    # March 2027: 23 weekdays; 10 before the lectures start on Monday 15th.
    row = ic.work_month(settings, (2027, 2))
    assert row["lecture_days"] + row["break_days"] == 23
    assert row["break_days"] == 10


def test_job_end_stops_the_hours(settings):
    jan = ic.work_month(settings, (2027, 0), job_end=date(2027, 1, 15))
    assert jan["break_days"] == 0 and jan["hours"] == 44 and jan["gross"] == 880
    feb = ic.work_month(settings, (2027, 1), job_end=date(2027, 1, 15))
    assert feb["kind"] == "none" and feb["gross"] == 0


def test_net_ratio_from_payslips(payslips):
    assert ic.net_ratio([], 1000) is None
    assert ic.net_ratio(payslips[:1], 2500) == pytest.approx(0.9)  # one payslip: its ratio
    assert ic.net_ratio(payslips, 500) == pytest.approx(0.9)        # below: nearest payslip
    assert ic.net_ratio(payslips, 4000) == pytest.approx(0.7)       # above: nearest payslip
    assert ic.net_ratio(payslips, 2000) == pytest.approx(0.8)       # halfway: blended
    assert ic.net_ratio(payslips, 2500) == pytest.approx(0.75)


def test_payslips_with_the_same_gross_are_averaged():
    slips = [Payslip(id=1, month="2026-01", gross=1000, net=800), Payslip(id=2, month="2026-02", gross=1000, net=900)]
    assert ic.net_ratio(slips, 1000) == pytest.approx(0.85)


def test_net_for_a_month(settings, payslips):
    # April: gross 1,760 -> ratio 0.9 - 0.2 x 760/2,000 = 0.824 -> 1,450.24.
    row = ic.with_net(ic.work_month(settings, (2027, 3)), payslips, settings)
    assert row["net"] == 1450.24 and row["net_extra"] == 0
    # February: gross 3,200 -> above the highest payslip -> 0.7.
    feb = ic.with_net(ic.work_month(settings, (2027, 1)), payslips, settings)
    assert feb["net_contract"] == 1120 and feb["net_extra"] == 1120 and feb["net"] == 2240


def test_pay_arrives_later(settings, payslips):
    """Contract pay one month after the work; extra hours one month after that."""
    paid = ic.paid_by_month(settings, payslips, (2027, 2), 2)
    # March gets February's contract pay (1,120) + January's extra hours:
    #   Jan gross 2,480 -> ratio 0.9 - 0.2 x 1,480/2,000 = 0.752; 800 x 0.752 = 601.60.
    assert paid[(2027, 2)] == 1120 + 601.6
    # April gets March's contract pay + February's extra hours (1,120):
    #   Mar gross 2,640 -> ratio 0.736; contract gross 1,840 x 0.736 = 1,354.24.
    assert paid[(2027, 3)] == 1354.24 + 1120


def test_pay_in_the_same_month(settings, payslips):
    same = settings.model_copy(update={"contract_pay_lag": 0, "extra_hours_delay": 0})
    paid = ic.paid_by_month(same, payslips, (2027, 2), 1)
    assert paid[(2027, 2)] == 1943.04  # March's own 2,640 x 0.736


def test_no_payslips_means_no_net(settings):
    assert ic.paid_by_month(settings, [], (2027, 2), 3) == {}
    view = ic.calendar_view(settings, [], (2027, 0), 3)
    assert view["total_net"] is None and "no_payslips" in view["warnings"]
    assert view["rows"][0]["net"] is None and view["rows"][0]["gross"] == 2480


def test_new_salary_after_graduation(settings, payslips):
    # Job ends 31 Aug 2027; a new job pays 3,000 net from September, booked in October.
    paid = ic.paid_by_month(settings, payslips, (2027, 9), 1, job_end=date(2027, 8, 31), new_net_salary=3000)
    # October also gets August's extra hours: 22 break days x 4 h x 20 = 1,760 gross extra,
    # month gross 3,520 -> ratio 0.7 -> 1,232. September's contract pay is 0 (job over).
    assert paid[(2027, 9)] == 3000 + 1232


def test_calendar_view(settings, payslips):
    view = ic.calendar_view(settings, payslips, (2027, 0), 3, [("Early end", date(2027, 3, 31))])
    jan, feb, mar = view["rows"]
    assert [r["kind"] for r in view["rows"]] == ["mixed", "break", "mixed"]
    assert jan["contract_paid_in"] == "Feb 27" and jan["extra_paid_in"] == "Mar 27"
    assert mar["job_ends"] == ["Early end"] and jan["job_ends"] == []
    assert view["total_gross"] == 2480 + 3200 + 2640
    assert view["warnings"] == []


def test_calendar_warns_when_lecture_dates_run_out(settings, payslips):
    view = ic.calendar_view(settings, payslips, (2027, 6), 12)
    assert "lecture_periods_end_early" in view["warnings"]
    assert view["lecture_periods_until"] == "2027-07-09"


def test_lecture_period_must_be_ordered():
    with pytest.raises(ValueError):
        LecturePeriod(start="2027-03-15", end="2027-03-01")


def test_net_cannot_exceed_gross():
    with pytest.raises(ValueError):
        Payslip(id=1, month="2026-10", gross=1000, net=1200)


# --- Net pay by German payroll rules (the default) ---------------------------

def test_tax_rules_give_each_month_its_own_net(settings):
    from app.services import german_payroll as gp
    rules = settings.model_copy(update={"net_method": "tax_rules"})
    lecture = ic.with_net(ic.work_month(rules, (2027, 4)), [], rules)   # May 2027: 21 weekdays × 4 h × 20 €
    full = ic.with_net(ic.work_month(rules, (2027, 1)), [], rules)      # February 2027: break, 40 h a week
    assert lecture["gross"] == 1680 and lecture["net"] == gp.month_net(1680, 2027)["net"]
    assert lecture["pension"] == gp.month_net(1680, 2027)["pension"] and lecture["rules_year"] == 2026
    # A full-time month loses a bigger share than a 20-hour month.
    assert full["deducted_pct"] > lecture["deducted_pct"] > 9
    assert full["income_tax"] > lecture["income_tax"]


def test_tax_rules_need_no_payslip(settings):
    rules = settings.model_copy(update={"net_method": "tax_rules"})
    paid = ic.paid_by_month(rules, [], (2027, 2), 2)
    assert paid[(2027, 2)] > 0
    view = ic.calendar_view(rules, [], (2027, 0), 3)
    assert "no_payslips" not in view["warnings"] and view["total_net"] is not None
    assert view["net_method"] == "tax_rules" and view["refund"]["year"] == 2027


def test_payslips_are_checked_against_the_rules(settings):
    from app.services import german_payroll as gp
    rules = settings.model_copy(update={"net_method": "tax_rules"})
    slips = [Payslip(id=1, month="2026-09", gross=3500, net=2700)]
    check = ic.calendar_view(rules, slips, (2027, 0), 1)["payslip_checks"][0]
    assert check["rules_net"] == gp.month_net(3500, 2026)["net"] == 2656.00
    assert check["difference"] == 44.00


def test_too_many_full_time_weeks_are_flagged(settings):
    """Lecture periods only until July 2027: the months after count as breaks (40 h)."""
    view = ic.calendar_view(settings, [], (2027, 6), 12)
    assert view["long_weeks"] > 26 and "werkstudent_26_weeks" in view["warnings"]
    short = ic.calendar_view(settings, [], (2026, 10), 3)
    assert "werkstudent_26_weeks" not in short["warnings"]


def test_church_tax_lowers_net(settings):
    rules = settings.model_copy(update={"net_method": "tax_rules"})
    church = rules.model_copy(update={"church_tax_rate": 8})
    a = ic.with_net(ic.work_month(rules, (2027, 1)), [], rules)
    b = ic.with_net(ic.work_month(church, (2027, 1)), [], church)
    assert b["net"] < a["net"] and b["income_tax"] > a["income_tax"]


# -- hours typed by hand, vacation (Josu's request, 18 Nov 2026) ------------------------------


def test_typed_hours_above_the_contract_hours_are_extra(settings):
    """February 2027 (break, 20 weekdays): the calendar says 160 h — 80 contract
    (4 h a day) + 80 extra. Typed 100 h: contract stays 80, extra 20.
    Gross 100 × 20 = 2,000 (contract 1,600, extra 400)."""
    settings.hours_typed = {"2027-02": 100}
    row = ic.work_month(settings, (2027, 1))
    assert (row["hours"], row["hours_contract"], row["hours_extra"]) == (100, 80, 20)
    assert (row["gross"], row["gross_contract"], row["gross_extra"]) == (2000, 1600, 400)
    assert row["hours_typed"] is True and row["hours_auto"] == 160


def test_typed_hours_below_the_contract_hours_are_all_contract(settings):
    """Typed 50 h in February 2027: all 50 are contract hours, no extra. Gross 1,000."""
    settings.hours_typed = {"2027-02": 50}
    row = ic.work_month(settings, (2027, 1))
    assert (row["hours_contract"], row["hours_extra"], row["gross"]) == (50, 0, 1000)
    assert ic.work_month(settings, (2027, 2))["hours_typed"] is False  # March untouched


@pytest.fixture
def breaks() -> IncomeSettings:
    """No lecture periods: every weekday is a break day, 8 h at €20 = €160 (4 h contract + 4 h extra)."""
    return IncomeSettings(hourly_rate=20, hours_lecture_week=20, hours_break_week=40, net_method="payslips")


def test_vacation_days_are_paid_at_the_three_month_average(breaks):
    """Vacation Wed 3 – Fri 5 March 2027: 3 vacation days, 20 days worked (March has 23
    weekdays) -> 160 h, gross 3,200 from hours.
    The 3 months before: Dec 2026 23 weekdays × 160 = 3,680; Jan 2027 21 × 160 = 3,360;
    Feb 2027 20 × 160 = 3,200. Sum 10,240 ÷ 64 working days = 160 a day.
    Vacation pay 3 × 160 = 480 (part of the contract pay): gross 3,200 + 480 = 3,680,
    contract 80 h × 20 + 480 = 2,080, extra 80 h × 20 = 1,600."""
    breaks.vacations = [Vacation(id=1, start="2027-03-03", end="2027-03-05")]
    row = ic.work_month(breaks, (2027, 2))
    assert (row["vacation_days"], row["break_days"], row["hours"]) == (3, 20, 160)
    assert (row["vacation_rate"], row["vacation_pay"]) == (160, 480)
    assert (row["gross"], row["gross_contract"], row["gross_extra"]) == (3680, 2080, 1600)


def test_a_payslip_gross_counts_instead_of_the_calendar(breaks):
    """Same vacation, but January 2027 has a payslip with gross 3,010 (instead of 3,360):
    3,680 + 3,010 + 3,200 = 9,890 ÷ 64 = 154.53 a day; 9,890 × 3 ÷ 64 = 463.59375 -> 463.59."""
    breaks.vacations = [Vacation(id=1, start="2027-03-03", end="2027-03-05")]
    row = ic.work_month(breaks, (2027, 2), payslips=[Payslip(id=1, month="2027-01", gross=3010, net=2500)])
    assert (row["vacation_rate"], row["vacation_pay"]) == (154.53, 463.59)


def test_weekends_inside_a_vacation_are_not_vacation_days(breaks):
    """Fri 5 – Mon 8 March 2027: Friday and Monday -> 2 vacation days, 2 × 160 = 320."""
    breaks.vacations = [Vacation(id=1, start="2027-03-05", end="2027-03-08")]
    row = ic.work_month(breaks, (2027, 2))
    assert (row["vacation_days"], row["vacation_pay"]) == (2, 320)


def test_a_vacation_month_counts_with_its_vacation_pay_in_a_later_average(breaks):
    """Vacation Mon 1 – Fri 5 Feb 2027 and Wed 3 – Fri 5 Mar 2027; November 2026 has a payslip
    with gross 2,000.
    February: Nov 2,000 + Dec 3,680 + Jan 3,360 = 9,040 ÷ 65 working days (21 + 23 + 21);
    5 days -> 9,040 × 5 ÷ 65 = 695.38. February worked 15 days -> 2,400; gross 3,095.38.
    March: Dec 3,680 + Jan 3,360 + Feb 3,095.38 = 10,135.38; × 3 ÷ 64 = 475.096 -> 475.10."""
    breaks.vacations = [Vacation(id=1, start="2027-02-01", end="2027-02-05"),
                        Vacation(id=2, start="2027-03-03", end="2027-03-05")]
    slips = [Payslip(id=1, month="2026-11", gross=2000, net=1700)]
    feb = ic.work_month(breaks, (2027, 1), payslips=slips)
    assert (feb["vacation_pay"], feb["gross"]) == (695.38, 3095.38)
    assert ic.work_month(breaks, (2027, 2), payslips=slips)["vacation_pay"] == 475.10
