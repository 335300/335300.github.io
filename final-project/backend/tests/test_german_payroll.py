"""German working-student payroll. Every expected figure is worked out by hand
from § 32a EStG and the pension rules (see the comments)."""

from __future__ import annotations

import pytest

from app.services import german_payroll as gp


def test_full_time_month_2026():
    """3 500 € in 2026: pension 9.3 % = 325.50. Yearly: 42 000 − 1 230 − 36 − 3 906 = 36 828
    -> zone 3, z = 1.9029: (173.10·z + 2 397)·z + 1 034.87 = 6 222 € -> 518.50 € a month."""
    m = gp.month_net(3500, 2026)
    assert m["pension"] == 325.50 and m["income_tax"] == 518.50
    assert m["solidarity"] == 0 and m["church_tax"] == 0
    assert m["net"] == 2656.00 and m["deducted_pct"] == 24.11 and m["rules_year"] == 2026


def test_lecture_month_in_the_uebergangsbereich():
    """1 800 € in 2026: reduced pension base 2 000/1 397 · (1 800 − 603) = 1 713.67 -> 159.37 €.
    Yearly: 21 600 − 1 230 − 36 − 1 913 = 18 421 -> z = 0.0622 -> 1 184 € -> 98.66 € a month."""
    m = gp.month_net(1800, 2026)
    assert m["pension"] == 159.37 and m["income_tax"] == 98.66
    assert m["net"] == 1541.97 and m["deducted_pct"] == 14.33


def test_small_months():
    # 1 000 €: taxable 10 099 € is below the 12 348 € allowance -> no tax, only reduced pension.
    m = gp.month_net(1000, 2026)
    assert m["income_tax"] == 0 and m["pension"] == 52.86 and m["net"] == 947.14
    # A mini-job (up to 603 €): 3.6 % pension.
    assert gp.month_net(500, 2026)["pension"] == 18.00
    assert gp.month_net(0, 2026)["net"] == 0


def test_church_tax_and_solidarity():
    assert gp.month_net(3500, 2026, church_tax_rate=8)["church_tax"] == 41.48  # 8 % of 518.50
    # 10 000 € a month: pension stops at the 8 450 € cap; the yearly tax passes the free limit.
    rich = gp.month_net(10_000, 2026)
    assert rich["pension"] == round(8450 * 0.093, 2) and rich["solidarity"] > 0


def test_tariff_zones_join_up():
    """Each zone starts where the one before ends (checks the copied coefficients)."""
    for year in (2025, 2026):
        r, _ = gp.rules_for(year)
        assert gp.income_tax(r["gfb"], r) == 0
        for edge in ("z2", "z3", "z4"):
            assert abs(gp.income_tax(r[edge], r) - gp.income_tax(r[edge] + 1, r)) <= 1


def test_year_without_rules_uses_the_nearest():
    assert gp.rules_for(2027)[1] == 2026 and gp.rules_for(2024)[1] == 2025
    assert gp.month_net(3500, 2027)["rules_year"] == 2026


def test_yearly_refund():
    """8 lecture months of 1 800 € and 4 full-time months of 3 500 €.
    Withheld 8·98.66 + 4·518.50 = 2 863.28. Owed: 28 400 − 1 230 − 36 − 2 577 = 24 557
    -> z = 0.6758 -> 2 733 €. Back from the tax return: 130.28 €."""
    r = gp.yearly_refund([1800] * 8 + [3500] * 4, 2026)
    assert r["withheld"] == 2863.28 and r["owed"] == 2733 and r["refund"] == 130.28
    # A steady year is taxed right month by month: nothing comes back.
    assert gp.yearly_refund([3500] * 12, 2026)["refund"] == pytest.approx(0, abs=1)
