#!/bin/bash
# Shared state paths for the session-tracking hooks.
#
# One directory per session. Sharing a single directory across sessions looks
# fine until you run two at once: the second session's start wipes the first
# session's state. Key everything by session id.

STATE_ROOT="${CLAUDE_STATE_ROOT:-$HOME/.claude/session-state}"
SESSION_ID="${CLAUDE_CODE_SESSION_ID:-unknown}"
STATE_DIR="$STATE_ROOT/sessions/$SESSION_ID"
mkdir -p "$STATE_DIR"

# The marker your own logging step writes when the session has been recorded.
# Change the filename if you like; change it in on-stop.sh too.
LOGGED_FLAG="$STATE_DIR/logged"

session_is_logged() {
    [ -f "$LOGGED_FLAG" ]
}
