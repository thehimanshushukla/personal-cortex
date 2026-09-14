#!/usr/bin/env python3
"""stage-guard: refuse directory-level `git add` inside a chosen repository.

WHY THIS EXISTS
    If you run more than one Claude Code session at a time and they write into
    the same repository, `git add .` stages whatever the OTHER session has
    written there, half of it unfinished, and commits it under this session's
    message. Writing the rule down does not stop it: the rule competes with
    everything else in the context window. A hook does not compete.

WHAT IS BLOCKED (exit 2), when the command targets the guarded repo:
    git add .            git add -A        git add --all
    git add -u           git add :/        git add <a directory>
    git commit -a        git commit --all

WHAT IS ALLOWED:
    git add <file> <file>   - explicit paths, which is the point
    anything outside the guarded repo

FAIL-OPEN BY DESIGN
    Any internal error exits 0 and allows the call. These guards protect you
    from your own automation moving quickly, not from an adversary, and a bug
    in a guard must not halt real work. If you adapt this to stand between an
    attacker and something valuable, invert that: fail closed, because a silent
    allow is the outcome such a guard exists to prevent.

SETUP
    export GUARDED_REPO=~/notes     (defaults to ~/notes)
    Wire as a PreToolUse hook with matcher "Bash". See settings.json.

KILL SWITCH
    export STAGE_GUARD=off
"""
import json
import os
import re
import shlex
import sys
from pathlib import Path

def _guarded_repo() -> Path:
    """Resolve symlinks. Without this the guard silently allows everything on
    any system where the repo path goes through a symlink - /var -> /private/var
    on macOS being the common case. It fails open, so you get no error: just a
    guard that never fires."""
    raw = Path(os.environ.get("GUARDED_REPO", Path.home() / "notes")).expanduser()
    try:
        return raw.resolve()
    except OSError:
        return raw


REPO = _guarded_repo()
SWEEP_FLAGS = {".", "-A", "--all", "-u", "--update", ":/", ":/.", "./"}


def targets_repo(command: str, cwd: str) -> bool:
    """True if this command plausibly operates on the guarded repository."""
    try:
        here = Path(cwd or ".").resolve()
        if here == REPO or REPO in here.parents:
            return True
    except OSError:
        pass
    needles = [str(REPO), "~/" + REPO.name, "$HOME/" + REPO.name]
    return any(n in command for n in needles)


def offending_add(command: str, cwd: str):
    """Return a description of the sweeping stage, or None if the command is fine."""
    for part in re.split(r"&&|\|\||;|\n", command):
        try:
            tokens = shlex.split(part)
        except ValueError:
            continue
        if len(tokens) < 2 or tokens[0] != "git":
            continue

        if tokens[1] == "commit" and any(t in ("-a", "--all") for t in tokens[2:]):
            return "git commit -a stages every tracked change, including other sessions'"

        if tokens[1] == "add":
            args = [t for t in tokens[2:] if not t.startswith("-") or t in SWEEP_FLAGS]
            for a in args:
                if a in SWEEP_FLAGS:
                    return f"`git add {a}` stages everything under the current directory"
                try:
                    if (Path(cwd) / a).is_dir():
                        return f"`git add {a}` stages a whole directory"
                except OSError:
                    continue
    return None


def main() -> int:
    if os.environ.get("STAGE_GUARD", "on").lower() == "off":
        return 0

    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        return 0

    command = payload.get("tool_input", {}).get("command", "") or ""
    cwd = payload.get("cwd", "") or "."

    if not targets_repo(command, cwd):
        return 0

    offence = offending_add(command, cwd)
    if not offence:
        return 0

    print(
        f"Blocked: {offence}.\n"
        f"Another session may be mid-write in {REPO}. Stage explicitly instead:\n"
        f"  git add path/to/one.md path/to/two.md\n"
        f"To disable for this shell: export STAGE_GUARD=off",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Fail open. A broken guard must never block real work.
        sys.exit(0)
