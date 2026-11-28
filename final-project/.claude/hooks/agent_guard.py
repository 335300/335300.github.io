#!/usr/bin/env python3
"""PreToolUse hook for ONE subagent: limit where it may write and what it may read.

Used in the ``hooks:`` block of an agent file in ``.claude/agents/``:

    python3 "$CLAUDE_PROJECT_DIR/.claude/hooks/agent_guard.py" \
        --write frontend/ memory.md --no-read backend/app/services

--write PREFIX...    the agent may Edit/Write only inside these project paths
                     (plus /tmp for scratch files). No --write = no project writes.
--no-read PREFIX...  the agent may not Read/Grep/Glob these project paths, and
                     Bash commands that mention them are blocked (used to keep
                     the calculation verifier "blind").

Exit 0 = allowed, exit 2 = blocked (message goes back to the agent).
Standard library only, Python 3.9+.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

SCRATCH = [Path("/tmp"), Path("/private/tmp"), Path(tempfile.gettempdir())]


def norm(p: Path) -> Path:
    try:
        return p.resolve()
    except (OSError, RuntimeError):
        return p


def under(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", nargs="*", default=[])
    ap.add_argument("--no-read", nargs="*", default=[])
    opts = ap.parse_args()

    payload = json.loads(sys.stdin.read() or "{}")
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input") or {}
    project = norm(Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()))
    base = Path(payload.get("cwd") or project)

    def resolve(raw: str) -> Path:
        p = Path(os.path.expanduser(raw))
        return norm(p if p.is_absolute() else base / p)

    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        target = resolve(ti.get("file_path") or ti.get("notebook_path") or "")
        ok = any(under(target, norm(s)) for s in SCRATCH)
        ok = ok or any(under(target, norm(project / w)) for w in opts.write)
        if not ok:
            allowed = ", ".join(opts.write) if opts.write else "nothing in the project"
            print(f"BLOCKED: this agent may only write to: {allowed} (and /tmp). "
                  f"Hand the change for {target} back to the main session.", file=sys.stderr)
            return 2

    if opts.no_read:
        def rel(path: Path) -> str:
            try:
                return path.relative_to(project).as_posix()
            except ValueError:
                return "/" + path.as_posix()

        prefixes = [r.rstrip("/") if not r.endswith("_") else r for r in opts.no_read]
        names = ", ".join(opts.no_read)
        if tool in ("Read", "Grep", "Glob", "LS"):
            raw = ti.get("file_path") or ti.get("path") or ""
            target = rel(resolve(raw) if raw else norm(base))
            pattern = ti.get("pattern", "") if tool == "Glob" else ""
            if any(target.startswith(pre) for pre in prefixes) or any(pre in pattern for pre in prefixes):
                print("BLOCKED: this agent works blind and may not read " + names
                      + ". Use the rules and run_service.py instead.", file=sys.stderr)
                return 2
            searching = tool in ("Grep", "Glob") or (tool == "LS")
            if searching and any(pre.startswith(target + "/") or target in ("", ".") for pre in prefixes):
                print("BLOCKED: this search would include hidden paths (" + names
                      + "). Search a narrower folder.", file=sys.stderr)
                return 2
        if tool == "Bash":
            cmd = ti.get("command", "")
            if any(pre in cmd for pre in prefixes):
                print("BLOCKED: this agent works blind; the command mentions " + names + ".", file=sys.stderr)
                return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"agent_guard error ({exc!r}); blocked to be safe.", file=sys.stderr)
        sys.exit(2)
