#!/usr/bin/env python3
"""Compare the verifier's expected figures with the service's output.

    python3 .claude/skills/verify-numbers/scripts/compare.py expected.json actual.json [--abs 0.01] [--pct 0]

- Only the fields in ``expected.json`` are checked (the verifier may compute a
  subset). Nested dicts and lists are compared field by field ("a.b[2].c").
- Numbers pass when |expected − actual| <= --abs (default 0.01 euro).
  For forecasts or estimates, add --pct 1 (1 % of the expected value) and
  explain why in the report.
- Text and true/false must be equal.

Prints a Markdown table and exits 1 if any field fails. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys


def flatten(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from flatten(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expected")
    ap.add_argument("actual")
    ap.add_argument("--abs", type=float, default=0.01, dest="abs_tol")
    ap.add_argument("--pct", type=float, default=0.0)
    o = ap.parse_args()

    expected = dict(flatten(json.load(open(o.expected, encoding="utf-8"))))
    actual = dict(flatten(json.load(open(o.actual, encoding="utf-8"))))
    fails = 0
    print("| field | expected | service | diff | result |")
    print("|---|---|---|---|---|")
    for key, exp in expected.items():
        if key not in actual:
            fails += 1
            print(f"| {key} | {exp} | (missing) | - | FAIL |")
            continue
        act = actual[key]
        if is_number(exp) and is_number(act):
            diff = act - exp
            limit = max(o.abs_tol, abs(exp) * o.pct / 100)
            ok = abs(diff) <= limit + 1e-12
            shown = f"{diff:+.4f}"
        else:
            ok = exp == act
            shown = "-" if ok else "differs"
        fails += 0 if ok else 1
        print(f"| {key} | {exp} | {act} | {shown} | {'PASS' if ok else 'FAIL'} |")
    total = len(expected)
    print(f"\n{total - fails} of {total} fields PASS (abs {o.abs_tol}, pct {o.pct}).")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
