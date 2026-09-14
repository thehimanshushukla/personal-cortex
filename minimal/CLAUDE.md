<!--
  ~/.claude/CLAUDE.md - your global instruction file.
  Loads in full, at the start of every session, in every project on this machine.

  Read WHAT-GOES-WHERE.md before filling this in. The short version:
  every line here costs you on every session forever, so the file works by
  being short. Aim for under 50 lines. Mine is 38.

  Delete any section you do not need. An empty section is worse than no section.
-->

# Global instructions

## How I work

<3-5 lines, maximum. How you want Claude to behave in every project, regardless
 of what the project is. Tone, verbosity, whether to ask before acting.

 Good: "Explain what changed and why, not how you did it."
 Bad:  "Be helpful and accurate."  <- says nothing, costs tokens forever.>

## Never

<Only rules that must ALWAYS hold, with no legitimate exception.
 Anything that needs judgment about scope belongs in a skill, not here.

 Be honest about this list. If a rule here has been broken twice while written
 down, it does not belong in this file at all - it belongs in a hook.
 See "Which rules deserve a hook" in WHAT-GOES-WHERE.md.>

## Where things are

<A map, not the things themselves. Point outward.

 The test: can Claude find this by looking, in under ten seconds? If yes,
 leave it out - you will not keep it up to date, and a stale instruction is
 worse than no instruction.

 Genuinely non-obvious things belong here: a build step with an undocumented
 flag, a convention nothing in the code hints at, where your notes live.>

## Looking things up

<If you keep notes or docs outside the tool, tell Claude how to search them
 cheaply. Without this, its instinct is to read the largest file that might
 contain the answer.

 A shape that works:
   1. Check what is already loaded.
   2. Search the source files.
   3. Open the one page the search found.
   Never read generated or index files - they are large and derived.>

## Context discipline

<Optional, and worth it if your sessions run long.

 Two rules that came out of measuring where the spend went:
   - Before changing topic, write decisions to disk, then compact with an
     instruction naming what to keep.
   - Do not re-read a large file already read this session. Read the specific
     section instead.>
