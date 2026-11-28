"""Savings goals and their contributions."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import ValidationError

from ..config import JOINT_PROFILE
from ..models import Contribution, ContributionInput, GoalInput, GoalPatch, PayFromFundInput, SavingsGoal
from ..services import goals as goals_service
from ..services import joint, projection, rolling_forecast, sinking
from ..storage import AppStore, Repository
from .deps import bad_request, get_repository, get_store, get_synced_repository, get_today, not_found

router = APIRouter(prefix="/api/goals", tags=["goals"])


def _forecast_summary(repo: Repository, year: int | None) -> tuple[dict[str, Any] | None, int | None]:
    """The chosen year's forecast summary (None if that year does not exist)."""
    data = repo.data
    if year is None:
        year = data.settings.last_year or (max(data.year_numbers()) if data.year_numbers() else None)
    year_data = data.get_year(year) if year is not None else None
    if year_data is None:
        return None, year
    return projection.build(year_data, year)["summary"], year


def _only_emergency_fund(repo: Repository, goal_id: int) -> None:
    """Only one goal can be the emergency fund: marking one unmarks the rest."""
    for g in repo.data.goals:
        if g.id != goal_id:
            g.emergency_fund = False


def _goal(repo: Repository, goal_id: int) -> SavingsGoal:
    goal = repo.data.find_goal(goal_id)
    if goal is None:
        raise not_found(f"Goal {goal_id} not found")
    return goal


@router.get("")
def list_goals(
    year: int | None = Query(default=None),
    repo: Repository = Depends(get_synced_repository),
    store: AppStore = Depends(get_store),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    summary, used_year = _forecast_summary(repo, year)
    if store.active == JOINT_PROFILE:
        # Shared goals are part of the shared plan: each person pays in their
        # part of every goal's monthly pace, so goals count on that.
        expected = joint.goal_saving(repo.data, (today.year, today.month - 1), today)
        checks = joint.goal_checks(repo.data, today)
    else:
        # Goals look ahead, so they count on the rolling 12-month forecast.
        expected = rolling_forecast.expected_monthly_savings(repo.data)
        checks = rolling_forecast.goal_checks(repo.data)
    saved = summary["actual_savings"] if summary else 0.0
    built = goals_service.build_all(repo.data.goals, expected, today)
    for g in built["goals"]:
        g["forecast"] = checks.get(g["id"])
    return {
        "year": used_year,
        **built,
        "allocation": goals_service.allocation(repo.data.goals, saved, used_year or today.year),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalInput,
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    if payload.goal_type == "sinking" and payload.repeat_months is None:
        raise bad_request("A sinking fund needs to say how often the bill comes back.")
    goal = SavingsGoal(
        id=repo.data.take_goal_id(),
        name=payload.name.strip(),
        target_amount=payload.target_amount,
        target_date=payload.target_date,
        created_date=today.isoformat(),
        notes=payload.notes,
        emergency_fund=payload.emergency_fund,
        goal_type=payload.goal_type,
        repeat_months=payload.repeat_months if payload.goal_type == "sinking" else None,
        spend_in_forecast=payload.spend_in_forecast,
    )
    if goal.emergency_fund:
        _only_emergency_fund(repo, goal.id)
    repo.data.goals.append(goal)
    repo.save()
    return goal.model_dump()


@router.patch("/{goal_id}")
def update_goal(goal_id: int, payload: GoalPatch, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    goal = _goal(repo, goal_id)
    changes = payload.model_dump(exclude_none=True)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    # Validate the edited copy first, so a bad edit never touches the stored goal.
    merged = {**goal.model_dump(), **changes}
    if merged["goal_type"] == "one_time":
        merged["repeat_months"] = None
    try:
        updated = SavingsGoal.model_validate(merged)
    except ValidationError as exc:
        raise bad_request(exc.errors()[0]["msg"].removeprefix("Value error, ")) from None
    repo.data.goals = [updated if g.id == goal_id else g for g in repo.data.goals]
    if updated.emergency_fund:
        _only_emergency_fund(repo, goal_id)
    repo.save()
    return updated.model_dump()


@router.delete("/{goal_id}")
def delete_goal(goal_id: int, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    _goal(repo, goal_id)
    repo.data.goals = [g for g in repo.data.goals if g.id != goal_id]
    repo.save()
    return {"deleted": goal_id}


@router.post("/{goal_id}/contributions", status_code=status.HTTP_201_CREATED)
def add_contribution(
    goal_id: int, payload: ContributionInput, repo: Repository = Depends(get_repository)
) -> dict[str, Any]:
    goal = _goal(repo, goal_id)
    contribution = Contribution(id=goal.take_contribution_id(), **payload.model_dump())
    goal.contributions.append(contribution)
    repo.save()
    return contribution.model_dump()


@router.delete("/{goal_id}/contributions/{contribution_id}")
def delete_contribution(
    goal_id: int, contribution_id: int, repo: Repository = Depends(get_repository)
) -> dict[str, Any]:
    goal = _goal(repo, goal_id)
    before = len(goal.contributions)
    goal.contributions = [c for c in goal.contributions if c.id != contribution_id]
    if len(goal.contributions) == before:
        raise not_found(f"Contribution {contribution_id} not found")
    repo.save()
    return {"deleted": contribution_id}


@router.post("/{goal_id}/pay")
def pay_from_fund(goal_id: int, payload: PayFromFundInput, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    """Pay a sinking fund's bill: the expense, the money out of the fund, the next due date."""
    goal = _goal(repo, goal_id)
    try:
        result = sinking.pay_from_fund(repo.data, goal, payload)
    except sinking.FundError as exc:
        raise bad_request(str(exc)) from None
    repo.save()
    return result
