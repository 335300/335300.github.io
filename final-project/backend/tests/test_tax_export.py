"""Tax export: tax-relevant categories, totals, commute estimate, German CSV."""

from __future__ import annotations

import pytest

from app.models import AppData, Category, Transaction, YearCategories, YearData
from app.services import csv_format, tax_export


def t(id, kind, date, amount, cat, desc="") -> Transaction:
    return Transaction(id=id, type=kind, date=date, month=int(date[5:7]) - 1, amount=amount, cat=cat, desc=desc)


@pytest.fixture
def data() -> AppData:
    year = YearData(
        categories=YearCategories(
            expense=[Category(name="Tuition", tax_relevant=True), Category(name="Work equipment", tax_relevant=True),
                     Category(name="Groceries")],
            income=[Category(name="Salary"), Category(name="Tax refund", tax_relevant=True)],
        ),
        transactions=[
            t(1, "expense", "2026-08-03", 220, "Tuition", "Semester fee"),
            t(2, "expense", "2026-02-10", 1500.5, "Tuition", "Semester fee"),
            t(3, "expense", "2026-05-01", 899, "Work equipment", "Laptop; 14 inch"),
            t(4, "expense", "2026-05-02", 60, "Groceries"),
            t(5, "income", "2026-07-01", 300, "Tax refund"),
            t(6, "income", "2026-07-01", 2000, "Salary"),
        ],
        next_id=7,
    )
    d = AppData()
    d.years["2026"] = year
    return d


def test_only_tax_relevant_categories_by_date(data):
    view = tax_export.build(data, 2026)
    assert [r["date"] for r in view["rows"]] == ["2026-02-10", "2026-05-01", "2026-07-01", "2026-08-03"]
    assert view["categories"] == ["Tax refund", "Tuition", "Work equipment"]


def test_totals_per_category(data):
    view = tax_export.build(data, 2026)
    tuition = next(x for x in view["totals"] if x["cat"] == "Tuition")
    assert tuition == {"type": "expense", "cat": "Tuition", "amount": 1720.5, "count": 2}
    assert view["expenses_total"] == 2619.5 and view["income_total"] == 300


def test_commute_estimate(data):
    assert tax_export.build(data, 2026)["commute"] is None
    data.years["2026"].commute_days, data.years["2026"].commute_km = 130, 15
    view = tax_export.build(data, 2026)
    # 130 days x 15 km x €0.38 = 741.00
    assert view["commute"]["amount"] == 741.0
    assert view["work_costs_total"] == 2619.5 + 741


def test_commute_needs_both_numbers(data):
    data.years["2026"].commute_days = 130
    assert tax_export.build(data, 2026)["commute"] is None


def test_unknown_year(data):
    with pytest.raises(KeyError):
        tax_export.build(data, 2025)


@pytest.mark.parametrize("value,text", [(1234.5, "1.234,50"), (0.38, "0,38"), (-12, "-12,00"), (None, "")])
def test_german_numbers(value, text):
    assert csv_format.number(value) == text


def test_csv_opens_in_german_excel(data):
    data.years["2026"].commute_days, data.years["2026"].commute_km = 130, 15
    raw = tax_export.to_csv(tax_export.build(data, 2026))
    assert raw.startswith(b"\xef\xbb\xbf")  # byte-order mark for Excel
    text = raw.decode("utf-8-sig")
    lines = text.split("\r\n")
    assert "Date;Type;Category;Description;Amount (EUR)" in lines
    assert "10.02.2026;Expense;Tuition;Semester fee;1.500,50" in lines
    assert '01.05.2026;Expense;Work equipment;"Laptop; 14 inch";899,00' in lines  # a ; inside is quoted
    assert "Expense;Tuition;2;1.720,50" in lines
    assert "130;15,00;0,38;741,00" in lines
    assert "Work-related costs incl. commute (EUR);3.360,50" in lines
