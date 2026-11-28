"""Bank statement import: preview first, then save the rows the user kept."""

from __future__ import annotations

import base64
import binascii
from typing import Any

from fastapi import APIRouter, Depends

from ..config import IMPORT_MAX_BYTES
from ..models import ImportCommitInput, ImportFileInput
from ..services import bank_import
from ..storage import Repository
from .deps import bad_request, get_repository

router = APIRouter(prefix="/api/import", tags=["import"])


@router.post("/preview")
def preview_import(payload: ImportFileInput, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    """Read a CSV-CAMT file and say what is new. Saves nothing."""
    try:
        raw = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError):
        raise bad_request("The file could not be read.") from None
    if len(raw) > IMPORT_MAX_BYTES:
        raise bad_request("The file is too big for a statement export.")
    try:
        rows = bank_import.parse_camt_csv(bank_import.decode(raw))
    except bank_import.ImportFormatError as exc:
        raise bad_request(str(exc)) from None
    return {"filename": payload.filename, **bank_import.preview(repo.data, rows)}


@router.post("/commit")
def commit_import(payload: ImportCommitInput, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    """Save the chosen rows — all or nothing."""
    with repo.lock:
        try:
            result = bank_import.commit(repo.data, payload.rows)
        except ValueError as exc:
            raise bad_request(str(exc)) from None
        if result["created"]:
            repo.save()
    return result
