# personal-cortex

**A working setup for coding agents.** 
A record that outlives the conversation, an instruction file that stays short, and guardrails that actually refuse. Organised by **the failure each piece prevents**, with three stages: the record, a minimal guard, the full hook set.

Written for [Claude Code](https://code.claude.com/docs) and built to travel. The record is plain markdown in git and works with any agent that can open a file. The instruction file is `AGENTS.md`, which Codex, Cursor and Gemini CLI read natively and Claude Code imports with one line. The hooks use the shape Claude Code, Codex and Cursor now share: a JSON description on stdin, exit code 2 to block, the reason on stderr. Event names and input fields differ per agent, so a hook ports with edits, not unchanged; the tests tell you when an edit broke it.

Nothing here is a copy of my configuration. The files are structure plus guidance on what goes in them, because the decisions are the transferable part and my project names are not.

Three stages:

| | `record/` | `minimal/` | `full/` |
|---|---|---|---|
| For | Anyone, with any agent | You have never written a hook | You run an agent daily, often more than one session at a time |
| Contents | An instruction template, a decision record, a session page and a checkpoint template | One instruction file, one guard, one settings file | The full hook set, session tracking, a write ledger |
| Time to working | Ten minutes | About ten minutes | About an hour |

Start with `record/`. Add `minimal/` when a rule you wrote down gets broken anyway. Move to `full/` when you hit one of the failures below and want it to stop happening. `examples/` holds the small pieces the articles walk through: a skill, a bounded hook with its registration, a review-eligibility check, and their tests.

---

## Stage 1: the record (any agent)

1. Copy `record/AGENTS.template.md` to your project's `AGENTS.md`, merging any existing instructions. If you use Claude Code, make `./CLAUDE.md` a single line: `@AGENTS.md`.
2. Copy `record/decisions.md` to `docs/decisions.md`. Replace the illustrative entry with a real decision, with the reason and the alternative you rejected.
3. Open a fresh session and ask what remains and why. Check its answer against the record. If it misses the reason, improve the record or its entry point.
4. When one file stops being enough, use `record/session.template.md` for a page per substantial session and `record/checkpoint.template.md` for the running note that survives a compaction.

---

## The failures these prevent

Each row is a real failure mode. Read the ones you recognise; skip the rest.

| Failure | What it looks like | What fixes it |
|---|---|---|
| Your instruction file keeps growing and stops being followed | You add a rule after every bad result. The file passes 200 lines. Rules that matter compete with rules that do not. | `CLAUDE.md` template and the belongs-here test in [WHAT-GOES-WHERE.md](WHAT-GOES-WHERE.md) |
| A rule you wrote is ignored anyway | The rule is in the file, in capitals, and the thing still happens. | A hook. Context is advice; only a hook is enforcement. `full/scripts/` |
| One session commits another session's work | You run two terminals. A directory-level `git add` sweeps up whatever the other one was mid-way through writing. | `stage-guard.py` |
| An agent writes somewhere it should not | A path under `~/.ssh`, `~/.aws`, or a destructive shell command. | `danger-guard.py` |
| You finish a long session and write nothing down | The sessions most worth recording are the ones where you are most tired. | The `Stop` gate in `full/scripts/session-tracking/on-stop.sh` |
| Compaction eats the reasoning | The conversation is summarised and the *why* behind today's decisions is gone. | `on-pre-compact.sh`, which writes to disk before the summary, not after |
| You cannot tell which files a session touched | You want to stage precisely and cannot reconstruct what changed. | `on-post-write.py`, a per-session write ledger |

---

## Stage 2: install the minimal guard (Claude Code)

```bash
git clone https://github.com/thehimanshushukla/personal-cortex
cd personal-cortex

# 1. instruction file - open it and fill the placeholders
cp minimal/CLAUDE.md ~/.claude/CLAUDE.md

# 2. the guard
mkdir -p ~/.claude/scripts
cp minimal/scripts/stage-guard.py ~/.claude/scripts/
chmod +x ~/.claude/scripts/stage-guard.py

# 3. wire the hook - merge this into ~/.claude/settings.json
cat minimal/settings.json
```

Then verify the guard actually blocks, which is the step people skip:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git add ."},"cwd":"'$HOME'/notes"}' \
  | GUARDED_REPO=~/notes python3 ~/.claude/scripts/stage-guard.py; echo "exit: $?"
# expect: a message on stderr and exit 2
```

A guard you have only ever seen allow things is a guard you have not tested.

---

## Design rules these follow

**Fail open or fail closed, deliberately.** Every guard here declares its choice in its docstring. These fail *open*: an internal error exits 0 and allows the call, because they protect you from your own automation moving fast, and a bug in a guard should not halt real work. If you adapt one to stand between an attacker and your credentials, **change it to fail closed** — a silent allow is the outcome such a guard exists to prevent. The question is: if this hook breaks, would you rather lose the work or lose the protection?

**Say what to do instead.** A blocked command with no explanation produces a retry loop. Every refusal here names the safe alternative.

**Exit 0 when it is not your business.** A hook on every Bash call must be cheap and quiet or you will disable it within a week.

**Give it a kill switch.** Each script honours an environment variable that turns it off for one shell. Knowing the escape hatch exists is what stops you deleting the hook the first time it is inconvenient.

**Expect a false positive.** When one arrives, prefer changing the workflow that collided over loosening the pattern. Loosening is how a guard quietly stops guarding.

---

## Tests

```bash
python3 -m pytest tests -q            # the guards
python3 -m unittest -v examples/test_examples.py   # the article examples
```

The guards are tested for both the block and the allow case, and for the bug that is easy to write: a `Stop` hook with no attempt counter is an infinite loop.

---

## What this is not

It is not a framework, and there is nothing to install beyond copying files. It is not a substitute for reading [the hooks reference](https://code.claude.com/docs/en/hooks) — the exit-code semantics in particular are worth ten minutes.

It also will not make Claude follow your rules through sheer volume. That is the mistake the instruction-file template is built to prevent.

---

## Contributing

If something here broke in your setup, please open an issue. What people trip over is genuinely useful to me and shapes what gets fixed.

---

Written by [Himanshu Shukla](https://thehimanshushukla.com). The reasoning behind each piece is in the [Claude Code setup series](https://thehimanshushukla.com/blog/claude-code-setup-series).

MIT licensed. Use it however you like.
