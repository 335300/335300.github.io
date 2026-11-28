"""Transfer to Joint, the fair-share calculator, the settle-up balance and the
two Joint pages (Overview and Forecast)."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, status

from ..config import DEFAULT_PROFILE, JOINT_PROFILE
from ..models import FairShare, SettlementInput, Settlement, SharedExpense, SharedExpenseInput, TransferInput
from ..services import cashflow, forecast_ranges, joint
from ..storage import AppStore, Repository
from .deps import bad_request, get_repository, get_store, get_synced_repository, get_today, not_found, sync_joint_links

router = APIRouter(prefix="/api/joint", tags=["joint"])


@router.get("/household")
def get_household(
    year: int = Query(...),
    month: int = Query(..., ge=0, le=11),
    repo: Repository = Depends(get_synced_repository),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """The Joint Overview. Remembers the month, so the app reopens there."""
    data = repo.data
    if data.get_year(year) is None:
        raise not_found(f"Year {year} is not tracked yet")
    settings = data.settings
    if (settings.last_year, settings.last_month) != (year, month):
        settings.last_year, settings.last_month = year, month
        repo.save()
    return joint.household(data, year, month, today)


@router.get("/bill")
def get_bill(repo: Repository = Depends(get_synced_repository), today: date = Depends(get_today)) -> dict[str, Any]:
    """The Joint Forecast: the next 12 months of the shared plan, and who pays which part.
    ``ranges``: the 50 % / 80 % bands around the pot, or ``None`` with too little history."""
    body = joint.bill_forecast(repo.data, today)
    body["ranges"] = forecast_ranges.for_joint(body, repo.data, today)
    return body


def _view(repo: Repository, year: int | None, month: int | None) -> dict[str, Any]:
    data = repo.data
    shared_costs = None
    if year is not None and month is not None and data.get_year(year) is not None:
        shared_costs = cashflow.costs_yardstick(data, year, month)[0]
    return {
        "fair_share": joint.fair_share(data.fair_share, shared_costs),
        "settle_up": joint.settle_up(data.fair_share, data.shared_expenses, data.settlements),
    }


@router.get("")
def get_joint(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=0, le=11),
    repo: Repository = Depends(get_repository),
) -> dict[str, Any]:
    return _view(repo, year, month)


@router.put("/fair-share")
def put_fair_share(
    payload: FairShare,
    repo: Repository = Depends(get_repository),
    store: AppStore = Depends(get_store),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """New names rename each person's "From <name>" category; a new split
    moves both contributions and the Personal "Transfer to Joint" budget."""
    try:
        joint.rename_people(repo.data, payload)
    except joint.LinkError as exc:
        raise bad_request(str(exc)) from None
    repo.data.fair_share = payload
    repo.save()
    sync_joint_links(store, today)
    return _view(repo, None, None)


@router.post("/shared", status_code=status.HTTP_201_CREATED)
def add_shared(payload: SharedExpenseInput, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    repo.data.shared_expenses.append(SharedExpense(id=repo.data.take_shared_id(), **payload.model_dump()))
    repo.save()
    return _view(repo, None, None)


@router.delete("/shared/{item_id}")
def delete_shared(item_id: int, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    before = len(repo.data.shared_expenses)
    repo.data.shared_expenses = [e for e in repo.data.shared_expenses if e.id != item_id]
    if len(repo.data.shared_expenses) == before:
        raise not_found(f"Shared cost {item_id} not found")
    repo.save()
    return _view(repo, None, None)


@router.post("/settlements", status_code=status.HTTP_201_CREATED)
def add_settlement(payload: SettlementInput, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    repo.data.settlements.append(Settlement(id=repo.data.take_shared_id(), **payload.model_dump()))
    repo.save()
    return _view(repo, None, None)


@router.delete("/settlements/{item_id}")
def delete_settlement(item_id: int, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    before = len(repo.data.settlements)
    repo.data.settlements = [s for s in repo.data.settlements if s.id != item_id]
    if len(repo.data.settlements) == before:
        raise not_found(f"Settlement {item_id} not found")
    repo.save()
    return _view(repo, None, None)


@router.post("/transfer", status_code=status.HTTP_201_CREATED)
def transfer_to_joint(payload: TransferInput, store: AppStore = Depends(get_store)) -> dict[str, Any]:
    """Personal → Joint: writes one record in each profile, linked by an ID."""
    personal, shared = store.repo(DEFAULT_PROFILE), store.repo(JOINT_PROFILE)
    with personal.lock, shared.lock:
        try:
            result = joint.transfer(personal.data, shared.data, payload)
        except joint.LinkError as exc:
            raise bad_request(str(exc)) from None
        personal.save()
        shared.save()
    return result
