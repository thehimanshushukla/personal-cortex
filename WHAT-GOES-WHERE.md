# What goes where

Four places knowledge can live in a Claude Code setup. Putting a thing in the wrong one is the most common reason a setup stops working as it grows.

| Place | Holds | Loads | Put a thing here when |
|---|---|---|---|
| `~/.claude/CLAUDE.md` | Standing instructions about **you** | Every session, in full | It applies regardless of which project you are in |
| `./CLAUDE.md` in a repo | Standing instructions about **that project** | Every session in that repo, in full | It is non-obvious and cannot be cheaply rediscovered |
| A skill | A **procedure** | Only when invoked | It is multi-step and needed only sometimes |
| A hook | An **enforced rule** | At a fixed lifecycle moment | You have already broken the rule twice with it written down |

---

## The belongs-here test for CLAUDE.md

Before adding a line, ask in this order. The first "no" is your answer.

**1. Does this apply every session?**
If it applies occasionally, it is a skill. A procedure you run once at the end of a session should not sit at the top of every session's context.

**2. Can Claude find this out by looking, in under ten seconds?**
Directory layouts, what a script does, what a folder contains. If yes, leave it out. Not because writing it is wrong, but because you will not maintain it, and a stale instruction is worse than none.

This is where I part company with the official guidance, which suggests documenting architecture, commands and conventions. Where something is genuinely non-obvious — a build step with an undocumented flag, a convention nothing in the code hints at — write it down. The rule is not "never describe the project". It is "do not write what Claude can find, because you will not maintain it."

**3. Would you say this out loud to a new contractor on day one?**
If it is too detailed for that, it is reference material. Link to it instead of inlining it.

**4. Is it a preference, or must it always hold?**
Preferences belong in the file. Things that must *always* hold, where "usually" is not good enough, belong in a hook. The file is delivered to Claude as a message, not as configuration, and the docs are explicit that there is no guarantee of strict compliance. A rule that matters more than the others does not get followed more by being written in capitals.

---

## Which rules deserve a hook

A rule needs **all three**. Most candidates fail the third.

**It applies at a fixed, detectable moment.** Before a Bash call. After a write. When the session ends. If you cannot name the event, you want better judgment, not a guardrail.

**The cost of missing it is hard to undo.** A commit that swept up someone else's work. A write into a credentials directory. If the cost is "slightly untidy", a hook is overkill.

**It holds regardless of circumstances.** This is the disqualifier. If the right answer is ever "it depends what we are doing", the hook will be wrong exactly when the exception matters, and you will disable it in irritation instead of thinking.

The honest signal that something should become a hook is not "this is important". It is **"I have already failed at this more than once with the rule in front of me."**

### What not to hook

Anything needing judgment about scope. "Never send anything externally" sounds hookable until you try to draw the line mechanically between a draft file, a comment on your own repo, and a message to a client. Every place the line is drawn wrongly trains you to work around the guard — and working around guards is a habit you then carry to the guards that were right.

---

## Filling in the templates

Placeholders look like `<this>`. Each one has a line above it saying what belongs there and, where it matters, what does *not*.

Two habits worth keeping after the first pass:

- **Date nothing, explain everything.** A rule with its reasoning survives; a rule with a date attached just looks audited. Write *why* the rule exists, so that in three months you can decide whether it still needs to.
- **Delete on sight.** When a rule has not been relevant for a month, remove it. The file works by being short. Every line you keep out of habit costs you on every session, forever.
