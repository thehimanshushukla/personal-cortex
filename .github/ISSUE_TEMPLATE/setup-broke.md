---
name: Something here broke in my setup
about: A guard fired when it should not have, or did not fire when it should
title: ''
labels: ''
---

**Which file**


**What you expected**


**What happened instead**
<!-- If a hook blocked something, paste the message it printed on stderr. -->


**Your setup**
- OS:
- Claude Code version (`claude --version`):
- Profile: minimal / full / adapted

<!--
False positives are the interesting ones. If a guard blocked legitimate work,
say what the command was - the usual fix is changing the workflow that
collided rather than loosening the pattern, and knowing which collisions
happen in practice is what makes that possible.
-->
