"""The yearly tax export and its commute settings."""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, Depends, Path

from ..models import TaxSettingsInput, YearData
from ..services import tax_export
from ..storage import Repository
from .deps import get_repository, get_year

router = APIRouter(prefix="/api/{year}/tax", tags=["tax"])


@router.get("")
def get_tax(year: int = Path(...), year_data: YearData = Depends(get_year), repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    return tax_export.build(repo.data, year)


@router.put("/settings")
def put_tax_settings(
    payload: TaxSettingsInput,
    year: int = Path(...),
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_repository),
) -> dict[str, Any]:
    year_data.commute_days, year_data.commute_km = payload.commute_days, payload.commute_km
    repo.save()
    return tax_export.build(repo.data, year)


@router.get("/file")
def get_tax_file(year: int = Path(...), year_data: YearData = Depends(get_year), repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    """The export as a CSV file, for the page to hand to the Save window."""
    content = tax_export.to_csv(tax_export.build(repo.data, year))
    return {"filename": f"{year}-tax-export.csv", "content_base64": base64.b64encode(content).decode()}
