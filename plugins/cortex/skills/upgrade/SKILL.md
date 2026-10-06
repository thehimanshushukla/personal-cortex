---
name: upgrade
description: Update the cortex to a newer kit version without touching the person's own pages - update the plugin, refresh the kit-managed block in AGENTS.md, bump the version, rebuild and save. Use when the person says "update my cortex", "upgrade my cortex", "is there a new version", "get the latest cortex", or after being told a new version is out.
---

# Update my cortex

The kit (plugin) is replaced as a whole; the person's pages are never edited, moved or deleted by an update. Only the block between the markers in their AGENTS.md is rewritten.

## 1. Update the plugin

Explain and guide them, one step at a time:
- In the Claude desktop app (Code tab) or Claude Code: type `/plugin`, open the marketplace that holds Cortex, and choose update for `cortex`. In a terminal the same is `claude plugin update cortex`.
- After updating, start a new session (the update applies to new sessions). If they started this skill in the old session, ask them to open a new one and say "update my cortex" again; then continue from step 2.

## 2. Compare versions

- Installed kit version: read `~/.cortex/engine/.claude-plugin/plugin.json` -> `version`.
- Vault version: `kit_version` in the vault `kit.yaml` (vault path from `~/.cortex/config.json`).
- Same version: "You are already on the latest version (X)." Stop.
- Show: "Your cortex is on X; the kit is now Y." If `~/.cortex/engine/docs/CHANGELOG.md` exists, show the entries between X and Y in plain words.

## 3. Back up first

Run `python3 ~/.cortex/engine/scripts/cortex.py backup` so the current state is saved before anything changes. If it fails, stop and say why; do not upgrade without a saved copy.

## 4. Refresh the managed block in AGENTS.md

- Read the vault `AGENTS.md` and the template `~/.cortex/engine/templates/vault/AGENTS.md`.
- Replace ONLY the text between `<!-- cortex:begin -->` and `<!-- cortex:end -->` in the vault file with the same block from the template. Keep every line outside the markers exactly as it was.
- If the markers are missing or broken in the vault file, do not guess: show the person the problem and ask before adding a fresh block at the top.
- Show a short summary of what changed in the block (added or removed lines).

## 5. Migrations

If `~/.cortex/engine/migrations/` contains steps numbered above the old version, describe each in plain words, ask for a yes, then run them in order. Each migration must only add or rename fields or folders as it describes; if one wants to delete pages, stop and ask.

## 6. Bump the version, rebuild, save

1. Set `kit_version: Y` in `kit.yaml` and `"kit_version": "Y"` in `~/.cortex/config.json` (keep other keys).
2. `python3 ~/.cortex/engine/scripts/cortex.py build` - fix any errors before continuing.
3. `git -C <vault> add -- AGENTS.md kit.yaml _cortex/` plus any files a migration changed, by name.
4. `git -C <vault> commit -m "upgrade: kit X -> Y"` then `cortex.py backup`.
5. `cortex.py doctor` and show the result.

## Teaching note

"Only the kit's own section of your instructions changed; every page you wrote is exactly as it was, and your backup has the version from before the update." With `teach: short`: "Updated to Y - your pages untouched."
