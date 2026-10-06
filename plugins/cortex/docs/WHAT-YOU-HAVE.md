# What your cortex gives you

The one fact sheet about this plugin. Setup reads it to give the tour at the end, and the guide reads it to answer questions. **Describe hooks and skills only from this file, never from memory.** Replace `<vault>`, `<repo url>` and `<areas>` with the person's real values from `kit.yaml` and `git remote get-url origin`.

## 1. Where your cortex lives and how to look at it

- **On this Mac:** `<vault>` (normally `~/cortex`). Every page is a plain `.md` text file you can open in any text editor. Say "open my cortex" and the folder opens in Finder.
- **Your private GitHub copy:** `<repo url>`. Only you can see it. Pages read nicely there, and it works from your phone's browser too.
- **Nicer reading (optional, free):** [Obsidian](https://obsidian.md) can open `<vault>` as a "vault". It shows the pages with clickable links and a map of how they connect. It changes nothing in your cortex.
- **Key files to know:**
  - `home.md`: the map of your areas and things
  - `_cortex/card.md`: the start card
  - `_cortex/followups.md`: everything owed, both ways
  - `_cortex/sorting-desk.md`: imports waiting for your decision

## 2. What runs on its own (hooks)

You never start these. Claude Code runs them at fixed moments.

| When | What it does | Why it helps you |
|---|---|---|
| A session starts | Shows your start card: what is active, your latest decisions and lessons, follow-ups due this week, imports waiting, last backup. If the weekly backup was missed because the Mac was asleep, it runs it now. | Every session starts where the last one left off. You never re-explain your work. |
| You send a message | Watches how long the chat is getting. It says so once at about 60% full and once at about 80% full. | Long chats get worse answers and lose detail. You get told in time to log and start fresh. |
| Before a long chat is compressed | Marks that a summary happened, so the log knows to check nothing was lost. | Decisions made early in a long chat still get recorded. |
| Claude finishes a reply | If this chat changed your cortex, or ran 10 minutes or more, and has not been logged, it asks once: "Want me to log this session?" Say "log it" or "skip". It asks at most twice. | Work is not lost when you close the window. |
| Before a command runs or a file is written | Refuses commands that could do damage:<br>- deleting your home or cortex folder<br>- force-pushing over your backup<br>- running scripts straight from the internet<br>- writing into password and key folders<br>It also stops one chat from saving another chat's half-finished pages. | Mistakes that cannot be undone are blocked before they happen. |
| After a file is written | Notes which cortex files this chat wrote. | Logging and backup save exactly this chat's work. |

## 3. What you can ask for (skills)

Say these in your own words. Exact phrases are not needed.

| Say | What happens | Value |
|---|---|---|
| "log this" | Writes up the session. It also saves each decision, lesson, insight, how-to, new person and follow-up as its own page, then checks, builds and backs up. | Nothing learned stays buried in a chat. |
| "get me up to speed on X" | A deep brief on a project, person or organisation from your pages. | Pick up anything in a minute. |
| "show my card" | The start card, on demand. | A quick view of where things stand. |
| "go through this meeting" (paste a transcript or give a file) | Creates a meeting page and decision pages. Writes follow-ups, updates people pages and drafts a follow-up email for you to send. | A meeting becomes actions and a record in minutes. |
| "what did I promise whom" | Every open follow-up by person, yours and theirs, overdue first. | Nothing slips. |
| "prep me for my call with X" | One page covering who they are, history, open items and three talking points. | You walk in prepared. |
| "bring in this folder / my OneNote export / this deck" | Keeps the original file in `sources/` and turns each file into a note in `inbox/`. Then proposes where each note belongs (area, project, type, tags, links) on the sorting desk. | Old notes join your cortex in the right place instead of sitting idle. |
| "open the sorting desk" | Shows the proposals. Say "accept all", "accept all except 3", or "move 4 to ...". Nothing is filed until you confirm. | You stay in control of where everything goes. |
| "what should I automate" | Reads how you have worked and proposes up to 5 improvements, each with the dates it saw the pattern: a new skill, an automatic action, a scheduled job, a standing rule or a template. Answer Yes, Not now or Never. | The cortex learns your way of working. This becomes useful after a week or two of use. |
| (after a Yes) | Builds what you approved. A new skill starts on a 30-day trial and is retired if unused. | Only improvements you use stay. |
| "how does my cortex work" | Explains any part, using your own pages. | Learn as you go. |
| "back up my cortex" | Saves and pushes to GitHub now. | Peace of mind. |
| "update my cortex" | Moves you to a newer version without touching your pages. | New features, nothing lost. |
| "send feedback" / "I wish it could..." / "something is broken" | Saves your note and opens a ready-to-send email to the maker. You press Send. | Your requests shape the next version. |
| "what's coming next" | Shows what the next updates bring. | You know what to expect. |

## 4. Backup

- Every log saves and pushes to your private GitHub.
- Every Sunday at 18:00 a weekly backup saves anything left over. If the Mac was asleep, it runs at your next session.
- Your pages are plain files you own. They work without this plugin, and you can read them on GitHub from anywhere.

## 5. Help, feedback and what's next

- **Feedback or ideas:** say "send feedback". The plugin drafts the email for you.
- **Problems:** say "something is broken". It runs a health check and includes the result in the email draft.
- **Contact:** info@thehimanshushukla.com
- **What's next:** say "what's coming next", or see `docs/ROADMAP.md` in the plugin.
