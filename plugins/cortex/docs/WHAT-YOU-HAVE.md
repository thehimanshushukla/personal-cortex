# What your cortex gives you

The one fact sheet about this plugin. Setup reads it to give the tour at the end, and the guide reads it to answer questions. **Describe hooks and skills only from this file, never from memory.** Replace `<vault>`, `<repo url>` and `<areas>` with the person's real values from `kit.yaml` and `git remote get-url origin`.

## 1. Where your cortex lives and how to look at it

- **On this Mac:** `<vault>` (normally `~/cortex`). Every page is a plain `.md` text file you can open in any text editor. Say "open my cortex" and the folder opens in Finder.
- **Your private GitHub copy:** `<repo url>`. Setup creates it as private, and GitHub shows a "Private" label next to its name. Pages read nicely there, and it works from your phone's browser too.
- **Nicer reading (optional, free):** [Obsidian](https://obsidian.md) can open `<vault>` as a "vault". It shows the pages with clickable links and a map of how they connect. Opening it this way changes nothing in your cortex unless you edit pages yourself.
- **Key files to know:**
  - `home.md`: the map of your areas and things
  - `_cortex/card.md`: the start card
  - `_cortex/followups.md`: everything owed, both ways
  - `_cortex/sorting-desk.md`: imports waiting for your decision

## 2. What runs on its own (hooks)

You never start these. Your coding tool (Claude Code or Codex) runs them at fixed moments.

| When | What it does | Why it helps you | Why it exists (what went wrong first) |
|---|---|---|---|
| A session starts | Shows your start card: what is active, latest decisions and lessons, follow-ups due this week, imports waiting, last backup. Runs a missed weekly backup. | Every session starts where the last one left off. You rarely have to re-explain your work. | Every new chat started from zero, and a good part of each session went on re-explaining the project. |
| You send a message | Says once when the chat's working memory is about 60% full, and once at about 80%. | You log and start fresh before answers get worse. | Very long chats gave weaker answers and cost the most: in one review of the maker's own plan, 72% of the spend sat in turns where the chat had grown past 150K tokens. |
| Before a long chat is compressed | Marks that a summary happened, so logging knows to check nothing was lost. | Decisions made early in a long chat still get recorded. | When a long chat was summarised, early decisions and their reasons quietly disappeared. |
| Claude finishes a reply | If this chat changed your cortex or ran 10+ minutes and is not logged, asks once: "Want me to log this session?" (at most twice). | Work is not lost when you close the window. | In a hurry, sessions got closed without notes, and the reasoning behind decisions was gone the next week. A written rule to log was not enough; a reminder at the moment of closing was. |
| Before a command or file write | Refuses deleting your home or cortex folder, overwriting the history of your GitHub backup, running scripts straight from the internet, writing into password folders, and one chat saving another chat's half-done pages. | Mistakes that cannot be undone are blocked first. | With several chats open at once, one chat's "save everything" swept up another chat's unfinished work, three times in one day. |
| After a file is written | Notes which cortex files this chat wrote. | Logging and backup save exactly this chat's work. | Same day as above: the fix for "save everything" was knowing precisely which files each chat wrote. |
| Every Sunday 18:00 (and next start if missed) | Saves and pushes everything to your private GitHub. | Your work survives a lost or broken Mac. | Work piled up for six days with nearly 200 changes not backed up anywhere. |

The short version: each of these hooks exists because something went wrong first in a year of daily use. They are written down so it does not happen to you.

## 3. What you can ask for (skills)

Say these in your own words. Exact phrases are not needed.

| Say | What happens | Value | Why it exists |
|---|---|---|---|
| "log this" | Writes up the session. It also saves each decision, lesson, insight, how-to, new person and follow-up as its own page, then checks, builds and backs up. | Nothing learned stays buried in a chat. | In one nine-day stretch, 44 decisions, problems and lessons were written down only inside session notes, where nobody would ever find them. |
| "get me up to speed on X" | A deep brief on a project, person or organisation from your pages. | Pick up anything in a minute. | "Get me up to speed" turned out to be about a quarter of the sessions the maker started. It was worth doing properly, every time. |
| "show my card" | The start card, on demand. | A quick view of where things stand. | Same reason as the start card: no session should start from zero. |
| "go through this meeting" (paste a transcript or give a file) | Creates a meeting page and decision pages. Writes follow-ups, updates people pages and drafts a follow-up email for you to send. | A meeting becomes actions and a record in minutes. | Turning a meeting into actions by hand was repeated in more than 15 sessions before it became a skill. |
| "what did I promise whom" | Every open follow-up by person, yours and theirs, overdue first. | Nothing slips. | Meeting items owned by other people kept turning into personal to-dos. Follow-ups now say whose they are: mine or theirs. |
| "prep me for my call with X" | One page covering who they are, history, open items and three talking points. | You walk in prepared. | Built for this kit: everything needed is already in your pages, so a call never starts cold. |
| "bring in this folder / my OneNote export / this deck" | Keeps the original file in `sources/` and turns each file into a note in `inbox/`. Then proposes where each note belongs (area, project, type, tags, links) on the sorting desk. | Old notes join your cortex in the right place instead of sitting idle. | Built for this kit: imported notes that land in one folder are rarely opened again. |
| "open the sorting desk" | Shows the proposals. Say "accept all", "accept all except 3", or "move 4 to ...". Nothing is filed until you confirm. | You stay in control of where everything goes. | Automatic filing gets some things wrong. You decide, the cortex does the work. |
| "what should I automate" | Reads how you have worked and proposes up to 5 improvements, each with the dates it saw the pattern: a new skill, an automatic action, a scheduled job, a standing rule or a template. Answer Yes, Not now or Never. | The cortex learns your way of working. This becomes useful after a week or two of use. | The skills above were found by reading months of sessions for repeated work. Suggest does that reading for you, continuously. |
| (after a Yes) | Builds what you approved. A new skill starts on a 30-day trial and is retired if unused. | Only improvements you use stay. | An audit found 194 skills installed, only 5 of them written by the person using them. Unused skills pile up unless something retires them. |
| "what skills can I add" | Shows a short vetted list of add-ons (Anthropic's document skills, skill creator, productivity and role plugins), with who makes each and its license. | Grow the cortex safely. | Add-ons can run code on your Mac, so only known publishers are listed, and nothing installs without your yes. |
| "check my CLAUDE.md" | Reviews your instruction file: too long, history mixed in, rules that keep being broken, procedures that should be skills. Changes only with your yes. | Instructions stay short enough to be followed. | Instruction files that gain a rule after every bad result grow long, and long files get followed less. |
| "how does my cortex work" | Explains any part, using your own pages. | Learn as you go. | A system you do not understand is a system you stop using. |
| "back up my cortex" | Saves and pushes to GitHub now. | Your latest work is safe on GitHub right now. | See the weekly backup above. |
| "update my cortex" | Moves you to a newer version without touching your pages. | New features, nothing lost. | Copies of a kit that cannot be updated go stale on every machine. |
| "send feedback" / "I wish it could..." / "something is broken" | Saves your note, shows you exactly what will be sent, and on your yes sends it to the maker's feedback form (an email draft if you are offline). | Your requests shape the next version. | This kit gets better from the people using it. |
| "what's coming next" | Shows what the next updates bring. | You know what to expect. | People asked what was planned; the answer is now one question away. |

## 4. Backup

- Every log saves and pushes to your private GitHub.
- Every Sunday at 18:00 a weekly backup saves anything left over. If the Mac was asleep, it runs at your next session.
- Your pages are plain files you own. They work without this plugin, and you can read them on GitHub from anywhere.

## 5. Learn more

The thinking behind every piece is written up in the maker's Claude Code series: [thehimanshushukla.com/blog/claude-code-setup-series](https://thehimanshushukla.com/blog/claude-code-setup-series?utm_source=cortex). The guide links the right article when a question goes deeper.

## 6. Help, feedback and what's next

- **Feedback or ideas:** say "send feedback". You see exactly what is sent before it goes.
- **Problems:** say "something is broken". It runs a health check and includes the result in the report.
- **Contact:** info@thehimanshushukla.com
- **What's next:** say "what's coming next", or see `docs/ROADMAP.md` in the plugin.
