# Cortex plugin v0.1 - build spec

The contract every piece of the plugin follows. Skills, hooks and scripts all read this; if one of them needs something this file does not say, change this file first.

## Who it is for

A professional on a Mac with a paid Claude plan who does not write code. They use the Claude desktop app's Code tab or Claude Code in a terminal. They start with an **empty** cortex. A guided setup builds the structure they choose, and the cortex teaches them how it works as they go. Old notes come in only when they ask, through the sorting desk.

## Two pieces

| Piece | Where | Who edits |
|---|---|---|
| Engine (this plugin: skills, hooks, scripts, templates) | Plugin cache, `~/.cortex/engine` | Nobody; replaced on update |
| Record (the vault: their markdown pages) | A folder they choose, default `~/cortex`, a git repo backed up to their private GitHub | Them and Claude |

A small pointer file, `~/.cortex/config.json`, tells the hooks where the vault is:

```json
{"vault": "/Users/you/cortex", "kit_version": "0.1.0"}
```

When the pointer file is missing, every hook does nothing except the start hook, which says: "Cortex is installed but not set up yet. Say 'set up my cortex' to begin."

## Requirements

- macOS with Xcode Command Line Tools. These provide both `git` and `python3`. Setup checks for them with `xcode-select -p` and offers `xcode-select --install`.
- All scripts use the **Python standard library only**: no pip, no YAML library.
- No services and no daemons. The one exception is the weekly backup, which is a user LaunchAgent that setup installs. The Gardener's background count (below) is a short run that ends by itself. Its optional weekly LaunchAgent is installed only on a person's yes, never by setup or upgrade.

## Vault layout

The setup interview decides the areas and collections. This example is the shape, not a default:

```
~/cortex/
  CLAUDE.md                 standing instructions (kit-managed block between markers + the person's own part)
  kit.yaml                  the setup answers + kit version (simple key: value, see Frontmatter rules)
  .gitignore
  .claude/                  thin copy for cloud sessions (later)
  home.md                   the map of the cortex: areas, what lives where (generated)
  _cortex/                  generated - never edited by hand
    card.md                 the start card
    index.md                every page: title, type, area, status, summary
    followups.md            open follow-ups by person and date
    sorting-desk.md         import proposals awaiting a decision
    backup.log              last backup runs
    suggest-log.jsonl       Suggest proposals + answers
    journal/<year>-W<week>.md  the weekly journal: counts, and titles of logged pages only
  people/<slug>.md          person pages (shared across areas - one person, one page)
  organisations/<slug>.md   organisation pages (shared across areas)
  sources/<yyyy-mm>/<file>  original imported files, kept as they came
  inbox/                    imported notes waiting for the sorting desk
  <area>/                   e.g. personal/, work/, acme/
    _index.md               what this area is for
    meetings/<yyyy-mm-dd>-<slug>.md
    <collection>/<slug>/    e.g. projects/pilot-project/, sites/northfield/
      _index.md             current state, open items, recent sessions
      sessions/<yyyy-mm-dd>-<slug>.md
      decisions/<slug>.md
      lessons/<slug>.md
      insights/<slug>.md
      how-to/<slug>.md
```

People and organisations sit at the top level because one person spans many areas. Meetings sit in the area they belong to. The thing-level folders (`sessions/`, `decisions/` and so on) are created when the first page of that type is written, not at setup.

## Page types

| type | Folder | Holds | The person's word |
|---|---|---|---|
| `session` | `<thing>/sessions/` | What happened in one working session, why, what is open | session |
| `decision` | `<thing>/decisions/` | What was decided, why, what was rejected, when to reopen | decision |
| `lesson` | `<thing>/lessons/` | A trap hit, the cause, how to avoid it | lesson |
| `insight` | `<thing>/insights/` | Something non-obvious learned | insight |
| `how-to` | `<thing>/how-to/` | A repeatable way of doing something | how-to |
| `thing` | `<thing>/_index.md` | A project / site / pilot / anything tracked: current state | (their collection word) |
| `area` | `<area>/_index.md` | What the area is for | area |
| `person` | `people/` | Who they are, where they fit, history, open promises | person |
| `organisation` | `organisations/` | What it is, relationship, people, history | organisation |
| `meeting` | `<area>/meetings/` | Who, decisions, actions, follow-ups | meeting |
| `note` | anywhere | An imported note after sorting, not yet split into the types above | note |

