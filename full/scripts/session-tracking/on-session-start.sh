#!/bin/bash
# Fires on: SessionStart (startup, resume, clear)
# Purpose: tell a fresh session what is already in flight.
#
# stdout from SessionStart IS added to Claude's context, so whatever this
# prints becomes something the session knows without being told.
#
# Keep it under about 1KB. This loads every single session; a long card is
# the same mistake as a long instruction file.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/session-common.sh"

# Replace this with however you generate a summary of current state.
# The three headings below are the ones that earn their space:
#   Active  - stops the session proposing work already underway
#   Settled - stops it relitigating a decision that took an afternoon
#   Avoid   - a trap you have already paid for once
if [ -f "$HOME/.claude/context-card.txt" ]; then
    cat "$HOME/.claude/context-card.txt"
fi
exit 0
