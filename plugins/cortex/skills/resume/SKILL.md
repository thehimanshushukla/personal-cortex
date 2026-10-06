---
name: resume
description: Give a deep brief on any project, site, pilot, person or organisation from the cortex - current state, recent sessions, decisions, lessons and open follow-ups - so work picks up where it left off. Use when the person says "get me up to speed on X", "where were we on X", "catch me up on X", "what's the status of X", "remind me about X", "continue the X work", or "what do we know about X".
---

# Get me up to speed on X

Build a brief from the record, not from memory. Read only what is needed.

## 1. Find the thing

- Vault: `~/.cortex/config.json` -> `vault`. If missing: suggest "set up my cortex" and stop.
- Search `_cortex/index.md` for the name they used (titles, ids, summaries). Also check `people/` and `organisations/` filenames.
- One clear match: say which ("Pilot project, in Acme"). Several: list up to 5 as numbered choices and ask. None: say so, show the 5 most recently updated things from the index, and ask whether it is one of those or something new.

## 2. Read in this order (stop when you have enough)

For a thing:
1. `<thing>/_index.md` - current state, open items, recent sessions.
2. The 3 most recent `sessions/` pages (by date in the filename).
3. All `decisions/` with `status: active`, newest first; note any superseded ones only if relevant.
4. `lessons/` - all of them (they are the traps to avoid).
5. Open follow-ups for this thing from `_cortex/followups.md`.
6. Person and organisation pages linked from the above, only their summary and open promises.

For a person or organisation: their page, meetings that list them (`grep` the `people:` field in `*/meetings/`), open follow-ups with `@slug`, and the things they are linked to.

## 3. Write the brief

Keep it to one screen:

- **Where it stands** - 2-4 lines from the current state, with the date of the last session.
- **Recent sessions** - one line each, newest first.
- **Decisions in force** - one line each with the why in a few words.
- **Watch out for** - lessons, one line each.
- **Open follow-ups** - `{mine}` first, then `{theirs}`, with due dates; flag overdue ones.
- **People involved** - name, role, one line.
- **Suggested next step** - one line, based on the open items.

Name the pages you used at the end in one line (titles, not paths), so they can ask to open any of them.

If the `_index.md` current state is older than the newest session, say so in one line and offer to refresh it after this session's log.

## Teaching note

End with: "This brief came only from pages you logged, so the more you log, the sharper it gets." Say it only in the first week or if `teach` is `full`; with `teach: short` skip it.
