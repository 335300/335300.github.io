"""Payee rules: matching, the late-payment date, and suggestions."""

from __future__ import annotations

from datetime import date

import pytest

from app.models import AppData, PayeeRule, Transaction, YearData
from app.services import payee_rules as pr


def rule(id=1, contains="rewe", category="Groceries", **kw) -> PayeeRule:
    return PayeeRule(id=id, contains=contains, category=category, **kw)


def test_contains_ignores_case_and_umlaut_spelling():
    assert pr.matches(rule(contains="REWE"), "Rewe Markt GmbH//Heidelberg", "expense")
    assert pr.matches(rule(contains="Bäckerei"), "BAECKEREI SUESS", "expense")
    assert pr.matches(rule(contains="acme gmbh payroll"), "ACME GmbH, Payroll 10/2026", "income")
    assert not pr.matches(rule(contains="rewe"), "Penny Markt", "expense")


def test_rule_for_one_type_only():
    r = rule(tx_type="income")
    assert pr.matches(r, "REWE refund", "income")
    assert not pr.matches(r, "REWE", "expense")


def test_first_matching_rule_wins():
    rules = [rule(1, "markt", "Shopping"), rule(2, "rewe", "Groceries")]
    assert pr.find_rule(rules, "REWE Markt", "expense").id == 1
    assert pr.find_rule(rules, "Lidl", "expense") is None


@pytest.mark.parametrize("bank,booked", [
    (date(2026, 10, 29), date(2026, 11, 1)),
    (date(2026, 12, 30), date(2027, 1, 1)),   # into the next year
    (date(2026, 10, 25), date(2026, 11, 1)),  # the 25th already counts
    (date(2026, 10, 24), date(2026, 10, 24)),
])
def test_late_payment_moves_to_the_first_of_next_month(bank, booked):
    assert pr.booked_date(rule(next_month_if_late=True), bank) == booked


def test_without_the_option_the_date_stays():
    assert pr.booked_date(rule(), date(2026, 10, 29)) == date(2026, 10, 29)
    assert pr.booked_date(None, date(2026, 10, 29)) == date(2026, 10, 29)


# -- suggestions ---------------------------------------------------------------

def data_with(*txs: tuple[str, str, str]) -> AppData:
    """(payee, category, type) per transaction."""
    year = YearData()
    for i, (payee, cat, kind) in enumerate(txs, start=1):
        year.transactions.append(Transaction(
            id=i, type=kind, date="2026-11-05", month=10, amount=10, cat=cat, payee=payee,
        ))
    d = AppData()
    d.years["2026"] = year
    return d


def test_suggest_after_the_same_category_twice():
    d = data_with(("REWE Markt GmbH//Heidelberg", "Groceries", "expense"), ("REWE Markt GmbH", "Groceries", "expense"))
    (s,) = pr.suggestions(d)
    assert s["contains"] == "rewe markt" and s["category"] == "Groceries" and s["count"] == 2
    assert s["tx_type"] == "expense"


def test_once_is_not_enough():
    assert pr.suggestions(data_with(("REWE Markt", "Groceries", "expense"))) == []


def test_uncategorised_rows_do_not_count():
    d = data_with(("REWE Markt", "Uncategorised", "expense"), ("REWE Markt", "Uncategorised", "expense"))
    assert pr.suggestions(d) == []


def test_no_suggestion_when_a_rule_already_matches():
    d = data_with(("REWE Markt", "Groceries", "expense"), ("REWE Markt", "Groceries", "expense"))
    d.payee_rules = [rule(contains="rewe")]
    assert pr.suggestions(d) == []


def test_dismissed_suggestions_stay_away():
    d = data_with(("REWE Markt", "Groceries", "expense"), ("REWE Markt", "Groceries", "expense"))
    d.dismissed_rule_suggestions = ["rewe markt"]
    assert pr.suggestions(d) == []


def test_most_used_category_is_suggested():
    d = data_with(
        ("Drogerie Beispiel", "Groceries", "expense"),
        ("Drogerie Beispiel", "Groceries", "expense"),
        ("Drogerie Beispiel", "Groceries", "expense"),
        ("Drogerie Beispiel", "Shopping", "expense"),
        ("Drogerie Beispiel", "Shopping", "expense"),
    )
    (s,) = pr.suggestions(d)
    assert s["category"] == "Groceries" and s["count"] == 3


def test_hand_typed_transactions_without_payee_are_ignored():
    d = data_with(("", "Groceries", "expense"), ("", "Groceries", "expense"))
    assert pr.suggestions(d) == []
