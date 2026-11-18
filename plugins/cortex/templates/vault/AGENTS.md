<!-- cortex:begin v0.5.1 - managed by the cortex plugin; upgrades rewrite only this block -->
# How to work in this cortex

This folder is a cortex: the person's working record, kept as markdown pages and backed up to their private GitHub. Every session starts from the card the start hook shows you. Use it - do not re-ask what it already says.

## Rules
- One home per thing. Before creating a page, look in `_cortex/index.md` for an existing one; add to it instead of duplicating.
- Create every page with `python3 ~/.cortex/engine/scripts/cortex.py new <type> ...` so its path, id and fields are right. Never invent ids.
- Page types: session, decision (what and why), lesson (a trap and how to avoid it), insight, how-to, person, organisation, meeting, note. Rules for each are in the plugin's docs/SPEC.md.
- Follow-ups (promises between the person and someone else) are lines: `- [ ] @person-slug what (due YYYY-MM-DD) (added YYYY-MM-DD) {mine|theirs}`. The person's own to-dos use `@me`: `- [ ] @me what (due YYYY-MM-DD) (added YYYY-MM-DD) {mine}`. New lines get `(added <today>)`; a closed line gets `- [x]` and `(done <today>)`; `{doing}` after the owner means in progress. "show my board" opens them as cards.
- A decision that only lives inside a session page is not captured - give it its own decision page.
- After writing pages: `cortex.py check <files>`, then `cortex.py build`. Fix every problem before moving on.
- Dates are local time (`date +%F`). Plain words, short sentences, plain hyphens.
- Anything outward-facing (emails, posts, messages) is a draft. The person sends it.
- Never delete the person's pages. Mark them `status: archived` or `superseded` instead.
- Stage commits by file name. Never `git add .` - the weekly backup handles everything else.
- Cortex runs on the person's own Mac. If `~/.cortex/config.json` is missing and no Cortex skill is running ("set up my cortex" and "update my cortex" create or change that file), Cortex is not set up where this session runs. Check with `uname`: anything other than Darwin is a cloud session (Claude on the web, or a cloud environment), which cannot reach the Mac. Say so in one plain sentence and tell them where to go: on their Mac, the Claude desktop app's Code tab with a local session, or Claude Code in the terminal, in any folder. On their own Mac, install the Cortex plugin first if it is not installed, then say "set up my cortex"; if this folder is already their cortex, tell setup its path so it uses it instead of starting a new one. Either way, do not build a substitute board, card or home page as an artifact or file, and do not log or change pages - none of it would reach the cortex.
- After any change to the cortex, end with one or two plain sentences on what you did and why it helps (one line if kit.yaml says `teach: short`).
<!-- cortex:end -->

# My own notes and rules

(Anything below this line is yours. Upgrades never touch it. Standing rules that Suggest proposes and you approve are added here with the date and reason.)
