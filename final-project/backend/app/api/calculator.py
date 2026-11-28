"""The pocket calculator shown on every tab."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from ..services import calculator
from .deps import bad_request

router = APIRouter(prefix="/api/calc", tags=["calculator"])


class CalcInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expression: str = Field(max_length=400)


@router.post("")
def calculate(payload: CalcInput) -> dict[str, Any]:
    """Arithmetic only — nothing is read from or written to the data."""
    try:
        return calculator.evaluate(payload.expression)
    except calculator.CalculatorError as exc:
        raise bad_request(str(exc)) from None
