"""Profile switch: Personal or Joint. Each is its own database."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ..models import ProfileSwitch
from ..storage import AppStore
from .deps import get_store, not_found

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


def _state(store: AppStore) -> dict[str, Any]:
    return {"active": store.active, "profiles": store.describe()}


@router.get("")
def list_profiles(store: AppStore = Depends(get_store)) -> dict[str, Any]:
    return _state(store)


@router.post("/active")
def switch_profile(payload: ProfileSwitch, store: AppStore = Depends(get_store)) -> dict[str, Any]:
    try:
        store.switch(payload.profile)
    except KeyError:
        raise not_found(f"Unknown profile {payload.profile!r}") from None
    return _state(store)
