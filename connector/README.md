# Cortex in the Chat tab

Not yet released. This is a small extension for the Claude desktop app. It lets the Chat tab read your Cortex and save to it. Your Cortex stays in a folder on your computer; the extension makes no internet calls of its own.

## What you can do

Inside a Claude Project set up as below:

- **Your card shows up on its own.** Claude reads your start card before its first reply.
- **Ask about your work.** "What did we decide about the budget?" Claude searches your pages and opens the right one. Parts marked private stay hidden.
- **"Add to my list."** Adds one to-do or follow-up.
- **"Save this chat."** Saves the title, summary, decisions, follow-ups and open questions as a note in your inbox.
- **"What's in my inbox?"** Lists what is waiting.
- **"File that under Work."** Files a saved chat as a proper session page. Its follow-ups then count on your card and your board.
- **"Set up my cortex."** Only if you have none yet: creates the folders from your name and areas.

## Install

1. Get the file `cortex-chat-0.1.0.mcpb`.
2. Double-click the file. The Claude desktop app opens and shows the install screen.
3. Click **Install**.
4. Leave the Cortex folder as it is, unless your Cortex lives somewhere else. If you already use the Cortex plugin, the extension finds your folder by itself.

An earlier test version installed with no warning. If you do see a note that the file is unsigned, that is expected for a file installed by hand.

## The permission prompts

Claude asks before every tool, the first time and each time after, including tools that only read. For each one you can allow it once or always.

- **Safe to always allow:** Show my Cortex card, Search my Cortex, Open a Cortex page, What is in my inbox. They only read.
- **Keep asking for the rest:** Add a to-do, Save this chat, File a saved chat, Set up a new Cortex. That prompt is your chance to see what is being written.

## Create the Project

Without this, chats do not fetch your card by themselves.

1. In the Chat tab, click **Projects**, then create a new Project called Cortex.
2. Open the Project's instructions.
3. Paste the text from [PROJECT-INSTRUCTIONS.md](PROJECT-INSTRUCTIONS.md).
4. Start your chats inside this Project.

Optional: upload `cortex-chat-skill.zip` as a skill, so phrases like "save this chat" work the same way everywhere.

## What works and what does not

| | |
|---|---|
| Claude desktop app, Chat tab | Works |
| Claude on the web or on your phone | Does not work. The extension runs on your computer. |
| A chat inside the Project | Reads your card first: 20 of 20 test chats. Tested on one account and one model, so read this as "usually", not "always". |
| A chat outside the Project | Works when you ask for Cortex by name. It does not read your card by itself. |
| Saving | Happens when you ask, or when Claude offers and you say yes. There is no save when a chat ends, so a chat you never saved is not in your Cortex. |
| Old chats | Cannot be read. |
| Your board | Saved items reach it after you file them. The board itself opens from the Code tab, not from chat. |
| Your full to-do list | The card shows what is due soon and how many are open. The full list is on the board. |
| Changing or deleting a page | Not possible from chat. Nothing here edits or deletes a page. |
| Imported notes | Listed in the inbox, but filed from the sorting desk in the Code tab. |
| Backup | Not done by this extension. If you set up from chat, your pages exist only on this computer until you set up backup from the Code tab. |
| Updates | Do not arrive by themselves. Install the new file the same way. |
| Windows | Built to work, but not tested. |
| Mac | An earlier test version worked in the real app. This version passes its automated tests; the checks only the real app can do are in [MORNING-TESTS.md](MORNING-TESTS.md). |

## How saving stays safe

- Everything from chat lands in `inbox/` first. It does not count as fact until you file it.
- Filing only ever makes new pages. A follow-up that names someone new also makes a short new page for that person.
- The saved note is kept under `sources/` after filing.
- The most it saves is 20 KB at a time and 20 writes an hour. The hourly count restarts when the app restarts.
- It cannot write anywhere you name, cannot run commands, and refuses to open anything outside your Cortex folder.
- Text from your pages is handed to Claude marked as your notes and not as instructions. That lowers the risk of a page tricking Claude. It does not remove it, so read the prompt before you allow a save.

## For whoever builds it

`python3 connector/build.py` writes the `.mcpb` and the skill zip to `connector/dist/`. Standard library only; nothing is downloaded. `python3 -m pytest connector/tests -q` runs the tests, which need `node`.
