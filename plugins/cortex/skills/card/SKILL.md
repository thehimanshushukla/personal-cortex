---
name: card
description: Show the cortex start card on demand - current things, recent decisions, open follow-ups and backup status. Use when the person says "what do you know", "show my card", "show the card", "what's on my plate", "what does my cortex know", "what's loaded", or "rebuild my card".
---

# Show my card

## Steps

1. If `~/.cortex/config.json` is missing: "Your cortex isn't set up yet - say 'set up my cortex' to begin." Stop.
2. If they said "rebuild" or the card looks older than the newest page, run first:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cortex.py build
   ```
   If build reports errors, show them in plain words and offer to fix them (the pages it names).
3. Print the card:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cortex.py card
   ```
4. Show it as-is (it is already plain text). Do not add facts that are not on the card.
5. Offer one next step based on the card: the most overdue `{mine}` follow-up, or the thing touched most recently ("Want me to get you up to speed on the pilot project?").

If the card is empty because nothing is logged yet, say: "Your card is empty because nothing has been logged yet. Do some work and say 'log this' - the card fills from there."

## Teaching note

First week / `teach: full` only: "This is exactly what every new session reads before you type, which is why it already knows where you left off."
