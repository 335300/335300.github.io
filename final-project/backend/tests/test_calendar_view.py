"""Calendar tab: events + money dates day by day, the fake calendar, the API.

Every test runs with a throwaway CENTWISE_DATA_DIR, so the calendar source is
always the fake one: no test can read or touch a real Apple Calendar.

Weekdays used (checked on a calendar): Mon 16 Nov 2026 … Sun 22 Nov 2026;
Thu 19, Fri 20, Sat 21 Nov.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import apple_calendar
from app.api.deps import get_today
from app.app import create_app
from app.models import LecturePeriod
from app.services import calendar_view

TODAY = date(2026, 11, 18)


def ev(title: str, start: str, end: str, all_day: bool = False) -> dict:
    return {"id": title, "calendar_id": "c", "title": title, "all_day": all_day, "start": start, "end": end,
            "location": "", "calendar": "C", "color": "#000000"}


NO_MONEY = {"profile": "personal", "pay_day": 0, "items": [], "due_total": 0.0, "expected_total": 0.0}


# -- laying out the days -------------------------------------------------------------------


def test_events_go_on_every_day_they_touch_inside_the_window():
    """Window Thu 19 - Sat 21 Nov.
    - "Trip" all day 20-21 -> on the 20th and 21st.
    - "Late film" 19th 23:00 - 20th 00:00 ends at midnight -> only the 19th.
    - "Conference" all day 18-19 starts before the window -> only the 19th.
    - "Dentist" 20th 09:00-10:00 -> the 20th, after the all-day trip.
    """
    events = [
        ev("Dentist", "2026-11-20T09:00", "2026-11-20T10:00"),
        ev("Late film", "2026-11-19T23:00", "2026-11-20T00:00"),
        ev("Trip", "2026-11-20", "2026-11-21", all_day=True),
        ev("Conference", "2026-11-18", "2026-11-19", all_day=True),
    ]
    view = calendar_view.build(date(2026, 11, 19), date(2026, 11, 21), TODAY, NO_MONEY, events)
    assert [(d["date"], [e["title"] for e in d["events"]]) for d in view["days"]] == [
        ("2026-11-19", ["Conference", "Late film"]),
        ("2026-11-20", ["Trip", "Dentist"]),
        ("2026-11-21", ["Trip"]),
    ]
    assert [d["weekday"] for d in view["days"]] == [3, 4, 5]


def test_money_dates_lecture_days_and_today():
    """A bill on the 20th sits on the 20th; the lecture period ends on the 20th, so the
    21st is not a lecture day; today (18th) is flagged. Totals pass through unchanged."""
    money = {**NO_MONEY, "items": [{"date": "2026-11-20", "kind": "bill", "name": "Rent"}],
             "due_total": 400.0, "expected_total": 1000.0}
    periods = [LecturePeriod(start="2026-10-01", end="2026-11-20")]
    view = calendar_view.build(date(2026, 11, 18), date(2026, 11, 21), TODAY, money, [], periods)
    assert [(d["date"], d["lecture"], d["is_today"], len(d["money"])) for d in view["days"]] == [
        ("2026-11-18", True, True, 0),
        ("2026-11-19", True, False, 0),
        ("2026-11-20", True, False, 1),
        ("2026-11-21", False, False, 0),
    ]
    assert (view["due_total"], view["expected_total"], view["profile"]) == (400.0, 1000.0, "personal")


# -- the fake calendar and the source choice ----------------------------------------------------


def test_fake_calendar_asks_first_then_shows_its_events(isolated_data_dir):
    """Week Mon 16 - Sun 22 Nov: lectures Mon 16 and Wed 18, seminar Thu 19, trip 20-21.
    (The 10th and the 5th are not in this week.) Only Home: just the trip."""
    fake = apple_calendar.FakeCalendar(isolated_data_dir)
    assert fake.access() == "not_asked" and fake.calendars() == []
    assert fake.events(date(2026, 11, 16), date(2026, 11, 22), ["fake-uni"]) == []
    assert fake.request_access() == (True, None)
    assert fake.access() == "full" and [c["id"] for c in fake.calendars()] == ["fake-uni", "fake-home", "fake-birthdays"]
    every = [c["id"] for c in fake.calendars()]
    week = fake.events(date(2026, 11, 16), date(2026, 11, 22), every)
    assert sorted((e["start"][:10], e["title"]) for e in week) == [
        ("2026-11-16", "Lecture: Statistics"),
        ("2026-11-18", "Lecture: Statistics"),
        ("2026-11-19", "Seminar: Marketing"),
        ("2026-11-20", "Weekend trip"),
    ]
    assert [e["title"] for e in fake.events(date(2026, 11, 16), date(2026, 11, 22), ["fake-home"])] == ["Weekend trip"]


def test_a_denied_fake_stays_denied(isolated_data_dir):
    (isolated_data_dir).mkdir(parents=True, exist_ok=True)
    (isolated_data_dir / "fake-calendar.json").write_text(json.dumps({"access": "denied"}))
    fake = apple_calendar.FakeCalendar(isolated_data_dir)
    assert fake.request_access() == (False, None) and fake.access() == "denied"


def test_tests_always_get_the_fake_source(monkeypatch):
    """A throwaway data folder means the fake; only CENTWISE_CALENDAR=apple picks the real one."""
    monkeypatch.delenv("CENTWISE_CALENDAR", raising=False)
    assert isinstance(apple_calendar.source(), apple_calendar.FakeCalendar)
    monkeypatch.setenv("CENTWISE_CALENDAR", "fake")
    assert isinstance(apple_calendar.source(), apple_calendar.FakeCalendar)
    monkeypatch.setenv("CENTWISE_CALENDAR", "apple")
    assert isinstance(apple_calendar.source(), apple_calendar.AppleCalendar)  # not called: never reads a calendar


# -- API -----------------------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("CENTWISE_CALENDAR", raising=False)
    app = create_app()
    app.dependency_overrides[get_today] = lambda: TODAY
    with TestClient(app) as c:
        c.post("/api/setup", json={"year": 2026, "opening_balance": 0, "start_month": 8})
        yield c


def week(client) -> dict:
    return client.get("/api/calendar/view", params={"start": "2026-11-16", "end": "2026-11-22"}).json()


def titles(view: dict) -> list[tuple[str, str]]:
    return [(d["date"], e["title"]) for d in view["days"] for e in d["events"]]


def test_api_ask_show_and_hide_calendars(client):
    """Before access: no events, but money dates still show (a 50 € bill on Fri 20 Nov).
    After "Allow": the week's 4 events, each with its calendar's name and colour.
    Hiding University removes the lectures and the seminar — in Joint too."""
    client.post("/api/bills", json={"name": "Gym", "amount": 50, "category": "Rent", "rhythm_months": 1,
                                    "next_due": "2026-11-20"})
    status = client.get("/api/calendar/status").json()
    assert (status["source"], status["access"], status["calendars"]) == ("fake", "not_asked", [])
    before = week(client)
    assert before["access"] == "not_asked" and titles(before) == []
    friday = next(d for d in before["days"] if d["date"] == "2026-11-20")
    assert [(m["name"], m["amount"]) for m in friday["money"]] == [("Gym", 50.0)]

    allowed = client.post("/api/calendar/allow").json()
    assert allowed["granted"] is True and allowed["access"] == "full"
    assert [(c["id"], c["shown"]) for c in allowed["calendars"]] == [
        ("fake-uni", True), ("fake-home", True), ("fake-birthdays", True)]
    after = week(client)
    assert titles(after) == [
        ("2026-11-16", "Lecture: Statistics"), ("2026-11-18", "Lecture: Statistics"),
        ("2026-11-19", "Seminar: Marketing"), ("2026-11-20", "Weekend trip"), ("2026-11-21", "Weekend trip")]
    trip = next(e for d in after["days"] for e in d["events"] if e["title"] == "Weekend trip")
    assert (trip["calendar"], trip["color"]) == ("Home", "#2e9e5b")

    assert client.patch("/api/prefs", json={"calendar_hidden": ["fake-uni"]}).status_code == 200
    assert titles(week(client)) == [("2026-11-20", "Weekend trip"), ("2026-11-21", "Weekend trip")]
    shown = {c["id"]: c["shown"] for c in client.get("/api/calendar/status").json()["calendars"]}
    assert shown == {"fake-uni": False, "fake-home": True, "fake-birthdays": True}

    client.post("/api/profiles/active", json={"profile": "joint"})
    joint = week(client)
    assert joint["profile"] == "joint" and titles(joint) == [("2026-11-20", "Weekend trip"), ("2026-11-21", "Weekend trip")]


def test_api_view_checks_the_window(client):
    assert client.get("/api/calendar/view", params={"start": "2026-11-22", "end": "2026-11-16"}).status_code == 422
    assert client.get("/api/calendar/view", params={"start": "2026-01-01", "end": "2027-03-01"}).status_code == 422


def test_api_too_many_hidden_calendars_are_refused(client):
    assert client.patch("/api/prefs", json={"calendar_hidden": [f"c{i}" for i in range(201)]}).status_code == 422


# -- iPhone sync -------------------------------------------------------------------------------------


def fake_state(folder) -> dict:
    return json.loads((folder / "fake-calendar.json").read_text())


def own_entries(folder, calendar_id: str) -> list[tuple[str, str]]:
    return sorted((e["date"], e["title"]) for e in fake_state(folder).get("entries", {}).values()
                  if e["calendar_id"] == calendar_id)


def test_api_iphone_sync(client, isolated_data_dir):
    """A 50 € gym bill, monthly from 20 Nov 2026. Today 18 Nov; the window runs 183 days,
    to 19 May 2027, so the 20th of Nov, Dec, Jan, Feb, Mar and Apr: 6 entries "Gym due"
    in "Centwise" (no amounts). "Centwise Joint" is made too, empty (no Joint plan).
    A second sync changes nothing. An entry added by hand survives. Deleting the bill
    removes its 6 entries. "Remove" deletes both calendars and switches the sync off."""
    client.post("/api/bills", json={"name": "Gym", "amount": 50, "category": "Rent", "rhythm_months": 1,
                                    "next_due": "2026-11-20"})
    assert client.post("/api/calendar/sync").status_code == 422  # off
    client.post("/api/calendar/allow")
    client.patch("/api/prefs", json={"calendar_push": True})

    first = client.post("/api/calendar/sync").json()
    assert (first["added"], first["updated"], first["removed"]) == (6, 0, 0)
    assert first["push"] is True and first["last_sync"]
    ids = client.get("/api/prefs").json()["calendar_own_ids"]
    assert set(ids) == {"personal", "joint"}
    assert fake_state(isolated_data_dir)["own"] == {ids["personal"]: "Centwise Final Project", ids["joint"]: "Centwise Final Project Joint"}
    gym = own_entries(isolated_data_dir, ids["personal"])
    assert gym == [(f"{m}-20", "Gym due") for m in
                   ("2026-11", "2026-12", "2027-01", "2027-02", "2027-03", "2027-04")]
    assert own_entries(isolated_data_dir, ids["joint"]) == []
    assert all("50" not in title and "€" not in title for _, title in gym)

    second = client.post("/api/calendar/sync").json()
    assert (second["added"], second["updated"], second["removed"]) == (0, 0, 0)

    # The app's own calendars never show as event calendars in the Calendar tab.
    status = client.get("/api/calendar/status").json()
    assert [c["id"] for c in status["calendars"]] == ["fake-uni", "fake-home", "fake-birthdays"]
    view = client.get("/api/calendar/view", params={"start": "2026-11-16", "end": "2026-11-22"}).json()
    assert "Gym due" not in [e["title"] for d in view["days"] for e in d["events"]]

    # Something added by hand to "Centwise" is left alone; deleting the bill removes its entries.
    from app.apple_calendar import FakeCalendar
    FakeCalendar(isolated_data_dir).add_entry(ids["personal"], None, date(2026, 12, 2), "Dinner")
    client.delete("/api/bills/1")
    third = client.post("/api/calendar/sync").json()
    assert (third["added"], third["removed"]) == (0, 6)
    assert own_entries(isolated_data_dir, ids["personal"]) == [("2026-12-02", "Dinner")]

    gone = client.delete("/api/calendar/own").json()
    assert gone["push"] is False and gone["last_sync"] is None
    assert fake_state(isolated_data_dir)["own"] == {} and client.get("/api/prefs").json()["calendar_own_ids"] == {}
    assert [c["id"] for c in gone["calendars"]] == ["fake-uni", "fake-home", "fake-birthdays"]


def test_api_sync_writes_joint_money_dates(client, isolated_data_dir):
    """Joint rent plan 650 (50/50) for December 2026; Josu's pay day default (-1): Fri 27 Nov
    -> both parts the working day after, Mon 30 Nov, for December: "Money from Josu" and
    "Money from Isa" in "Centwise Joint" (no amounts)."""
    client.post("/api/profiles/active", json={"profile": "joint"})
    client.post("/api/setup", json={"year": 2026, "opening_balance": 0, "start_month": 8})
    r = client.put("/api/2026/budgets", json={"kind": "expense", "cat": "Rent", "month": 11, "value": 650})
    assert r.status_code == 200, r.text
    client.post("/api/calendar/allow")
    client.patch("/api/prefs", json={"calendar_push": True})
    client.post("/api/calendar/sync")
    joint_id = client.get("/api/prefs").json()["calendar_own_ids"]["joint"]
    nov30 = [t for d, t in own_entries(isolated_data_dir, joint_id) if d == "2026-11-30"]
    assert sorted(nov30) == ["Money from Isa", "Money from Josu"], own_entries(isolated_data_dir, joint_id)
