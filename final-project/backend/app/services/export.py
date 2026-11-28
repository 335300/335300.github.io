"""A full export, so the data is never locked in.

- every transaction of a profile as a CSV in German Excel format;
- the profile's whole data file as plain JSON.

Neither file is encrypted.
"""

from __future__ import annotations

import json

from ..models import AppData
from . import csv_format


def transactions_csv(data: AppData) -> bytes:
    rows = [["Date", "Type", "Category", "Description", "Payee", "Amount (EUR)", "One-off", "Foreign amount", "Currency"]]
    every = sorted(
        (t for year in data.years.values() for t in year.transactions),
        key=lambda t: (t.date, t.id),
    )
    for t in every:
        rows.append([
            csv_format.day(t.date),
            "Expense" if t.type == "expense" else "Income",
            t.cat,
            t.desc,
            t.payee,
            csv_format.number(t.amount),
            "yes" if t.one_off else "",
            csv_format.number(t.foreign_amount),
            t.foreign_currency or "",
        ])
    return csv_format.write(rows)


def full_json(data: AppData) -> bytes:
    return json.dumps(data.model_dump(mode="json"), indent=2, ensure_ascii=False).encode("utf-8")
