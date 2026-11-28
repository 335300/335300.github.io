"""The Calendar tab's days: Apple Calendar events and money dates, day by day.

:func:`build` lays out a window of days (``start``-``end``, both included):

- **events** (from the calendar source, already filtered to the calendars the
  user shows) go on every day they touch inside the window: an all-day trip
  of the 20th-21st on both days; a timed event that ends at midnight only on
  the day it starts. All-day events come first, then by start time, then title.
- **money** items (from :func:`money_dates.money_dates`) go on their date, in
  the order they come.
- **lecture**: the day lies in one of the income calendar's lecture periods
  (Personal only; first and last day included, weekends too).

Totals come from the money dates unchanged. Pure: no clock, no disk.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from ..models import LecturePeriod


def _days_of(event: dict[str, Any]) -> tuple[date, date]:
    """First and last day an event touches."""
    if event["all_day"]:
        return date.fromisoformat(event["start"][:10]), date.fromisoformat(event["end"][:10])
    begins = datetime.fromisoformat(event["start"])
    ends = datetime.fromisoformat(event["end"])
    last = ends.date()
    if ends > begins and ends.time() == datetime.min.time():
        last -= timedelta(days=1)  # ends at midnight: it does not touch the next day
    return begins.date(), max(begins.date(), last)


def _event_order(event: dict[str, Any]) -> tuple:
    return (0 if event["all_day"] else 1, event["start"], event["title"].lower())


def build(start: date, end: date, today: date, money: dict[str, Any], events: list[dict[str, Any]],
          lecture_periods: list[LecturePeriod] | None = None) -> dict[str, Any]:
    """The days from ``start`` to ``end`` with their events, money dates and lecture flag."""
    by_day_events: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for event in sorted(events, key=_event_order):
        first, last = _days_of(event)
        day = max(first, start)
        while day <= min(last, end):
            by_day_events[day].append(event)
            day += timedelta(days=1)

    by_day_money: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in money["items"]:
        by_day_money[item["date"]].append(item)

    periods = [(p.start, p.end) for p in lecture_periods or []]
    days = []
    day = start
    while day <= end:
        iso = day.isoformat()
        days.append({
            "date": iso,
            "weekday": day.weekday(),
            "is_today": day == today,
            "lecture": any(first <= iso <= last for first, last in periods),
            "events": by_day_events.get(day, []),
            "money": by_day_money.get(iso, []),
        })
        day += timedelta(days=1)

    return {
        "profile": money["profile"],
        "start": start.isoformat(),
        "end": end.isoformat(),
        "today": today.isoformat(),
        "pay_day": money["pay_day"],
        "days": days,
        "due_total": money["due_total"],
        "expected_total": money["expected_total"],
    }
