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
import stat
import subprocess
import sys
from pathlib import Path

from cortex import config_vault

HERE = Path(__file__).resolve().parent
STATE_ROOT = Path.home() / ".cortex" / "sessions"
CONFIG = Path(os.environ.get("CORTEX_CONFIG", Path.home() / ".cortex" / "config.json"))
# Chat-length estimate: transcript bytes at which a ~200k-token window is roughly full.
FULL_BYTES = int(os.environ.get("CORTEX_FULL_BYTES", 2_400_000))
STOP_MIN_SECONDS = 600
MAX_STOP_BLOCKS = 2


def vault() -> Path | None:
    try:
        return config_vault(json.loads(CONFIG.read_text(encoding="utf-8")))
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

ENGINE = Path.home() / ".cortex" / "engine"


def sync_engine() -> None:
    """Keep a stable copy of scripts, templates and docs at ~/.cortex/engine.

    Skills refer to that path, so they work in every coding tool, whichever way the
    plugin was installed (Claude Code fills in its plugin path; Codex and others do not).
    """
    import shutil
    root = HERE.parent
    stamp = ENGINE / ".source"
    marker = f"{root}|{(root / '.claude-plugin' / 'plugin.json').stat().st_mtime if (root / '.claude-plugin' / 'plugin.json').exists() else 0}"
    if stamp.exists() and stamp.read_text() == marker and (ENGINE / ".claude-plugin" / "plugin.json").exists():
        return
    ENGINE.mkdir(parents=True, exist_ok=True)
    for sub in ("scripts", "templates", "docs", ".claude-plugin"):   # the upgrade skill reads the version from .claude-plugin
        if (root / sub).is_dir():
            shutil.copytree(root / sub, ENGINE / sub, dirs_exist_ok=True)
    stamp.write_text(marker)


