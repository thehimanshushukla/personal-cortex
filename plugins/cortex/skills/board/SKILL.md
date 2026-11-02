---
name: board
description: Open the person's board and inbox in the browser - their to-dos and follow-ups in columns (Overdue, This week, Later, In progress, Waiting on others, Done) and the notes waiting to be filed. Use when the person says "show my board", "open my board", "my board", "open the inbox", "show me the overdue ones on the board", or the card says "say 'show my board'".
---

# Show my board

The board is a page on this Mac only. It shows every task line in the cortex as a card, and the inbox of notes waiting for a home. The pages stay the record: moving a card changes exactly one line on its page.

## Steps

1. If `~/.cortex/config.json` is missing: "Your cortex isn't set up yet - say 'set up my cortex' to begin." Stop.
2. Start it in the background (it keeps running while the person uses it, and closes itself after 30 minutes without use):
   ```
   python3 ~/.cortex/engine/scripts/cortex.py board --open
   ```
   Run it with `run_in_background` (or end the command with `&`). If a board is already open, the same command just brings it up again.
3. Wait a second and read its first line. If it says "could not read" or "not set up", tell the person in plain words and offer "something is broken" (the health check). Do not repeat the link's secret part (`?t=...`) in the chat.
4. Tell the person what they are looking at, in plain words. Build it from `cortex.py card` (counts) if useful, for example:

   > Your board is open in your browser. Overdue shows 3 things past their date - "rehearse the talk" is the oldest. To move a card, drag it to another column, or use "Move to..." on the card. Click a card to see the page it came from and to ask me about it. The Inbox tab shows 2 notes waiting for a home.

5. If they said "open the inbox", say: "Click the Inbox tab at the top."

## What a move writes (tell the person when they ask)

| Moved to | What changes on the line |
|---|---|
| This week | due date set to this Friday (next Friday at the weekend) |
| Later | the due date is removed (a date more than a week away is kept) |
| In progress | `{doing}` is added |
| Waiting on others | `{theirs}` - not for the person's own to-dos (it asks who it is waiting on) |
| Done | `- [x]` and `(done <today>)` |

Only Waiting on others changes whose turn it is. Every other move keeps `{mine}` or `{theirs}` as it was, so "Alex owes me" never turns into "I owe Alex"; a card someone else owes stays in Waiting on others with its new date.

Overdue is worked out from the date, so nothing can be dropped there. "Undo last change" puts the page back exactly as it was. Every write is checked like a log, and the card and follow-ups list are rebuilt right after.

## Ask Claude from a card

"Ask Claude" opens a new Claude Code chat with a question about that card already typed in. Claude asks to confirm the folder first, and nothing is sent until the person presses send. "Copy prompt" puts the same question on the clipboard for any other Claude window. Sometimes the app starts that chat in a temporary folder even though the right one was confirmed; the question names the cortex folder, so Claude can still find the page.

## If something looks wrong

- "This page changed - reloaded": the page was edited somewhere else (Obsidian, another chat) after the board read it. The board never guesses which line was meant; try the move again.
- "could not read X": that page has a problem. Offer to fix it (`cortex.py check <file>`), then refresh the board.
- To stop the board: it closes itself after 30 minutes without use. To close it now (or when it says another board is open): `python3 ~/.cortex/engine/scripts/cortex.py board --stop`.

## Teaching note

First week / `teach: full` only: "The board is a view of your pages, not a separate list. Moving a card edits the line on its page, so Claude, Obsidian and the board always agree."
