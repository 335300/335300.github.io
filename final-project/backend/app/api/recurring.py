"""Recurring bills, the bills the app suggests, and what is due soon."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Path, status

from ..models import BillSuggestionDismiss, RecurringBill, RecurringBillInput
from ..services import recurring
from ..services.payee_rules import normalise
from ..storage import Repository
from .deps import bad_request, get_repository, get_today, not_found

router = APIRouter(prefix="/api/bills", tags=["bills"])


def _view(repo: Repository, today: date) -> dict[str, Any]:
    data = repo.data
    return {
        "bills": [recurring.bill_view(data, b) for b in data.recurring_bills],
        "suggestions": recurring.suggestions(data, today),
        "upcoming": recurring.upcoming(data, today),
    }


def _check_goal(repo: Repository, payload: RecurringBillInput) -> None:
    if payload.goal_id is not None and repo.data.find_goal(payload.goal_id) is None:
        raise bad_request(f"Goal {payload.goal_id} not found")


@router.get("")
def list_bills(repo: Repository = Depends(get_repository), today: date = Depends(get_today)) -> dict[str, Any]:
    return _view(repo, today)


@router.get("/calendar/{year}/{month}")
def bills_calendar(
    year: int = Path(ge=2000, le=2100),
    month: int = Path(ge=0, le=11),
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """Bills and goal deadlines of one month, for the Overview calendar."""
    return recurring.month_calendar(repo.data, year, month, today)


@router.post("", status_code=status.HTTP_201_CREATED)
def add_bill(
    payload: RecurringBillInput, repo: Repository = Depends(get_repository), today: date = Depends(get_today)
) -> dict[str, Any]:
    _check_goal(repo, payload)
    repo.data.recurring_bills.append(RecurringBill(id=repo.data.take_bill_id(), **payload.model_dump()))
    repo.save()
    return _view(repo, today)


@router.put("/{bill_id}")
def update_bill(
    bill_id: int,
    payload: RecurringBillInput,
    repo: Repository = Depends(get_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    _check_goal(repo, payload)
    for i, bill in enumerate(repo.data.recurring_bills):
        if bill.id == bill_id:
            repo.data.recurring_bills[i] = RecurringBill(id=bill_id, **payload.model_dump())
            repo.save()
            return _view(repo, today)
    raise not_found(f"Bill {bill_id} not found")


@router.delete("/{bill_id}")
def delete_bill(bill_id: int, repo: Repository = Depends(get_repository), today: date = Depends(get_today)) -> dict[str, Any]:
    before = len(repo.data.recurring_bills)
    repo.data.recurring_bills = [b for b in repo.data.recurring_bills if b.id != bill_id]
    if len(repo.data.recurring_bills) == before:
        raise not_found(f"Bill {bill_id} not found")
    repo.save()
    return _view(repo, today)


@router.post("/suggestions/dismiss")
def dismiss_bill_suggestion(
    payload: BillSuggestionDismiss, repo: Repository = Depends(get_repository), today: date = Depends(get_today)
) -> dict[str, Any]:
    key = normalise(payload.key)
    if key and key not in repo.data.dismissed_bill_suggestions:
        repo.data.dismissed_bill_suggestions.append(key)
        repo.save()
    return _view(repo, today)
