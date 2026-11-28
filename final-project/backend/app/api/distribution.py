"""Distributing a month's savings across goals in one go."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Path, status

from ..config import MONTHS
from ..models import Contribution, DistributionInput, YearData
from ..services import cashflow
from ..storage import Repository
from .deps import conflict, get_repository, get_today, get_year, not_found

router = APIRouter(prefix="/api/{year}/distribution", tags=["distribution"])


def _check(repo: Repository, payload: DistributionInput) -> list[tuple[Any, float]]:
    """Resolve the goals and drop empty rows."""
    wanted = []
    for item in payload.allocations:
        goal = repo.data.find_goal(item.goal_id)
        if goal is None:
            raise not_found(f"Goal {item.goal_id} not found")
        if item.amount > 0:
            if goal.status != "active":
                raise conflict(f"{goal.name!r} is not an active goal")
            wanted.append((goal, round(item.amount, 2)))
    return wanted


def _summary(repo: Repository, year_data: YearData, year: int, month: int, adding: float) -> dict[str, Any]:
    spread = cashflow.distribution(year_data, year, month, repo.data.goals)
    left_after = round(spread["saved"] - spread["to_goals"] - adding, 2)
    return {
        "month": month,
        "saved": spread["saved"],
        "to_goals": spread["to_goals"],
        "left_to_assign": spread["left_to_assign"],
        "adding": round(adding, 2),
        "left_after": left_after,
        "over": left_after < 0,
    }


@router.post("/preview")
def preview_distribution(
    payload: DistributionInput,
    year: int = Path(...),
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_repository),
) -> dict[str, Any]:
    """What would be left of the month's savings — nothing is saved."""
    wanted = _check(repo, payload)
    return _summary(repo, year_data, year, payload.month, sum(amount for _, amount in wanted))


@router.post("", status_code=status.HTTP_201_CREATED)
def apply_distribution(
    payload: DistributionInput,
    year: int = Path(...),
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """Add one contribution per goal, dated in the month being distributed.

    The date is the month's last day, or today while the month is still running,
    so the money shows up under that month. Assigning more than the month saved
    is allowed (money from the existing balance) — the preview warns about it.
    """
    if date(year, payload.month + 1, 1) > today:
        raise conflict(f"{MONTHS[payload.month]} {year} has not started yet")
    wanted = _check(repo, payload)
    if not wanted:
        raise conflict("Nothing to assign — enter an amount for at least one goal")
    when = min(today, cashflow.month_end(year, payload.month)).isoformat()
    note = f"{MONTHS[payload.month]} {year} distribution"
    for goal, amount in wanted:
        goal.contributions.append(
            Contribution(id=goal.take_contribution_id(), date=when, amount=amount, note=note)
        )
    repo.save()
    return {**_summary(repo, year_data, year, payload.month, 0.0), "assigned": len(wanted), "date": when}
