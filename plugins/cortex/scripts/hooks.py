#!/usr/bin/env python3
"""Cortex hooks. One entry point, one argument: the event name.

  python3 hooks.py session-start | prompt | pre-compact | stop | guard | post-write

Every hook fails soft: an internal error exits 0 and never blocks the person's
work. Blocking happens only on purpose (exit 2 with a plain-words reason).
Session state lives in ~/.cortex/sessions/<session_id>/. Contract: docs/SPEC.md.
Kill switch for everything: export CORTEX_HOOKS=off
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE_ROOT = Path.home() / ".cortex" / "sessions"
CONFIG = Path(os.environ.get("CORTEX_CONFIG", Path.home() / ".cortex" / "config.json"))
# Chat-length estimate: transcript bytes at which a ~200k-token window is roughly full.
FULL_BYTES = int(os.environ.get("CORTEX_FULL_BYTES", 2_400_000))
STOP_MIN_SECONDS = 600
MAX_STOP_BLOCKS = 2


def vault() -> Path | None:
    try:
        v = json.loads(CONFIG.read_text()).get("vault")
        return Path(v).expanduser().resolve() if v else None
    except (OSError, ValueError):
        return None


def state_dir(payload: dict) -> Path:
    sid = payload.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID") or "unknown"
    d = STATE_ROOT / sid
    d.mkdir(parents=True, exist_ok=True)
    return d


def emit_context(event: str, text: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}))


# ---------------------------------------------------------------- session start

def session_start(p: dict) -> int:
    v = vault()
    if v:
        sd = state_dir(p)
        if not (sd / "started").exists():
            (sd / "started").write_text(dt.datetime.now().isoformat())
    if not v:
        emit_context("SessionStart", "Cortex is installed but not set up yet. Tell the person once, in one line: "
                     "\"Your cortex is installed - say 'set up my cortex' whenever you want to start.\"")
        return 0
    if not v.exists():
        emit_context("SessionStart", f"Cortex: the cortex folder {v} is missing. Suggest 'cortex doctor' via the guide skill.")
        return 0
    card = v / "_cortex" / "card.md"
    text = card.read_text() if card.exists() else "Cortex card not built yet."
    # Weekly backup safety net: if the scheduled one was missed (Mac asleep), run it now in the background.
    try:
        subprocess.Popen([sys.executable, str(HERE / "cortex.py"), "--vault", str(v), "backup",
                          "--if-older-than-days", "7", "--quiet"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass
    emit_context("SessionStart",
                 f"CORTEX (vault: {v}). This is the person's start card. Begin your FIRST reply in this session with a compact "
                 f"version of it under the heading 'Your cortex' (at most 5 short lines: what is active, anything due or overdue, "
                 f"anything waiting such as imports or a missing backup), then answer what they asked. Do not show it again later "
                 f"in the session unless asked. Use it - do not re-ask what it already says. Pages are created with the cortex "
                 f"skills, wherever this session is running.\n\n{text}")
    return 0


# ---------------------------------------------------------------- chat length

def prompt(p: dict) -> int:
    tp = p.get("transcript_path")
    if not tp or not vault():
        return 0
    try:
        size = Path(tp).stat().st_size
    except OSError:
        return 0
    sd = state_dir(p)
    frac = size / FULL_BYTES
    if frac >= 0.8 and not (sd / "warned_80").exists():
        (sd / "warned_80").touch()
        (sd / "warned_60").touch()
        emit_context("UserPromptSubmit", "Cortex: this chat is about 80% full. Before answering, tell the person in one "
                     "line: \"This chat is nearly full - long chats start to lose detail. Say 'log this' now so nothing is lost, then start a fresh chat.\"")
    elif frac >= 0.6 and not (sd / "warned_60").exists():
        (sd / "warned_60").touch()
        emit_context("UserPromptSubmit", "Cortex: this chat is about 60% full. At a natural pause, mention once in one "
                     "line that long chats start to lose detail, so logging and starting a fresh chat soon keeps answers sharp.")
    return 0


def pre_compact(p: dict) -> int:
    if not vault():
        return 0
    sd = state_dir(p)
    with (sd / "compacted").open("a") as fh:
        fh.write(dt.datetime.now().isoformat() + "\n")
    return 0


# ---------------------------------------------------------------- stop gate

def stop(p: dict) -> int:
    v = vault()
    if not v:
        return 0
    sd = state_dir(p)
    if (sd / "logged").exists() or (sd / "skipped").exists():
        return 0
    wrote = (sd / "written.txt").exists() and (sd / "written.txt").read_text().strip()
    try:
        started = dt.datetime.fromisoformat((sd / "started").read_text().strip())
        long_enough = (dt.datetime.now() - started).total_seconds() >= STOP_MIN_SECONDS
    except (OSError, ValueError):
        long_enough = False
    if not wrote and not long_enough:
        return 0
    attempts = int((sd / "stop_attempts").read_text()) if (sd / "stop_attempts").exists() else 0
    if attempts >= MAX_STOP_BLOCKS:
        (sd / "outcome").write_text("unlogged")
        return 0
    (sd / "stop_attempts").write_text(str(attempts + 1))
    sid = p.get("session_id", "")
    print("This session has not been logged in the cortex yet. Ask the person in one short line: "
          "\"Want me to log this session, so the reasons behind today's decisions are not lost? Say 'log it' or 'skip'.\" If they say skip, run: "
          f"touch ~/.cortex/sessions/{sid}/skipped  - if they say log it, use the cortex log skill.",
          file=sys.stderr)
    return 2


# ---------------------------------------------------------------- guards

DANGER = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f|-[a-zA-Z]*f[a-zA-Z]*r)[a-zA-Z]*\s+(/|~|\$HOME)/?(\s|$)"), "deletes your whole home folder or disk"),
    (re.compile(r"\bsudo\s+rm\b"), "deletes files as administrator"),
    (re.compile(r"\bgit\s+push\b[^|;&]*\s(--force|-f)(\s|$)"), "force-push overwrites your GitHub backup"),
    (re.compile(r"\bgit\s+push\b[^|;&]*--force-with-lease"), "force-push overwrites your GitHub backup"),
    (re.compile(r"(curl|wget)[^|;&]*\|\s*(sudo\s+)?(ba|z)?sh\b"), "runs a script straight from the internet"),
    (re.compile(r"\bchmod\s+-R\s+777\s+/"), "opens up permissions on the whole disk"),
]
CRED_DIRS = [".ssh", ".aws", ".gnupg", "Library/Keychains"]
SWEEP = re.compile(r"\bgit\s+(add\s+(-A|--all|\.(\s|$))|commit\s+(-[a-zA-Z]*a[a-zA-Z]*\b|--all))")


def guard(p: dict) -> int:
    tool = p.get("tool_name", "")
    ti = p.get("tool_input") or {}
    v = vault()
    if tool == "Bash":
        cmd = ti.get("command", "")
        for rx, why in DANGER:
            if rx.search(cmd):
                print(f"Cortex safety guard refused this command because it {why}. "
                      "If the person really wants it, they can run it themselves in Terminal.", file=sys.stderr)
                return 2
        if v and re.search(r"\brm\s+-[a-zA-Z]*r", cmd) and re.search(re.escape(str(v)) + r"/?(\s|$|['\"])", cmd):
            print("Cortex safety guard: refusing to delete the whole cortex folder.", file=sys.stderr)
            return 2
        if v and re.search(r"\bgit\s+reset\s+--hard", cmd) and (str(v) in cmd or str(v) in p.get("cwd", "")):
            print("Cortex safety guard: 'git reset --hard' would throw away unsaved cortex pages. "
                  "Commit or ask the person first.", file=sys.stderr)
            return 2
        in_vault = v and (str(v) in cmd or p.get("cwd", "").startswith(str(v)))
        if in_vault and SWEEP.search(cmd) and "cortex.py" not in cmd:
            print("Cortex multi-chat guard: stage the files this chat wrote by name "
                  "(see ~/.cortex/sessions/<session>/written.txt) instead of 'git add .' / '-A' / 'commit -a', "
                  "so one chat never saves another chat's half-done pages. The weekly backup handles everything else.",
                  file=sys.stderr)
            return 2
    elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        fp = str(Path(ti.get("file_path", "") or ti.get("notebook_path", "")).expanduser())
        home = str(Path.home())
        for d in CRED_DIRS:
            if fp.startswith(f"{home}/{d}/") or fp == f"{home}/{d}":
                print(f"Cortex safety guard: refusing to write into ~/{d} (credentials).", file=sys.stderr)
                return 2
    return 0


def post_write(p: dict) -> int:
    v = vault()
    ti = p.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("notebook_path")
    if not v or not fp:
        return 0
    fp = str(Path(fp).expanduser().resolve())
    if not fp.startswith(str(v) + os.sep):
        return 0
    led = state_dir(p) / "written.txt"
    seen = set(led.read_text().splitlines()) if led.exists() else set()
    if fp not in seen:
        with led.open("a") as fh:
            fh.write(fp + "\n")
    return 0


EVENTS = {"session-start": session_start, "prompt": prompt, "pre-compact": pre_compact,
          "stop": stop, "guard": guard, "post-write": post_write}


def main() -> int:
    if os.environ.get("CORTEX_HOOKS") == "off" or len(sys.argv) < 2 or sys.argv[1] not in EVENTS:
        return 0
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError:
        payload = {}
    return EVENTS[sys.argv[1]](payload)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
