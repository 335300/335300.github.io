"""Payee rules ("contains X → category Y") and the rules the app suggests."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status

from ..models import PayeeRule, PayeeRuleInput, RuleSuggestionDismiss
from ..services import payee_rules
from ..storage import Repository
from .deps import get_repository, not_found

router = APIRouter(prefix="/api/rules", tags=["rules"])


def _view(repo: Repository) -> dict[str, Any]:
    return {
        "rules": [r.model_dump() for r in repo.data.payee_rules],
        "suggestions": payee_rules.suggestions(repo.data),
    }


@router.get("")
def list_rules(repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    return _view(repo)


@router.post("", status_code=status.HTTP_201_CREATED)
def add_rule(payload: PayeeRuleInput, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    repo.data.payee_rules.append(PayeeRule(id=repo.data.take_rule_id(), **payload.model_dump()))
    repo.save()
    return _view(repo)


@router.put("/{rule_id}")
def update_rule(rule_id: int, payload: PayeeRuleInput, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    for i, rule in enumerate(repo.data.payee_rules):
        if rule.id == rule_id:
            repo.data.payee_rules[i] = PayeeRule(id=rule_id, **payload.model_dump())
            repo.save()
            return _view(repo)
    raise not_found(f"Rule {rule_id} not found")


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    before = len(repo.data.payee_rules)
    repo.data.payee_rules = [r for r in repo.data.payee_rules if r.id != rule_id]
    if len(repo.data.payee_rules) == before:
        raise not_found(f"Rule {rule_id} not found")
    repo.save()
    return _view(repo)


@router.post("/suggestions/dismiss")
def dismiss_suggestion(payload: RuleSuggestionDismiss, repo: Repository = Depends(get_repository)) -> dict[str, Any]:
    text = payee_rules.normalise(payload.contains)
    if text and text not in repo.data.dismissed_rule_suggestions:
        repo.data.dismissed_rule_suggestions.append(text)
        repo.save()
    return _view(repo)
