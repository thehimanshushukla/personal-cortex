---
name: log
description: Write up the current session into the cortex - a session page plus any decisions, lessons, insights, how-tos, people, organisations and follow-ups it produced - then check, build and back up. Use when the person says "log this", "log it", "log the session", "save this", "write this up", "record this", or answers yes when the end-of-session reminder asks to log.
---

# Log this session

Turn what happened in this conversation into pages in the cortex, so the next session starts from it. Plain words throughout; the person does not see commands unless they ask.

## 0. Find the vault and session

- Vault path: `~/.cortex/config.json` -> `vault`. If missing, say "Your cortex isn't set up yet - say 'set up my cortex'." and stop.
- Session id: env `CLAUDE_CODE_SESSION_ID`. State folder: `~/.cortex/sessions/<session_id>/`.
- Read `kit.yaml` (areas, collections, `teach`).

## 1. Which thing was this about?

Decide the area and thing (project, site, pilot...) from the conversation. If it is clear, say which in one line. If unclear, ask one question with choices from existing folders (`ls <area>/<collection>/`).

If the thing does not exist yet, ask: "This looks new. Shall I create <name> under <area> / <collection>?" On yes, create `<area>/<collection>/<slug>/_index.md` with `cortex.py new thing ...` output. A session can touch more than one thing; log each in its own folder.

## 2. Evaluate EVERY type (do not skip any)

Go through this list and decide for each one. Say the result for each in your own working notes; tell the person only the ones that produce pages.

| Type | Ask yourself |
|---|---|
| session | Always one page: what we set out to do, what was done and how, what is still open. |
| decision | Was anything decided? Each decision gets its own page with the why, what was rejected, and when to reopen. **A decision that only lives inside a session page is not captured** - nobody will find it there later. |
| lesson | Did something go wrong or nearly go wrong? Cause and how to avoid it. |
| insight | Did we learn something non-obvious? |
| how-to | Did we work out a repeatable way of doing something? |
| person | Was someone new mentioned, or did we learn something about a known person? Create or update `people/<slug>.md`. |
| organisation | Same for organisations. |
| follow-ups | Any promise made, by the person or to them? Write follow-up lines (format below) in the session page and the person page. |

If something already has a page (a decision being changed, a person already known), **update that page** with a dated line instead of creating a duplicate. If a decision replaces an older one, set the old one `status: superseded` and `superseded_by: <new id>`.

Follow-up line format:
```
- [ ] @alex-rivera send the roadmap doc (due 2026-10-15) {theirs}
```
`{mine}` = the person owes it; `{theirs}` = someone owes it to them. Close done ones as `- [x]`.

## 3. Write pages the right way

For each page, get the correct path, id and frontmatter from the script, never by guessing:
```
python3 ~/.cortex/engine/scripts/cortex.py new <type> --area <area> [--thing <thing>] --title "<title>"
```
Write the page at the path it prints, keeping its frontmatter and filling the body. Today's date from `date +%F` (local time). Use `[[id]]` style links in the body only for pages that exist; also list them in `links:`.

Session page body sections: **What we set out to do**, **What was done**, **Decisions** (one line each, linking the decision pages), **Open / next** (follow-up lines).

## 4. Update the thing's current state

Edit `<thing>/_index.md`: refresh "Current state" (2-4 lines), "Open items", and add the session to "Recent sessions" (newest first). Bump `updated:`.

## 5. Check, build, fix

```
python3 ~/.cortex/engine/scripts/cortex.py check <every page you wrote or changed>
python3 ~/.cortex/engine/scripts/cortex.py build
```
If either reports errors, fix the pages and run again. Do not continue past an error. Do not tell the person it is saved until build passes.

## 6. Save and back up (only this session's files)

- Files to save = lines in `~/.cortex/sessions/<session_id>/written.txt` that are inside the vault, plus anything you edited in this step, plus `_cortex/` generated files.
- `git -C <vault> add -- <each file by name>` then `git -C <vault> commit -m "log: <date> <thing> - <short title>"`. Never `git add .` or `-A` (another chat may be working in the same vault).
- `python3 ~/.cortex/engine/scripts/cortex.py backup` to push. If the push fails (offline, sign-in), say: "Saved on your Mac; the online copy will catch up at the next backup."
- Mark done: `touch ~/.cortex/sessions/<session_id>/logged`.

## 7. Tell the person (short)

List what was written, one line each, grouped: "Session page, 1 decision (quarterly reports move to the portal), 1 new person (Sam Lee), 2 follow-ups." Then the teaching note.

## Teaching note

Pick the one that fits what was written, 1-2 sentences, for example:
- "I put the reporting change on its own decision page, not just in the session notes, so the card will show it the next time you open the pilot project."
- "Sam Lee now has a person page in the shared people folder, so his promise shows up wherever you meet him again."

If `teach: short` in kit.yaml, one short line: "Logged - 1 decision, 2 follow-ups."

## Skip

If the person says "skip" or "nothing worth keeping", touch the `logged` flag and say "OK, not logged." Never argue.
