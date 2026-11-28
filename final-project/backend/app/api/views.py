"""Read-only composite endpoints: the Overview payload and the Forecast."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Path, Query

from ..models import YearData
from ..services import dashboard, projection
from ..storage import Repository
from .deps import get_repository, get_synced_repository, get_today, get_year

router = APIRouter(prefix="/api/{year}", tags=["views"])


@router.get("/dashboard")
def get_dashboard(
    year: int = Path(...),
    month: int = Query(..., ge=0, le=11),
    repo: Repository = Depends(get_synced_repository),
    year_data: YearData = Depends(get_year),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """Remembering the view here means the app reopens where the user left it."""
    settings = repo.data.settings
    if (settings.last_year, settings.last_month) != (year, month):
        settings.last_year, settings.last_month = year, month
        repo.save()
    return dashboard.build(repo.data, year, month, today)


@router.get("/projection")
def get_projection(year: int = Path(...), year_data: YearData = Depends(get_year)) -> dict[str, Any]:
    return projection.build(year_data, year)
