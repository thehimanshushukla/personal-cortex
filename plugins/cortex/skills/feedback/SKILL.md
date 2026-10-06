---
name: feedback
description: Send feedback, a feature request or a problem report to the maker of the cortex plugin, or show what is coming next. Use when the person says "send feedback", "I wish it could...", "can you add...", "feature request", "something is broken", "this is not working", "report a problem", "how do I contact you", "who made this", "what's coming next", "what's new", "what's in the next update".
---

# Feedback, requests and what's next

Below, `cortex` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/cortex.py"`. The vault path is in `~/.cortex/config.json`.

The maker's contact is **info@thehimanshushukla.com**. Nothing is sent automatically, ever: you prepare the email and the person presses Send.

## "What's coming next" / "what's new"

Read `${CLAUDE_PLUGIN_ROOT}/docs/ROADMAP.md` and `${CLAUDE_PLUGIN_ROOT}/docs/CHANGELOG.md`.
- Say which version they have (`kit_version` in `kit.yaml`).
- Say what the latest version added.
- Say what is planned next, in plain words.

Then offer: "Want to tell the maker what you would like first?" If yes, continue below.

## Feedback or a feature request

1. Ask one question, only if it is unclear: "What would you like it to do, and what would that save you?"
2. Write it up in 3-6 lines. Cover what they want, why, and an example from their own work. Leave out private details like names of people, clients or numbers unless they say to include them, and ask before including anything that looks confidential.
3. Append it to `<vault>/_cortex/feedback.md` as a dated entry: `## YYYY-MM-DD - <one-line title>` followed by the write-up and `Status: drafted`. Create the file if it is missing.
4. Show them the email text and ask: "Send this from your Mail app? I'll open it ready to go - you press Send."
5. On yes, open a prefilled draft. URL-encode the subject and body with Python's standard library, not by hand:
   ```
   python3 -c "import urllib.parse,subprocess,sys; s,b=sys.argv[1],sys.argv[2]; subprocess.run(['open','mailto:info@thehimanshushukla.com?subject='+urllib.parse.quote(s)+'&body='+urllib.parse.quote(b)])" "<subject>" "<body>"
   ```
   - Subject: `Cortex feedback: <title>`
   - Body: the write-up, plus a final line `Cortex version: <kit_version>`.
6. If no Mail app is set up, show the address and the text so they can copy it into any email.
7. Change the entry's status to `Status: email opened <date>`.

## Something is broken

1. Run `cortex doctor` and read the result.
2. If the cause is clear and safe to fix, explain it, and fix it with their OK. Typical causes are a missing GitHub sign-in, a moved folder, or a page with a problem.
3. If it cannot be fixed here, prepare the email as above with the subject `Cortex problem: <one line>`. The body holds:
   - what they were doing
   - what happened, with the exact error text
   - the doctor output
   - the version

   Remove folder paths that contain their name. Anything else that looks private is left out unless they say otherwise.

## "How do I contact you" / "who made this"

Answer: "The cortex plugin was made by Himanshu Shukla. You can reach him at info@thehimanshushukla.com, or say 'send feedback' and I will draft the email for you."

## Teaching note

End with one plain sentence:
- After feedback: "I saved a copy in your cortex too, so you can see what you have asked for."
- After a problem report: "The health check is in the email, so the fix can start without back-and-forth."

If `teach: short`, one short line.
