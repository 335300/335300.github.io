"""Net worth, the accounts kept by hand, and the exchange rates."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, status

from ..models import Account, AccountInput, AccountValue, AccountValueInput, ExchangeRate, ExchangeRateInput
from ..services import net_worth, net_worth_history
from ..storage import Repository
from .deps import get_repository, get_today, not_found

router = APIRouter(prefix="/api", tags=["net worth"])


def _keep_snapshot(repo: Repository, today: date) -> None:
    """Every time net worth is worked out, this month's snapshot is kept current
    (only written when a figure changed), so later months can show its history."""
    if net_worth_history.upsert_snapshot(repo.data, today):
        repo.save()


def _view(repo: Repository, today: date) -> dict[str, Any]:
    _keep_snapshot(repo, today)
    return net_worth.build(repo.data, today)


def _account(repo: Repository, account_id: int) -> Account:
    for a in repo.data.accounts:
        if a.id == account_id:
            return a
    raise not_found(f"Account {account_id} not found")


@router.get("/net-worth")
def get_net_worth(repo: Repository = Depends(get_repository), today: date = Depends(get_today)) -> dict[str, Any]:
    return _view(repo, today)


@router.get("/net-worth/history")
def get_net_worth_history(repo: Repository = Depends(get_repository), today: date = Depends(get_today)) -> dict[str, Any]:
    """Month-end net worth for the last 12 months and where the change came from."""
    _keep_snapshot(repo, today)
    return net_worth_history.history(repo.data, today)


@router.post("/accounts", status_code=status.HTTP_201_CREATED)
def add_account(payload: AccountInput, repo: Repository = Depends(get_repository), today: date = Depends(get_today)) -> dict[str, Any]:
    repo.data.accounts.append(Account(id=repo.data.take_account_id(), **payload.model_dump()))
    repo.save()
    return _view(repo, today)


@router.put("/accounts/{account_id}")
def update_account(
    account_id: int, payload: AccountInput, repo: Repository = Depends(get_repository), today: date = Depends(get_today)
) -> dict[str, Any]:
    account = _account(repo, account_id)
    for key, value in payload.model_dump().items():
        setattr(account, key, value)
    repo.save()
    return _view(repo, today)


@router.delete("/accounts/{account_id}")
def delete_account(account_id: int, repo: Repository = Depends(get_repository), today: date = Depends(get_today)) -> dict[str, Any]:
    _account(repo, account_id)
    repo.data.accounts = [a for a in repo.data.accounts if a.id != account_id]
    repo.save()
    return _view(repo, today)


@router.post("/accounts/{account_id}/values")
def set_account_value(
    account_id: int, payload: AccountValueInput, repo: Repository = Depends(get_repository), today: date = Depends(get_today)
) -> dict[str, Any]:
    """Record what the account held on a day (replaces a value of the same day)."""
    account = _account(repo, account_id)
    account.values = [v for v in account.values if v.date != payload.date] + [AccountValue(**payload.model_dump())]
    repo.save()
    return _view(repo, today)


@router.delete("/accounts/{account_id}/values/{day}")
def delete_account_value(
    account_id: int, day: str, repo: Repository = Depends(get_repository), today: date = Depends(get_today)
) -> dict[str, Any]:
    account = _account(repo, account_id)
    before = len(account.values)
    account.values = [v for v in account.values if v.date != day]
    if len(account.values) == before:
        raise not_found(f"No value on {day}")
    repo.save()
    return _view(repo, today)


@router.post("/rates")
def set_rate(payload: ExchangeRateInput, repo: Repository = Depends(get_repository), today: date = Depends(get_today)) -> dict[str, Any]:
    """Record an exchange rate (replaces one of the same currency and day)."""
    repo.data.exchange_rates = [
        r for r in repo.data.exchange_rates if (r.currency, r.date) != (payload.currency, payload.date)
    ] + [ExchangeRate(**payload.model_dump())]
    repo.save()
    return _view(repo, today)


@router.delete("/rates/{currency}/{day}")
def delete_rate(currency: str, day: str, repo: Repository = Depends(get_repository), today: date = Depends(get_today)) -> dict[str, Any]:
    before = len(repo.data.exchange_rates)
    repo.data.exchange_rates = [r for r in repo.data.exchange_rates if (r.currency, r.date) != (currency, day)]
    if len(repo.data.exchange_rates) == before:
        raise not_found(f"No {currency} rate on {day}")
    repo.save()
    return _view(repo, today)
