"""Calendar tab and iPhone sync: Apple Calendar events and the money dates.

The calendar source is real Apple Calendar in the installed app and a fake one
in tests and UI checks (see :mod:`app.apple_calendar`). Which calendars are
shown is one app-wide preference (``calendar_hidden`` in app-state.json), so
Personal and Joint show the same ones.

**iPhone sync** (``calendar_push``): the money dates of the next
``CALENDAR_SYNC_DAYS`` days go into the app's own iCloud calendars
(``OWN_CALENDARS``), titles only. What changes is worked out by
:mod:`services.calendar_sync`; this module only applies it. The app's own
calendars never show as event calendars in the Calendar tab.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query

from .. import apple_calendar
from ..config import CALENDAR_SYNC_DAYS, DEFAULT_PROFILE, JOINT_PROFILE, MONEY_DATES_MAX_DAYS, OWN_CALENDARS
from ..models import AppData
from ..services import calendar_sync, calendar_view, money_dates
from ..storage import AppStore
from .deps import bad_request, get_store, get_today

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

#: One sync at a time (the page may ask twice in a row).
_SYNC_LOCK = threading.Lock()


def _check_window(start: date, end: date) -> None:
    if end < start:
        raise bad_request("The end date is before the start date.")
    if (end - start).days > MONEY_DATES_MAX_DAYS:
        raise bad_request(f"Ask for at most {MONEY_DATES_MAX_DAYS} days at a time.")


def _money(store: AppStore, profile: str, start: date, end: date, today: date) -> tuple[dict[str, Any], AppData]:
    """One profile's money dates, and its data.

    Reads the other profile without changing it: Personal needs the Joint plan
    for the transfer amount, Joint needs the owner's pay day from Personal.
    """
    personal = store.repo(DEFAULT_PROFILE).data
    shared = store.repo(JOINT_PROFILE).data
    if profile == JOINT_PROFILE:
        pay_day = personal.income_plan.pay_day if personal.income_plan else None
        return money_dates.money_dates(shared, start, end, today, profile="joint", pay_day=pay_day), shared
    return money_dates.money_dates(personal, start, end, today, shared=shared), personal


def _own_ids(store: AppStore) -> set[str]:
    return set(store.prefs()["calendar_own_ids"].values())


def _user_calendars(src: apple_calendar.CalendarSource, store: AppStore) -> list[dict[str, Any]]:
    """The user's calendars: everything except the app's own (by id, or by title when ids were lost)."""
    own, titles = _own_ids(store), set(OWN_CALENDARS.values())
    return [c for c in src.calendars() if c["id"] not in own and c["title"] not in titles]


def _status(store: AppStore) -> dict[str, Any]:
    src = apple_calendar.source()
    access = src.access()
    prefs = store.prefs()
    hidden = set(prefs["calendar_hidden"])
    calendars = [{**c, "shown": c["id"] not in hidden} for c in _user_calendars(src, store)] if access == "full" else []
    return {
        "source": src.kind,
        "access": access,
        "calendars": calendars,
        "push": prefs["calendar_push"],
        "last_sync": prefs["calendar_last_sync"],
        "own_calendars": list(OWN_CALENDARS.values()),
        "sync_days": CALENDAR_SYNC_DAYS,
    }


@router.get("/status")
def get_status(store: AppStore = Depends(get_store)) -> dict[str, Any]:
    """Calendar access (``full``, ``not_asked``, ``denied``, …), the calendars to pick from, the iPhone sync."""
    return _status(store)


@router.post("/allow")
def allow(store: AppStore = Depends(get_store)) -> dict[str, Any]:
    """Ask macOS for calendar access. Waits (up to 2 minutes) for the user's answer."""
    granted, error = apple_calendar.source().request_access()
    return {**_status(store), "granted": granted, "error": error}


