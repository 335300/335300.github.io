"""Display preferences (stored in app-state.json, not in data.json)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..models import PrefsPatch
from ..storage import AppStore
from .deps import get_store

router = APIRouter(prefix="/api/prefs", tags=["prefs"])


@router.get("")
def get_prefs(store: AppStore = Depends(get_store)) -> dict[str, Any]:
    return store.prefs()


@router.patch("")
def update_prefs(payload: PrefsPatch, store: AppStore = Depends(get_store)) -> dict[str, Any]:
    return store.update_prefs(**payload.model_dump(exclude_none=True))
