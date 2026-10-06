---
name: import
description: Bring existing notes and files into the cortex - keeps the originals, converts them to pages in the inbox, and proposes where each one belongs on the sorting desk. Use when the person says "bring in this folder", "import my OneNote", "import my notes", "add this deck", "bring in these PDFs", "load my old notes", "here is my export", or drops files or a folder to add to the cortex.
---

# Import notes and files

Bring files in without losing anything. Each file is filed only after the person confirms where it goes, on the sorting desk.

Below, `cortex` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cortex.py"`. The vault path is in `~/.cortex/config.json`.

## 1. Know what is coming

Ask for the file or folder path if none was given. List what you found: how many files of each type, and the total size. Confirm before copying more than about 50 files or 200 MB.

### OneNote (be honest about Mac limits)

OneNote for Mac has no full-notebook export to plain files. Offer the reliable routes, in this order:

1. **One section at a time as PDF (most reliable):**
   - In OneNote, go to File > Print, then save as PDF.
   - Or use Share > Export or Send a copy as PDF, where the version offers it.
   - Put the PDFs in one folder and give me the folder.
2. **Obsidian Importer,** if they use or will install Obsidian. It can import a OneNote notebook into markdown files. A work account may need IT approval to sign in.
3. **Copy and paste** a page or section into the chat, or into a `.md` file. This works for a few important pages.

Recommend route 1 for anything important. Never claim a one-click OneNote import exists.

## 2. Keep the originals

Copy every file **unchanged** to `sources/<yyyy-mm>/` in the vault, using this month's year and month.
- Keep the original file name.
- If a file with the same name already exists, add `-2`, `-3` and so on.
- Never modify or delete the person's original files where they came from.

Large audio or video recordings (over about 50 MB) stay out of git. Copy them into `sources/` only if the person agrees, and add their paths to `.gitignore`. Otherwise, record where they live on disk in the note.

## 3. Convert each file into an inbox note

For each source file, write one markdown file into `inbox/`, named `<yyyy-mm-dd>-<short-slug>.md`. Use these conversions:

| File | How |
|---|---|
| `.md`, `.txt` | Use the text as is |
| `.html`, `.htm` | `textutil -convert txt -stdout "<file>"` |
| `.docx`, `.doc`, `.rtf` | `textutil -convert txt -stdout "<file>"` |
| `.pdf` | Read it with the Read tool and write the text, keeping headings and lists |
| `.pptx` | Extract slide text with the standard library (below); for complex slides, describe each slide's text in order |
| `.vtt`, `.srt` | Drop timestamps, keep speakers; better: hand it to the debrief skill instead |
| images | Read with the Read tool and write a short description plus any visible text |

pptx text extraction (standard library only):

```
python3 - "<file.pptx>" <<'PY'
import sys, zipfile, re
z = zipfile.ZipFile(sys.argv[1])
slides = sorted([n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)],
                key=lambda n: int(re.findall(r"\d+", n)[-1]))
for i, n in enumerate(slides, 1):
    text = re.findall(r"<a:t>([^<]*)</a:t>", z.read(n).decode("utf-8", "ignore"))
    print(f"## Slide {i}\n" + "\n".join(t for t in text if t.strip()) + "\n")
PY
```

Each inbox note gets this frontmatter:

```
---
id: note-inbox-<slug>
title: <a clear title from the content>
type: note
status: draft
created: <today>
updated: <today>
sources: [sources/<yyyy-mm>/<file>]
summary: <one sentence on what this is>
---
```

Below the frontmatter goes the converted text. Never summarise the text away, because the full content must survive.

## 4. Propose where each one belongs

1. Read `_cortex/index.md` for the existing areas, things, people and organisations, and `kit.yaml` for the person's areas and collection words.
2. For every inbox note, propose:
   - **Area:** one of their areas.
   - **Thing:** an existing thing slug, or `NEW: <name>` when it clearly needs one. Say plainly that it is new.
   - **Page type:**
     - usually `note`;
     - `meeting` if it is meeting notes;
     - or a split, for example "split: 1 decision + 2 follow-ups". This happens only when the content clearly holds those.
   - **Tags:** 1-4 short words.
   - **Links:** ids of existing pages it should link to, such as people mentioned or the thing it is about.
   - **Confidence:** high, medium or low.
   - **Reason:** one line saying why.
3. Write the proposals to `_cortex/sorting-desk.md`. Append rows if the desk already has some, and continue the numbering:

```
# Sorting desk

Proposals waiting for your decision. Nothing here is filed until you confirm.

| # | Inbox file | Title | Area | Thing | Type | Tags | Links | Confidence | Why |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | inbox/2026-10-12-northfield-plan.md | Northfield pilot plan | acme | NEW: northfield-pilot | note | pilot-site, launch | person-sam-lee | medium | Mentions the Northfield center and the 14 Oct announcement |
```

## 5. Save and hand off

1. Commit the new `sources/` files, the `inbox/` notes and the desk, by name. Never use `git add .`.
2. Tell the person: "<N> items are waiting on your sorting desk. Say 'open the sorting desk' to review where each one goes."

## 6. Teaching note

End with one or two plain sentences. For example: "I kept your original files untouched in sources, so every page can always point back to where it came from. Nothing is filed until you confirm on the sorting desk."

If `kit.yaml` has `teach: short`, use one sentence.

## Rules

- **Originals are never changed or deleted.**
- **Nothing is filed into an area without the person's confirmation.** Filing is the sort skill's job.
- **Use plain words and plain hyphens.**
