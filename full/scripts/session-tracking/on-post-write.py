#!/usr/bin/env python3
"""Fires on: PostToolUse for Write/Edit/MultiEdit/NotebookEdit.

Purpose: record every file this session wrote, so you can stage precisely
later instead of reaching for `git add .` - which is the thing stage-guard.py
exists to refuse.

PostToolUse cannot block, and should not try. Exit 0 always.
"""
import json
import os
import sys
from pathlib import Path

STATE_ROOT = Path(os.environ.get("CLAUDE_STATE_ROOT", Path.home() / ".claude" / "session-state"))


def main() -> int:
    payload = json.load(sys.stdin)
    session = payload.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID", "unknown")
    target = (payload.get("tool_input", {}) or {}).get("file_path")
    if not target:
        return 0

    state_dir = STATE_ROOT / "sessions" / session
    state_dir.mkdir(parents=True, exist_ok=True)
    ledger = state_dir / "written-paths.txt"

    existing = set()
    if ledger.exists():
        existing = set(ledger.read_text().splitlines())
    if target not in existing:
        with ledger.open("a") as fh:
            fh.write(target + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
