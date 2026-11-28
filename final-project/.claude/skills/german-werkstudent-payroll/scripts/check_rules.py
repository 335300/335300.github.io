#!/usr/bin/env python3
"""Compare the app's payroll values with this skill's reference values.

    python3 .claude/skills/german-werkstudent-payroll/scripts/check_rules.py

Reads ``backend/app/config.py`` (without starting the app) and
``reference/values.json``, then prints a Markdown table:

    year | key | app | reference | status | result

Results: MATCH, DIFF, MISSING IN APP, YEAR NOT IN APP (the app then uses the
latest listed year), NO REFERENCE. Exit code 1 when a FINAL reference value
differs from the app or is missing for a year the app lists; otherwise 0.

Standard library only. Reads no real data.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SKILL = HERE.parents[1]
PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or HERE.parents[4])


def load_config():
    path = PROJECT / "backend" / "app" / "config.py"
    spec = importlib.util.spec_from_file_location("centwise_config", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def same(a, b) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return a == b


def main() -> int:
    ref = json.loads((SKILL / "reference" / "values.json").read_text(encoding="utf-8"))
    cfg = load_config()
    app_rules = cfg.PAYROLL_RULES
    bad = 0
    rows = []

    for year, keys in sorted(ref["payroll_rules"].items()):
        y = int(year)
        app_year = app_rules.get(y)
        for key, item in keys.items():
            value, status = item.get("value"), item.get("status", "?")
            if app_year is None:
                result = "YEAR NOT IN APP"
                app_value = "-"
            elif key not in app_year:
                app_value = "-"
                result = "MISSING IN APP"
                if status == "FINAL":
                    bad += 1
            else:
                app_value = app_year[key]
                if value is None:
                    result = "NO REFERENCE"
                elif same(app_value, value):
                    result = "MATCH"
                else:
                    result = "DIFF"
                    if status == "FINAL":
                        bad += 1
            rows.append((year, key, app_value, "-" if value is None else value, status, result))

    for name, years in ref.get("other_config", {}).items():
        app_value = getattr(cfg, name, "-")
        for year, item in sorted(years.items()):
            value, status = item.get("value"), item.get("status", "?")
            if isinstance(app_value, dict):
                current = app_value.get(int(year), "-")
            else:
                current = app_value  # one value for every year
            result = "MATCH" if same(current, value) else "DIFF"
            if result == "DIFF" and status == "FINAL" and not isinstance(app_value, dict) and int(year) > max(app_rules):
                result = "DIFF (app has one value for all years)"
            elif result == "DIFF" and status == "FINAL":
                bad += 1
            rows.append((year, name, current, value, status, result))

    print(f"Reference verified on: {ref.get('verified_on')}")
    print(f"Years in app PAYROLL_RULES: {sorted(app_rules)} (later years fall back to {max(app_rules)})\n")
    print("| year | key | app | reference | status | result |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")
    print()
    if bad:
        print(f"FAIL: {bad} FINAL value(s) differ from the app or are missing.")
        return 1
    print("OK: every FINAL reference value matches the app (drafts and open values are listed above).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
