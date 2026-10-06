---
name: followups
description: Show open promises and follow-ups by person and date, and close the ones that are done. Use when the person says "what did I promise whom", "what do I owe people", "what is waiting on others", "who owes me what", "open follow-ups", "what is overdue", "my follow-ups with <name>", or "mark the <thing> follow-up done".
---

# Follow-ups

Show what the person owes to others and what others owe them, gathered from every page in the cortex.

Below, `cortex` means `python3 ~/.cortex/engine/scripts/cortex.py`. The vault path is in `~/.cortex/config.json`.

## 1. Make sure the list is current

1. Run `cortex build`. It rebuilds `_cortex/followups.md` from every task line in the vault, and is quick.
2. If the build fails, say so in one line and use the last `_cortex/followups.md`, noting it may be out of date.

## 2. Read and group

Read `_cortex/followups.md`. Every follow-up came from a line shaped like this:

```
- [ ] @<person-slug> <what> (due YYYY-MM-DD) {mine|theirs}
```

The build records the source file for each one. Group the list:

1. **Overdue first**: a due date before today. Show how many days late.
2. **Then by mine and theirs:**
   - "You owe" means `{mine}`.
   - "Waiting on others" means `{theirs}`.
3. **Within each, by person**, with the earliest due date first. Items with no date go last.

If the person asked about one person ("my follow-ups with Alex"), show only that person, both directions.

Keep it to one screen:

```
Overdue (2)
- You owe Alex Rivera: send the roadmap notes - due 10 Oct (3 days late)
- Waiting on Sam Lee: intro to Acme marketing - due 9 Oct (4 days late)

You owe (4)
- ...

Waiting on others (3)
- ...
```

Number every line, so the person can refer to it by number.

## 3. Offer to close

Ask: "Any of these done? Say the numbers, for example 'close 2 and 5'."

**Only after the person confirms:**
1. Open the source file, find that exact task line, and change `- [ ]` to `- [x]`.
2. Change nothing else on the line or in the page.
3. Set `updated:` to today in that page's frontmatter.
4. Run `cortex check <changed files>`, then `cortex build`.
5. Commit only the changed files, by name: `git -C <vault> add <files>` then `git -C <vault> commit -m "followups: closed N"`.

If the person wants to add a follow-up ("remind me Alex owes me the deck by Friday"):
1. Ask which page it belongs on, suggesting the person's page or the latest meeting with them.
2. Write one line in the exact shape above.
3. Check, build and commit the same way.

## 4. Teaching note

End with one or two plain sentences. For example: "These come from the follow-up lines in your meeting and person pages, so anything a debrief records shows up here automatically. Closing one marks it done in the page it came from."

If `kit.yaml` has `teach: short`, use one sentence.

## Rules

- **Never edit a follow-up without confirmation.** Never delete one either: close it with `[x]`.
- **Use the person's real name in the output,** not the slug. Take it from the `people/` page title.
- **Use plain words and plain hyphens.**