## Frontmatter rules (the validator enforces these)

Only a small subset of YAML is allowed, so that standard-library Python can parse it:

```
---
id: decision-acme-pilot-project-quarterly-reporting
title: Quarterly reporting moves to the member portal
type: decision
area: acme
thing: pilot-project
status: active
created: 2026-10-12
updated: 2026-10-12
tags: [reporting, pilots]
links: [person-alex-rivera, session-acme-pilot-project-2026-10-12-kickoff]
sources: [sources/2026-10/q3-pilot-notes.pdf]
summary: One sentence that says what this page is.
---
```

- **Line shapes.** Each line is `key: value` or `key: [a, b, c]`. No nesting and no multi-line values. A value containing `: ` is fine, because only the first `: ` splits.
- **Required for every page:**
  - `id`
  - `title`
  - `type`
  - `status`
  - `created`
  - `updated`
  - `summary`
- **Required by type:**
  - `area` for everything except `person` and `organisation`
  - `thing` for `session`, `decision`, `lesson`, `insight` and `how-to` when they sit under a thing
  - `date` for `meeting`
  - `people: [..]` for `meeting`
- **`id`** is globally unique and must equal `<type>-<area>-<thing?>-<filename slug>`, with these exceptions:
  - person pages: `person-<slug>`
  - organisation pages: `organisation-<slug>`
  - area pages: `area-<area>`
  - thing pages: `thing-<area>-<slug>`
- **`status`** is one of `active`, `done`, `superseded`, `archived`, `draft`. A superseded page needs `superseded_by: <id>`.
- **Dates** are `YYYY-MM-DD`, local time.
- **`links`** must name ids that exist. The build reports any link that is not mirrored as a warning, never an error.
- **`sources`** paths must exist in the vault.
- **`chat_id`** is optional: the session a page was logged from, or a list when one page covers several. `cortex.py new session` fills it in. A value that does not look like a session id is a build note, never an error.
- **The folder must match the type and fields.** A decision with `area: acme` and `thing: pilot-project` must live in `acme/*/pilot-project/decisions/`.

## Follow-ups (inside pages, no separate database)

A follow-up is a task line in any page. It names a person, may name a date, and shows whose action it is:

```
- [ ] @alex-rivera send the roadmap doc (due 2026-10-15) (added 2026-10-08) {theirs}
- [ ] @sam-lee intro Acme marketing (due 2026-10-10) {mine} {doing}
- [x] @me rehearse the talk (added 2026-10-01) (done 2026-10-09) {mine}
```

