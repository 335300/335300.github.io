"""Import a Sparkasse CSV-CAMT (V8) statement file.

Three steps:

1. :func:`parse_camt_csv` reads the file. Columns are found by their header
   name, so a different column order still works. German numbers ("1.234,56")
   and dates ("03.11.26") are converted; the bank's old text encoding
   (Windows-1252) is handled by :func:`decode`.
2. :func:`preview` decides, for every row, whether it is new or skipped:
   - skipped when the bank still marks it "vorgemerkt" (pending), when it is
     not in euros, or when its month is not tracked in the app;
   - a **duplicate** when a saved transaction has the same bank reference, or
     the same type and amount, a date at most ``DUPLICATE_DAYS`` days away
     and a similar payee;
   - a **possible duplicate** when the amount and date match a transaction
     typed by hand, which has no payee to compare;
   Each saved transaction can match only one imported row, so two genuine
   €3.50 coffees on the same day are not merged. Payee rules set the category
   and may move the date (see :mod:`payee_rules`).
3. :func:`commit` saves the rows the user kept, all or nothing.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..config import DUPLICATE_DAYS, UNCATEGORISED
from ..models import AppData, Category, ImportRow, Transaction, TxType, YearData
from . import payee_rules

#: Header names (normalised) the parser looks for. The first match wins.
_COLUMNS: dict[str, tuple[str, ...]] = {
    "booking_date": ("buchungstag",),
    "booking_text": ("buchungstext",),
    "purpose": ("verwendungszweck",),
    "bank_ref": ("kundenreferenzendtoend", "kundenreferenz"),
    "payee": ("beguenstigterzahlungspflichtiger", "beguenstigter", "zahlungspflichtiger"),
    "amount": ("betrag",),
    "currency": ("waehrung",),
    "info": ("info",),
}
_REQUIRED = ("booking_date", "amount")
#: Words that say nothing about who was paid.
_STOPWORDS = {
    "gmbh", "mbh", "co", "kg", "ag", "se", "ohg", "gbr", "ev", "inc", "ltd", "und", "the",
    "der", "die", "das", "sagt", "danke", "sepa", "www", "com", "de", "eur",
}


class ImportFormatError(ValueError):
    """The file is not a CSV-CAMT statement this importer understands."""


@dataclass(frozen=True)
class BankRow:
    line: int
    booking_date: date
    booking_text: str
    payee: str
    purpose: str
    amount: float  # signed: negative = money out
    bank_ref: str | None
    currency: str
    pending: bool


# ---------------------------------------------------------------------------
# Reading the file
# ---------------------------------------------------------------------------

def decode(raw: bytes) -> str:
    """Sparkasse exports are Windows-1252; accept UTF-8 too."""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def _header_key(name: str) -> str:
    return payee_rules.normalise(name).replace(" ", "")


def parse_amount(text: str) -> float:
    """German format: "-1.234,56" -> -1234.56."""
    cleaned = text.strip().replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        raise ImportFormatError(f"'{text}' is not an amount") from None


def parse_date(text: str) -> date:
    """"03.11.26" or "03.11.2026"."""
    m = re.fullmatch(r"\s*(\d{1,2})\.(\d{1,2})\.(\d{2}|\d{4})\s*", text)
    if not m:
        raise ImportFormatError(f"'{text}' is not a date")
    day, month, year = int(m[1]), int(m[2]), int(m[3])
    if year < 100:
        year += 2000
    try:
        return date(year, month, day)
    except ValueError:
        raise ImportFormatError(f"'{text}' is not a date") from None


def _ref(value: str) -> str | None:
    value = value.strip()
    return None if not value or value.upper() == "NOTPROVIDED" else value


def parse_camt_csv(text: str) -> list[BankRow]:
    reader = csv.reader(io.StringIO(text), delimiter=";", quotechar='"')
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        raise ImportFormatError("The file is empty.")
    header = [_header_key(h) for h in rows[0]]
    index: dict[str, int] = {}
    for field, names in _COLUMNS.items():
        for name in names:
            if name in header:
                index[field] = header.index(name)
                break
    if any(f not in index for f in _REQUIRED):
        raise ImportFormatError(
            "This does not look like a Sparkasse CSV-CAMT file (no 'Buchungstag' or 'Betrag' column)."
        )

    def cell(row: list[str], field: str) -> str:
        i = index.get(field)
        return row[i].strip() if i is not None and i < len(row) else ""

    out: list[BankRow] = []
    for line, row in enumerate(rows[1:], start=2):
        try:
            booking_date = parse_date(cell(row, "booking_date"))
            amount = parse_amount(cell(row, "amount"))
        except ImportFormatError as exc:
            raise ImportFormatError(f"Line {line}: {exc}") from None
        out.append(BankRow(
            line=line,
            booking_date=booking_date,
            booking_text=cell(row, "booking_text"),
            payee=" ".join(cell(row, "payee").split()),
            purpose=" ".join(cell(row, "purpose").split()),
            amount=amount,
            bank_ref=_ref(cell(row, "bank_ref")),
            currency=cell(row, "currency").upper() or "EUR",
            pending="vorgemerkt" in cell(row, "info").lower(),
        ))
    return out


# ---------------------------------------------------------------------------
# Duplicate check
# ---------------------------------------------------------------------------

def _tokens(text: str) -> set[str]:
    return {w for w in payee_rules.normalise(text).split() if len(w) >= 3 and w not in _STOPWORDS}


def similar_payee(a: str, b: str) -> bool:
    """Two payee texts name the same party: a shared word, or one inside the other."""
    na, nb = payee_rules.normalise(a), payee_rules.normalise(b)
    if not na or not nb:
        return False
    if len(min(na, nb, key=len)) >= 3 and (na in nb or nb in na):
        return True
    return bool(_tokens(a) & _tokens(b))


def describe(payee: str, purpose: str) -> str:
    """The description saved with an imported row."""
    if not payee:
        return purpose[:120]
    if purpose and len(purpose) <= 60:
        return f"{payee} · {purpose}"[:120]
    return payee[:120]


def is_tracked(data: AppData, d: date) -> bool:
    year = data.get_year(d.year)
    return year is not None and d.month - 1 > year.start_month


def _existing(data: AppData, around: date) -> list[tuple[int, Transaction]]:
    out = []
    for y in (around.year - 1, around.year, around.year + 1):
        year = data.get_year(y)
        if year is not None:
            out.extend((y, t) for t in year.transactions)
    return out


def preview(data: AppData, rows: list[BankRow]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for r in rows:
        tx_type: TxType = "expense" if r.amount < 0 else "income"
        rule = payee_rules.find_rule(data.payee_rules, f"{r.payee} {r.purpose}", tx_type)
        booked = payee_rules.booked_date(rule, r.booking_date)
        item: dict[str, Any] = {
            "line": r.line,
            "bank_date": r.booking_date.isoformat(),
            "date": booked.isoformat(),
            "type": tx_type,
            "amount": abs(r.amount),
            "payee": r.payee,
            "purpose": r.purpose,
            "booking_text": r.booking_text,
            "desc": describe(r.payee, r.purpose),
            "cat": rule.category if rule else UNCATEGORISED,
            "rule_id": rule.id if rule else None,
            "bank_ref": r.bank_ref,
            "status": "new",
            "reason": None,
            "match": None,
        }
        if r.pending:
            item.update(status="skipped", reason="pending")
        elif r.currency != "EUR":
            item.update(status="skipped", reason="currency")
        elif r.amount == 0:
            item.update(status="skipped", reason="zero")
        elif not is_tracked(data, booked):
            item.update(status="skipped", reason="not_tracked")
        items.append(item)

    used: set[tuple[int, int]] = set()

    def mark(item: dict[str, Any], y: int, t: Transaction, status: str, reason: str) -> None:
        used.add((y, t.id))
        item.update(status=status, reason=reason, match={
            "date": t.date, "amount": t.amount, "desc": t.desc, "cat": t.cat, "payee": t.payee,
        })

    # Pass 1: the bank reference — the surest sign.
    for item in items:
        if item["status"] != "new" or not item["bank_ref"]:
            continue
        for y, t in _existing(data, date.fromisoformat(item["date"])):
            if (y, t.id) not in used and t.bank_ref == item["bank_ref"]:
                mark(item, y, t, "duplicate", "bank_ref")
                break

    # Pass 2: same type and amount, close date, similar payee.
    for item in items:
        if item["status"] != "new":
            continue
        dates = {date.fromisoformat(item["date"]), date.fromisoformat(item["bank_date"])}
        best: tuple[int, int, int, Transaction] | None = None  # (rank, days, year, tx)
        for y, t in _existing(data, date.fromisoformat(item["date"])):
            if (y, t.id) in used or t.type != item["type"] or round(t.amount, 2) != item["amount"]:
                continue
            days = min(abs((date.fromisoformat(t.date) - d).days) for d in dates)
            if days > DUPLICATE_DAYS:
                continue
            if t.payee:
                if not similar_payee(item["payee"], t.payee):
                    continue
                rank = 0
            else:
                rank = 0 if similar_payee(item["payee"], t.desc) else 1
            if best is None or (rank, days) < best[:2]:
                best = (rank, days, y, t)
        if best is not None:
            rank, _, y, t = best
            mark(item, y, t, "duplicate" if rank == 0 else "possible_duplicate",
                 "same_amount_date_payee" if rank == 0 else "same_amount_date")

    new = sum(1 for i in items if i["status"] == "new")
    reasons: dict[str, int] = {}
    for i in items:
        if i["status"] != "new":
            reasons[i["reason"]] = reasons.get(i["reason"], 0) + 1
    return {
        "rows": items,
        "new": new,
        "skipped": len(items) - new,
        "skipped_by_reason": reasons,
        "total": len(items),
    }


# ---------------------------------------------------------------------------
# Saving
# ---------------------------------------------------------------------------

def _ensure_category(year: YearData, kind: TxType, name: str) -> None:
    if year.find_category(kind, name) is None:
        getattr(year.categories, kind).append(Category(name=name))
        getattr(year.budgets, kind).setdefault(name, [0.0] * 12)


def _already_saved(data: AppData, row: ImportRow) -> bool:
    """Protects against saving the same preview twice."""
    d = date.fromisoformat(row.date)
    for _, t in _existing(data, d):
        if row.bank_ref and t.bank_ref == row.bank_ref:
            return True
        if (row.payee and t.payee == row.payee and t.date == row.date
                and t.type == row.type and round(t.amount, 2) == round(row.amount, 2)):
            return True
    return False


def commit(data: AppData, rows: list[ImportRow]) -> dict[str, Any]:
    """Add the chosen rows. Raises ``ValueError`` (nothing saved) when a row's
    month is not tracked."""
    for i, row in enumerate(rows):
        if not is_tracked(data, date.fromisoformat(row.date)):
            raise ValueError(f"Row {i + 1}: {row.date} is in a month the app does not track.")

    # Two identical rows in one save are both kept (two real coffees); only
    # rows already saved before are left out.
    keep = [row for row in rows if not _already_saved(data, row)]
    created: list[Transaction] = []
    for row in keep:
        d = date.fromisoformat(row.date)
        year = data.get_year(d.year)
        assert year is not None
        installments = 1 if row.type == "expense" and data.investment_for_category(row.cat) else None
        t = Transaction(
            id=year.take_id(), type=row.type, date=row.date, month=d.month - 1, amount=row.amount,
            desc=row.desc, cat=row.cat, installments=installments, payee=row.payee, bank_ref=row.bank_ref,
        )
        _ensure_category(year, row.type, row.cat)
        year.transactions.append(t)
        created.append(t)
    return {"created": len(created), "skipped": len(rows) - len(keep)}
