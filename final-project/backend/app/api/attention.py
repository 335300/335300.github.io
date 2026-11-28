"""The Overview's "Worth a look" banner and its "Move … from …" button."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Path, Query

from ..models import AttentionMoveInput, YearData
from ..services import attention, budget_links
from ..storage import AppStore, Repository
from .budgets import _fills_itself
from .deps import conflict, get_store, get_synced_repository, get_today, get_year

router = APIRouter(prefix="/api/{year}", tags=["attention"])

REASONS = {
    "nothing_needed": "Nothing needs to move: this budget is still on pace.",
    "no_room": "No other variable budget has enough room this month.",
    "fills_itself": "One of these budgets fills itself (it follows a plan). Change it in the budget plan.",
    "linked": "One of these budgets is linked to a % of income. Change it in the budget plan.",
}


def _locked(repo: Repository, store: AppStore, year: int, month: int, today: date) -> set[str]:
    """Variable categories whose budget box fills itself this month."""
    year_data = repo.year(year)
    return {
        c.name for c in year_data.categories.expense
        if c.kind == "variable" and _fills_itself(repo, store, year, "expense", c.name, month, today)
    }


def _view(repo: Repository, store: AppStore, year: int, month: int, today: date) -> dict[str, Any] | None:
    return attention.build(repo.data, year, month, today, _locked(repo, store, year, month, today))


@router.get("/attention")
def get_attention(
    year: int = Path(...),
    month: int = Query(..., ge=0, le=11),
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_synced_repository),
    store: AppStore = Depends(get_store),
    today: date = Depends(get_today),
) -> dict[str, Any] | None:
    """The banner for the month shown; ``null`` for any month but the current one."""
    return _view(repo, store, year, month, today)


@router.post("/attention/move")
def move_budget(
    payload: AttentionMoveInput,
    year: int = Path(...),
    year_data: YearData = Depends(get_year),
    repo: Repository = Depends(get_synced_repository),
    store: AppStore = Depends(get_store),
    today: date = Depends(get_today),
) -> dict[str, Any]:
    """Apply the banner's suggestion. Refused (409) unless it is still exactly
    what the banner offers now and both boxes are plain euro budgets."""
    view = _view(repo, store, year, payload.month, today)
    if view is None:
        raise conflict("Budgets can only be moved this way in the current month.")
    offered = (view["source"], view["category"], view["needed"])
    if offered != (payload.from_cat, payload.to_cat, payload.amount):
        raise conflict("The suggestion has changed. Look at the banner again.")
    if not view["can_move"]:
        raise conflict(REASONS.get(view["cannot_move_reason"], "This move is not possible."))
    values = attention.move_budget(year_data, payload.month, payload.from_cat, payload.to_cat, payload.amount)
    budget_links.sync(repo.data, today)
    repo.save()
    return {"budgets": values, "attention": _view(repo, store, year, payload.month, today)}
