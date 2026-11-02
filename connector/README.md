# Cortex in the Chat tab

Not yet released. This is a small extension for the Claude desktop app. It lets the Chat tab read your Cortex and save to it. Your Cortex stays in a folder on your computer, and the extension makes no internet calls of its own. What Claude reads from it in a chat becomes part of that chat, like anything else you type there.

## What you can do

Inside a Claude Project set up as below:

- **Your card shows up on its own.** Claude reads your start card before its first reply.
- **Ask about your work.** "What did we decide about the budget?" Claude searches your pages and opens the right one. Parts you mark private are not handed to Claude: see [What counts as private](#what-counts-as-private).
- **"Add to my list."** Adds one to-do or follow-up.
- **"Save this chat."** Saves the title, summary, decisions, follow-ups and open questions as a note in your inbox.
- **"What's in my inbox?"** Lists what is waiting.
- **"File that under Work."** Files a saved chat as a proper session page. Its follow-ups then count on your card and your board.
- **"Set up my cortex."** Only if you have none yet: creates the folders from your name and areas, and the settings file described under [Which folder it uses](#which-folder-it-uses).

## Install

1. Get the file `cortex-chat-0.1.0.mcpb`.
2. Double-click the file. The Claude desktop app opens and shows the install screen.
3. Click **Install**.
4. Leave the Cortex folder as it is, unless your Cortex lives somewhere else. If you already use the Cortex plugin, the extension finds your folder by itself.

An earlier test version installed with no warning. If you do see a note that the file is unsigned, that is expected for a file installed by hand. These steps are checked in the real app by [MORNING-TESTS.md](MORNING-TESTS.md).

## Which folder it uses

The rule, in order:

1. If `~/.cortex/config.json` exists and names a folder, that folder is used. This file wins over the extension's folder setting. If it names a folder that is not there, Cortex says so and does not try another one.
2. Otherwise, the folder chosen in the extension's settings.
3. Otherwise, `~/cortex`.

Your card has a line saying which folder is in use and why. Setup says it too.

**Setting up from chat creates that file**, when it does not exist, so the Cortex plugin can find your folder later. From then on the file decides, and changing the extension's folder setting has no effect. To use another folder, change or remove the file. An existing file is never overwritten.

## The permission prompts

In the earlier test version, Claude asked before every tool, the first time and each time after, including tools that only read. For each one you could allow it once or always. Step 10 of the morning tests checks this version.

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
| A chat outside the Project | Should work when you ask for Cortex by name. Nothing tells it to read your card by itself. Step 11 of the morning tests checks this. |
| Saving | Happens when you ask, or when Claude offers and you say yes. There is no save when a chat ends, so a chat you never saved is not in your Cortex. |
| Old chats | This extension cannot read them. |
| Your board | Saved items reach it after you file them. The board itself opens from the Code tab, not from chat. |
| Your full to-do list | The card shows what is due soon and how many are open. The full list is on the board. |
| Changing or deleting a page | Not possible from chat. Nothing here edits or deletes a page. |
| Imported notes | Listed in the inbox, but filed from the sorting desk in the Code tab. |
| Backup | Not done by this extension. If you set up from chat, your pages exist only on this computer until you add backup: open the Code tab, install the Cortex plugin and say "set up my cortex". It finds your folder and only offers backup. It needs a free GitHub account. |
| Updates | Do not arrive by themselves. Install the new file the same way. |
| Windows | Built to work, but not tested. |
| Mac | An earlier test version worked in the real app. This version passes its automated tests; the checks only the real app can do are in [MORNING-TESTS.md](MORNING-TESTS.md). |

## What counts as private

Two markings hide text from every chat tool: the card, search, opening a page and the inbox.

- **A private section:** a heading such as `## Private`, down to the next `#` heading of the same or a higher level. `## **Private**`, `## _Private_`, `## Private {private}`, `## Notes {private}` and `Private` underlined with `---` all count. When in doubt it hides more, not less.
- **A private line:** any line with `{private}` on it. In a page's header, the value shows as `(private)`.

Be clear about the limits:

- Nothing else is hidden. A page that only says "secret" in words is not private.
- It is hidden from chat, not locked. The text is still plain text in your folder and in your backup, and the plugin in the Code tab can read it.
- The files Cortex generates (`_cortex/` and `home.md`) can repeat private text, because the build does not hide it. So chat refuses to open or search them.

## How saving stays safe

- Everything from chat lands in `inbox/` first. It does not count as fact until you file it.
- Filing only ever makes new pages. A follow-up that names someone new also makes a short new page for that person.
- The saved note is moved to `sources/` after filing.
- If a save, filing or setup fails part way, for example on a full disk, it undoes what it did and says so. If it could not undo something, it names the file. The automated tests check this with a limit on file size standing in for a full disk. A sudden power cut is not covered: it cannot leave a half-written page, but it can leave a finished extra file.
- Two chats at once take turns. If one has to wait too long, it says nothing was saved and asks you to try again.
- A note bigger than 2 MB is not read. The card counts it as skipped and the inbox says so.
- The most it saves is 20 KB at a time and 20 writes an hour. The hourly count restarts when the app restarts.
- It cannot write anywhere you name and cannot run commands. It writes only inside your Cortex folder, apart from the one settings file above. It refuses to open anything outside your Cortex folder.
- Text from your pages is handed to Claude marked as your notes and not as instructions. That lowers the risk of a page tricking Claude. It does not remove it, so read the prompt before you allow a save.

## For whoever builds it

`python3 connector/build.py` writes the `.mcpb` and the skill zip to `connector/dist/`. Standard library only; nothing is downloaded. `python3 -m pytest connector/tests -q` runs the tests, which need `node`.
