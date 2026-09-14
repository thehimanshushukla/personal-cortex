#!/usr/bin/env python3
"""danger-guard: refuse writes to credential paths and a short list of
destructive shell commands.

WHY THIS EXISTS
    Not because the model is malicious. Because an agent working quickly on a
    plausible-looking instruction can do something irreversible, and the cost
    of a false negative here is much higher than the cost of a false positive.

    Keep the deny list SHORT. A long list becomes a list you stop reading, and
    then a list you turn off. Everything not on it is allowed.

WHAT IS BLOCKED (exit 2):
    Write/Edit to ~/.ssh, ~/.aws, ~/.gnupg, ~/Library/Keychains, /etc, /System
    Bash matching: rm -rf on / or ~, sudo rm -rf, curl|sh, chmod -R 777 /

FAIL-OPEN BY DESIGN, AND THIS ONE DESERVES A SECOND THOUGHT
    Any internal error exits 0 and allows the call, matching the other guards
    in this repo. That is the right default when the thing you are guarding
    against is your own automation moving fast.

    It is the WRONG default if you are guarding against an attacker. A
    credential-write blocker that fails open leaks credentials exactly when it
    is broken. If that is your threat model, change the handler at the bottom
    to exit 2, accept that a bug will block real work, and write the choice
    down in this docstring so the next person knows it was deliberate.

SETUP
    Wire as a PreToolUse hook with matcher "Write|Edit|MultiEdit|NotebookEdit|Bash".

KILL SWITCH
    export DANGER_GUARD=off
"""
import json
import os
import re
import sys
from pathlib import Path

PROTECTED = [
    Path.home() / ".ssh",
    Path.home() / ".aws",
    Path.home() / ".gnupg",
    Path.home() / "Library" / "Keychains",
    Path("/etc"),
    Path("/System"),
]

DESTRUCTIVE = [
    (re.compile(r"\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rR][a-zA-Z]*f|\brm\s+-fr\b"), "recursive forced delete"),
    (re.compile(r"\bsudo\s+rm\b"), "sudo rm"),
    (re.compile(r"\bchmod\s+-R\s+777\s+/"), "chmod -R 777 on a root path"),
    (re.compile(r"curl[^|]*\|\s*(ba)?sh"), "piping a download straight into a shell"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;:"), "fork bomb"),
]


def protected_path(target: str):
    """Return the protected root this path falls under, or None."""
    if not target:
        return None
    try:
        resolved = Path(target).expanduser().resolve()
    except (OSError, RuntimeError):
        return None
    for root in PROTECTED:
        try:
            if resolved == root or root in resolved.parents:
                return root
        except OSError:
            continue
    return None


def destructive(command: str):
    """Return a description of the destructive pattern matched, or None.

    Note the deliberate narrowness: `rm -rf ./build` is fine and common, so
    only root- and home-anchored deletes are refused.
    """
    for pattern, label in DESTRUCTIVE:
        if not pattern.search(command):
            continue
        if label == "recursive forced delete":
            if not re.search(r"-[a-zA-Z]*[rR][a-zA-Z]*f?\s+(/|~|\$HOME)(\s|/|$)", command):
                continue
        return label
    return None


def main() -> int:
    if os.environ.get("DANGER_GUARD", "on").lower() == "off":
        return 0

    payload = json.load(sys.stdin)
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    if tool == "Bash":
        command = tool_input.get("command", "") or ""
        hit = destructive(command)
        if hit:
            print(
                f"Blocked: {hit}.\n"
                "If this is genuinely what you want, run it yourself in a terminal.\n"
                "To disable for this shell: export DANGER_GUARD=off",
                file=sys.stderr,
            )
            return 2
        return 0

    target = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    root = protected_path(target)
    if root:
        print(
            f"Blocked: writing inside {root}, which holds credentials or system files.\n"
            "Edit it yourself if that is really the intent.\n"
            "To disable for this shell: export DANGER_GUARD=off",
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Fail open. See the docstring: reconsider this line if your threat
        # model includes an adversary rather than your own automation.
        sys.exit(0)
