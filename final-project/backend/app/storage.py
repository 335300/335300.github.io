"""Persistence: one JSON document, written atomically, with backups.

Every read and write goes through a :class:`Repository`. :class:`AppStore`
owns one repository per profile (Personal, Joint), knows which one is open,
and keeps the small app-state file (last profile + display preferences).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from . import config
from .models import AppData, YearData


class StorageError(RuntimeError):
    pass


def atomic_write(path: Path, payload: str) -> None:
    """Write ``payload`` to ``path`` so a crash never leaves a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


class Repository:
    """Loads, mutates and saves the database.

    The in-memory :class:`AppData` is the source of truth during a session; the
    file is rewritten in full on every save, so the on-disk state is always
    consistent rather than partially applied.
    """

    def __init__(
        self,
        path: Path | None = None,
        backups: Path | None = None,
    ):
        self.path = Path(path) if path else config.data_file()
        self.backup_dir = Path(backups) if backups else self.path.parent / "backups"
        self._lock = threading.RLock()
        self._data: AppData | None = None

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    # -- lifecycle --------------------------------------------------------
    @property
    def data(self) -> AppData:
        with self._lock:
            if self._data is None:
                self._data = self._read()
            return self._data

    def _read(self) -> AppData:
        if not self.path.exists():
            # Nothing is written until the first real change.
            return AppData()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StorageError(f"Could not read {self.path}: {exc}") from exc

        version = raw.get("schema_version", 0)
        if version > config.SCHEMA_VERSION:
            raise StorageError(
                f"{self.path} was written by a newer version of Personal Centwise "
                f"(schema {version} > {config.SCHEMA_VERSION}). Upgrade before opening it."
            )
        data = AppData.model_validate(raw)
        # Older files only lack fields that have defaults; the next save writes
        # them out under the current schema number.
        data.schema_version = config.SCHEMA_VERSION
        return data

    # -- writing ----------------------------------------------------------
    def save(self) -> None:
        """Write the database atomically, keeping a timestamped backup.

        The payload is serialised *before* the existing file is touched, so a
        validation error can never leave a truncated database behind.
        """
        with self._lock:
            if self._data is None:
                return
            payload = json.dumps(self._data.model_dump(mode="json"), indent=2, ensure_ascii=False)
            self._rotate_backup()
            atomic_write(self.path, payload)

    def replace(self, data: AppData) -> Path | None:
        """Swap in restored data. The current file is first copied next to it as
        ``data-before-restore-<time>.json`` (returned), so a restore can be undone."""
        with self._lock:
            safety = None
            if self.path.exists():
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                safety = self.path.parent / f"data-before-restore-{stamp}.json"
                shutil.copy2(self.path, safety)
            self._data = data
            self.save()
            return safety

    def _rotate_backup(self) -> None:
        if not self.path.exists():
            return
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        try:
            shutil.copy2(self.path, self.backup_dir / f"data-{stamp}.json")
        except OSError:
            # A failed backup must never block the user's actual save.
            return
        snapshots = sorted(self.backup_dir.glob("data-*.json"))
        for stale in snapshots[: max(0, len(snapshots) - config.BACKUP_RETENTION)]:
            stale.unlink(missing_ok=True)

    # -- year access ------------------------------------------------------
    def year(self, year: int) -> YearData:
        found = self.data.get_year(year)
        if found is None:
            raise KeyError(year)
        return found

    def ensure_year(self, year: int, copy_from: int | None = None) -> YearData:
        """Create a year if absent, optionally seeded from an earlier one.

        Seeding carries over categories and budgets, and sets the opening balance
        to the source year's closing balance — so a new year starts pre-filled
        with last year's plan instead of blank.
        """
        existing = self.data.get_year(year)
        if existing is not None:
            return existing

        fresh = YearData()
        if copy_from is not None:
            source = self.data.get_year(copy_from)
            if source is not None:
                fresh.categories = source.categories.model_copy(deep=True)
                fresh.budgets = source.budgets.model_copy(deep=True)
                from .services.aggregation import closing_balance

                fresh.opening_balance = closing_balance(source)

        self.data.years[str(year)] = fresh
        self.save()
        return fresh


class AppStore:
    """One repository per profile, plus app-state.json.

    Switching profile only changes which repository the API talks to; nothing is
    copied between them.
    """

    def __init__(self):
        self._repos: dict[str, Repository] = {}
        self._lock = threading.RLock()
        self._active = self._read_last_profile()

    # -- profiles ------------------------------------------------------------
    @staticmethod
    def describe() -> list[dict]:
        return [{"id": pid, "label": label} for pid, label in config.PROFILES.items()]

    @property
    def active(self) -> str:
        return self._active

    def switch(self, profile: str) -> None:
        if profile not in config.PROFILES:
            raise KeyError(profile)
        with self._lock:
            self._active = profile
            self._write_state(profile=profile)

    def repo(self, profile: str | None = None) -> Repository:
        profile = profile or self._active
        with self._lock:
            if profile not in self._repos:
                self._repos[profile] = Repository(path=config.data_file(profile))
            return self._repos[profile]

    def _read_last_profile(self) -> str:
        profile = self._read_state().get("profile", config.DEFAULT_PROFILE)
        return profile if profile in config.PROFILES else config.DEFAULT_PROFILE

    # -- app-state.json --------------------------------------------------------
    # Holds no financial data. Losing it only resets these conveniences.
    @staticmethod
    def _read_state() -> dict:
        try:
            raw = json.loads(config.app_state_file().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def _write_state(self, **changes) -> None:
        state = {**self._read_state(), **changes}
        try:
            atomic_write(config.app_state_file(), json.dumps(state))
        except OSError:
            pass  # Only a convenience; never block the user over it.

    def prefs(self) -> dict:
        """Display preferences, with defaults for anything not set yet."""
        stored = self._read_state().get("prefs", {})
        stored = stored if isinstance(stored, dict) else {}
        hidden = stored.get("calendar_hidden", [])
        own = stored.get("calendar_own_ids", {})
        last = stored.get("calendar_last_sync")
        look = stored.get("appearance")
        return {
            # Light / dark look; "system" (the default) follows the Mac setting.
            "appearance": look if look in ("system", "light", "dark") else "system",
            "show_savings_tile": bool(stored.get("show_savings_tile", False)),
            # Calendar tab: Apple calendars NOT shown (ids). One list for both
            # profiles; a calendar added later shows by default.
            "calendar_hidden": [str(x) for x in hidden][:200] if isinstance(hidden, list) else [],
            # iPhone sync: on/off, the ids of the app's own calendars (written by the
            # backend only) and when it last ran.
            "calendar_push": bool(stored.get("calendar_push", False)),
            "calendar_own_ids": {str(k): str(v) for k, v in own.items()} if isinstance(own, dict) else {},
            "calendar_last_sync": str(last) if last else None,
        }

    def update_prefs(self, **changes) -> dict:
        self._write_state(prefs={**self.prefs(), **changes})
        return self.prefs()
