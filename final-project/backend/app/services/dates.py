"""Small date helpers shared by sinking funds and recurring bills."""

from __future__ import annotations

import calendar
from datetime import date


def add_months(d: date, months: int) -> date:
    """Same day ``months`` later; a day the month lacks becomes its last day
    (31 Jan + 1 month = 28 Feb)."""
    index = d.year * 12 + d.month - 1 + months
    year, month0 = divmod(index, 12)
    last = calendar.monthrange(year, month0 + 1)[1]
    return date(year, month0 + 1, min(d.day, last))
