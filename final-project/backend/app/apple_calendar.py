"""Apple Calendar on this Mac, through Apple's EventKit — and a fake for tests.

The Calendar tab (``AI output/2026-11-18-calendar-tab-plan.md``) reads the
user's events through a *calendar source*:

- :class:`AppleCalendar` — the real one (EventKit). Used by the installed app.
- :class:`FakeCalendar` — made-up calendars and events plus a pretend
  permission, kept in ``fake-calendar.json`` in the (throwaway) data folder.

:func:`source` picks one: ``CENTWISE_CALENDAR=apple`` or ``fake`` decides; with
neither, the fake is used whenever ``CENTWISE_DATA_DIR`` is set (tests, UI
checks, development) and the real one only for the real data folder. So no
test can ever read or touch the user's calendars.

Rules for everything in this module:

- The user's own calendars are only ever **read**.
- Writing happens only in calendars this app created, found by their
  identifier; :func:`remove_calendar` also checks the title first (Step 3).
- Event titles go to the page only: never logged, never saved.
- EventKit is imported lazily, so the tests never load it.

macOS asks the user once ("Personal Centwise would like to access your
calendars"). The backend is a child of the Electron app, so the question and
the permission belong to Personal Centwise.app, whose Info.plist carries the
explanation (``NSCalendarsFullAccessUsageDescription``). Step 0 proved this
in the packaged app.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

from .config import data_dir

#: EKAuthorizationStatus values -> plain words.
_ACCESS = {0: "not_asked", 1: "restricted", 2: "denied", 3: "full", 4: "write_only"}

#: EKSourceType values -> plain words (account kinds).
_SOURCE_KINDS = {0: "on_this_mac", 1: "exchange", 2: "caldav", 3: "mobileme", 4: "subscribed", 5: "birthdays"}

#: Shown for a calendar whose colour cannot be read.
_GREY = "#8e8e93"


class CalendarError(Exception):
    """Apple Calendar refused or failed an action; the message is safe to show."""


class CalendarSource(Protocol):
    kind: str

    def access(self) -> str:
        """``full``, ``not_asked``, ``denied``, ``restricted``, ``write_only`` or ``unavailable``."""

    def request_access(self, timeout: float = 120.0) -> tuple[bool, str | None]:
        """Ask for full access (macOS shows its question once); ``(granted, error)``."""

    def calendars(self) -> list[dict[str, Any]]:
        """``[{id, title, color "#rrggbb", account}]`` — empty without full access."""

    def events(self, start: date, end: date, calendar_ids: list[str]) -> list[dict[str, Any]]:
        """Events touching ``start``..``end`` (both included) in the given calendars.

        Each: ``{id, calendar_id, title, all_day, start, end, location}``. Timed
        events have ``start``/``end`` as local ``YYYY-MM-DDTHH:MM``; all-day
        events as ``YYYY-MM-DD`` with ``end`` = the last day.
        """

    # -- the app's own calendars (iPhone sync) --------------------------------------

    def ensure_calendar(self, title: str, known_id: str | None) -> str:
        """The id of the app's own calendar: ``known_id`` while it exists, else one
        titled ``title`` in iCloud (found, or made)."""

    def entries(self, calendar_id: str, start: date, end: date) -> list[dict[str, Any]]:
        """Entries of the app's own calendar: ``[{event_id, key, date, title}]``."""

    def add_entry(self, calendar_id: str, key: str, day: date, title: str) -> str:
        """Add an all-day entry with the hidden ``key``; returns its id. No alarm of
        its own: the calendar's default alert for all-day events applies (adding one
        too gave two reminders in Step 0)."""

    def update_entry(self, calendar_id: str, event_id: str, day: date, title: str) -> None:
        """Move or rename one entry — only if it is in ``calendar_id``."""

    def delete_entry(self, calendar_id: str, event_id: str) -> None:
        """Delete one entry — only if it is in ``calendar_id``."""

    def delete_calendar(self, calendar_id: str, expected_title: str) -> bool:
        """Delete the app's own calendar; refuses when its title is not ``expected_title``."""


