import json
import shlex
import sys

try:
    payload = json.load(sys.stdin)
    command = payload.get("tool_input", {}).get("command", "")
    words = shlex.split(command)
except (ValueError, AttributeError, TypeError):
    print("Hook could not parse input; this advisory guard allows it.", file=sys.stderr)
    sys.exit(0)

blocked = (["git", "add", "."], ["git", "add", "-A"], ["git", "add", "--all"])
if words in blocked:
    print("Blocked: broad staging. Inspect the changes and stage named files.", file=sys.stderr)
    sys.exit(2)
sys.exit(0)