@router.get("/money")
def get_money_dates(
    start: date = Query(...),
    end: date = Query(...),
    store: AppStore = Depends(get_store),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """Salary, transfers, bills and goal deadlines from ``start`` to ``end``."""
    _check_window(start, end)
    return _money(store, store.active, start, end, today)[0]


@router.get("/view")
def get_view(
    start: date = Query(...),
    end: date = Query(...),
    store: AppStore = Depends(get_store),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """Day by day from ``start`` to ``end``: events of the shown calendars, money dates, lecture days."""
    _check_window(start, end)
    money, data = _money(store, store.active, start, end, today)
    src = apple_calendar.source()
    access = src.access()
    events: list[dict[str, Any]] = []
    events_error = None
    if access == "full":
        hidden = set(store.prefs()["calendar_hidden"])
        try:
            shown = {c["id"]: c for c in _user_calendars(src, store) if c["id"] not in hidden}
            events = [
                {**e, "calendar": shown[e["calendar_id"]]["title"], "color": shown[e["calendar_id"]]["color"]}
                for e in src.events(start, end, list(shown))
                if e["calendar_id"] in shown
            ]
        except Exception:  # noqa: BLE001 - money dates still show when Apple Calendar fails
            events_error = "Apple Calendar could not be read just now."
    periods = data.income_plan.lecture_periods if data.income_plan else []
    view = calendar_view.build(start, end, today, money, events, periods)
    return {**view, "access": access, "events_error": events_error}


@router.post("/sync")
def sync(store: AppStore = Depends(get_store), today: date = Depends(get_today)) -> dict[str, Any]:
    """Bring the app's own iCloud calendars up to date (only when the iPhone sync is on)."""
    if not store.prefs()["calendar_push"]:
        raise bad_request("Sending money dates to the iPhone is switched off.")
    src = apple_calendar.source()
    if src.access() != "full":
        raise bad_request("Calendar access is not allowed.")
    start, end = today, today + timedelta(days=CALENDAR_SYNC_DAYS - 1)
    counts = {"added": 0, "updated": 0, "removed": 0}
    with _SYNC_LOCK:
        ids = dict(store.prefs()["calendar_own_ids"])
        try:
            for profile, title in OWN_CALENDARS.items():
                ids[profile] = cid = src.ensure_calendar(title, ids.get(profile))
                want = calendar_sync.desired(_money(store, profile, start, end, today)[0], profile)
                changes = calendar_sync.plan(want, src.entries(cid, start, end), start, end)
                for entry in changes["add"]:
                    src.add_entry(cid, entry["key"], date.fromisoformat(entry["date"]), entry["title"])
                for entry in changes["update"]:
                    src.update_entry(cid, entry["event_id"], date.fromisoformat(entry["date"]), entry["title"])
                for event_id in changes["delete"]:
                    src.delete_entry(cid, event_id)
                counts["added"] += len(changes["add"])
                counts["updated"] += len(changes["update"])
                counts["removed"] += len(changes["delete"])
        except apple_calendar.CalendarError as exc:
            store.update_prefs(calendar_own_ids=ids)
            raise bad_request(str(exc)) from None
        last = datetime.now().isoformat(timespec="minutes")
        store.update_prefs(calendar_own_ids=ids, calendar_last_sync=last)
    return {**_status(store), **counts}


@router.delete("/own")
def remove_own_calendars(store: AppStore = Depends(get_store)) -> dict[str, Any]:
    """Switch the iPhone sync off and delete the app's own calendars (nothing else)."""
    src = apple_calendar.source()
    ids = store.prefs()["calendar_own_ids"]
    with _SYNC_LOCK:
        store.update_prefs(calendar_push=False)
        try:
            for profile, cid in ids.items():
                src.delete_calendar(cid, OWN_CALENDARS.get(profile, ""))
        except apple_calendar.CalendarError as exc:
            raise bad_request(str(exc)) from None
        store.update_prefs(calendar_own_ids={}, calendar_last_sync=None)
    return _status(store)
