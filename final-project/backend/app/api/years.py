"""Years, the first-run setup, and each year's starting point."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, status

from ..config import MONTHS, STARTER_CATEGORIES
from ..models import Category, SetupInput, YearData, YearInput, YearPatch
from ..services import aggregation, budget_links
from ..storage import Repository
from .deps import conflict, get_repository, get_today, not_found

router = APIRouter(prefix="/api", tags=["years"])


def _describe(repo: Repository, year_num: int) -> dict[str, Any]:
    year = repo.year(year_num)
    recorded = aggregation.last_recorded_month(year)
    return {
        "year": year_num,
        "transactions": len(year.transactions),
        "opening_balance": year.opening_balance,
        "closing_balance": aggregation.closing_balance(year),
        "start_month": year.start_month,
        "last_recorded_month": recorded if recorded >= 0 else None,
    }


@router.get("/years")
def list_years(
    repo: Repository = Depends(get_repository), today: date = Depends(get_today)
) -> dict[str, Any]:
    """``needs_setup`` is true on first run, before any year exists."""
    numbers = repo.data.year_numbers()
    return {
        "years": [_describe(repo, y) for y in numbers],
        "needs_setup": not numbers,
        "settings": repo.data.settings.model_dump(),
        "months": MONTHS,
        "current_year": today.year,
        "current_month": today.month - 1,
        "today": today.isoformat(),
    }


@router.post("/setup", status_code=status.HTTP_201_CREATED)
def first_run_setup(payload: SetupInput, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    """Create the first year with its starting balance and, optionally, starter categories."""
    if repo.data.year_numbers():
        raise conflict("Already set up")
    year = YearData(opening_balance=payload.opening_balance, start_month=payload.start_month)
    if payload.starter_categories:
        for kind, items in STARTER_CATEGORIES.items():
            for name, cat_kind in items:
                getattr(year.categories, kind).append(Category(name=name, kind=cat_kind))
                getattr(year.budgets, kind)[name] = [0.0] * 12
    repo.data.years[str(payload.year)] = year
    repo.data.settings.last_year = payload.year
    repo.save()
    return _describe(repo, payload.year)


@router.post("/years", status_code=status.HTTP_201_CREATED)
def create_year(
    payload: YearInput, repo: Repository = Depends(get_repository), today: date = Depends(get_today)
) -> dict[str, Any]:
    """Add a year, carrying the latest earlier year's plan and closing balance forward."""
    if repo.data.get_year(payload.year) is not None:
        raise conflict(f"Year {payload.year} already exists")
    copy_from = payload.copy_from
    if copy_from is None:
        earlier = [y for y in repo.data.year_numbers() if y < payload.year]
        copy_from = max(earlier) if earlier else None
    elif repo.data.get_year(copy_from) is None:
        raise not_found(f"Cannot copy from year {copy_from} — it is not tracked")
    repo.ensure_year(payload.year, copy_from=copy_from)
    # Copied % links and the salary from the calendar follow the new year's income.
    if budget_links.sync(repo.data, today):
        repo.save()
    return {"created": _describe(repo, payload.year), "copied_from": copy_from}


@router.patch("/years/{year}")
def update_year(
    year: int, payload: YearPatch, repo: Repository = Depends(get_repository)
) -> dict[str, Any]:
    data = repo.data.get_year(year)
    if data is None:
        raise not_found(f"Year {year} is not tracked yet")
    if payload.start_month is not None:
        first_tx = min((t.month for t in data.transactions), default=12)
        if payload.start_month >= first_tx:
            raise conflict(
                f"There are transactions in {MONTHS[first_tx]}, so tracking must start "
                f"in {MONTHS[first_tx]} or earlier."
            )
        data.start_month = payload.start_month
    if payload.opening_balance is not None:
        data.opening_balance = round(payload.opening_balance, 2)
    repo.save()
    return _describe(repo, year)
