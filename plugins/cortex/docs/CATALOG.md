# Skills and plugins catalog

A short, vetted list of add-ons that work well beside your cortex. **Suggest proposes an item from this list only when your own history shows you need it.** For example: "you made Word documents by hand four times this month; the document skills would format them properly". To see the full list, say "what skills can I add".

Every entry comes from a known publisher, with its source and license. Nothing is installed without your yes. Anything not on this list deserves a careful look before you install it, because add-ons can run code on your Mac.

To install from the Claude desktop app: Code tab > Plugins > Add marketplace (the repo name), then install the plugin. Or in Claude Code, run the two commands shown.

## Document skills (Word, Excel, PowerPoint, PDF)

- **Who:** Anthropic. Source: [github.com/anthropics/skills](https://github.com/anthropics/skills). License: source-available, not open source.
- **What:** creates and edits real .docx, .xlsx, .pptx and .pdf files, with proper formatting, tables and charts.
- **Propose when:** the history shows reports, memos, spreadsheets or decks being made or fixed by hand, three times or more.
- **Install:**
  ```
  /plugin marketplace add anthropics/skills
  /plugin install document-skills@anthropic-agent-skills
  ```

## Skill creator

- **Who:** Anthropic, in the same repo. Part of `example-skills`. License: Apache 2.0.
- **What:** helps write a new skill properly: clear triggers, steps, and tests from real examples.
- **Propose when:** the person approves two or more skills from Suggest, or says "I want to make my own skill". Build-skill can then use it.
- **Install:** `/plugin install example-skills@anthropic-agent-skills` (after adding the marketplace above).

## Productivity (tasks, daily planning, email and calendar sweep)

- **Who:** Anthropic. Source: [github.com/anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins). License: Apache 2.0.
- **What:** a task list, daily planning, and a sweep of email, calendar and chat for missed to-dos. Uses the Microsoft 365, Google or Slack connectors your organisation allows.
- **Propose when:** the history shows daily planning or "what's on my plate" requests three times or more, and the cortex task board has not shipped yet. It works alongside your cortex; your cortex stays the record.
- **Install:**
  ```
  /plugin marketplace add anthropics/knowledge-work-plugins
  /plugin install productivity@knowledge-work-plugins
  ```

## Role plugins from the same Anthropic collection

These live in the same marketplace and install the same way. Propose one only when the history clearly matches the role:
- **sales:** call prep, follow-ups, account research
- **legal:** contract and NDA review
- **marketing:** content and campaigns
- **product-management:** specs and roadmaps

## Agents

- **Reviewer (built in, coming next):** a second opinion on an important document before it goes out. It never grades its own work.
- **Any other agent:** Suggest proposes it with build-skill, from your own repeated work, so it carries your examples.

## Adding to this catalog

New entries need:
- a known publisher
- a public source
- a clear license
- a real "propose when" signal

Say "send feedback" to recommend one.
