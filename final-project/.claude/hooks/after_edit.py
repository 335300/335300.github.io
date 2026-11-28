#!/usr/bin/env python3
"""PostToolUse hook: check the code right after Claude edits it.

- A Python file under ``backend/`` changed  -> run the backend tests
  (``pytest -x -q``) against a throwaway data folder.
- A TypeScript file under ``frontend/src/`` changed -> run the type check
  (``tsc --noEmit``).

Exit 0 = fine. Exit 2 = something broke; the last lines of the output go back
to Claude so it can fix the problem straight away. (The edit itself is not
undone — this hook only reports.)

Standard library only, Python 3.9+.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SKIP_PARTS = {".venv", "build", "dist", "node_modules", "__pycache__", ".pytest_cache"}
TAIL_LINES = 60


def tail(text: str, n: int = TAIL_LINES) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-n:])


def run(cmd: list[str], cwd: Path, env: dict, timeout: int) -> tuple[int, str]:
    try:
        done = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
        return done.returncode, (done.stdout or "") + (done.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"Timed out after {timeout} s: {' '.join(cmd)}"
    except OSError as exc:
        return 127, f"Could not start {cmd[0]}: {exc}"


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    tool_input = payload.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not raw:
        return 0
    project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()).resolve()
    path = Path(raw)
    if not path.is_absolute():
        path = Path(payload.get("cwd") or project) / path
    try:
        rel = path.resolve().relative_to(project)
    except ValueError:
        return 0
    if SKIP_PARTS & set(rel.parts):
        return 0

    env = dict(os.environ)

    if rel.parts[0] == "backend" and rel.suffix == ".py":
        python = project / "backend" / ".venv" / "bin" / "python"
        if not python.exists():
            print("after_edit hook: backend/.venv is missing, tests not run. Run ./setup.sh.", file=sys.stderr)
            return 1
        with tempfile.TemporaryDirectory(prefix="pc-hook-") as tmp:
            env["CENTWISE_DATA_DIR"] = str(Path(tmp) / "appdata")
            env.pop("CENTWISE_TOKEN", None)
            code, out = run([str(python), "-m", "pytest", "-x", "-q"], project / "backend", env, 280)
        if code != 0:
            print(f"Backend tests FAILED after editing {rel.as_posix()}:\n{tail(out)}", file=sys.stderr)
            return 2
        return 0

    if rel.parts[:2] == ("frontend", "src") and rel.suffix in (".ts", ".tsx"):
        tsc = project / "frontend" / "node_modules" / ".bin" / "tsc"
        if not tsc.exists():
            print("after_edit hook: frontend/node_modules is missing, type check not run. Run ./setup.sh.", file=sys.stderr)
            return 1
        code, out = run([str(tsc), "--noEmit"], project / "frontend", env, 180)
        if code != 0:
            print(f"Type check FAILED after editing {rel.as_posix()}:\n{tail(out)}", file=sys.stderr)
            return 2
        return 0

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"after_edit hook error: {exc!r}", file=sys.stderr)
        sys.exit(1)
