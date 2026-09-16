import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parent


def run(script, payload):
    return subprocess.run(
        [sys.executable, str(ROOT / script)], input=payload,
        text=True, capture_output=True, check=False,
    )


class Examples(unittest.TestCase):
    def test_hook_blocks_documented_forms(self):
        for command in ('git add .', 'git add -A', 'git add --all', 'git  add "."'):
            with self.subTest(command=command):
                result = run('block-sweeping-add.py', json.dumps({'tool_input': {'command': command}}))
                self.assertEqual(result.returncode, 2)
                self.assertIn('stage named files', result.stderr)

    def test_hook_allows_named_file_and_documented_out_of_scope_forms(self):
        for command in ('git add docs/decisions.md', 'git -C repo add .', 'git add . && git status'):
            with self.subTest(command=command):
                result = run('block-sweeping-add.py', json.dumps({'tool_input': {'command': command}}))
                self.assertEqual(result.returncode, 0)

    def test_hook_malformed_input_is_advisory(self):
        result = run('block-sweeping-add.py', '{invalid')
        self.assertEqual(result.returncode, 0)
        self.assertIn('could not parse', result.stderr)

    def test_review_refuses_incomplete_or_conflicting_provenance(self):
        cases = [None, [], {}, {'producer_session': 'a'},
                 {'producer_session': 'a', 'reviewer_session': '', 'artifact_version': 'v1'},
                 {'producer_session': 1, 'reviewer_session': 'b', 'artifact_version': 'v1'},
                 {'producer_session': ' a ', 'reviewer_session': 'a', 'artifact_version': 'v1'}]
        for record in cases:
            with self.subTest(record=record):
                result = run('review_eligibility.py', json.dumps(record))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stdout)['verdict'], 'REFUSED')

    def test_review_malformed_json_refuses(self):
        result = run('review_eligibility.py', '{invalid')
        self.assertEqual(result.returncode, 2)

    def test_distinct_ids_only_establish_eligibility(self):
        result = run('review_eligibility.py', json.dumps({
            'producer_session': 'a', 'reviewer_session': 'b', 'artifact_version': 'v1',
        }))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['verdict'], 'ELIGIBLE')
        self.assertIn('review still required', json.loads(result.stdout)['reason'])

    def test_registration_points_to_project_script(self):
        config = json.loads((ROOT / 'settings.example.json').read_text())
        hook = config['hooks']['PreToolUse'][0]
        self.assertEqual(hook['matcher'], 'Bash')
        self.assertEqual(hook['hooks'][0]['command'],
                         'python3 "$CLAUDE_PROJECT_DIR/.claude/scripts/block-sweeping-add.py"')


if __name__ == '__main__':
    unittest.main()
