# Changelog

## 0.4.0
The board and inbox: say "show my board".
- A page in your browser, on this Mac only, with every to-do and follow-up as a card in six columns: Overdue, This week, Later, In progress, Waiting on others, Done (last 7 days). Filter by area or person.
- Move a card by dragging it or with "Move to..." on the card (keyboard works too). A move changes exactly that one line on its page: This week sets the due date to Friday, Later removes it (a date more than a week away is kept), In progress adds `{doing}`, Waiting on others marks it `{theirs}`, Done ticks it and adds `(done <date>)`. Only Waiting on others changes whose turn it is. "Undo last change" puts the page back exactly as it was; its copies stay on this Mac in `~/.cortex/board-trash/` (the last 20), never in your GitHub backup.
- Tasks written inside code blocks (``` or ~~~) are examples, not tasks: the build and the board both skip them.
- `cortex.py board --stop` closes the board.
- Click a card to see its line, its page and the person, and to open it in Obsidian, open the file, or ask Claude about it (Claude opens with the question typed in; nothing is sent until you press send).
- The Inbox tab lists sorting-desk proposals, notes in `inbox/`, loose notes (with how many task lines they hold) and pages not saved yet, each with Open file and Ask Claude.
- Safe by design: the board only answers this Mac, needs the secret key in its link, never changes a line it cannot find exactly once ("this page changed - reloaded"), checks the page after every change and puts it back if the check fails, and rebuilds the card right after.
- Task lines can carry `(added <date>)`, `(done <date>)` and `{doing}`. Log and debrief write `(added <date>)` on every new line. Existing lines work exactly as before.
- The start card says "say 'show my board' to open them" next to overdue items.
- The board has three looks, Paper, Blue and Night, and follows your Mac unless you pick one. Your choice is remembered. The font ships with the kit, so the page still calls nothing outside your Mac.
- A closed board says so plainly, and Refresh no longer says "Up to date" when it has closed.
- "Update my cortex" reads the installed version correctly and gives the Code tab steps (it used to look for a file the engine copy did not have).
- Ask Claude names your cortex folder in its question, because the Claude app can start a linked chat in a temporary folder.

## 0.3.1
Fixes from the first weeks of real use:
- The build no longer stops on AGENTS.md and GEMINI.md (every 0.3.0 cortex hit this).
- Notes with no header (empty Obsidian daily notes, scribbles) no longer stop the build; the card counts them and the sorting desk lists them.
- Your own to-dos (`@me`) are kept apart from follow-ups with other people. Lines written under your own name before this update are treated as to-dos too, nothing to redo.
- Logging saves every page it wrote, even where the hooks did not run (a Claude chat). The start card shows pages written but not yet saved to GitHub.
- Logging asks about every person and organisation that acted in the session, so people pages fill in.
- Setup writes the real kit version (it stayed at 0.1.0 before).
- A page whose header is damaged (first line lost, a byte-order mark from a Windows editor) is reported as broken, never quietly set aside.
- README.md and CLAUDE.md inside any folder are left alone, as before.
- The start card also says when saved changes never reached GitHub (a log done offline).
- "What is on my list" shows your to-dos; "open the sorting desk" now lists loose notes and offers each a home.

## 0.3.0
Works in Codex too: Codex plugin manifest and marketplace, hooks handle Codex file edits (apply_patch). The cortex's instructions now live in AGENTS.md (CLAUDE.md and GEMINI.md point to it). Skills use a stable engine copy at ~/.cortex/engine, so they work in any tool.

## 0.2.3
The first reply of every session opens with a short "Your cortex" card; Suggest reads every session where Cortex was active, in any folder.

## 0.2.2
Setup asks before changing the chat-history setting; README section "What Cortex touches, sends and runs"; test dependency pinned.

## 0.2.0
Vetted skills and plugins catalog (Suggest proposes from it on evidence), "check my CLAUDE.md", learn-more links to the Claude Code series, feedback form, why-it-exists throughout, Apache 2.0.

## 0.1.0 - first release
Guided setup (blank start) with an end-of-setup tour, feedback skill (drafts email to info@thehimanshushukla.com), roadmap,, start card, gentle log gate, chat-length warning, safety and multi-chat guards, write ledger, weekly backup to GitHub; skills: setup, guide, log, resume, card, debrief, followups, prep, import, sort, suggest, build-skill, upgrade; validator and builder.
