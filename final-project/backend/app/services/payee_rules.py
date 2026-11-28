"""Payee rules: "if the payee or purpose contains X, use category Y".

Plain text matching, no guessing: the first rule (in list order) whose text is
found, ignoring upper/lower case and German umlaut spelling, wins.

Suggestions: when the user has given the same payee the same category at least
``RULE_SUGGESTION_MIN`` times, and no rule matches that payee yet, the app
offers a rule for it. Only imported transactions have a payee, and rows left
in the "Uncategorised" fallback never count.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta
from typing import Any

from ..config import LATE_PAYMENT_DAY, RULE_SUGGESTION_MIN, UNCATEGORISED
from ..models import AppData, PayeeRule, TxType

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def normalise(text: str) -> str:
    """Lower case, umlauts spelled out, punctuation turned into single spaces."""
    text = text.casefold().translate(_UMLAUTS)
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text).split())


def matches(rule: PayeeRule, text: str, tx_type: TxType) -> bool:
    if rule.tx_type is not None and rule.tx_type != tx_type:
        return False
    needle = normalise(rule.contains)
    return bool(needle) and needle in normalise(text)


def find_rule(rules: list[PayeeRule], text: str, tx_type: TxType) -> PayeeRule | None:
    for rule in rules:
        if matches(rule, text, tx_type):
            return rule
    return None


def booked_date(rule: PayeeRule | None, bank_date: date) -> date:
    """The date a payment is recorded on.

    A rule with ``next_month_if_late`` moves a payment made on the 25th or
    later to the 1st of the next month — that is how salary and month-end rent
    are recorded (they pay for the coming month).
    """
    if rule is not None and rule.next_month_if_late and bank_date.day >= LATE_PAYMENT_DAY:
        return (bank_date.replace(day=28) + timedelta(days=4)).replace(day=1)
    return bank_date


def suggested_text(payee: str) -> str:
    """The rule text offered for a payee: its first two words, normalised.

    "REWE Markt GmbH//Heidelberg" -> "rewe markt". The user can edit it.
    """
    return " ".join(normalise(payee).split()[:2])


def suggestions(data: AppData) -> list[dict[str, Any]]:
    """Rules worth adding, most-used payee first."""
    counts: Counter[tuple[str, TxType, str]] = Counter()
    examples: dict[tuple[str, TxType, str], str] = {}
    for year in data.years.values():
        for t in year.transactions:
            if not t.payee or t.cat == UNCATEGORISED:
                continue
            text = suggested_text(t.payee)
            if not text:
                continue
            key = (text, t.type, t.cat)
            counts[key] += 1
            examples.setdefault(key, t.payee)

    dismissed = {normalise(d) for d in data.dismissed_rule_suggestions}
    best: dict[tuple[str, TxType], tuple[int, str]] = {}
    for (text, tx_type, cat), n in counts.items():
        if n < RULE_SUGGESTION_MIN or text in dismissed:
            continue
        if find_rule(data.payee_rules, examples[(text, tx_type, cat)], tx_type) is not None:
            continue
        current = best.get((text, tx_type))
        if current is None or n > current[0]:
            best[(text, tx_type)] = (n, cat)

    out = [
        {
            "contains": text,
            "category": cat,
            "tx_type": tx_type,
            "count": n,
            "example_payee": examples[(text, tx_type, cat)],
        }
        for (text, tx_type), (n, cat) in best.items()
    ]
    return sorted(out, key=lambda s: (-s["count"], s["contains"]))
