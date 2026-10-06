---
name: guide
description: Explain how the person's own cortex works, using their own pages as examples - the start card, logging, page types, follow-ups, sorting desk, Suggest, backup and best practices. Use when the person asks "how does my cortex work", "explain my cortex", "what is a lesson page", "what is the difference between a decision and a session", "where does X go", "what happens when I log", "is my cortex backed up", "help", or seems unsure what to do next.
---

# How does my cortex work

Answer what they asked, using their own cortex as the example. Short, plain words, no jargon, no analogies.

## First, look at their cortex

- `~/.cortex/config.json` -> vault path. If missing: "Your cortex isn't set up yet - say 'set up my cortex' and I'll walk you through it." Stop.
- Read `kit.yaml` (their areas, collections, `teach`, `setup_date`), `home.md`, and `_cortex/card.md`.
- Pick real examples from their pages (a decision title, a person, a follow-up). If the cortex is still empty, say so and use the setup choices as examples.

## If they ask a specific question, answer only that

Give the answer in 2-5 sentences, with one real example from their vault and the exact place it lives. Then: "Want the full tour?"

## The full tour (only if asked, or if they say "explain everything")

Go one section at a time; after each, ask "Next?" so they can stop.

1. **The loop.** When you open a session, the start card is read first, so Claude already knows your current projects, recent decisions and open follow-ups. You work. When you are done you say "log this", and the session becomes pages. The next session's card is built from those pages. Show their current card.
2. **Where things live.** Areas (theirs: list), collections inside each area, one folder per thing. People and organisations are shared at the top because one person shows up across areas. Show their real tree in 5-10 lines.
3. **Page types.** Session, decision, lesson, insight, how-to, person, organisation, meeting - one line each, with one real example from their vault where one exists. The key rule: a decision goes on its own page with the why, never only inside a session page, because that is how it gets found again.
4. **Follow-ups.** The line format `- [ ] @person what (due YYYY-MM-DD) {mine|theirs}`. `{mine}` = you owe it, `{theirs}` = someone owes you. "What did I promise whom" lists them all. Show one of theirs if present.
5. **Bringing in old notes.** Import puts the original file in `sources/` and a copy in `inbox/`; the sorting desk proposes where each one belongs and you accept or change it. Nothing is filed until you confirm.
6. **Suggest.** After a week or two, "what should I automate" reads how you have worked and proposes up to five improvements (a new skill, an automatic action, a scheduled job, a standing rule, a template), each with the dates it saw the pattern. It never installs anything without your yes, and new skills start on trial.
7. **Backup.** Every log saves to your private GitHub copy; a weekly backup runs Sunday evening. Run `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/cortex.py doctor` and tell them the real last-backup date.
8. **Best practices.**
   - One home per thing; let the cortex create the folder the first time.
   - Log before closing - it takes a minute and it is what makes the next card useful.
   - Write the why on every decision; the what alone is useless in three months.
   - Keep people pages shared, not per area.
   - Ask "prep me for my call with X" before calls and "what did I promise whom" on Mondays.
9. **When something feels off.** Card looks stale -> log the last sessions, or say "rebuild my cortex" (run `cortex.py build`). Backup warning -> run `cortex.py doctor` and follow what it says. A page in the wrong place -> say where it should go; you move it and update its links.

## Offer to shorten teaching notes (after the first week)

If today is 7+ days after `setup_date` in kit.yaml and `teach` is still `full`, ask once at the end: "Every skill ends with a short note explaining what it did. Now that you know the basics, want me to shorten those to one line?" On yes, set `teach: short` in kit.yaml and commit it (`git add kit.yaml` by name).

## Teaching note

End with one sentence tying the answer to their next action, for example: "Next time you finish working on Northfield, say 'log this' and you'll see the card pick it up." If `teach: short`, skip it.
