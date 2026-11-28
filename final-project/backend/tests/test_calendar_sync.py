"""iPhone sync: titles without amounts, and changes that touch only the app's own entries.

Window used: 18 Nov 2026 (today) to 19 May 2027.
"""

from __future__ import annotations

from datetime import date

from app.services import calendar_sync as cs

START, END = date(2026, 11, 18), date(2027, 5, 19)


def item(kind: str, name: str, day: str, done: bool = False, key: str | None = None, amount: float = 123.45) -> dict:
    return {"kind": kind, "name": name, "date": day, "done": done, "amount": amount, "key": key or f"{kind}/{day}"}


def test_titles_have_words_and_never_amounts():
    """Each kind, open and done. 123.45 never shows up in a title."""
    cases = [
        (item("bill", "Rent", "2026-12-01"), "Rent due"),
        (item("bill", "Rent", "2026-12-01", done=True), "Rent — paid ✓"),
        (item("salary", "Salary", "2026-11-27"), "Salary arrives"),
        (item("salary", "Salary", "2026-11-27", done=True), "Salary received ✓"),
        (item("transfer", "Transfer to Joint", "2026-11-30"), "Transfer to Joint"),
        (item("transfer", "Transfer to Joint", "2026-11-30", done=True), "Transfer to Joint — sent ✓"),
        (item("contribution", "From Isa", "2026-11-30"), "Money from Isa"),
        (item("contribution", "From Josu", "2026-11-30", done=True), "Money from Josu ✓"),
        (item("goal", "Laptop", "2026-12-20"), "Goal deadline: Laptop"),
        (item("sinking", "Insurance fund", "2026-12-15", done=True), "Goal reached: Insurance fund ✓"),
    ]
    for money_item, title in cases:
        assert cs.entry_title(money_item) == title
        assert "123" not in title and "€" not in title


def test_desired_entries_carry_the_profile_in_their_key():
    money = {"items": [item("bill", "Rent", "2026-12-01", key="bill/1/2026-12-01")]}
    assert cs.desired(money, "joint") == [
        {"key": "centwise:joint/bill/1/2026-12-01", "date": "2026-12-01", "title": "Rent due"}]


def want(*entries: tuple[str, str, str]) -> list[dict]:
    return [{"key": f"centwise:personal/{k}", "date": d, "title": t} for k, d, t in entries]


def apply(existing: list[dict], changes: dict) -> list[dict]:
    """What the calendar holds after the changes (like the route does it)."""
    out = [e for e in existing if e["event_id"] not in set(changes["delete"])]
    updates = {u["event_id"]: u for u in changes["update"]}
    out = [{**e, **{k: updates[e["event_id"]][k] for k in ("date", "title")}} if e["event_id"] in updates else e
           for e in out]
    out += [{"event_id": f"new{i}", **a} for i, a in enumerate(changes["add"])]
    return out


def test_first_sync_adds_everything_and_a_second_changes_nothing():
    w = want(("bill/1/2026-12-01", "2026-12-01", "Rent due"), ("salary/2026-12", "2026-11-27", "Salary arrives"))
    first = cs.plan(w, [], START, END)
    assert [a["title"] for a in first["add"]] == ["Salary arrives", "Rent due"]  # by date
    assert first["update"] == [] and first["delete"] == []
    again = cs.plan(w, apply([], first), START, END)
    assert again == {"add": [], "update": [], "delete": []}


def test_changes_only_touch_own_entries_inside_the_window():
    """- e1 Rent: now paid -> new title (update).
    - e2 salary moved from 30 Nov to 27 Nov -> new date (update).
    - e3 a bill no longer there -> delete.
    - e4 "Dinner" added by hand (no key) -> left alone.
    - e5 an own entry from last month (before today) -> left alone.
    - e6 the same key as e1 again -> the extra one is deleted.
    - e7 a key of another app ("other:...") -> left alone.
    - Goal Laptop not there yet -> add."""
    w = want(
        ("bill/1/2026-12-01", "2026-12-01", "Rent — paid ✓"),
        ("salary/2026-12", "2026-11-27", "Salary arrives"),
        ("goal/1", "2026-12-20", "Goal deadline: Laptop"),
    )
    existing = [
        {"event_id": "e1", "key": "centwise:personal/bill/1/2026-12-01", "date": "2026-12-01", "title": "Rent due"},
        {"event_id": "e2", "key": "centwise:personal/salary/2026-12", "date": "2026-11-30", "title": "Salary arrives"},
        {"event_id": "e3", "key": "centwise:personal/bill/9/2026-12-05", "date": "2026-12-05", "title": "Gym due"},
        {"event_id": "e4", "key": None, "date": "2026-12-02", "title": "Dinner"},
        {"event_id": "e5", "key": "centwise:personal/bill/1/2026-10-01", "date": "2026-10-01", "title": "Rent due"},
        {"event_id": "e6", "key": "centwise:personal/bill/1/2026-12-01", "date": "2026-12-01", "title": "Rent due"},
        {"event_id": "e7", "key": "other:thing", "date": "2026-12-03", "title": "Something"},
    ]
    changes = cs.plan(w, existing, START, END)
    assert changes["delete"] == ["e3", "e6"]
    assert [(u["event_id"], u["date"], u["title"]) for u in changes["update"]] == [
        ("e1", "2026-12-01", "Rent — paid ✓"), ("e2", "2026-11-27", "Salary arrives")]
    assert [a["title"] for a in changes["add"]] == ["Goal deadline: Laptop"]
    after = apply(existing, changes)
    assert {e["event_id"] for e in after} >= {"e4", "e5", "e7"}
    assert cs.plan(w, after, START, END) == {"add": [], "update": [], "delete": []}


def test_nothing_wanted_removes_only_own_entries_in_the_window():
    existing = [
        {"event_id": "a", "key": "centwise:personal/goal/1", "date": "2027-05-19", "title": "Goal deadline: X"},
        {"event_id": "b", "key": "centwise:personal/goal/2", "date": "2027-05-20", "title": "Goal deadline: Y"},
    ]
    assert cs.plan([], existing, START, END) == {"add": [], "update": [], "delete": ["a"]}
