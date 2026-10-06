---
name: guide
description: Explain how the person's own cortex works, using their own pages as examples - the start card, logging, page types, follow-ups, sorting desk, Suggest, backup and best practices. Use when the person asks "how does my cortex work", "explain my cortex", "what is a lesson page", "what is the difference between a decision and a session", "where does X go", "what happens when I log", "is my cortex backed up", "help", "open my cortex", "show me my files", "where are my files", "back up my cortex", "is everything ok", "health check", "what hooks do I have", "what can you do", "what skills can I add", "recommend skills", "what agents can I use", "check my CLAUDE.md", "set up my CLAUDE.md well", "where can I read more", or seems unsure what to do next.
---

# How does my cortex work

Answer what they asked, using their own cortex as the example. Short, plain words, no jargon, no analogies.

## Source of truth

For anything about what runs on its own (hooks), what they can ask for (skills), where files live, backup, feedback or what's next, read `~/.cortex/engine/docs/WHAT-YOU-HAVE.md` and answer from it. Never describe a hook or skill from memory.

## Quick actions

- **"open my cortex" / "show me my files":** run `open <vault>`, so Finder opens the folder. Mention that `home.md` is the map.
- **"back up my cortex":** run `python3 ~/.cortex/engine/scripts/cortex.py backup` and say the result in plain words.
- **"is everything ok" / "health check":** run `python3 ~/.cortex/engine/scripts/cortex.py doctor` and explain each line marked FIX.

## "What skills can I add?" / "recommend skills or agents"

Show `~/.cortex/engine/docs/CATALOG.md` grouped as it is: who makes each entry, its license, what it does, how to install. Mark anything their history already suggests ("you have made Word documents several times, so this one fits"). Install nothing without their yes.

## "Set up my CLAUDE.md well" / "check my CLAUDE.md"

AGENTS.md is the instruction file every session reads in full (CLAUDE.md and GEMINI.md just point to it). Read the vault's `AGENTS.md` and `~/.cortex/engine/docs/WHAT-GOES-WHERE.md`. Then report in plain words, with line numbers, one short list per finding:
- **Length:** past about 150 lines, every rule competes with every other. Say which lines could move out.
- **History instead of instructions:** dated stories, meeting notes or decisions belong in the record (a decision page), not here. Offer to move each one.
- **Rules that keep being broken:** a rule written down but broken twice needs an automatic action (a hook), not stronger wording. Offer to hand it to Suggest.
- **Procedures:** multi-step "how to do X" text belongs in a skill that loads only when needed.
- **Never touch the managed block** between the `cortex:begin` and `cortex:end` markers. Change only their own part, and only after they say yes to each change.

End with the deeper read: "A CLAUDE.md That Survives 100 Sessions" (link below).

## Learn more (the maker's articles)

When a question goes deeper than a quick answer, end with the matching article. One link at most, only where it helps understanding, never as promotion:

| Topic | Article |
|---|---|
| CLAUDE.md, what goes where | [A CLAUDE.md That Survives 100 Sessions](https://thehimanshushukla.com/blog/claude-md-that-survives-100-sessions?utm_source=cortex) |
| The record, logging, the card | [Claude Code Memory That Lives in a Wiki, Not a Prompt](https://thehimanshushukla.com/blog/claude-code-memory-wiki-not-prompt?utm_source=cortex) |
| What runs on its own (hooks) | [Claude Code Hooks as Guardrails](https://thehimanshushukla.com/blog/claude-code-hooks-as-guardrails?utm_source=cortex) |
| Skills, Suggest | [Claude Code Skills: Designing So You Never Have to Remember They Exist](https://thehimanshushukla.com/blog/claude-code-skills-natural-phrasing?utm_source=cortex) |
| Agents | [Claude Code Sub-Agents: Why I Stopped Handing Whole Deliverables to Specialists](https://thehimanshushukla.com/blog/claude-code-subagents-when-to-delegate?utm_source=cortex) |
| Connectors (MCP) | [Claude Code MCP Servers: The Cost Moved](https://thehimanshushukla.com/blog/claude-code-mcp-servers-worth-having?utm_source=cortex) |
| The whole system | [MANSHU: Six Layers, One System](https://thehimanshushukla.com/blog/claude-code-manshu-system?utm_source=cortex) |
| All of it, in order | [The Claude Code setup series](https://thehimanshushukla.com/blog/claude-code-setup-series?utm_source=cortex) |

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
7. **Backup.** Every log saves to your private GitHub copy; a weekly backup runs Sunday evening. Run `python3 ~/.cortex/engine/scripts/cortex.py doctor` and tell them the real last-backup date.
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
