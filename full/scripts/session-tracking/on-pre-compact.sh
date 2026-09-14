#!/bin/bash
# Fires on: PreCompact (before the conversation is summarised)
# Purpose: get the reasoning onto disk BEFORE it is summarised away.
#
# Compaction replaces the history with a summary. Whatever was only in the
# conversation is now only in someone's paraphrase of it. This hook is the
# last moment the detail still exists.
#
# stdout from PreCompact is not shown to Claude, so this writes a file and
# leaves an instruction for the post-compaction session to pick up.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/session-common.sh"

echo "compaction at $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$STATE_DIR/checkpoint.md"
exit 0
