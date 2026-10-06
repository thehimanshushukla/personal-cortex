---
name: suggest
description: Look back at how the person has actually worked and propose up to five improvements - a new skill, an automatic action, a scheduled job, a standing rule, or a page template - each with dated evidence; the person answers Yes, Not now, or Never. Use when the person says "what should I automate", "suggest improvements", "what do I keep repeating", "what have you noticed about how I work", "make my cortex smarter", "any skills I should have", or "review my habits".
---

# Suggest

Find the patterns in how the person really works, and propose a small number of concrete improvements, each backed by dates. **Never install anything. Only propose.** Building happens in the build-skill skill, after a yes.

Below, `cortex` means `python3 ~/.cortex/engine/scripts/cortex.py`. The vault path is in `~/.cortex/config.json`.

## 1. Gather the evidence (read only)

1. Run `cortex history --days 30`. It prints the person's own typed requests with dates, and the summaries of their session pages.
2. Read session pages from the last 30 days, at least their summaries and "Open" sections.
3. Read `_cortex/suggest-log.jsonl` if it exists. It holds every earlier proposal and its answer.
4. Read the vault's `.claude/skills/*/SKILL.md` frontmatter for trial skills: `status: trial` and `trial_until`. Check whether the history shows each one being used, meaning its trigger phrases appear in requests after it was created.

**If there are fewer than about 5 sessions or 20 requests,** say so honestly. For example: "I only have 3 sessions to learn from so far. Ask me again after another week of use and I will have enough to spot real patterns." Then stop, and do not invent patterns.

## 2. Detect patterns (group by meaning, not exact words)

Treat "prep me for Alex", "brief me before the Alex call" and "what do I know about Alex before we talk" as the **same** request.

| What you see | Times needed | Propose |
|---|---|---|
| The person corrects the same thing (a wording, a fact, a format, "no, we say members not customers") | 2+ | **Standing rule** in their AGENTS.md |
| The same multi-step procedure asked for, or walked through by hand | 3+ | **Skill** |
| "every time", "always", "whenever", "after each" about an action ("always save to GitHub after", "every time I debrief, also...") | 1+ clear statement, or 2+ hints | **Automatic action** (a hook) |
| A task on a rhythm: weekly, monthly, "before every call", "every Friday" | 3+ occurrences | **Scheduled job** |
| The same page shape rebuilt by hand (the same headings again and again) | 3+ | **Template** |
| A trial skill past its `trial_until` with no use seen | - | **Retire** it |
| A need that a vetted add-on in `~/.cortex/engine/docs/CATALOG.md` already covers, matching its "propose when" signal | as the entry says | **Install from the catalog** (say who makes it and its license) |
| The same rule is written in AGENTS.md but was broken 2+ times anyway | 2+ | **Automatic action** (a hook): a rule written down but still broken needs enforcing |
| AGENTS.md has grown past about 150 lines, or holds history instead of instructions | - | **Tidy the instruction file** (hand to the guide's "check my CLAUDE.md") |

Rules for the evidence:
- **Only real items.** Every proposal must cite real, dated items from the history or session pages. If you cannot point to the dates, drop the proposal.
- **Skip what was already answered:**
  - Never re-propose anything answered **Never** in the suggest log, including the same idea worded differently.
  - Re-propose a **Not now** only if at least 14 days have passed since that answer **and** new evidence exists.
- **Skip what already exists.** Do not propose a skill the cortex already has. If a built-in skill would do it, say "you can already say '<phrase>'" instead.

## 3. Rank and show at most five

Rank by times seen multiplied by time saved each time (a rough guess). Show at most 5:

```
1. Skill - "Speaking invitation triage"
   Seen: 4 times - 2 Oct ("is this conference worth it"), 6 Oct ("should I speak at X"),
         9 Oct (walked through dates + audience + travel by hand), 14 Oct ("triage this invite")
   Would do: read the invite, check your calendar notes and past talks, give go/no-go with reasons
   Effort: small
   Yes / Not now / Never?

2. Standing rule - "Say member companies, never customers"
   Seen: 2 corrections - 5 Oct, 11 Oct
   Would do: add one line to your instructions (AGENTS.md) so every session follows it
   Effort: small
   Yes / Not now / Never?
```

Keep the evidence quotes short, up to about 8 words each. Use the person's own wording for the proposal name where possible.

## 4. Record every answer

For each proposal the person answers, append one JSON line to `_cortex/suggest-log.jsonl`:

```
{"date": "2026-10-20", "proposal": "Speaking invitation triage", "type": "skill", "evidence_dates": ["2026-10-02", "2026-10-06", "2026-10-09", "2026-10-14"], "answer": "yes"}
```

- `answer` is one of `yes`, `not_now`, `never`.
- Proposals the person does not answer are not recorded.
- Commit the log by name.

## 5. On Yes

Hand over to the build-skill skill, with the proposal, its type, its evidence and the person's own wording. Do not build anything here.

For a **catalog** item, there is nothing to build. Show the install steps exactly as `CATALOG.md` gives them. In the desktop app that is Code tab > Plugins > Add marketplace, then install. Say once more who makes it and its license. Only add the marketplace and install it if they say yes, then record the answer as usual.

## 6. Teaching note

End with one or two plain sentences. For example: "Every suggestion here came from things you actually did on those dates. Anything you approve starts on a 30-day trial and is retired if you stop using it, so your cortex only keeps what earns its place."

If `kit.yaml` has `teach: short`, use one sentence.

## Rules

- **Never install, write skills, change hooks or edit AGENTS.md here.** Only propose and record.
- **At most 5 proposals per run.** Fewer is fine. None is fine if nothing is real.
- **Never invent evidence or dates.**
- **Use plain words and plain hyphens.**
