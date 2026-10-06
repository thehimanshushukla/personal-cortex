---
name: setup
description: Set up a new cortex from scratch with a guided, one-question-at-a-time interview, then build the folders, backup and first card. Use when the person says "set up my cortex", "set up cortex", "start my cortex", "get me started", "I just installed cortex", "how do I begin", or when the start hook says Cortex is installed but not set up yet.
---

# Set up my cortex

The person starts with an empty cortex. You interview them level by level, explain each level, show the full plan, and build only when they say yes. They do not write code; you run every command for them.

## Open with why this exists (say this first, before any question)

In three short sentences, in your own words:
"This setup comes from a year of daily work with AI. Every session used to start from zero, and decisions and their reasons got lost between sessions. Each piece you are about to set up fixes one of those problems, and I will show you which one as we go."

Then start Step 1.

## Rules for the whole interview

- Ask ONE question per message. Wait for the answer.
- Offer suggested answers as numbered choices, plus "something else". Suggestions are choices only: never fill pages with example content.
- Before each question, explain in 1-2 plain sentences what the level is for and the best practice. No jargon, no analogies.
- Keep a running summary of their answers. Show it whenever they ask "where are we".
- They can say "go back" at any point; redo that level.
- Nothing is written to disk until the final "yes" in step 5.

## Step 1 - Areas

Explain: "An area is a part of your life you want kept separate - for example your personal life and your work. Keeping them separate means a session about one never pulls in the other by mistake."

Ask: "Which areas should your cortex hold? Pick any:"
1. Personal
2. Work (your main job)
3. Your organisation (name it)
4. Other - tell me the name (for example a board, a side venture, a club)

Turn each answer into a short lowercase folder name (`personal`, `work`, `acme`, `side-venture`). Confirm the names.

## Step 2 - Collections inside each area (one area at a time)

Explain: "Inside each area you keep collections - the kinds of things you track there. Best practice: one home per thing, so any later session can find it."

For each area ask: "In <area>, what do you track? Pick any, or name your own:"
- projects
- sites or locations
- pilots
- committees
- events
- speaking opportunities
- something else

Then explain once: "People and organisations get their own shared folders at the top, not inside an area, because one person often shows up across several areas. Meetings are kept inside the area they belong to."

Ask whether they want a `meetings` folder in each area (default yes).

## Step 3 - Page types

Explain each in one line, with one example line, then ask "Any questions before I show you the plan?":

| Page | What it holds | Example line |
|---|---|---|
| session | what happened in one working session and what is still open | "Reviewed the pilot's Q3 numbers; waiting on the budget sheet." |
| decision | what was decided, why, and what was rejected | "Quarterly reports move to the member portal, because email copies went stale." |
| lesson | a trap you hit and how to avoid it next time | "Exports from the portal drop images - always check the PDF." |
| insight | something non-obvious you learned | "Members respond faster to a one-page summary than to the full deck." |
| how-to | a repeatable way of doing something | "How I prepare a member-meeting talk." |
| person | who someone is, history, open promises | "Alex Rivera - leads the roadmap work." |
| organisation | what it is and your relationship | "Northfield Education Trust - owns the pilot site." |
| meeting | who, decisions, actions, follow-ups | "2026-10-14 Northfield launch prep." |

Also show the follow-up line they will see in pages: `- [ ] @alex-rivera send the roadmap doc (due 2026-10-15) {theirs}` - "{mine} means you owe it, {theirs} means someone owes it to you."

## Step 4 - Where it lives and backup

Ask: "Where should your cortex live on this Mac?"
1. `~/cortex` (recommended)
2. Somewhere else - tell me

If the path is inside iCloud Drive, Desktop/Documents with iCloud sync on, OneDrive, Dropbox or Google Drive, warn: "Sync folders damage the backup history. Please pick a normal folder; your private GitHub copy is the backup." Re-ask.

Ask: "Back it up to a private GitHub repository?" (recommended yes). Explain: "Every time you log, your pages are saved to a private copy on GitHub that only you can see. A weekly backup also runs every Sunday evening, in case anything was left behind."

If yes, ask what to call the repository, with a suggestion they can accept: "I'll call the repository `<firstname>-cortex` (for example `dan-cortex`; only you will see it). Say 'ok' or give another name." Use exactly the name they give (lowercase, hyphens for spaces). Never pick the name yourself. Below, `<repo>` is that name.

## Step 5 - Show the full plan and wait for yes

Print the full tree with their real names, for example:

```
~/cortex/
  CLAUDE.md, kit.yaml, home.md
  people/   organisations/   sources/   inbox/
  personal/  (_index.md, meetings/)
  acme/       (_index.md, meetings/, sites/, pilots/, committees/)
```

