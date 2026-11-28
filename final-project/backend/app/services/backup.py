"""Encrypted backups: make one, verify it, read it back for a restore.

**The file.** A small JSON document:

- a header in plain text — format name, version, when it was made, how the key
  was made (scrypt with its salt and cost) and the AES-GCM nonce;
- the encrypted payload: every profile's full data file plus a **check sheet**.

The key comes from the password via **scrypt**, which is deliberately slow and
memory-hungry, so guessing passwords is expensive. The payload is encrypted
with **AES-256-GCM**, which also detects any change to the file: the header is
bound in as "associated data", so editing even the header makes it unreadable.
The password is never stored anywhere. Forget it, and the backup is lost.

**The check sheet** records, per profile and year, the number of transactions,
total income, total expenses and the closing balance — plus goal and account
counts. :func:`verify` decrypts the file in memory, reads every profile as a
real data file, re-calculates the check sheet and compares. It changes nothing.

Profiles stay separate inside the file; nothing is combined.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from pydantic import ValidationError

from ..config import APP_NAME, BACKUP_MIN_PASSWORD, BACKUP_SCRYPT_N, PROFILES, SCHEMA_VERSION
from ..models import AppData
from .aggregation import closing_balance

FORMAT = "personal-centwise-backup"
VERSION = 1


class BackupError(ValueError):
    """The backup cannot be made or read; the message is safe to show."""


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def _unb64(text: str) -> bytes:
    return base64.b64decode(text, validate=True)


def _round2(v: float) -> float:
    return round(v, 2)


def checksheet(profiles: dict[str, AppData]) -> dict[str, Any]:
    """The figures a restored backup must reproduce exactly."""
    out: dict[str, Any] = {}
    for pid, data in profiles.items():
        years = {}
        for y in data.year_numbers():
            year = data.years[str(y)]
            years[str(y)] = {
                "transactions": len(year.transactions),
                "income": _round2(sum(t.amount for t in year.transactions if t.type == "income")),
                "expenses": _round2(sum(t.amount for t in year.transactions if t.type == "expense")),
                "closing_balance": closing_balance(year),
            }
        out[pid] = {
            "years": years,
            "transactions": sum(v["transactions"] for v in years.values()),
            "goals": len(data.goals),
            "goal_money": _round2(sum(g.saved() for g in data.goals)),
            "accounts": len(data.accounts),
        }
    return out


def _key(password: str, salt: bytes, n: int) -> bytes:
    return Scrypt(salt=salt, length=32, n=n, r=8, p=1).derive(password.encode("utf-8"))


def _aad(header: dict[str, Any]) -> bytes:
    return json.dumps(header, sort_keys=True, separators=(",", ":")).encode()


def make(
    profiles: dict[str, AppData],
    password: str,
    created: str,
    n: int = BACKUP_SCRYPT_N,
    salt: bytes | None = None,
    nonce: bytes | None = None,
) -> bytes:
    if len(password) < BACKUP_MIN_PASSWORD:
        raise BackupError(f"Use a password of at least {BACKUP_MIN_PASSWORD} characters.")
    salt = salt or os.urandom(16)
    nonce = nonce or os.urandom(12)
    header = {
        "format": FORMAT,
        "version": VERSION,
        "app": APP_NAME,
        "created": created,
        "schema_version": SCHEMA_VERSION,
        "kdf": {"name": "scrypt", "n": n, "r": 8, "p": 1, "salt": _b64(salt)},
        "cipher": "AES-256-GCM",
        "nonce": _b64(nonce),
        "profiles": sorted(profiles),
    }
    payload = {
        "profiles": {pid: data.model_dump(mode="json") for pid, data in profiles.items()},
        "checksheet": checksheet(profiles),
    }
    plaintext = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    ciphertext = AESGCM(_key(password, salt, n)).encrypt(nonce, plaintext, _aad(header))
    return json.dumps({**header, "ciphertext": _b64(ciphertext)}, indent=1).encode("utf-8")


def read(raw: bytes, password: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """(header, payload). Raises :class:`BackupError` for a wrong password, a
    damaged file, or a file that is not a backup."""
    try:
        doc = json.loads(raw.decode("utf-8"))
        ciphertext = _unb64(doc.pop("ciphertext"))
        header = doc
        if header.get("format") != FORMAT:
            raise ValueError
        kdf = header["kdf"]
        salt, nonce, n = _unb64(kdf["salt"]), _unb64(header["nonce"]), int(kdf["n"])
    except (ValueError, KeyError, TypeError, AttributeError, UnicodeDecodeError):
        raise BackupError("This is not a Personal Centwise backup file.") from None
    if header.get("version", 0) > VERSION or header.get("schema_version", 0) > SCHEMA_VERSION:
        raise BackupError("This backup was made by a newer version of the app. Update the app first.")
    if not 2**10 <= n <= 2**20:
        raise BackupError("This backup file is damaged.")
    try:
        plaintext = AESGCM(_key(password, salt, n)).decrypt(nonce, ciphertext, _aad(header))
    except InvalidTag:
        raise BackupError("Wrong password, or the file was changed or damaged.") from None
    try:
        payload = json.loads(plaintext.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise BackupError("This backup file is damaged.") from None
    return header, payload


def verify(raw: bytes, password: str) -> dict[str, Any]:
    """Decrypt, read every profile as a data file, re-calculate and compare.

    Returns ``{"ok": bool, ...}``; ``profiles`` holds the validated data (for
    a restore) and is not meant to be sent to the page.
    """
    header, payload = read(raw, password)
    stored = payload.get("checksheet") or {}
    profiles: dict[str, AppData] = {}
    problems: list[str] = []
    for pid, raw_data in (payload.get("profiles") or {}).items():
        if pid not in PROFILES:
            problems.append(f"Unknown profile {pid!r} in the backup.")
            continue
        try:
            data = AppData.model_validate(raw_data)
        except ValidationError as exc:
            problems.append(f"{PROFILES[pid]}: the data does not read correctly ({exc.error_count()} problems).")
            continue
        data.schema_version = SCHEMA_VERSION
        profiles[pid] = data

    fresh = checksheet(profiles)
    for pid in sorted(set(stored) | set(fresh)):
        label = PROFILES.get(pid, pid)
        if pid not in fresh:
            continue  # already reported above
        if pid not in stored:
            problems.append(f"{label}: missing from the check sheet.")
            continue
        for y in sorted(set(stored[pid]["years"]) | set(fresh[pid]["years"])):
            a, b = stored[pid]["years"].get(y), fresh[pid]["years"].get(y)
            if a != b:
                problems.append(f"{label} {y}: the totals do not match the check sheet.")
        for key in ("goals", "goal_money", "accounts"):
            if stored[pid].get(key) != fresh[pid][key]:
                problems.append(f"{label}: {key.replace('_', ' ')} do not match the check sheet.")

    return {
        "ok": not problems and bool(profiles),
        "created": header.get("created"),
        "problems": problems if profiles else problems or ["The backup holds no profile."],
        "summary": [
            {
                "profile": pid,
                "label": PROFILES[pid],
                "years": sorted(int(y) for y in fresh[pid]["years"]),
                "transactions": fresh[pid]["transactions"],
                "goals": fresh[pid]["goals"],
            }
            for pid in sorted(fresh)
        ],
        "profiles": profiles,
    }
