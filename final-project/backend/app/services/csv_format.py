"""CSV files the way German Excel and Numbers open them cleanly.

Semicolons between columns, a decimal comma ("1.234,56"), dates as
"31.12.2026", and a byte-order mark so umlauts show correctly.
"""

from __future__ import annotations

import csv
import io
from datetime import date


def number(value: float | None) -> str:
    """1234.5 -> "1.234,50"; None -> ""."""
    if value is None:
        return ""
    text = f"{abs(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-{text}" if value < 0 else text


def day(iso: str) -> str:
    """"2026-10-05" -> "05.10.2026"."""
    return date.fromisoformat(iso).strftime("%d.%m.%Y")


def write(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")