Say: "Collection folders start empty. Each project or center gets its own folder the first time you work on it." Ask: "Shall I build this? (yes / change something)". Build ONLY on yes.

## Step 6 - Build (you run every command; tell them what each does in one line)

1. **Tools check:** `xcode-select -p`. If it fails: "Your Mac needs Apple's free command line tools for backup. A window will open - click Install, it takes a few minutes." Run `xcode-select --install`, wait for them to confirm, re-check.
2. **Folders:** create vault root, `people/`, `organisations/`, `sources/`, `inbox/`, `_cortex/`, each area folder, its `meetings/` if chosen, and each collection folder (add an empty `.gitkeep` so git keeps empty folders).
3. **Files from templates** in `${CLAUDE_PLUGIN_ROOT}/templates/vault/`:
   - `CLAUDE.md` -> vault `CLAUDE.md` (keep the `<!-- cortex:begin -->` ... `<!-- cortex:end -->` block exactly; their own notes go below it).
   - `kit.yaml` -> vault `kit.yaml`; fill in name, areas, collections per area, vault path, github yes/no, `kit_version`, `teach: full`, `setup_date` (today, local `date +%F`).
   - `gitignore` -> vault `.gitignore`.
   - `area_index.md` -> `<area>/_index.md` for each area, filling id `area-<area>`, title, created/updated today, summary from what they said the area is for (ask one line if they did not say).
4. **Pointer file:** write `~/.cortex/config.json` as `{"vault": "<absolute path>", "kit_version": "<version from kit.yaml>"}`.
5. **Git:** `git init` in the vault, set branch `main`, first commit of the files you created (by name, not `git add .`).
6. **Private GitHub repo (if yes):**
   - If `gh auth status` succeeds: `gh repo create <repo> --private --source <vault> --remote origin --push`.
   - Otherwise walk them through it: open https://github.com/new, name it `<repo>`, choose **Private**, do not add a README, click Create; they paste the URL; you run `git remote add origin <url>` and `git push -u origin main`. If the push asks for sign-in, explain the browser prompt.
   - Never create a public repository. Double-check with `gh repo view --json visibility` when gh is available.
7. **Weekly backup:** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cortex.py install-backup`.
8. **Keep chat history longer:** read `~/.claude/settings.json` (treat missing as `{}`), set `"cleanupPeriodDays": 365` and keep every other key as it was, write it back, then show them the before/after line. Explain: "Claude normally deletes your chat history after 30 days. Suggest needs it to spot what you repeat, so I kept it for a year. It stays on this Mac."
9. **Phone access (explain, do not change settings):** "You can continue a session from your phone while this Mac is on, using Remote Control in the Claude app. Your organisation's Claude admin may need to switch it on." Offer to show how later.
10. **Build and card:** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cortex.py build`; fix any error it reports, then `cortex.py card` and show the card.

If any step fails, say in plain words what failed and what you will try; never leave a half-built vault silently. Run `cortex.py doctor` at the end and show its result.

## Step 7 - The tour: show everything they now have

Do not wait to be asked. Read `${CLAUDE_PLUGIN_ROOT}/docs/WHAT-YOU-HAVE.md` and present it with their real values filled in:
- their vault path
- their GitHub repo URL (from `git -C <vault> remote get-url origin`)
- their areas

Describe hooks and skills only as that file does, never from memory. Show it in four short parts. Pause after each and ask "Any questions on this part?":
1. **Where your cortex lives and how to look at it.** Run `open <vault>` so Finder opens the folder while you explain. Mention the GitHub copy, and Obsidian as an optional free viewer.
2. **What runs on its own.** The hooks table: when, what, why it helps.
3. **What you can ask for.** The skills table, with the phrases to say.
4. **Backup, help and what's next.** Feedback goes through "send feedback". Contact is info@thehimanshushukla.com. The next updates are in "what's coming next".

Close the tour with: "You don't need to remember any of this. Say 'how does my cortex work' any time and I'll show it again."

## Step 8 - First real session

Say: "Your cortex is ready and empty. Now do some real work - for example, tell me about something you are working on this week. When you are done, just say 'log this' and I will write it up and show you what I wrote and why."

Then offer, only once: "If you want, we can also bring in your OneNote notes now - you export a notebook and I sort each page into the right place for you to approve. Or we can do it any time later." If yes, hand over to the `import` skill.

## Teaching note (end of setup)

End with: "I built only the structure you chose and nothing else, so everything in your cortex from now on comes from your own work. Each time you log, the start card gets better at telling the next session where you left off." (If `teach: short`: "Structure built - your work fills it from here.")
