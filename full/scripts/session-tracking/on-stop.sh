#!/bin/bash
# Fires on: Stop (when Claude finishes responding)
# Purpose: refuse to end the session until its work has been written down.
#
# Exit 2 on Stop prevents Claude from stopping and continues the conversation.
#
# THE COUNTER IS NOT OPTIONAL. A Stop hook that always exits 2 when its
# condition is unmet is an infinite loop: the model cannot stop, so it
# responds, so the hook fires again. Two refusals, then let go and record the
# session as unlogged so the next one can pick it up. A guardrail with no
# release valve is a trap with extra steps.
#
# Kill switch: export STOP_GATE=off

[ "${STOP_GATE:-on}" = "off" ] && exit 0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/session-common.sh"

if session_is_logged; then
    exit 0
fi

ATTEMPTS=0
[ -f "$STATE_DIR/stop_attempts" ] && ATTEMPTS=$(cat "$STATE_DIR/stop_attempts")
ATTEMPTS=$((ATTEMPTS + 1))
echo "$ATTEMPTS" > "$STATE_DIR/stop_attempts"

if [ "$ATTEMPTS" -gt 2 ]; then
    echo "unlogged" > "$STATE_DIR/outcome"
    exit 0
fi

# stderr becomes the blocking message the model sees. Say what to do.
cat >&2 <<MSG
This session has not been recorded yet.

Write down what happened - decisions made, what broke, what is still open -
then mark it done:

  touch "$LOGGED_FLAG"

If this was a trivial session with nothing worth keeping, just run that
command. To disable the gate for this shell: export STOP_GATE=off
MSG
exit 2
