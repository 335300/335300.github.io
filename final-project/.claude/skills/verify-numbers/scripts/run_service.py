#!/usr/bin/env python3
"""Run one Personal Centwise service function and print its result as JSON.

Used by the blind calculation verifier: it gets the service's answer without
reading the service's code.

Run it with the backend's Python (it needs pydantic):

    backend/.venv/bin/python .claude/skills/verify-numbers/scripts/run_service.py \\
        german_payroll.month_net --args '{"gross": 1800, "year": 2026}'

    # what the function expects (signature + its docstring only, no code):
    backend/.venv/bin/python .claude/skills/verify-numbers/scripts/run_service.py \\
        german_payroll.month_net --signature

Special values inside --args (JSON):

    {"$date": "2026-10-21"}                       -> datetime.date
    {"$appdata": "/tmp/pc-verify/fixture.json"}   -> models.AppData from a JSON file
    {"$model": "YearData", "value": {...}}        -> any class from app.models
    {"$model": "IncomePlan", "file": "/tmp/x.json"}

Fixture files must be synthetic and live in /tmp/ or backend/tests/fixtures/.
The data folder is pointed at a temp folder, so nothing real is ever opened.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import decimal
import importlib
import inspect
import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or HERE.parents[4]).resolve()
BACKEND = PROJECT / "backend"
ALLOWED_FIXTURE_ROOTS = [Path("/tmp").resolve(), Path(tempfile.gettempdir()).resolve(), (BACKEND / "tests" / "fixtures").resolve()]

os.environ["CENTWISE_DATA_DIR"] = tempfile.mkdtemp(prefix="pc-verify-")
os.environ.pop("CENTWISE_TOKEN", None)
sys.path.insert(0, str(BACKEND))


def fixture_path(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = PROJECT / p
    p = p.resolve()
    if not any(p == root or root in p.parents for root in ALLOWED_FIXTURE_ROOTS):
        sys.exit(f"Refusing fixture {p}: synthetic fixtures must be in /tmp/ or backend/tests/fixtures/.")
    return p


def decode(value):
    models = importlib.import_module("app.models")
    if isinstance(value, dict):
        if set(value) == {"$date"}:
            return dt.date.fromisoformat(value["$date"])
        if set(value) == {"$appdata"}:
            raw = json.loads(fixture_path(value["$appdata"]).read_text(encoding="utf-8"))
            return models.AppData.model_validate(raw)
        if "$model" in value:
            cls = getattr(models, value["$model"])
            if "file" in value:
                raw = json.loads(fixture_path(value["file"]).read_text(encoding="utf-8"))
            else:
                raw = value.get("value", {})
            return cls.model_validate(raw)
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def encode(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    if isinstance(obj, (dt.date, dt.datetime)):
        return obj.isoformat()
    if isinstance(obj, decimal.Decimal):
        return str(obj)
    if isinstance(obj, (set, tuple)):
        return list(obj)
    return str(obj)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="module.function inside app/services, e.g. german_payroll.month_net")
    ap.add_argument("--args", default="{}", help="keyword arguments as JSON")
    ap.add_argument("--signature", action="store_true", help="print the signature and docstring, do not run")
    ap.add_argument("--out", help="also write the JSON result to this file (in /tmp)")
    opts = ap.parse_args()

    module_name, _, func_name = opts.target.rpartition(".")
    if not module_name or "/" in opts.target:
        sys.exit("target must look like module.function, e.g. german_payroll.month_net")
    module = importlib.import_module(f"app.services.{module_name}")
    func = getattr(module, func_name)

    if opts.signature:
        print(f"{opts.target}{inspect.signature(func)}\n")
        print(inspect.getdoc(func) or "(no docstring)")
        return 0

    kwargs = decode(json.loads(opts.args))
    result = func(**kwargs)
    text = json.dumps(result, default=encode, indent=2, ensure_ascii=False, sort_keys=True)
    print(text)
    if opts.out:
        out = fixture_path(opts.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