# -- the real one --------------------------------------------------------------------


def _ek():
    import EventKit  # noqa: PLC0415 - lazy on purpose (see module docstring)

    return EventKit


def _store():
    return _ek().EKEventStore.alloc().init()


def _nsdate(moment: datetime):
    from Foundation import NSDate  # noqa: PLC0415

    return NSDate.dateWithTimeIntervalSince1970_(moment.timestamp())


def _to_datetime(nsdate) -> datetime:
    return datetime.fromtimestamp(float(nsdate.timeIntervalSince1970()))


def _error_text(error, fallback: str) -> str:
    return str(error.localizedDescription()) if error is not None else fallback


def _hex(nscolor) -> str:
    try:
        from AppKit import NSColorSpace  # noqa: PLC0415

        c = nscolor.colorUsingColorSpace_(NSColorSpace.sRGBColorSpace())
        r, g, b = (max(0, min(255, round(float(x) * 255))) for x in (c.redComponent(), c.greenComponent(), c.blueComponent()))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:  # noqa: BLE001 - a colour is never worth an error
        return _GREY


def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day)


class AppleCalendar:
    """The user's real Apple Calendar (all accounts the Calendar app shows).

    One instance serves one request, with one event store (made on first use,
    so it sees a permission granted just before)."""

    kind = "apple"

    def __init__(self) -> None:
        self._event_store = None

    @property
    def store(self):
        if self._event_store is None:
            self._event_store = _store()
        return self._event_store

    def access(self) -> str:
        try:
            ek = _ek()
        except ImportError:
            return "unavailable"
        raw = int(ek.EKEventStore.authorizationStatusForEntityType_(ek.EKEntityTypeEvent))
        return _ACCESS.get(raw, "unknown")

    def request_access(self, timeout: float = 120.0) -> tuple[bool, str | None]:
        store = _store()
        done = threading.Event()
        answer: dict[str, Any] = {"granted": False, "error": None}

        def handler(granted, error) -> None:
            answer["granted"] = bool(granted)
            answer["error"] = None if error is None else _error_text(error, "")
            done.set()

        store.requestFullAccessToEventsWithCompletion_(handler)
        if not done.wait(timeout):
            return False, "no answer to the permission question"
        return answer["granted"], answer["error"]

    def calendars(self) -> list[dict[str, Any]]:
        if self.access() != "full":
            return []
        ek = _ek()
        out = []
        for cal in self.store.calendarsForEntityType_(ek.EKEntityTypeEvent) or []:
            source = cal.source()
            out.append({
                "id": str(cal.calendarIdentifier()),
                "title": str(cal.title()),
                "color": _hex(cal.color()),
                "account": str(source.title()) if source is not None else "",
            })
        return sorted(out, key=lambda c: (c["account"].lower(), c["title"].lower()))

    def events(self, start: date, end: date, calendar_ids: list[str]) -> list[dict[str, Any]]:
        if not calendar_ids or self.access() != "full":
            return []
        ek = _ek()
        store = self.store
        wanted = set(calendar_ids)
        calendars = [c for c in store.calendarsForEntityType_(ek.EKEntityTypeEvent) or []
                     if str(c.calendarIdentifier()) in wanted]
        if not calendars:
            return []
        predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
            _nsdate(_midnight(start)), _nsdate(_midnight(end) + timedelta(days=1)), calendars
        )
        out = []
        for event in store.eventsMatchingPredicate_(predicate) or []:
            begins, ends = _to_datetime(event.startDate()), _to_datetime(event.endDate())
            all_day = bool(event.isAllDay())
            if all_day:
                first, last = begins.date(), max(begins, ends - timedelta(seconds=1)).date()
                when = (first.isoformat(), last.isoformat())
            else:
                when = (begins.strftime("%Y-%m-%dT%H:%M"), ends.strftime("%Y-%m-%dT%H:%M"))
            title = event.title()
            out.append({
                "id": f"{event.eventIdentifier()}/{when[0]}",
                "calendar_id": str(event.calendar().calendarIdentifier()),
                "title": str(title) if title else "(No title)",
                "all_day": all_day,
                "start": when[0],
                "end": when[1],
                "location": str(event.location() or ""),
            })
        return out


    # -- the app's own calendars (iPhone sync) --------------------------------------

    def _own(self, calendar_id: str):
        calendar = self.store.calendarWithIdentifier_(calendar_id)
        if calendar is None:
            raise CalendarError("The app's calendar was not found.")
        return calendar

    def ensure_calendar(self, title: str, known_id: str | None) -> str:
        ek = _ek()
        if known_id and self.store.calendarWithIdentifier_(known_id) is not None:
            return known_id
        src = _icloud_source(self.store)
        if src is None:
            raise CalendarError("There is no iCloud calendar account on this Mac.")
        for cal in self.store.calendarsForEntityType_(ek.EKEntityTypeEvent) or []:
            if str(cal.title()) == title and cal.source() is not None and cal.source().sourceIdentifier() == src.sourceIdentifier():
                return str(cal.calendarIdentifier())
        calendar = ek.EKCalendar.calendarForEntityType_eventStore_(ek.EKEntityTypeEvent, self.store)
        calendar.setTitle_(title)
        calendar.setSource_(src)
        ok, error = self.store.saveCalendar_commit_error_(calendar, True, None)
        if not ok:
            raise CalendarError(_error_text(error, "Apple Calendar could not create the calendar."))
        return str(calendar.calendarIdentifier())

    def entries(self, calendar_id: str, start: date, end: date) -> list[dict[str, Any]]:
        calendar = self.store.calendarWithIdentifier_(calendar_id)
        if calendar is None:
            return []
        predicate = self.store.predicateForEventsWithStartDate_endDate_calendars_(
            _nsdate(_midnight(start)), _nsdate(_midnight(end) + timedelta(days=1)), [calendar]
        )
        out = []
        for event in self.store.eventsMatchingPredicate_(predicate) or []:
            url = event.URL()
            out.append({
                "event_id": str(event.eventIdentifier()),
                "key": str(url.absoluteString()) if url is not None else None,
                "date": _to_datetime(event.startDate()).date().isoformat(),
                "title": str(event.title() or ""),
            })
        return out

    def _event_in(self, calendar_id: str, event_id: str):
        event = self.store.eventWithIdentifier_(event_id)
        if event is None or str(event.calendar().calendarIdentifier()) != calendar_id:
            raise CalendarError("Refused: that entry is not in the app's own calendar.")
        return event

    @staticmethod
    def _set_day(event, day: date) -> None:
        # Like the Calendar app's own all-day entries: 00:00 to 23:59:59 of the day
        # (EventKit refuses an end equal to the start — found in Step 0).
        midnight = _midnight(day)
        event.setAllDay_(True)
        event.setStartDate_(_nsdate(midnight))
        event.setEndDate_(_nsdate(midnight + timedelta(days=1, seconds=-1)))

    def _save(self, event) -> None:
        ok, error = self.store.saveEvent_span_commit_error_(event, _ek().EKSpanThisEvent, True, None)
        if not ok:
            raise CalendarError(_error_text(error, "Apple Calendar could not save the entry."))

    def add_entry(self, calendar_id: str, key: str, day: date, title: str) -> str:
        from Foundation import NSURL  # noqa: PLC0415

        event = _ek().EKEvent.eventWithEventStore_(self.store)
        event.setCalendar_(self._own(calendar_id))
        event.setTitle_(title)
        self._set_day(event, day)
        event.setURL_(NSURL.URLWithString_(key))
        self._save(event)
        return str(event.eventIdentifier())

    def update_entry(self, calendar_id: str, event_id: str, day: date, title: str) -> None:
        event = self._event_in(calendar_id, event_id)
        event.setTitle_(title)
        self._set_day(event, day)
        self._save(event)

    def delete_entry(self, calendar_id: str, event_id: str) -> None:
        event = self._event_in(calendar_id, event_id)
        ok, error = self.store.removeEvent_span_commit_error_(event, _ek().EKSpanThisEvent, True, None)
        if not ok:
            raise CalendarError(_error_text(error, "Apple Calendar could not delete the entry."))

    def delete_calendar(self, calendar_id: str, expected_title: str) -> bool:
        calendar = self.store.calendarWithIdentifier_(calendar_id)
        if calendar is None:
            return False
        if str(calendar.title()) != expected_title:
            raise CalendarError(f"Refused: the calendar is no longer called \"{expected_title}\".")
        ok, error = self.store.removeCalendar_commit_error_(calendar, True, None)
        if not ok:
            raise CalendarError(_error_text(error, "Apple Calendar could not remove the calendar."))
        return True


