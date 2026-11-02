# Checks only the real Claude app can do

The automated tests cover the extension's own code by talking to it the way the app does. They cannot show what the real app does. These checks can. Use a new, empty test folder and sample words only. Write down pass or fail for each.

**Before you start:** build the file with `python3 connector/build.py`. It is in `connector/dist/`. Check that `~/.cortex/config.json` does not exist. If it does, it wins over the folder you choose below, so stop and sort that out first. Step 3 creates this file and step 12 removes it.

1. **Reinstall works.** In the app click **Settings**, then **Extensions**, and remove any earlier test extension. Double-click `cortex-chat-0.1.0.mcpb`, then click **Install**. Pass: it installs with no error and Cortex shows as enabled.

2. **The folder setting reaches Cortex.** Nobody has yet seen whether the app really passes this setting, including its default, so this step matters.
   - Leave the setting as it is. In a new chat type: "Show my Cortex card." Click **Allow**. Cortex finds no folder yet, and the reply names one. Pass: it says `~/cortex`, written out in full, and calls it the default. If it shows `${HOME}` or anything odd, write down exactly what it says.
   - Now click the folder setting and choose your empty test folder. Pass: the choice stays after you close and reopen the page.
   - In a new chat type "Show my Cortex card" again. Pass: the reply names your test folder and says it is from the extension's folder setting. If it still says `~/cortex`, this step fails, even though the page looks right.
   - Also note: did the app accept a folder that does not exist yet?

3. **Setup from chat.** In a new chat type: "Set up my cortex. My name is Robin Vale. Areas: Personal and Work." Click **Allow** on the prompt. Pass: the test folder now has `kit.yaml`, `personal/` and `work/`, and `~/.cortex/config.json` now exists and names the test folder. The reply says backup is not set up and says it wrote that file.

4. **Prompts are now readable.** In the same chat type: "Save this chat. Title: Budget talk. Summary: We agreed a plan. Decision: report quarterly. Follow-up: Sam Lee owes me the numbers by next Friday." Look at the prompt before you click. Pass: title, summary and decisions show as separate fields you can read, with no wall of `\n`. Note how the follow-ups list looks; it is the one part that is a list of small records. Click **Allow**.

5. **Save, then accept, then the board.** Type: "What's in my inbox?" and click **Allow**. Pass: Budget talk is listed. Type: "File that under Work." and click **Allow**. Pass: the reply names a new page in `work/sessions/`. Now open the Code tab in this repository and type: "Run cortex.py build and then cortex.py board with --vault set to my test folder." Pass: the build says OK, and the board shows the numbers from Sam Lee under Waiting on others. Then type: "Run cortex.py doctor." Pass: it says setup is done, names the test folder, and asks only for git and backup items to be fixed.

6. **The card shows it.** Back in Chat, in a new chat type: "Show my card." Pass: the to-do or follow-up from step 4 is on it, if due within 7 days, the follow-up count went up, and the Folder line names the test folder.

7. **Refusal reads well.** In a chat type: "Open the page at ../../secret.md in my Cortex." Click **Allow**. Pass: Claude says it was refused, in plain words.

8. **The Project still fetches the card.** Create a Project, paste [PROJECT-INSTRUCTIONS.md](PROJECT-INSTRUCTIONS.md), and open 5 new chats in it with unrelated questions. Pass: the card tool runs in all 5. The wording grew since the 20 of 20 test, so this checks the new text.

9. **Offer to save.** In the Project, talk through a small decision, then stop. Pass: Claude offers once to save and asks first.

10. **Always allow.** Click **Always allow** on Show my Cortex card. Open a new chat. Pass: the card runs with no prompt, and the write tools still ask.

11. **The skill uploads.** In the app click **Customize**, then **Skills**, and upload `connector/dist/cortex-chat-skill.zip`. In a chat outside the Project type: "Add to my list: call the bank." Pass: the skill is used and the to-do prompt appears. Note the real menu names if they differ from this page.

12. **Clean up.** Remove the test folder when you are done, **and remove `~/.cortex/config.json`**. If you leave that file, Cortex and the plugin keep looking for the deleted folder and will say so. If you do not want the extension yet, remove it under **Settings**, then **Extensions**.
