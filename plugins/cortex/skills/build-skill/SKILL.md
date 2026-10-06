---
name: build-skill
description: Build an improvement the person approved - a new skill, a standing rule, a page template, a scheduled job, or an automatic action - grounded in their real examples and started on a 30-day trial. Use after a "yes" to a Suggest proposal, or when the person says "make this a skill", "turn this into a skill", "automate this", "always do this from now on", "make a template for this", or "do this every Friday".
---

# Build what was approved

Build exactly one approved improvement, show it to the person, and start it on trial. Ground everything in the person's real examples.

Below, `cortex` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cortex.py"`. The vault path is in `~/.cortex/config.json`. All builds go **inside the vault**, so they travel with it and are backed up.

## 0. Inputs

- From suggest, you receive the proposal, its type, the dated evidence and the person's wording.
- From a direct request ("make this a skill"), use the current conversation and recent history as the examples.
  - Ask one question if the scope is unclear.
  - Check `_cortex/suggest-log.jsonl` and add a line with `"answer": "yes"` and `"source": "direct"`.

## 1. By type

### Skill

Write the skill to `<vault>/.claude/skills/<short-name>/SKILL.md`:

```
---
name: <short-name>
description: <what it does, in one line>. Use when the person says "<their phrase 1>", "<their phrase 2>", "<their phrase 3>".
status: trial
trial_until: <today + 30 days>
created: <today>
built_from: [<evidence dates>]
---

# <Title>

## When
<one or two lines>

## Steps
1. ...
2. ...

## Examples from your own work
- <date>: <what was asked> -> <what a good result looked like>
```

- **Trigger phrases:** take them from the person's own words in the evidence.
- **Steps:** describe what was actually done in the real episodes, not generic best practice.
- **Pages:** if the skill writes pages, use `cortex new` for paths and end with `cortex check` and `cortex build`.
- **Teaching note:** end the skill with a one-sentence teaching note, as every cortex skill does.

### Standing rule

Append to the vault `CLAUDE.md`, in the person's own part, **outside** the `<!-- cortex:begin ... -->` / `<!-- cortex:end -->` markers. Never edit inside the markers.

```
- <the rule in one line>. (Added <today>: you corrected this on <dates>.)
```

### Template

Write `<vault>/_templates/<name>.md` containing the frontmatter skeleton and the headings that were rebuilt by hand. Mention it in the vault CLAUDE.md person's part: "Use `_templates/<name>.md` for <what>."

### Scheduled job

For v0, write the plan first and show it. The plan covers:
- what runs
- when it runs (local time)
- what it reads
- where the result goes, usually a page or `_cortex/` file

Then offer one of two ways, and **install nothing until the person picks and confirms:**

1. **A scheduled task in the Claude desktop app:** give the exact prompt text and schedule for them to paste in.
2. **A Mac background job:** show the full plist you would write to `~/Library/LaunchAgents/com.cortex.<name>.plist`, running `claude -p "<prompt>"` in the vault. Only on yes, write it and run `launchctl bootstrap gui/$(id -u) <plist>`.

### Automatic action (hook)

1. Read `<vault>/.claude/settings.json` (create `{}` if missing).
2. **Merge** the new hook entry into the `hooks` section. **Never overwrite or remove existing entries.**
3. Show the exact before and after of the changed part, and ask "Add this?"
4. Write it only on yes.
5. Keep any hook script in `<vault>/.cortex/hooks/<name>.py`, using the standard library only and exiting 0 on any error.
6. Mark the trial in a comment field: `"_cortex_trial_until": "<date>"` beside the entry.

## 2. Show it

Show what was built in a few lines:
- the file path
- the phrases that start it (for a skill)
- what it will do
- "This is on a 30-day trial. If you do not use it by <date>, I will suggest retiring it."

Offer to try it once right now on a real example.

## 3. Save

1. Run `cortex build`. Fix any error it reports.
2. Commit the new or changed files by name: `git -C <vault> add <files>` then `git -C <vault> commit -m "build-skill: <name> (trial)"`.

## 4. Teaching note

End with one or two plain sentences. For example: "I built this from the four times you did it by hand, so it follows your way of doing it, not a generic one. It lives inside your cortex folder, so it is backed up and works in every session."

If `kit.yaml` has `teach: short`, use one sentence.

## Rules

- **Build only what was approved,** one item at a time.
- **Confirm before installing any scheduled job or hook.**
- **Never touch the plugin's own files.** Everything goes in the vault.
- **Never edit inside the cortex markers in CLAUDE.md.**
- **Use plain words and plain hyphens.**
