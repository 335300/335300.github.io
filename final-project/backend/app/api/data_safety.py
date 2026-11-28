"""Encrypted backups (make, verify, restore) and the full export."""

from __future__ import annotations

import base64
import binascii
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends

from ..config import BACKUP_MAX_BYTES, PROFILES
from ..models import BackupFileInput, BackupInput
from ..services import backup, export
from ..storage import AppStore
from .deps import bad_request, get_store, get_today

router = APIRouter(prefix="/api/data", tags=["data safety"])


def _file(name: str, content: bytes) -> dict[str, Any]:
    return {"filename": name, "content_base64": base64.b64encode(content).decode()}


def _raw(payload: BackupFileInput) -> bytes:
    try:
        raw = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise bad_request("The file could not be read.") from None
    if len(raw) > BACKUP_MAX_BYTES:
        raise bad_request("The file is too big to be a backup.")
    return raw


def _public(result: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in result.items() if k != "profiles"}


@router.post("/backup")
def make_backup(payload: BackupInput, store: AppStore = Depends(get_store), today: date = Depends(get_today)) -> dict[str, Any]:
    """Both profiles in one encrypted file (each kept separate inside)."""
    profiles = {pid: store.repo(pid).data for pid in PROFILES}
    try:
        content = backup.make(profiles, payload.password, created=datetime.now().isoformat(timespec="seconds"))
    except backup.BackupError as exc:
        raise bad_request(str(exc)) from None
    return _file(f"{today.isoformat()}-personal-centwise-backup.pcbackup", content)


@router.post("/backup/verify")
def verify_backup(payload: BackupFileInput) -> dict[str, Any]:
    try:
        return _public(backup.verify(_raw(payload), payload.password))
    except backup.BackupError as exc:
        raise bad_request(str(exc)) from None


@router.post("/backup/restore")
def restore_backup(payload: BackupFileInput, store: AppStore = Depends(get_store)) -> dict[str, Any]:
    """Replace the data with a verified backup; each current file is kept as a safety copy."""
    try:
        result = backup.verify(_raw(payload), payload.password)
    except backup.BackupError as exc:
        raise bad_request(str(exc)) from None
    if not result["ok"]:
        raise bad_request("The backup did not pass the check, so nothing was restored. " + " ".join(result["problems"]))
    safety = []
    for pid, data in result["profiles"].items():
        copy = store.repo(pid).replace(data)
        if copy is not None:
            safety.append(copy.name)
    return {**_public(result), "restored": sorted(result["profiles"]), "safety_copies": safety}


@router.get("/export/transactions")
def export_transactions(store: AppStore = Depends(get_store), today: date = Depends(get_today)) -> dict[str, Any]:
    return _file(f"{today.isoformat()}-{store.active}-transactions.csv", export.transactions_csv(store.repo().data))


@router.get("/export/json")
def export_json(store: AppStore = Depends(get_store), today: date = Depends(get_today)) -> dict[str, Any]:
    return _file(f"{today.isoformat()}-{store.active}-data.json", export.full_json(store.repo().data))
