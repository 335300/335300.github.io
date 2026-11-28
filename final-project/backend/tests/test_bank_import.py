"""Sparkasse CSV-CAMT (V8) import: reading, duplicate check, saving.

Uses the made-up file tests/fixtures/2026-11-13-sparkasse-camt-v8-synthetic.csv
(fake names and account numbers), stored in Windows-1252 like a real export:

line 2  03.11.26  Muster Markt GmbH          -23.45  no bank reference
line 3  04.11.26  Gesundheitskasse Beispiel -149.00  ref E2E-HK-2026-11
line 4  05.11.26  Beispiel Software AG     +1234.56  ref PAYROLL-202611
line 5  10.11.26  Bäckerei Süß               -3.50
line 6  10.11.26  Bäckerei Süß               -3.50  (a second, real coffee)
line 7  12.11.26  Max Mustermann            +50.00
line 8  13.11.26  Muster Markt GmbH         -12.00  "vorgemerkt" (pending)
line 9  27.11.26  Vermieter Beispiel       -500.00  ref MIETE-1126
line 10 30.12.25  Altes Jahr GmbH           -10.00  (2025 is not tracked)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from app.models import AppData, Category, ImportRow, InvestmentPlan, PayeeRule, Transaction, YearCategories, YearData
from app.services import bank_import as bi

FIXTURE = Path(__file__).parent / "fixtures" / "2026-11-13-sparkasse-camt-v8-synthetic.csv"


@pytest.fixture
def rows() -> list[bi.BankRow]:
    return bi.parse_camt_csv(bi.decode(FIXTURE.read_bytes()))


@pytest.fixture
def data() -> AppData:
    d = AppData()
    d.years["2026"] = YearData(
        categories=YearCategories(
            expense=[Category(name="Groceries"), Category(name="Insurance", kind="fixed"), Category(name="Rent", kind="fixed")],
            income=[Category(name="Salary")],
        ),
        next_id=1,
    )
    return d


def add(data: AppData, **fields) -> Transaction:
    year = data.years["2026"]
    d = date.fromisoformat(fields["date"])
    t = Transaction(id=year.take_id(), month=d.month - 1, **fields)
    year.transactions.append(t)
    return t


def by_line(result, line):
    return next(r for r in result["rows"] if r["line"] == line)


# -- reading -------------------------------------------------------------------

def test_reads_every_row_with_german_formats(rows):
    assert len(rows) == 9
    salary = next(r for r in rows if r.line == 4)
    assert salary.amount == 1234.56 and salary.booking_date == date(2026, 11, 5)
    assert salary.payee == "Beispiel Software AG" and salary.bank_ref == "PAYROLL-202611"
    assert rows[0].amount == -23.45 and rows[0].bank_ref is None  # NOTPROVIDED means none


def test_old_bank_encoding_keeps_umlauts(rows):
    assert next(r for r in rows if r.line == 5).payee == "Bäckerei Süß"


def test_pending_rows_are_recognised(rows):
    assert [r.line for r in rows if r.pending] == [8]


def test_columns_are_found_by_name_not_position():
    text = '"Betrag";"Buchungstag";"Beguenstigter/Zahlungspflichtiger"\n"-5,00";"01.02.2026";"Kiosk"\n'
    (row,) = bi.parse_camt_csv(text)
    assert row.amount == -5 and row.booking_date == date(2026, 2, 1) and row.payee == "Kiosk"


def test_not_a_camt_file_is_refused():
    with pytest.raises(bi.ImportFormatError, match="CSV-CAMT"):
        bi.parse_camt_csv('"Date","Amount"\n"2026-01-01","5"\n')
    with pytest.raises(bi.ImportFormatError, match="Line 2"):
        bi.parse_camt_csv('"Buchungstag";"Betrag"\n"tomorrow";"5"\n')


@pytest.mark.parametrize("text,value", [("-1.234,56", -1234.56), ("50,00", 50.0), ("0,5", 0.5)])
def test_amounts(text, value):
    assert bi.parse_amount(text) == value


# -- preview -------------------------------------------------------------------

def test_preview_on_an_empty_year(data, rows):
    result = bi.preview(data, rows)
    # 9 rows: pending (line 8) and 2025 (line 10) skipped, 7 new.
    assert (result["new"], result["skipped"]) == (7, 2)
    assert result["skipped_by_reason"] == {"pending": 1, "not_tracked": 1}
    coffee = by_line(result, 5)
    assert coffee["type"] == "expense" and coffee["amount"] == 3.5 and coffee["cat"] == "Uncategorised"
    assert by_line(result, 4)["type"] == "income"


def test_duplicate_by_bank_reference(data, rows):
    add(data, type="expense", date="2026-11-04", amount=149, cat="Insurance", desc="", bank_ref="E2E-HK-2026-11")
    row = by_line(bi.preview(data, rows), 3)
    assert row["status"] == "duplicate" and row["reason"] == "bank_ref"


def test_duplicate_by_amount_date_and_payee(data, rows):
    # Saved two days later, with a payee spelled differently.
    add(data, type="expense", date="2026-11-05", amount=23.45, cat="Groceries", desc="", payee="MUSTER MARKT")
    row = by_line(bi.preview(data, rows), 2)
    assert row["status"] == "duplicate" and row["reason"] == "same_amount_date_payee"
    assert row["match"]["date"] == "2026-11-05"


def test_four_days_apart_is_not_a_duplicate(data, rows):
    add(data, type="expense", date="2026-11-07", amount=23.45, cat="Groceries", desc="", payee="Muster Markt GmbH")
    assert by_line(bi.preview(data, rows), 2)["status"] == "new"


def test_other_payee_is_not_a_duplicate(data, rows):
    add(data, type="expense", date="2026-11-03", amount=23.45, cat="Groceries", desc="", payee="Anderer Laden")
    assert by_line(bi.preview(data, rows), 2)["status"] == "new"


def test_hand_typed_transaction_is_a_possible_duplicate(data, rows):
    # Typed by hand: no payee, description in other words.
    add(data, type="expense", date="2026-11-03", amount=23.45, cat="Groceries", desc="Weekly shop")
    row = by_line(bi.preview(data, rows), 2)
    assert row["status"] == "possible_duplicate" and row["reason"] == "same_amount_date"


def test_hand_typed_with_the_payee_in_the_description_is_a_duplicate(data, rows):
    add(data, type="income", date="2026-11-04", amount=1234.56, cat="Salary", desc="Beispiel Software salary")
    assert by_line(bi.preview(data, rows), 4)["status"] == "duplicate"


def test_one_saved_transaction_matches_only_one_row(data, rows):
    """Two real coffees in the file, one already saved: one is new."""
    add(data, type="expense", date="2026-11-10", amount=3.5, cat="Eating out", desc="", payee="Bäckerei Süß")
    result = bi.preview(data, rows)
    assert [by_line(result, 5)["status"], by_line(result, 6)["status"]] == ["duplicate", "new"]


def test_payee_rule_sets_the_category(data, rows):
    data.payee_rules = [PayeeRule(id=1, contains="muster markt", category="Groceries")]
    result = bi.preview(data, rows)
    assert by_line(result, 2)["cat"] == "Groceries" and by_line(result, 2)["rule_id"] == 1


def test_rule_type_limits_the_match(data, rows):
    data.payee_rules = [PayeeRule(id=1, contains="beispiel", category="Rent", tx_type="expense")]
    result = bi.preview(data, rows)
    assert by_line(result, 4)["cat"] == "Uncategorised"  # the salary is income
    assert by_line(result, 9)["cat"] == "Rent"


def test_late_payment_rule_moves_the_date(data, rows):
    data.payee_rules = [PayeeRule(id=1, contains="Vermieter", category="Rent", next_month_if_late=True)]
    rent = by_line(bi.preview(data, rows), 9)
    assert rent["bank_date"] == "2026-11-27" and rent["date"] == "2026-12-01"


def test_moved_date_still_finds_the_typed_row(data, rows):
    """Rent paid on 27 Nov, typed by hand on 1 Dec: four days from the bank
    date, but the same booked date."""
    data.payee_rules = [PayeeRule(id=1, contains="Vermieter", category="Rent", next_month_if_late=True)]
    add(data, type="expense", date="2026-12-01", amount=500, cat="Rent", desc="December rent (paid 27.11.)")
    assert by_line(bi.preview(data, rows), 9)["status"] == "possible_duplicate"


def test_month_before_tracking_is_skipped(data, rows):
    data.years["2026"].start_month = 10  # tracking starts in December
    result = bi.preview(data, rows)
    assert by_line(result, 2)["reason"] == "not_tracked"


# -- saving --------------------------------------------------------------------

def _row(**fields) -> ImportRow:
    base = dict(date="2026-11-10", type="expense", amount=3.5, cat="Eating out", desc="Bäckerei Süß · Kaffee", payee="Bäckerei Süß")
    return ImportRow(**{**base, **fields})


def test_commit_saves_rows_and_new_categories(data):
    result = bi.commit(data, [_row(), _row(), _row(date="2026-11-04", amount=149, cat="Insurance", payee="Kasse", bank_ref="R1")])
    assert result == {"created": 3, "skipped": 0}
    year = data.years["2026"]
    assert len(year.transactions) == 3
    assert year.find_category("expense", "Eating out") is not None
    saved = year.transactions[2]
    assert saved.month == 10 and saved.bank_ref == "R1" and saved.payee == "Kasse"


def test_commit_twice_saves_nothing_new(data):
    rows = [_row(), _row(date="2026-11-04", amount=149, cat="Insurance", payee="Kasse", bank_ref="R1")]
    bi.commit(data, rows)
    assert bi.commit(data, rows) == {"created": 0, "skipped": 2}


def test_commit_is_all_or_nothing(data):
    with pytest.raises(ValueError, match="Row 2"):
        bi.commit(data, [_row(), _row(date="2025-12-30")])
    assert data.years["2026"].transactions == []


def test_commit_counts_an_instalment_for_investment_plans(data):
    data.years["2026"].categories.expense.append(Category(name="Land", kind="investment"))
    data.investments = [InvestmentPlan(id=1, name="Plot", category="Land", installment_amount=100,
                                       total_installments=10, created_date="2026-01-01")]
    bi.commit(data, [_row(cat="Land", amount=320)])
    assert data.years["2026"].transactions[0].installments == 1


def test_similar_payee():
    assert bi.similar_payee("REWE Markt GmbH//Heidelberg", "rewe")
    assert bi.similar_payee("Bäckerei Süß", "BAECKEREI SUESS")
    assert not bi.similar_payee("Muster GmbH", "Other GmbH")  # "gmbh" alone says nothing
    assert not bi.similar_payee("", "anything")
