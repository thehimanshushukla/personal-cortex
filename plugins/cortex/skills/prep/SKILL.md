---
name: prep
description: One-screen brief before a call or meeting with a person or organisation - who they are, history, recent meetings, decisions involving them, open follow-ups both ways, and three talking points. Use when the person says "prep me for my call with X", "brief me on X", "what do I know about X", "I am meeting X tomorrow", "get me ready for the X meeting", or "remind me where we are with X".
---

# Meeting prep

Give the person one screen they can read in two minutes before a call.

Below, `cortex` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cortex.py"`. The vault path is in `~/.cortex/config.json`.

## 1. Find who it is

1. Read `_cortex/index.md` and match the name to a `person` or `organisation` page.
2. If more than one matches, list them and ask which one.
3. If none matches, say so plainly. Offer to prep from whatever the vault mentions (search the vault for the name with Grep), and offer to create their page.

For an organisation, also gather the people pages linked to it. For a person, also gather their organisation page.

## 2. Gather (read only, change nothing)

From the vault:
- **Their page:** who they are, role, how they connect to the person, history lines.
- **Recent meetings:** meeting pages whose `people:` includes them, or that link to their id. Take the last 3, newest first.
- **Decisions:** decision pages that link to them or to those meetings. Take the last 3.
- **Open follow-ups both ways:** run `cortex build`, then read `_cortex/followups.md` and filter to this person or organisation.
- **Related things:** projects or other tracked things their page links to, with each one's current state from its `_index.md`.

## 3. The brief (one screen)

```
Prep: <Name> - <role, organisation>
Who: one or two lines on who they are and why they matter to you.
Last contact: <date> - <meeting title> - one line on what happened.
Where things stand: 2-3 lines from the related things and recent decisions.
You owe them: (follow-ups {mine}, with dates; overdue marked)
They owe you: (follow-ups {theirs})
Talking points:
1. ...
2. ...
3. ...
```

- **Base the talking points on the record only:** an overdue promise to raise, a decision to confirm, an open question from the last meeting.
- **Never invent facts about the person.** If the vault has little on them, say "Your cortex has only one meeting with them so far" instead of padding.
- **Use plain dates** such as "12 Oct" for readability.

## 4. Offer next steps (do not do them unasked)

- "Want me to debrief the call afterwards? Paste the notes or transcript."
- If their page is thin: "Want me to add what you know about them now?"

## 5. Teaching note

End with one plain sentence. For example: "This brief is built from your meeting and person pages, so every debrief you do makes the next prep richer."

## Rules

- **Read only.** Prep never changes the vault unless the person asks.
- **Use plain words and plain hyphens.** Keep it to one screen.
