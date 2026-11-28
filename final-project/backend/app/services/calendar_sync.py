"""Money dates on the iPhone: what the app's own calendars should hold.

The app keeps two calendars of its own in iCloud (``OWN_CALENDARS``):
"Centwise" for Personal and "Centwise Joint" for Joint. Each money date of the
next ``CALENDAR_SYNC_DAYS`` days becomes one all-day entry there:

- **Titles only, never amounts** (iCloud Calendar is not end-to-end
  encrypted): "Rent due", "Salary arrives", "Transfer to Joint", "Money from
  Isa", "Goal deadline: Laptop"; a done one gets a tick ("Rent — paid ✓").
- Every entry carries a hidden **key** ``centwise:<profile>/<money date key>``
  (in the event's URL field), so the app knows its own entries.

:func:`plan` compares what should be there with what is there and returns the
changes. It only ever touches entries that carry a key *and* lie inside the
window: anything added by hand, and every past entry, is left alone. A key
found twice keeps its first entry (lowest id). Running :func:`plan` again
after the changes are made gives no changes.

Pure: no clock, no disk, no calendar access — the route applies the changes.
"""

from __future__ import annotations

from datetime import date
from typing import Any

#: Start of every key the app writes.
KEY_PREFIX = "centwise:"


def entry_title(item: dict[str, Any]) -> str:
    """The entry's title for one money date: words only, no amount."""
    name, done, kind = item["name"], item["done"], item["kind"]
    if kind == "bill":
        return f"{name} — paid ✓" if done else f"{name} due"
    if kind == "salary":
        return f"{name} received ✓" if done else f"{name} arrives"
    if kind == "transfer":
        return f"{name} — sent ✓" if done else name
    if kind == "contribution":
        text = f"Money {name[:1].lower()}{name[1:]}"  # "From Isa" -> "Money from Isa"
        return f"{text} ✓" if done else text
    return f"Goal reached: {name} ✓" if done else f"Goal deadline: {name}"


def desired(money: dict[str, Any], profile: str) -> list[dict[str, Any]]:
    """The entries one profile's calendar should hold: ``[{key, date, title}]``."""
    return [
        {"key": f"{KEY_PREFIX}{profile}/{item['key']}", "date": item["date"], "title": entry_title(item)}
        for item in money["items"]
    ]


def plan(want: list[dict[str, Any]], existing: list[dict[str, Any]], start: date, end: date) -> dict[str, Any]:
    """The changes that make the calendar match ``want`` inside ``start``-``end``.

    ``existing``: the calendar's entries, ``[{event_id, key, date, title}]``
    (``key`` None for entries without one). Returns ``{"add": [entry],
    "update": [{event_id, key, date, title}], "delete": [event_id]}``.
    """
    wanted = {w["key"]: w for w in want}
    first, last = start.isoformat(), end.isoformat()
    managed = sorted(
        (e for e in existing if (e.get("key") or "").startswith(KEY_PREFIX) and first <= e["date"] <= last),
        key=lambda e: e["event_id"],
    )
    kept: dict[str, dict[str, Any]] = {}
    update: list[dict[str, Any]] = []
    delete: list[str] = []
    for entry in managed:
        key = entry["key"]
        if key in kept or key not in wanted:
            delete.append(entry["event_id"])
            continue
        kept[key] = entry
        target = wanted[key]
        if (entry["date"], entry["title"]) != (target["date"], target["title"]):
            update.append({"event_id": entry["event_id"], **target})
    add = sorted((w for k, w in wanted.items() if k not in kept), key=lambda w: (w["date"], w["key"]))
    return {"add": add, "update": update, "delete": delete}
