"""FastAPI application factory."""

from __future__ import annotations

from fastapi import Depends, FastAPI

from . import __version__
from .api import (
    attention,
    budgets,
    calculator,
    calendar,
    data_safety,
    distribution,
    goals,
    imports,
    income,
    investments,
    joint,
    net_worth,
    prefs,
    profiles,
    recurring,
    rules,
    tax,
    transactions,
    views,
    years,
)
from .api.deps import require_token, set_store
from .config import APP_NAME, BUDGET_WARNING_PCT, CURRENCY, CURRENCY_SYMBOL, MONTHS, SCHEMA_VERSION
from .storage import AppStore


def create_app(store: AppStore | None = None) -> FastAPI:
    set_store(store or AppStore())

    app = FastAPI(
        title=APP_NAME,
        version=__version__,
        docs_url="/docs",
        # The Electron shell is the only client; no CORS middleware is added,
        # so a stray browser tab cannot call this even if it knows the port.
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, object]:
        """Unauthenticated, so the Electron shell can poll for readiness."""
        return {
            "status": "ok",
            "app": APP_NAME,
            "version": __version__,
            "schema_version": SCHEMA_VERSION,
            "currency": CURRENCY,
            "currency_symbol": CURRENCY_SYMBOL,
            "months": MONTHS,
            "budget_warning_pct": BUDGET_WARNING_PCT,
        }

    guarded = [Depends(require_token)]
    for module in (
        profiles, prefs, years, transactions, budgets, views, goals, investments, distribution, calculator,
        income, imports, rules, recurring, joint, tax, data_safety, net_worth, calendar, attention,
    ):
        app.include_router(module.router, dependencies=guarded)
    return app
