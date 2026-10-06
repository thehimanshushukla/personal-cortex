---
name: sort
description: Review the sorting desk and file imported notes into the right area, project and page type, with links, only after the person confirms. Use when the person says "open the sorting desk", "file my imports", "sort my inbox", "where should these notes go", "accept all", "accept all except 3", "move 4 to <place>", or "make 5 a decision".
---

# Sorting desk

Show the import proposals, let the person accept or change them, then file them correctly. **Nothing is filed until they confirm.**

Below, `cortex` means `python3 ~/.cortex/engine/scripts/cortex.py`. The vault path is in `~/.cortex/config.json`.

## 1. Show the desk

Read `_cortex/sorting-desk.md` and check each row's inbox file still exists. If the desk is empty, say so, and offer the import skill.

Show the rows grouped by proposed area. Inside each area, put **low confidence first**, then medium, then high, so the person looks hardest at the uncertain ones. Keep each row to one line:

```
Acme (5)
 3  [low]    "Q2 notes from pilot call" -> pilot-project, note   (why: mentions the pilot twice, unclear if a meeting)
 1  [medium] "Northfield pilot plan" -> NEW thing: northfield-pilot, note
 ...
Personal (2)
 ...
```

Say what "NEW" means: a new thing folder would be created, with its own `_index.md`.

## 2. Take the person's decision

Understand any of these, in their own words:

| They say | Means |
|---|---|
| "accept all" | File every row as proposed |
| "accept all except 3, 7" | File all but 3 and 7; leave those on the desk |
| "move 4 to acme/projects/pilot-project" | Change row 4's area and thing |
| "make 5 a decision" | Change row 5's type (the page then needs the decision sections) |
| "4 is personal" | Change row 4's area |
| "drop 6" | Remove row 6 from the desk; keep its inbox note and source untouched |
| "skip for now" | Change nothing |

Before filing, repeat back what will happen in one short list and ask "Go ahead?" **Only file after a yes.**

## 3. File each accepted row

For each accepted row:

1. **Make the thing first if it is new:** `cortex new thing --area <area> --collection <collection> --title "<thing name>"` (the collection is the folder inside the area, for example projects; ask if unclear). Fill its `_index.md` with a one-line purpose and current state.
2. **Get the right path and id:** `cortex new <type> --area <area> [--thing <thing>] --title "<title>"`. Use its path, id and frontmatter.
3. **Write the page at that path.** Keep the full converted text from the inbox note. Keep `sources:` exactly as it was. Set:
   - `status: active`
   - `updated:` to today
   - `tags:` and `links:` as decided
4. **If the type is not `note`,** shape the content into that type's sections, using only what the text says:
   - decision: Decision / Why / Considered
   - meeting: Summary / Decisions / Follow-ups
   - lesson: What happened / Cause / How to avoid
5. **Add links both ways.** On each linked page, add this page's id to its `links:` and set its `updated:`. Never rewrite other text on those pages.
6. **Remove the inbox note** only once its content is safely in the new page. The original in `sources/` always stays.
7. **Remove the row** from `_cortex/sorting-desk.md`.

## 4. Check, build, save

```
cortex check <every file written or changed>
cortex build
```

- **Fix every error and run both again** until they pass. Never leave the vault failing.
- **Commit by name, never `git add .`.** Include the deleted inbox files, with `git -C <vault> add inbox/<file>` for each one by name (this records the deletion too). Then run `cortex backup` to push.

Report back in two or three lines: how many pages were filed, how many new things were created, and how many rows remain on the desk.

## 5. Teaching note

End with one or two plain sentences. For example: "Each note now sits with the project it belongs to and is linked to the people in it, so it shows up when you ask to get up to speed on that project or prep for a call with them."

If `kit.yaml` has `teach: short`, use one sentence.

## Rules

- **Nothing is filed without confirmation.**
- **Never delete a source file.** Never delete an inbox note before its content is in its new page.
- **Never rewrite the person's text on existing pages.** Only add links and dates.
- **Use plain words and plain hyphens.**
