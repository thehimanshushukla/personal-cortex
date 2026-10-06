---
name: debrief
description: Turn a meeting into a meeting page, decision pages, follow-ups, updated people and organisation pages, and a follow-up email draft. Use when the person says "go through this meeting", "debrief this call", "process this transcript", "here are my meeting notes", "what came out of this meeting", "extract the action items", or pastes or drops a transcript, recording notes, a .vtt/.txt/.docx/.pdf file, or a Notion or Teams meeting export.
---

# Debrief a meeting

Turn one meeting into pages in the cortex, so its decisions and promises can be found later and show up on the start card.

Scripts live at `~/.cortex/engine/scripts/cortex.py`. Below, `cortex` means `python3 ~/.cortex/engine/scripts/cortex.py`. The vault path is in `~/.cortex/config.json`.

## 1. Get the text

- **Pasted text:** use it as given.
- **File path:**
  - `.txt`, `.md`, `.vtt`, `.srt`: read with the Read tool. For `.vtt`/`.srt`, ignore timestamps and keep speaker names.
  - `.docx`, `.rtf`: `textutil -convert txt -stdout "<file>"`.
  - `.pdf`: read with the Read tool.
  - Notion or Teams export: read the file, and use the meeting title and date it carries.
- **Keep the original if it is a file.** Copy it unchanged to `sources/<yyyy-mm>/` in the vault and record that path in `sources:`.

If the date, the area it belongs to, or who attended is unclear, ask **one** short question that covers all three. Offer your best guess for each, so the person can just say "yes".

## 2. Read the vault first

- Read `_cortex/index.md` to find existing people, organisations, areas and things.
- Match names in the transcript to existing `people/` pages. A first name alone counts as a match only if exactly one person fits. Otherwise list the candidates and ask.

## 3. Draft, then show before writing

Show the person a short preview:

```
Meeting: <title> - <date> - <area>
Decisions (N): one line each, with the why
Follow-ups (N): who owes what to whom, by when, mine or theirs
People: existing pages to update (names) / NEW people pages to create (names)
Organisations: existing / NEW
```

- **Never create new people pages in bulk without asking.** List the new names and ask "Create pages for these N people?" Accept "yes", "only 1 and 3", or "none".
- **Say when a decision is unclear.** If the meeting only discussed something and nothing was decided, call it that and do not write a decision page for it.

## 4. Write the pages

For each page, get the correct path, id and frontmatter skeleton from the script, then fill it in:

```
cortex new meeting --area <area> --title "<meeting title>" --date <YYYY-MM-DD>
cortex new decision --area <area> [--thing <thing>] --title "<what was decided>"
cortex new person --title "<Full Name>"
cortex new organisation --title "<Org name>"
```

- **Meeting page:**
  - **Frontmatter:** `date:` and `people: [slug, ...]`.
  - **Sections:** Summary (2-3 sentences); Decisions (one line each, linking to the decision pages); Discussion (the main points, short); Follow-ups.
- **Decision pages:**
  - **Sections:** Decision; Why; What was considered and rejected (if said); When to reopen (only if said - never invent one).
  - **Links:** link back to the meeting id.
- **Follow-ups:** one task line each in the meeting page's Follow-ups section, in exactly this shape:
  ```
  - [ ] @<person-slug> <what> (due YYYY-MM-DD) {mine}
  - [ ] @<person-slug> <what> {theirs}
  ```
  - `{mine}` means the person owes it. `{theirs}` means someone owes it to them.
  - Leave out `(due ...)` when no date was said. Never guess a date.
- **People and organisation pages:**
  - Add a dated line under History, for example `- 2026-10-12: met at <meeting title> - <one line>`.
  - Add the meeting id to their `links:`.
  - Set `updated:` to today.
- Set `updated:` to today on every page you touch, and use local dates.

## 5. Check and build

```
cortex check <every file you wrote or changed>
cortex build
```

- **Fix every error the check or build reports**, then run them again until they pass.
- **Never leave the vault failing.** If an error cannot be fixed, tell the person plainly what is wrong.

## 6. Follow-up email draft

Write a short follow-up email **in the chat only**:
- thanks
- the decisions in one line each
- the follow-ups with owners and dates
- a closing line

Write it in the person's plain voice. **Never send it, and never open a mail tool to send it.** Say "Here is a draft you can copy."

## 7. Save

Commit only the files this debrief wrote, by name. Never use `git add .`.

```
git -C <vault> add <file1> <file2> ...
git -C <vault> commit -m "debrief: <meeting title> <date>"
```

## 8. Teaching note

End with one or two plain sentences on what was done and why it helps. For example: "I wrote the two decisions as their own pages, so next time you work on this they show up on your start card with the reason attached. The follow-ups now appear when you ask 'what did I promise whom'."

If `kit.yaml` has `teach: short`, use one sentence.

## Rules

- **Plain words only:** no jargon, no analogies, plain hyphens.
- **Never send email or messages.** Drafts only.
- **Never delete or rewrite the person's existing text on people or organisation pages.** Only add.
- **If the transcript is long, cover all of it,** not just the first part. Work through it in sections if needed.
