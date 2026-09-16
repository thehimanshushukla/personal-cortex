---
name: changelog
description: Turn the commits since the last tag into release notes grouped by
  what changed for a user. Use when the user says "what changed", "write the
  release notes", "changelog for this release", "what is in this version", or
  asks what to tell people about a release.
---

# Changelog

1. `git describe --tags --abbrev=0` for the last tag, then
   `git log <tag>..HEAD --format='%h %s'`. If there are no tags, ask for
   a starting commit or state that you are summarizing all available history.
2. Group by what a user would notice, not by commit type. Nobody reads
   "chore:". Put behaviour changes first, fixes second, internals last or not
   at all.
3. Anything that changes existing behaviour gets called out separately, even
   if the commit message was casual about it.
4. Write it in the project's existing changelog voice. Read the last entry
   first and match it.
5. Show it. Do not write it to a file unless asked.