# -- the fake one (tests, UI checks, development) ----------------------------------------


#: Made-up calendars of the fake source.
FAKE_CALENDARS = [
    {"id": "fake-uni", "title": "University", "color": "#1e6fd9", "account": "iCloud"},
    {"id": "fake-home", "title": "Home", "color": "#2e9e5b", "account": "iCloud"},
    {"id": "fake-birthdays", "title": "Birthdays", "color": "#8e5bd0", "account": "Other"},
]


class FakeCalendar:
    """Made-up events that repeat by weekday and day of month, so every window has some.

    - Monday and Wednesday 10:00-11:30 "Lecture: Statistics" (University, room A1)
    - Thursday 14:00-15:30 "Seminar: Marketing" (University)
    - the 10th 09:00-09:30 "Dentist" (Home)
    - the 20th-21st all day "Weekend trip" (Home)
    - the 5th all day "Birthday: Alex" (Birthdays)

    The pretend permission starts as ``not_asked``; :meth:`request_access`
    grants it. The app's own calendars and their entries (iPhone sync) are kept
    too, in ``fake-calendar.json`` in ``folder`` — so tests can check every
    change, and never touch a real calendar.
    """

    kind = "fake"

    def __init__(self, folder: Path) -> None:
        self.path = Path(folder) / "fake-calendar.json"

    def _state(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def access(self) -> str:
        return str(self._state().get("access", "not_asked"))

    def _write(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, indent=1), encoding="utf-8")

    def request_access(self, timeout: float = 120.0) -> tuple[bool, str | None]:
        if self.access() in ("denied", "restricted"):
            return False, None
        self._write({**self._state(), "access": "full"})
        return True, None

    def calendars(self) -> list[dict[str, Any]]:
        """The made-up calendars, plus the app's own ones (like Apple Calendar lists them)."""
        if self.access() != "full":
            return []
        own = [{"id": cid, "title": title, "color": "#999999", "account": "iCloud"}
               for cid, title in self._state().get("own", {}).items()]
        return [dict(c) for c in FAKE_CALENDARS] + own

    def events(self, start: date, end: date, calendar_ids: list[str]) -> list[dict[str, Any]]:
        if self.access() != "full":
            return []
        wanted = set(calendar_ids)
        out: list[dict[str, Any]] = []

        def timed(day: date, cal: str, title: str, begin: str, finish: str, location: str = "") -> None:
            out.append({"id": f"{cal}/{title}/{day.isoformat()}", "calendar_id": cal, "title": title,
                        "all_day": False, "start": f"{day.isoformat()}T{begin}", "end": f"{day.isoformat()}T{finish}",
                        "location": location})

        def all_day(first: date, last: date, cal: str, title: str) -> None:
            out.append({"id": f"{cal}/{title}/{first.isoformat()}", "calendar_id": cal, "title": title,
                        "all_day": True, "start": first.isoformat(), "end": last.isoformat(), "location": ""})

        for event_id, e in self._state().get("entries", {}).items():  # the app's own entries
            all_day(date.fromisoformat(e["date"]), date.fromisoformat(e["date"]), e["calendar_id"], e["title"])
            out[-1]["id"] = event_id

        day = start - timedelta(days=1)  # the trip of the 20th-21st can reach into the window
        while day <= end:
            if day.weekday() in (0, 2):
                timed(day, "fake-uni", "Lecture: Statistics", "10:00", "11:30", "Room A1")
            if day.weekday() == 3:
                timed(day, "fake-uni", "Seminar: Marketing", "14:00", "15:30")
            if day.day == 10:
                timed(day, "fake-home", "Dentist", "09:00", "09:30")
            if day.day == 20:
                all_day(day, day + timedelta(days=1), "fake-home", "Weekend trip")
            if day.day == 5:
                all_day(day, day, "fake-birthdays", "Birthday: Alex")
            day += timedelta(days=1)
        return [
            e for e in out
            if e["calendar_id"] in wanted and e["start"][:10] <= end.isoformat() and e["end"][:10] >= start.isoformat()
        ]


    # -- the app's own calendars (iPhone sync) --------------------------------------

    def ensure_calendar(self, title: str, known_id: str | None) -> str:
        state = self._state()
        own = state.setdefault("own", {})
        if known_id and known_id in own:
            return known_id
        for cid, existing in own.items():
            if existing == title:
                return cid
        state["next_id"] = state.get("next_id", 0) + 1
        cid = f"fake-own-{state['next_id']}"
        own[cid] = title
        self._write(state)
        return cid

    def entries(self, calendar_id: str, start: date, end: date) -> list[dict[str, Any]]:
        return [
            {"event_id": eid, "key": e.get("key"), "date": e["date"], "title": e["title"]}
            for eid, e in sorted(self._state().get("entries", {}).items())
            if e["calendar_id"] == calendar_id and start.isoformat() <= e["date"] <= end.isoformat()
        ]

    def add_entry(self, calendar_id: str, key: str | None, day: date, title: str) -> str:
        state = self._state()
        if calendar_id not in state.get("own", {}) and not calendar_id.startswith("fake-"):
            raise CalendarError("The app's calendar was not found.")
        state["next_id"] = state.get("next_id", 0) + 1
        eid = f"e{state['next_id']:05d}"
        state.setdefault("entries", {})[eid] = {"calendar_id": calendar_id, "key": key,
                                                 "date": day.isoformat(), "title": title}
        self._write(state)
        return eid

    def _entry_in(self, state: dict[str, Any], calendar_id: str, event_id: str) -> dict[str, Any]:
        entry = state.get("entries", {}).get(event_id)
        if entry is None or entry["calendar_id"] != calendar_id:
            raise CalendarError("Refused: that entry is not in the app's own calendar.")
        return entry

    def update_entry(self, calendar_id: str, event_id: str, day: date, title: str) -> None:
        state = self._state()
        entry = self._entry_in(state, calendar_id, event_id)
        entry.update(date=day.isoformat(), title=title)
        self._write(state)

    def delete_entry(self, calendar_id: str, event_id: str) -> None:
        state = self._state()
        self._entry_in(state, calendar_id, event_id)
        del state["entries"][event_id]
        self._write(state)

    def delete_calendar(self, calendar_id: str, expected_title: str) -> bool:
        state = self._state()
        own = state.get("own", {})
        if calendar_id not in own:
            return False
        if own[calendar_id] != expected_title:
            raise CalendarError(f"Refused: the calendar is no longer called \"{expected_title}\".")
        del own[calendar_id]
        state["entries"] = {k: v for k, v in state.get("entries", {}).items() if v["calendar_id"] != calendar_id}
        self._write(state)
        return True


def source() -> CalendarSource:
    """The calendar source for this run (see the module docstring)."""
    mode = os.environ.get("CENTWISE_CALENDAR", "").strip().lower()
    if mode == "fake" or (mode != "apple" and os.environ.get("CENTWISE_DATA_DIR")):
        return FakeCalendar(data_dir())
    return AppleCalendar()


# -- helpers ---------------------------------------------------------------------------------


def _icloud_source(store):
    ek = _ek()
    for src in store.sources():
        if int(src.sourceType()) == ek.EKSourceTypeCalDAV and str(src.title()) == "iCloud":
            return src
    return None
