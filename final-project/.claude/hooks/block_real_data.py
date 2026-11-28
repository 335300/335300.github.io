#!/usr/bin/env python3
"""PreToolUse hook: keep Claude's helpers away from Josue's real money data.

Claude Code runs this before every Read, Edit, Write, Grep, Glob and Bash call.
It reads the planned tool call (JSON on stdin) and:

- exits 0  -> the call may go ahead;
- exits 2  -> the call is BLOCKED; the message on stderr goes back to Claude.

Blocked:
1. Anything inside the real-data places: the project's ``Bank statements/`` and
   ``Payslips/`` folders, and the app's data folders in
   ``~/Library/Application Support/`` (Personal Centwise and Centwise).
2. Starting the app or the backend without a throwaway ``CENTWISE_DATA_DIR``
   (it would open the real data file).
3. Changing the safety setup itself (``.claude/hooks/`` and
   ``.claude/settings.json``), unless Josue started Claude Code with
   ``CENTWISE_HOOK_EDIT=1``.

Standard library only, Python 3.9+, so it runs with any python3 on the Mac.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from pathlib import Path

REAL_DATA_FOLDERS = ("Bank statements", "Payslips")
APP_SUPPORT_NAMES = ("Personal Centwise", "Centwise")
REAL_FILE_NAMES = re.compile(r"Konto_\d+-Auszug|Paystub_\d+", re.IGNORECASE)
APP_SUPPORT_TEXT = re.compile(r"Application[\\ ]+Support/(Personal )?Centwise", re.IGNORECASE)

# Commands that start the app or open its data store.
APP_STARTERS = re.compile(
    r"(-m\s+app\b|run_backend\.py|npm\s+run\s+(dev|start)\b|npm\s+start\b|electron\s+\.|"
    r"Personal Centwise\.app|AppStore\(|data_dir\(\)|data_file\(|profile_dir\()"
)
SAFE_DATA_DIR = re.compile(r"CENTWISE_DATA_DIR=(\"[^\"]+\"|'[^']+'|\S+)")

SAFETY_FILES = (".claude/hooks", ".claude/settings.json", ".claude/settings.local.json")
WRITE_WORDS = re.compile(r"(>|\bsed\s+-i|\btee\b|\bmv\b|\bcp\b|\brm\b|\btruncate\b|\bperl\s+-i|\bchmod\b|open\(|write_text)")


def project_dir(payload: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()).resolve()


def blocked_roots(project: Path) -> list[Path]:
    home = Path.home()
    roots = [project / name for name in REAL_DATA_FOLDERS]
    roots += [home / "Library" / "Application Support" / name for name in APP_SUPPORT_NAMES]
    return roots


def resolve(raw: str, base: Path) -> Path:
    p = Path(os.path.expanduser(raw))
    if not p.is_absolute():
        p = base / p
    try:
        return p.resolve()
    except (OSError, RuntimeError):
        return p


def inside(path: Path, roots: list[Path]) -> bool:
    for root in roots:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def path_problem(raw: str, base: Path, roots: list[Path]) -> str | None:
    if not raw:
        return None
    if REAL_FILE_NAMES.search(raw) or APP_SUPPORT_TEXT.search(raw):
        return raw
    if inside(resolve(raw, base), roots):
        return raw
    return None


def tokens_of(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return command.split()


def bash_problem(command: str, base: Path, roots: list[Path]) -> str | None:
    if REAL_FILE_NAMES.search(command) or APP_SUPPORT_TEXT.search(command) or "Payslips/" in command:
        return "the command names a real-data file or folder"
    for tok in tokens_of(command):
        for part in re.split(r"[=:]", tok):
            if part and not part.startswith("-") and path_problem(part, base, roots):
                return f"the command touches a real-data path ({part})"
    if APP_STARTERS.search(command):
        m = SAFE_DATA_DIR.search(command)
        value = m.group(1).strip("\"'") if m else ""
        if not value or APP_SUPPORT_TEXT.search(value) or inside(resolve(value, base), roots):
            return ("the command starts the app or opens its data store without a throwaway "
                    "CENTWISE_DATA_DIR (it would read the real data). Add "
                    "CENTWISE_DATA_DIR=/tmp/pc-test-data in front of the command")
    return None


def safety_edit_problem(tool: str, tool_input: dict, project: Path) -> str | None:
    if os.environ.get("CENTWISE_HOOK_EDIT") == "1":
        return None
    targets: list[str] = []
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        p = resolve(raw, project)
        try:
            targets.append(p.relative_to(project).as_posix())
        except ValueError:
            pass
        if any(t.startswith(s) for t in targets for s in SAFETY_FILES):
            return "the safety hooks and settings can only be changed by Josue"
    if tool == "Bash":
        cmd = tool_input.get("command", "")
        if any(s in cmd for s in SAFETY_FILES) and WRITE_WORDS.search(cmd):
            return "the safety hooks and settings can only be changed by Josue"
    return None


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        print("Privacy hook: could not read the tool call, so it was blocked to be safe.", file=sys.stderr)
        return 2

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    project = project_dir(payload)
    base = Path(payload.get("cwd") or project)
    roots = blocked_roots(project)

    problem = safety_edit_problem(tool, tool_input, project)

    if problem is None and tool in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit", "LS"):
        raw_path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path") or ""
        hit = path_problem(raw_path, base, roots)
        if hit:
            problem = f"{hit} is real money data"

    if problem is None and tool in ("Grep", "Glob"):
        hit = path_problem(tool_input.get("path") or "", base, roots)
        pattern = (tool_input.get("glob") or "") + " " + (tool_input.get("pattern") if tool == "Glob" else "")
        if hit:
            problem = f"{hit} is real money data"
        elif re.search(r"(^|[\s/*])(Bank statements|Payslips)(/|\*|$)", pattern.strip()) or REAL_FILE_NAMES.search(pattern):
            problem = "the search pattern points into a real-data folder"

    if problem is None and tool == "Bash":
        problem = bash_problem(tool_input.get("command", ""), base, roots)

    if problem:
        print(
            "BLOCKED by the Personal Centwise privacy hook: " + problem + ".\n"
            "Development helpers work only with code and synthetic test data "
            "(CENTWISE_DATA_DIR=/tmp/...). Real statements, payslips and the app's data folder are off-limits. "
            "If you only wanted to search the code for a word, use the Grep tool with path backend/ or frontend/. "
            "If Josue really wants this, he must do it himself or change .claude/settings.json.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # fail closed: a broken guard must not let data through
        print(f"Privacy hook error ({exc!r}); the call was blocked to be safe. Tell Josue.", file=sys.stderr)
        sys.exit(2)
