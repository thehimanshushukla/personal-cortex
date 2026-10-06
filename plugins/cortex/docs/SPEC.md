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
- No services and no daemons. The one exception is the weekly backup, which is a user LaunchAgent that setup installs.

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
- **The folder must match the type and fields.** A decision with `area: acme` and `thing: pilot-project` must live in `acme/*/pilot-project/decisions/`.

## Follow-ups (inside pages, no separate database)

A follow-up is a task line in any page. It names a person, may name a date, and shows whose action it is:

```
- [ ] @alex-rivera send the roadmap doc (due 2026-10-15) {theirs}
- [ ] @sam-lee intro Acme marketing (due 2026-10-10) {mine}
```

- **`@slug`** must match a page under `people/`.
- **`{mine}`** means the person owes it. **`{theirs}`** means someone owes it to them.
- **`- [x]`** marks it closed.

The build collects every open follow-up into `_cortex/followups.md`.

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

## Hooks (`hooks/hooks.json`)

Each hook is `python3 ~/.cortex/engine/scripts/hooks.py <event>`, and each one **fails soft**: any internal error exits 0.

| Event | What it does |
|---|---|
| SessionStart (startup, resume, clear) | No config: print the setup hint. Otherwise print `_cortex/card.md` as context, plus "last backup N days ago" if that is more than 7. A missed weekly backup is run in the background. |
| UserPromptSubmit | Chat-length warning. When the transcript file passes about 60% of the window (an estimate from its size), say once "this chat is getting long - consider logging and starting fresh". At about 80%, say it again with a checkpoint hint. Each level is said once per session. |
| PreCompact | Appends a checkpoint marker to the session state, so the log skill knows a summary happened. |
| Stop | Gentle log gate. If the session wrote files inside the vault, or ran for more than 10 minutes, and is not logged, block once with: "Want me to log this session? Say 'log it' or 'skip'." At most 2 blocks, then let go and record the session as unlogged. Sessions that never touched the vault and are short are never blocked. |
| PreToolUse (Bash, Write, Edit) | Safety guard: refuse `rm -rf` on the home or vault root, force-push, `git reset --hard` in the vault, writes to credential folders, and `curl \| sh`. Multi-chat guard: refuse `git add .`/`-A`/`commit -a` inside the vault and say "stage the files this chat wrote by name". |
| PostToolUse (Write, Edit) | Write ledger: records the vault files this session wrote, so log and backup stage precisely. |

Session state lives in `~/.cortex/sessions/<session_id>/`:
- `written.txt`
- `logged`
- `stop_attempts`
- `warned_60`
- `warned_80`
- `compacted`

## Skills (`skills/<name>/SKILL.md`, invoked by plain words)

| Skill | Trigger phrases | Core |
|---|---|---|
| `setup` | "set up my cortex", first-run hint | The level-by-level interview, builds the vault, git and GitHub, backup agent, first card |
| `guide` | "how does my cortex work", "what is a lesson page" | Explains, using their own vault as the example |
| `log` | "log this", "log it", Stop-gate yes | Session page plus every-type evaluation; `cortex.py new` for paths; check, build, commit by name, push |
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
