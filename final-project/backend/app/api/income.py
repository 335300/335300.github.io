"""Income calendar settings, payslips, and the rolling 12-month forecast."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, status

from ..config import FORECAST_MONTHS
from ..models import IncomePlan, IncomeSettings, Payslip, PayslipInput, TypedHoursInput, Vacation, VacationInput
from ..services import budget_links, forecast_ranges, income_calendar, rolling_forecast
from ..storage import Repository
from .deps import bad_request, get_repository, get_synced_repository, get_today, not_found

router = APIRouter(prefix="/api", tags=["income"])


def _plan(repo: Repository) -> IncomePlan:
    """The profile's income plan, created empty on first use."""
    if repo.data.income_plan is None:
        repo.data.income_plan = IncomePlan()
    return repo.data.income_plan


def _view(repo: Repository, today: date) -> dict[str, Any]:
    plan = repo.data.income_plan
    if plan is None:
        return {"plan": None, "calendar": None, "active": False}
    ends = [(s.name, date.fromisoformat(s.job_end)) for s in plan.scenarios]
    return {
        "plan": plan.model_dump(),
        "calendar": income_calendar.calendar_view(
            plan, plan.payslips, income_calendar.ym_of(today), FORECAST_MONTHS, ends
        ),
        "active": rolling_forecast.calendar_active(plan),
    }


@router.get("/income")
def get_income(repo: Repository = Depends(get_repository), today: date = Depends(get_today)) -> dict[str, Any]:
    return _view(repo, today)


@router.put("/income/settings")
def put_income_settings(
    payload: IncomeSettings,
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """Replace the calendar settings; the payslips, typed hours and vacations stay
    (they have their own endpoints)."""
    plan = _plan(repo)
    repo.data.income_plan = IncomePlan(
        **payload.model_dump(exclude={"hours_typed", "vacations"}),
        hours_typed=plan.hours_typed, vacations=plan.vacations,
        payslips=plan.payslips, next_payslip_id=plan.next_payslip_id,
    )
    budget_links.sync(repo.data, today)
    repo.save()
    return _view(repo, today)


@router.post("/income/payslips", status_code=status.HTTP_201_CREATED)
def add_payslip(
    payload: PayslipInput,
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    plan = _plan(repo)
    plan.payslips.append(Payslip(id=plan.take_payslip_id(), **payload.model_dump()))
    plan.payslips.sort(key=lambda p: (p.month, p.id))
    budget_links.sync(repo.data, today)
    repo.save()
    return _view(repo, today)


@router.delete("/income/payslips/{payslip_id}")
def delete_payslip(
    payslip_id: int,
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    plan = repo.data.income_plan
    if plan is None or not any(p.id == payslip_id for p in plan.payslips):
        raise not_found(f"Payslip {payslip_id} not found")
    plan.payslips = [p for p in plan.payslips if p.id != payslip_id]
    budget_links.sync(repo.data, today)
    repo.save()
    return _view(repo, today)


@router.put("/income/hours/{month}")
def set_typed_hours(
    month: str,
    payload: TypedHoursInput,
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """Type the hours worked in a month of work (``YYYY-MM``); ``null`` goes back to the calendar's hours."""
    try:
        key = date.fromisoformat(f"{month}-01").isoformat()[:7]
    except ValueError:
        raise bad_request("The month must look like YYYY-MM.") from None
    plan = _plan(repo)
    if payload.hours is None:
        plan.hours_typed.pop(key, None)
    else:
        plan.hours_typed[key] = round(payload.hours, 2)
    budget_links.sync(repo.data, today)
    repo.save()
    return _view(repo, today)


@router.post("/income/vacations", status_code=status.HTTP_201_CREATED)
def add_vacation(
    payload: VacationInput,
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    plan = _plan(repo)
    if len(plan.vacations) >= 60:
        raise bad_request("At most 60 vacations.")
    new_id = max((v.id for v in plan.vacations), default=0) + 1
    plan.vacations.append(Vacation(id=new_id, **payload.model_dump()))
    plan.vacations.sort(key=lambda v: (v.start, v.id))
    budget_links.sync(repo.data, today)
    repo.save()
    return _view(repo, today)


@router.delete("/income/vacations/{vacation_id}")
def delete_vacation(
    vacation_id: int,
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    plan = repo.data.income_plan
    if plan is None or not any(v.id == vacation_id for v in plan.vacations):
        raise not_found(f"Vacation {vacation_id} not found")
    plan.vacations = [v for v in plan.vacations if v.id != vacation_id]
    budget_links.sync(repo.data, today)
    repo.save()
    return _view(repo, today)


@router.get("/forecast")
def get_forecast(
    goals: bool = True, repo: Repository = Depends(get_synced_repository), today: date = Depends(get_today)
) -> dict[str, Any]:
    """The rolling forecast: the next 12 months, one line per scenario.
    ``goals=false`` leaves goal purchases out, to compare. ``ranges``: the 50 % /
    80 % bands around the first line, or ``None`` with too little history."""
    # Budgets that follow the calendar, an investment plan or a % of income
    # may have moved since (a new payment, a new month): bring them up to date.
    if budget_links.sync(repo.data, today):
        repo.save()
    body = rolling_forecast.build(repo.data, include_goals=goals)
    body["ranges"] = forecast_ranges.for_rolling(body, repo.data, today)
    return body
