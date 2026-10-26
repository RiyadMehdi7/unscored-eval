import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.suite = self.directory / 'suite.json'
        self.results = self.directory / 'results.jsonl'
        self.suite.write_text(json.dumps({
            'version': 1, 'name': 'Test', 'systems': ['A', 'B'],
            'cases': [{'id': 'one'}, {'id': 'two'}],
        }), encoding='utf-8')
        self.results.write_text('\n'.join(json.dumps(row) for row in [
            {'system': 'A', 'case_id': 'one', 'status': 'scored', 'score': 1},
            {'system': 'B', 'case_id': 'one', 'status': 'scored', 'score': 0.75},
            {'system': 'B', 'case_id': 'two', 'status': 'scored', 'score': 0.75},
        ]), encoding='utf-8')

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, '-m', 'unscored', *map(str, args)],
            cwd=self.directory,
            env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')},
            text=True, capture_output=True, timeout=20,
        )

    def test_demo_produces_portable_report_and_measurement_queue(self):
        out = self.directory / 'demo'
        result = self.run_cli('demo', '--out', out)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((out / 'report.json').read_text())
        self.assertEqual(report['summary']['verdict'], 'inconclusive')
        self.assertIn('INCONCLUSIVE', result.stdout)
        self.assertIn('<!doctype html>', (out / 'report.html').read_text().lower())
        self.assertIn('case_id', (out / 'rerun.csv').read_text())

    def test_default_audit_is_successful_even_when_inconclusive(self):
        before = set(self.directory.iterdir())
        result = self.run_cli('audit', self.suite, self.results)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('INCONCLUSIVE', result.stdout)
        self.assertEqual(set(self.directory.iterdir()), before)

    def test_gate_fails_when_claim_is_not_established_but_saves_report(self):
        out = self.directory / 'audit'
        result = self.run_cli('audit', self.suite, self.results,
                              '--require-winner', 'A', '--out', out)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertTrue((out / 'report.json').is_file())
        self.assertIn('not established', result.stdout.lower())

    def test_gate_succeeds_for_strict_winner(self):
        with self.results.open('a') as target:
            target.write('\n' + json.dumps({
                'system': 'A', 'case_id': 'two', 'status': 'scored', 'score': 1,
            }))
        result = self.run_cli('audit', self.suite, self.results, '--require-winner', 'A')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('A', result.stdout)

    def test_unknown_gate_is_input_error_and_writes_nothing(self):
        out = self.directory / 'audit'
        result = self.run_cli('audit', self.suite, self.results,
                              '--require-winner', 'typo', '--out', out)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(out.exists())
        self.assertNotIn('Traceback', result.stderr)

    def test_existing_directory_is_never_overwritten(self):
        out = self.directory / 'audit'
        out.mkdir()
        target = out / 'report.json'
        target.write_text('keep me')
        result = self.run_cli('audit', self.suite, self.results, '--out', out)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(target.read_text(), 'keep me')
        self.assertEqual([p.name for p in out.iterdir()], ['report.json'])

    def test_output_path_cannot_replace_input(self):
        original = self.suite.read_bytes()
        result = self.run_cli('audit', self.suite, self.results, '--out', self.suite)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.suite.read_bytes(), original)

    def test_spreadsheet_formula_ids_are_escaped_only_in_csv(self):
        self.suite.write_text(json.dumps({
            'version': 1, 'name': 'CSV safety', 'systems': ['=A', 'B'],
            'cases': [{'id': '=SUM(1,2)'}],
        }))
        self.results.write_text('')
        out = self.directory / 'audit'
        result = self.run_cli('audit', self.suite, self.results, '--out', out)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads((out / 'report.json').read_text())
        self.assertEqual(report['rerun_plan'][0]['case_id'], '=SUM(1,2)')
        self.assertIn("'=SUM(1,2)", (out / 'rerun.csv').read_text())

    def test_broken_symlink_output_is_not_followed_or_replaced(self):
        out = self.directory / 'audit'
        out.symlink_to(self.directory / 'does-not-exist', target_is_directory=True)
        result = self.run_cli('audit', self.suite, self.results, '--out', out)
        self.assertEqual(result.returncode, 2)
        self.assertTrue(out.is_symlink())

    def test_malformed_records_do_not_publish_partial_output(self):
        self.results.write_text('{invalid}')
        out = self.directory / 'audit'
        result = self.run_cli('audit', self.suite, self.results, '--out', out)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(out.exists())
        self.assertNotIn('Traceback', result.stderr)

    def test_missing_input_is_a_friendly_error(self):
        result = self.run_cli('audit', 'missing.json', self.results)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn('Traceback', result.stderr)

    def test_version_and_help(self):
        version = self.run_cli('--version')
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertIn('0.1.0', version.stdout)
        help_result = self.run_cli('--help')
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn('audit', help_result.stdout)

    def test_complete_score_is_displayed_as_a_point(self):
        result = self.run_cli('audit', self.suite, self.results)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('possible 75.00% (exact 3/4)', result.stdout)


if __name__ == '__main__':
    unittest.main()