def unsaved_pages(v: Path) -> int:
    """Pages written but never committed - a log done where the hooks did not run (Claude chat) leaves these."""
    if not (v / ".git").exists():  # not its own repo: never count files of a parent repo
        return 0
    try:
        r = subprocess.run(["git", "-C", str(v), "status", "--porcelain", "--untracked-files=all"],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return 0
    if r.returncode != 0:
        return 0
    paths = [line[3:].strip('"') for line in r.stdout.splitlines()]
    return sum(1 for f in paths if f.endswith(".md") and not f.startswith("_cortex/") and f != "home.md")


def unpushed_commits(v: Path) -> int:
    """Commits made locally but never pushed - a log done offline. 0 when there is no GitHub backup."""
    if not (v / ".git").exists():
        return 0
    try:
        r = subprocess.run(["git", "-C", str(v), "rev-list", "--count", "@{u}..HEAD"],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return 0
    return int(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip().isdigit() else 0


GARDENER = Path.home() / ".cortex" / "gardener" / "summary.json"
GARDENER_STALE = 3600   # seconds before the start hook asks for a fresh count
GARDENER_BYTES = 256 * 1024
WARN_DAYS = 21


def gardener_summary(v: Path) -> dict:
    """This vault's numbers. Opened so that a pipe in the file's place cannot hang a session start."""
    try:
        fd = os.open(GARDENER, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as fh:
            st = os.fstat(fh.fileno())
            if not stat.S_ISREG(st.st_mode) or st.st_size > GARDENER_BYTES:
                return {}
            info = json.loads(fh.read(GARDENER_BYTES))
    except (OSError, ValueError, RecursionError):
        return {}
    vaults = info.get("vaults") if isinstance(info, dict) else None
    entry = vaults.get(os.path.realpath(str(v))) if isinstance(vaults, dict) else None
    return entry if isinstance(entry, dict) else {}


def elsewhere_due(v: Path) -> bool:
    """Sessions elsewhere are said at most once a week. Asked only when there are some to say."""
    try:
        import gardener
        return gardener.claim_elsewhere_line(v)
    except Exception:  # the card goes on without this line
        return False


def gardener_line(v: Path) -> str:
    """The card's count of unlogged sessions. No transcript is opened here, so a huge folder cannot
    slow a session start: this reads one small file of numbers and ids, and a stale or missing one
    starts a separate run in the background. Sessions logged since that run are taken off."""
    info = gardener_summary(v)
    now = dt.datetime.now().timestamp()
    at, week, ids, oldest = info.get("at"), info.get("week"), info.get("week_ids"), info.get("risk_oldest")
    if not isinstance(at, (int, float)) or now - at > GARDENER_STALE:
        try:
            subprocess.Popen([sys.executable, str(HERE / "cortex.py"), "--vault", str(v), "gardener", "--refresh", "--quiet"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError:
            pass
    def still_open(count, id_list) -> int:
        if not isinstance(count, int) or not isinstance(id_list, list):
            return 0
        return max(0, count - sum(1 for s in id_list[:200] if isinstance(s, str) and "/" not in s
                                  and ((STATE_ROOT / s / "logged").exists() or (STATE_ROOT / s / "skipped").exists())))
    lines = []
    n, away = still_open(week, ids), still_open(info.get("elsewhere"), info.get("elsewhere_ids"))
    away = away if away and elsewhere_due(v) else 0
    missed = f"{n} session{' this week was' if n == 1 else 's this week were'} never logged"
    if n and away:     # always one short line, whichever of the two there is
        lines.append(f"{missed}, {away} elsewhere {'was' if away == 1 else 'were'} not checked - say 'catch up'.")
    elif n:
        lines.append(f"{missed} - say 'catch up'.")
    elif away:
        lines.append(f"{away} session{' elsewhere this week was' if away == 1 else 's elsewhere this week were'} not checked - "
                     f"say 'catch up' to see {'it' if away == 1 else 'them'}.")
    if isinstance(oldest, (int, float)) and 0 < oldest < now and now - oldest > WARN_DAYS * 86400:
        lines.append(f"The oldest unlogged session is {int((now - oldest) // 86400)} days old. Claude Code deletes "
                     "transcripts after 30 days by default - say 'catch up' soon.")
    return "\n".join(lines)


def session_start(p: dict) -> int:
    try:
        sync_engine()
    except OSError:
        pass
    v = vault()
    if v:
        sd = state_dir(p)
        if not (sd / "started").exists():
            (sd / "started").write_text(dt.datetime.now().isoformat())
    if not v and CONFIG.exists():
        emit_context("SessionStart", f"Cortex: the settings file {CONFIG} does not name a full folder path, so no cortex was loaded. "
                     "Tell the person once, in one line, and offer to look at it through 'set up my cortex', which shows what it finds and asks before changing anything.")
        return 0
    if not v:
        emit_context("SessionStart", "Cortex is installed but not set up yet. Tell the person once, in one line: "
                     "\"Your cortex is installed - say 'set up my cortex' whenever you want to start.\"")
        return 0
    if not v.exists():
        emit_context("SessionStart", f"Cortex: the cortex folder {v} is missing. Suggest 'cortex doctor' via the guide skill.")
        return 0
    card = v / "_cortex" / "card.md"
    text = card.read_text() if card.exists() else "Cortex card not built yet."
    unsaved = unsaved_pages(v)
    unpushed = unpushed_commits(v)
    if unsaved:
        text += (f"\n{unsaved} page(s) changed but not saved yet. Offer once: "
                 f"\"say 'back up my cortex' to save them now\".\n")
    elif unpushed:
        text += (f"\n{unpushed} saved change(s) not on GitHub yet (last push did not go through). Offer once: "
                 f"\"say 'back up my cortex' to send them\".\n")
    missed = gardener_line(v)
    if missed:
        text += f"\n{missed}\n"
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
                 f"anything waiting such as imports, unlogged sessions or a missing backup), then answer what they asked. Do not show it again later "
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


PATCH_FILE = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$|^\*\*\* Move to: (.+)$", re.M)


def patch_paths(p: dict) -> list[str]:
    """Files touched by a Codex apply_patch call (tool_input.command holds the patch)."""
    text = (p.get("tool_input") or {}).get("command", "") or ""
    cwd = p.get("cwd") or os.getcwd()
    out = []
    for m in PATCH_FILE.finditer(text):
        f = (m.group(1) or m.group(2) or "").strip()
        if f:
            out.append(str((Path(cwd) / Path(f).expanduser()).resolve()))
    return out


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
    elif tool in ("Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch"):
        fps = patch_paths(p) if tool == "apply_patch" else [str(Path(ti.get("file_path", "") or ti.get("notebook_path", "")).expanduser())]
        home = str(Path.home())
        for fp in fps:
            for d in CRED_DIRS:
                if fp.startswith(f"{home}/{d}/") or fp == f"{home}/{d}":
                    print(f"Cortex safety guard: refusing to write into ~/{d} (credentials).", file=sys.stderr)
                    return 2
    return 0


def post_write(p: dict) -> int:
    v = vault()
    ti = p.get("tool_input") or {}
    if p.get("tool_name") == "apply_patch":
        paths = patch_paths(p)
    else:
        fp = ti.get("file_path") or ti.get("notebook_path")
        paths = [str(Path(fp).expanduser().resolve())] if fp else []
    paths = [f for f in paths if v and f.startswith(str(v) + os.sep)]
    if not paths:
        return 0
    led = state_dir(p) / "written.txt"
    seen = set(led.read_text().splitlines()) if led.exists() else set()
    with led.open("a") as fh:
        for f in paths:
            if f not in seen:
                fh.write(f + "\n")
                seen.add(f)
    return 0


def mark_automation(p: dict) -> None:
    """A run the kit itself started (CORTEX_AUTOMATION=1): noted, so the Gardener never counts it as missed."""
    sid = str(p.get("session_id") or "")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", sid):
        d = STATE_ROOT / sid
        d.mkdir(parents=True, exist_ok=True)
        (d / "automation").touch()


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
    # In an automated run nobody is there to answer a log reminder or read a card. The safety guard stays on.
    if os.environ.get("CORTEX_AUTOMATION") and sys.argv[1] != "guard":
        mark_automation(payload)
        return 0
    return EVENTS[sys.argv[1]](payload)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)