- **`@slug`** must match a page under `people/`. `@me` (or the person's own slug) is their own to-do.
- **`{mine}`** means the person owes it. **`{theirs}`** means someone owes it to them.
- **Dated parts** after the text, all optional, in any order: `(due YYYY-MM-DD)`, `(added YYYY-MM-DD)` (written by log and debrief on every new line), `(done YYYY-MM-DD)`.
- **`{doing}`**, optional, after `{mine|theirs}`: the item is in progress (the board's In progress column).
- **`- [x]`** marks it closed.

The board (`cortex.py board`) shows these lines as cards. A move edits only that one line; see the board skill for what each column writes.

The build collects every open follow-up into `_cortex/followups.md`.

## The chat lane (`connector/`, not yet released)

A separate Node extension for the desktop app's Chat tab. It needs no Python. These rules add to the contract:

- **Proposals.** Chat writes land in `inbox/` as `chat-<date>-<slug>.md` (one saved chat) or `chat-todos.md` (added to-dos). A proposal starts with plain lines `source: chat`, `status: proposed`, `name: ...`, `saved: ...`, with **no `---` rule**. That makes it a loose note to the build, on purpose: `proposed` is not a page status, and its task lines may name people with no page yet, so as a page it would stop the build. Its task lines do not count anywhere until it is accepted. The sections are `## Summary`, `## Decisions`, `## Follow-ups` and `## Open questions`.
- **Accepting** writes one new session page (`source: chat`, `sources:` pointing at the kept proposal), creates a short `people/<slug>.md` for each person who has no page, and moves the proposal to `sources/<yyyy-mm>/`. It never edits an existing page. Text in other places in a hand-edited proposal is carried across as plain text, and a private part goes into the new page's own `## Private` section. A failure on the way undoes the earlier steps.
- **Its own card.** The extension computes the same card as `cortex.py card` from the pages, apart from the hints that name things chat cannot do. A proposal counts only in the inbox line. Until the next `cortex.py build`, `_cortex/card.md` does not include what was accepted in chat.
- **Private parts.** A `## Private` section (down to the next `#` heading of the same or a higher level) and any line tagged `{private}` are left out of every chat tool, including task counts on the card and search matches. Emphasis, tags and underlined headings count as the same heading (`## **Private**`, `Private` over `---`, `## Notes {private}`). A tagged header value shows as `(private)`.
- **Generated files.** `_cortex/` and `home.md` repeat page text with nothing hidden, so chat never opens or searches them, in any spelling of the path. This is the chat tools' rule only: `cortex.py build` still writes private text into them, so they stay plain files on disk and in the backup.
- **Task lines.** A line longer than 4,000 characters is never a task line, in `cortex.py` and in the extension.
- **Vault lookup.** `~/.cortex/config.json` if present and valid, else the folder set in the extension, else `~/cortex`. The card and setup say which folder is in use and why. A config that names a missing folder is reported, and no other folder is tried.
- **Setup from chat.** Writes `~/.cortex/config.json` the way the plugin's setup does when none exists, never over an existing one. So the plugin finds the folder, and its setup skill offers backup only.

## The Gardener (`scripts/gardener.py`, phase 1, no AI)

Finds working sessions that never reached the vault. No model is called, nothing leaves the Mac, and transcripts are only read.

- **Sources.** Claude Code transcripts at `~/.claude/projects/*/*.jsonl` (these include the desktop app's Code tab) and Codex at `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl`. Both formats are internal to those tools, so every read expects bad data. A file in no shape the code knows is counted as "could not understand" and reported. **A plain Claude Chat is not on the Mac and cannot be seen.** That is why the chat connector has "save this chat".
- **What counts as a session.** Skipped: files changed in the last 10 minutes, the session asking (`CLAUDE_CODE_SESSION_ID` or `CODEX_THREAD_ID`), subagent files and sidechains, sessions with fewer than 3 typed messages, small files holding only metadata lines such as `custom-title` or `bridge-session`, and automated runs. An automated run is one whose hook saw `CORTEX_AUTOMATION=1` (a flag in the session state), whose first message starts with `[CORTEX_AUTOMATION]`, whose lines all name an `sdk-*` entrypoint, or a Codex `exec` session. Any other entrypoint, known or not, is a person's work (`cli`, and `claude-desktop` for the Code tab). A fork that starts as a copy of another session (same first message at the same moment, or `forkedFrom` / `forked_from_id` in the file) shares one row with it, the one with the most messages. A session's id comes from the file name, never from inside the file.
- **Covered** when any of these is true: `~/.cortex/sessions/<id>/logged`; `skipped` (the person already said no when asked); a page carries the id in `chat_id`; `written.txt` names a page in the vault. Everything else substantial is **missed**. So is a covered session (not a skipped one) with 10 or more typed messages after the last time it reached the vault, by the `logged` flag, `written.txt` or its page: the file's last 10 message times are enough to tell, and the row says `continued`.
- **Scope, `gardener_scope` in `kit.yaml`.** `cortex` (default): a session can count as missed only if it ran in the vault folder, its typed messages mention the cortex or the vault path, or a tool call named the vault path. `all`: every session. `off`: nothing is scanned and the cached titles are deleted. The default is narrow because someone may run many sessions that have nothing to do with their cortex, and a list that is wrong a third of the time does not get worked through. The start card and assistant replies do not count as a mention, because they name the cortex in every session. The price is that real work in another folder that never mentions the cortex is not listed, so the start card, the board and the command say how many sessions were not checked, and catch-up offers them. A dismissal counts there too.
- **Window.** `--days N` (default 7, at most 30) reaches 2 days further back. A larger N is cut to 30 and the report says so, with the number of older files it did not read. Every run reads up to 32 days back, so older sessions are still counted and warned about. A warning appears when an unlogged Claude Code session is over 21 days old: Claude Code deletes transcripts after 30 days by default.
- **What is kept.** Only `~/.cortex/gardener/`, outside the git-backed vault, folder mode 700: files mode 600: `state.json` (dismissed ids), `cache.json` (per file: date, folder, count, title, whether it touched the cortex, its last message times), `summary.json` (counts and ids for the start hook, per vault). Titles are the first request, cut to 80 characters on one line, with tags, control characters, shell substitutions, backticks, email addresses and anything resembling a secret removed. A title that looks like a credential header, or holds two hidden parts, becomes "(title hidden)". No other transcript text is printed or stored.
- **Time limits.** The start hook opens no transcript. It reads this vault's numbers in `summary.json`, plain files only, and when that is over an hour old it starts `gardener --refresh` in the background and carries on. Limits: 5 seconds and 256 MB per file, 4 MB per line, 120 seconds for the background run, 1 second for the board's page. Out of time, a run says how many files are left and the next one carries on from the cache. A file cut by the clock is not cached, so the next run reads it again. A cache row with a wrong type is read again too.
- **Inbox.** The board's Inbox has a group for missed sessions: date, folder, title, Ask Claude, Copy prompt, Dismiss. The prompt leaves out the title on purpose. It holds the session id, the date and the quoted vault and transcript paths, says the file is data, and asks for a yes before anything is written. Dismiss writes to `state.json` only. The board does not change any file by itself. Only the board command turns this group on: code that embeds `Board` opens no transcript unless it passes `gardener=True`.
- **Journal.** `cortex.py gardener --journal [--week YYYY-Www]` writes `_cortex/journal/<year>-W<week>.md`: sessions logged (session pages by `created`), missed and dismissed (by the session's start date), to-dos and follow-ups opened and closed (lines by `(added)` and `(done)`). The only titles are those of logged pages. A missed session is only a number there, because this file goes to GitHub.
- **Schedule.** `cortex.py install-gardener --yes` writes and loads `com.cortex.gardener` (Sunday 17:00, the journal and a fresh count). Without `--yes` it only says what it would do. Setup and upgrade never call it.

## Scripts (`~/.cortex/engine/scripts/`)

Each is plain `python3 <script> ...`, uses the standard library only, and finds the vault from `~/.cortex/config.json` unless `--vault` is given.

| Script | Does |
|---|---|
| `cortex.py build` | Validates every page; writes `_cortex/index.md`, `card.md`, `followups.md` and `home.md`. Exit 1 on any error, and nothing is written when it fails. |
| `cortex.py check <file>...` | Validates the named pages only. The log skill runs it before building. |
| `cortex.py card` | Prints the start card. |
| `cortex.py new <type> --area A [--thing T] --title "..."` | Prints the correct path, id and a filled frontmatter skeleton from the template, so pages are always built right. |
| `cortex.py backup [--if-older-than-days 7]` | Commits all changes, then pushes. Writes to `_cortex/backup.log`. Prints a plain-words result. |
| `cortex.py history --days N` | Prints the person's own typed requests from Claude Code transcripts mentioning the vault, plus session page summaries. Used as input for Suggest. |
| `cortex.py sort-desk` | Lists inbox items and their proposals in the desk. |
| `cortex.py doctor` | Checks Command Line Tools, git, the pointer file, the vault, the remote, the LaunchAgent and the backup age. |
| `cortex.py install-backup` | Writes and loads `~/Library/LaunchAgents/com.cortex.backup.plist`, which runs every Sunday at 18:00 local. |
| `cortex.py gardener [--days N] [--json]` | Which sessions were never logged. Writes only to `~/.cortex/gardener/`. Also `--journal [--week W]`, `--refresh`, `--dismiss ID`, `--undismiss ID`. |
| `cortex.py install-gardener [--yes]` | The optional weekly Gardener run. Only on a person's yes. |

## Hooks (`hooks/hooks.json`)

Each hook is `python3 ~/.cortex/engine/scripts/hooks.py <event>`, and each one **fails soft**: any internal error exits 0.

| Event | What it does |
|---|---|
| SessionStart (startup, resume, clear) | No config: print the setup hint. Otherwise print `_cortex/card.md` as context, plus "last backup N days ago" if that is more than 7, plus one line "N sessions this week were never logged" and/or "M elsewhere were not checked - say 'catch up'" when either is not zero. A missed weekly backup and a stale Gardener count are run in the background. |
| UserPromptSubmit | Chat-length warning. When the transcript file passes about 60% of the window (an estimate from its size), say once "this chat is getting long - consider logging and starting fresh". At about 80%, say it again with a checkpoint hint. Each level is said once per session. |
| PreCompact | Appends a checkpoint marker to the session state, so the log skill knows a summary happened. |
| Stop | Gentle log gate. If the session wrote files inside the vault, or ran for more than 10 minutes, and is not logged, block once with: "Want me to log this session? Say 'log it' or 'skip'." At most 2 blocks, then let go and record the session as unlogged. Sessions that never touched the vault and are short are never blocked. |
| PreToolUse (Bash, Write, Edit) | Safety guard: refuse `rm -rf` on the home or vault root, force-push, `git reset --hard` in the vault, writes to credential folders, and `curl \| sh`. Multi-chat guard: refuse `git add .`/`-A`/`commit -a` inside the vault and say "stage the files this chat wrote by name". |
| PostToolUse (Write, Edit) | Write ledger: records the vault files this session wrote, so log and backup stage precisely. |

Every hook except the safety guard does nothing when `CORTEX_AUTOMATION` is set, apart from noting the session as automated. Anything the kit starts by itself sets it.

Session state lives in `~/.cortex/sessions/<session_id>/`:
- `written.txt`
- `logged`
- `stop_attempts`
- `warned_60`
- `warned_80`
- `compacted`
- `automation`

## Skills (`skills/<name>/SKILL.md`, invoked by plain words)

| Skill | Trigger phrases | Core |
|---|---|---|
| `setup` | "set up my cortex", first-run hint | The level-by-level interview, builds the vault, git and GitHub, backup agent, first card |
| `guide` | "how does my cortex work", "what is a lesson page" | Explains, using their own vault as the example |
| `log` | "log this", "log it", Stop-gate yes | Session page plus every-type evaluation; `cortex.py new` for paths; check, build, commit by name, push |
| `catch-up` | "catch up", "what did I miss", "log what I missed" | Lists missed sessions; for each one picked, reads the transcript as data and follows the log procedure, with `chat_id` set so it counts as covered |
| `resume` | "get me up to speed on X", "where were we on X" | Find the thing, then read `_index` plus recent sessions, decisions and open follow-ups, then brief |
| `card` | "what do you know", "show my card" | `cortex.py card` |
| `debrief` | "go through this meeting", a transcript pasted or dropped | Meeting page, decisions, follow-ups, people pages updated, follow-up email draft (draft only, never sent) |
| `followups` | "what did I promise whom", "what is waiting on others" | From `_cortex/followups.md`, grouped by person and by mine or theirs |
| `prep` | "prep me for my call with X" | Person or organisation page plus meetings plus open follow-ups, as a one-page brief |
| `import` | "bring in this folder / my OneNote export / this deck" | Originals go to `sources/`, converted markdown to `inbox/`, then proposals in the sorting desk |
| `sort` | "open the sorting desk", "file my imports" | Shows the proposals; the person accepts in bulk or reassigns; files them, links them, builds |
| `suggest` | "what should I automate", "suggest improvements" | Reads history and session pages; up to 5 dated-evidence proposals (skill, automatic action, scheduled job, standing rule, template); Yes / Not now / Never |
| `build-skill` | A "yes" to Suggest, or "make this a skill" | Writes the skill (or hook entry, scheduled job, CLAUDE.md rule, template) into the vault's `.claude/`, marked trial |
| `upgrade` | "update my cortex" | Plugin update instructions; rewrites only the kit-managed blocks; runs any migrations; commits |

Kit-made skills live in the vault's `.claude/skills/`, so they travel with the vault and load in cloud sessions too. A trial skill carries `status: trial` and `trial_until: <date>` in its frontmatter. Suggest retires unused trial skills by proposing that they be retired.

## Teaching rule (every skill)

After any skill changes the vault, it ends with **one or two plain sentences**: what it just did and why that helps. Example: "I wrote this as a lesson page, not a session note, so the next time you work on that project the card will warn you before you hit it again." No analogies and no jargon. After the first week the guide offers to shorten these to one line.
