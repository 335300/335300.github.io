"""Transactions CRUD, including the bulk "add multiple" path."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Path, Query, status

from ..models import BulkTransactionInput, Category, Transaction, TransactionInput, TxType, YearData
from ..config import PROFILES
from ..services import aggregation, joint, sinking
from ..storage import AppStore, Repository
from .deps import bad_request, get_repository, get_store, get_year, not_found

router = APIRouter(prefix="/api/{year}/transactions", tags=["transactions"])


def _ensure_category(year_data: YearData, kind: TxType, name: str) -> None:
    """Register an unseen category so it is immediately budgetable."""
    if year_data.find_category(kind, name) is None:
        getattr(year_data.categories, kind).append(Category(name=name))
        getattr(year_data.budgets, kind).setdefault(name, [0.0] * 12)


def _installments(repo: Repository, item: TransactionInput, default: int | None) -> int | None:
    """How many instalments of an investment plan a payment covers.

    Only payments into a plan's category carry a count. When the caller leaves
    it out, a *new* payment counts as one instalment (``default=1``); an edit
    keeps whatever was sent (``default=None``).
    """
    if item.type != "expense" or repo.data.investment_for_category(item.cat) is None:
        return None
    return default if item.installments is None else item.installments


def _other_repo(store: AppStore) -> Repository:
    """The profile that holds the other half of a "Transfer to Joint"."""
    return store.repo(next(p for p in PROFILES if p != store.active))


def _build(
    year_num: int,
    tx_id: int,
    item: TransactionInput,
    row: int | None = None,
    installments: int | None = None,
) -> Transaction:
    """Turn an input into a stored transaction; the month comes from the date."""
    d = date.fromisoformat(item.date)
    if d.year != year_num:
        where = f"Row {row + 1}: " if row is not None else ""
        raise bad_request(f"{where}the date {item.date} is not in {year_num}.")
    fields = {**item.model_dump(), "installments": installments}
    return Transaction(id=tx_id, month=d.month - 1, **fields)


@router.get("")
def list_transactions(
    year_data: YearData = Depends(get_year),
    type: TxType | None = Query(default=None),
    month: int | None = Query(default=None, ge=0, le=11),
    cat: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Search description and category"),
) -> dict[str, Any]:
    rows = year_data.transactions
    if type is not None:
        rows = [t for t in rows if t.type == type]
    if month is not None:
        rows = [t for t in rows if t.month == month]
    if cat:
        rows = [t for t in rows if t.cat == cat]
    if q:
        needle = q.strip().lower()
        rows = [t for t in rows if needle in t.desc.lower() or needle in t.cat.lower()]
    rows = sorted(rows, key=lambda t: (t.date, t.id), reverse=True)
    return {
        "transactions": [t.model_dump() for t in rows],
        "count": len(rows),
        "total_expense": round(sum(t.amount for t in rows if t.type == "expense"), 2),
        "total_income": round(sum(t.amount for t in rows if t.type == "income"), 2),
        "days": aggregation.day_totals(rows),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionInput,
    year: int = Path(...),
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_repository),
) -> dict[str, Any]:
    tx = _build(year, year_data.next_id, payload, installments=_installments(repo, payload, default=1))
    year_data.take_id()
    _ensure_category(year_data, payload.type, payload.cat)
    year_data.transactions.append(tx)
    repo.save()
    return tx.model_dump()


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def create_transactions(
    payload: BulkTransactionInput,
    year: int = Path(...),
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_repository),
) -> dict[str, Any]:
    """Add many rows in one shot — all or nothing.

    Every row is validated before anything is appended, so a bad row in the
    middle cannot leave a half-saved batch behind.
    """
    created = [
        _build(year, year_data.next_id + i, item, row=i, installments=_installments(repo, item, default=1))
        for i, item in enumerate(payload.transactions)
    ]
    year_data.next_id += len(created)
    for item in payload.transactions:
        _ensure_category(year_data, item.type, item.cat)
    year_data.transactions.extend(created)
    repo.save()
    return {"created": [t.model_dump() for t in created], "count": len(created)}


@router.put("/{tx_id}")
def update_transaction(
    tx_id: int,
    payload: TransactionInput,
    year: int = Path(...),
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_repository),
    store: AppStore = Depends(get_store),
) -> dict[str, Any]:
    for index, existing in enumerate(year_data.transactions):
        if existing.id == tx_id:
            updated = _build(year, tx_id, payload, installments=_installments(repo, payload, default=None))
            if existing.link_id:
                # The other half of a transfer gets the same date and amount.
                other = _other_repo(store)
                try:
                    joint.update_linked(other.data, existing.link_id, updated.date, updated.amount)
                except joint.LinkError as exc:
                    raise bad_request(str(exc)) from None
                other.save()
            # What the bank import recorded stays attached through an edit.
            updated.payee, updated.bank_ref = existing.payee, existing.bank_ref
            updated.link_id = existing.link_id
            _ensure_category(year_data, payload.type, payload.cat)
            year_data.transactions[index] = updated
            repo.save()
            return updated.model_dump()
    raise not_found(f"Transaction {tx_id} not found")


@router.delete("/{tx_id}")
def delete_transaction(
    tx_id: int,
    year: int = Path(...),
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_repository),
    store: AppStore = Depends(get_store),
) -> dict[str, Any]:
    target = next((t for t in year_data.transactions if t.id == tx_id), None)
    if target is None:
        raise not_found(f"Transaction {tx_id} not found")
    year_data.transactions = [t for t in year_data.transactions if t.id != tx_id]
    if target.link_id:
        # Deleting one half of a transfer deletes the other half too.
        other = _other_repo(store)
        if joint.delete_linked(other.data, target.link_id):
            other.save()
    # A bill paid from a sinking fund gives the money back to the fund.
    sinking.drop_withdrawals_for(repo.data, year, tx_id)
    repo.save()
    return {"deleted": tx_id}
