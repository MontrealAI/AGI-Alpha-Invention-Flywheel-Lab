"""Key-free source-race tests; only disposable synthetic Python trees."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from connected_enterprise import upgrades
from connected_enterprise.historical_snapshot import stage_verified_python_closure


class HistoricalSourceStaging(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='historical-staging-test-')
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'historical'
        self.root.mkdir()
        (self.root / 'inspected.py').write_text("RESULT='PINNED'\n")
        self.inventory = upgrades.source_inventory(self.root)

    def test_private_staging_keeps_exact_original_content(self):
        staged = stage_verified_python_closure(self.root, self.base / 'staged',
                                                self.inventory, upgrades.source_inventory)
        self.assertEqual(upgrades.source_inventory(staged), self.inventory)
        self.assertEqual((staged / 'inspected.py').stat().st_mode & 0o777, 0o400)
        (self.root / 'inspected.py').write_text("RESULT='CHANGED'\n")
        self.assertEqual((staged / 'inspected.py').read_text(), "RESULT='PINNED'\n")

    def test_preflight_refuses_changed_source(self):
        (self.root / 'inspected.py').write_text("RESULT='CHANGED'\n")
        with self.assertRaisesRegex(ValueError, 'CHANGED_BEFORE_STAGE'):
            stage_verified_python_closure(self.root, self.base / 'staged',
                                          self.inventory, upgrades.source_inventory)

    def test_midstage_change_is_rejected_before_execution(self):
        calls = []
        def mutated_reader(root):
            current = upgrades.source_inventory(root)
            calls.append(root)
            if len(calls) == 1:
                (self.root / 'inspected.py').write_text("RESULT='CHANGED'\n")
            return current
        with self.assertRaisesRegex(ValueError, 'CHANGED_DURING_STAGE'):
            stage_verified_python_closure(self.root, self.base / 'staged',
                                          self.inventory, mutated_reader)

    def test_running_child_imports_staged_bytes_not_raced_original(self):
        original_run = upgrades.subprocess.run
        observed = []
        def raced_run(*args, **kwargs):
            (self.root / 'inspected.py').write_text("RESULT='CHANGED'\n")
            completed = original_run(*args, **kwargs)
            observed.append(completed)
            return completed
        with patch.object(upgrades.subprocess, 'run', side_effect=raced_run):
            with self.assertRaisesRegex(ValueError, 'CHANGED_DURING_EXECUTION'):
                upgrades._run_pinned_historical_python(
                    self.root, 'import inspected;print(inspected.RESULT)', {}, self.inventory)
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0].returncode, 0, observed[0].stderr)
        self.assertEqual(observed[0].stdout.strip(), 'PINNED')

    def test_staged_source_mutation_is_refused_in_child_before_import(self):
        import ast
        import re
        original_run = upgrades.subprocess.run
        observed = []
        def raced_run(*args, **kwargs):
            script = args[0][-1]
            match = re.search(r"snapshot=pathlib\\.Path\\(([^)]+)\\)", script)
            self.assertIsNotNone(match)
            staged = Path(ast.literal_eval(match.group(1))) / 'inspected.py'
            staged.chmod(0o600)
            staged.write_text("RESULT='UNREGISTERED'\\n")
            completed = original_run(*args, **kwargs)
            observed.append(completed)
            return completed
        with patch.object(upgrades.subprocess, 'run', side_effect=raced_run):
            with self.assertRaisesRegex(ValueError, 'CHANGED_DURING_EXECUTION'):
                upgrades._run_pinned_historical_python(
                    self.root, 'import inspected;print(inspected.RESULT)', {}, self.inventory)
        self.assertEqual(len(observed), 1)
        self.assertNotEqual(observed[0].returncode, 0)
        self.assertIn('STAGED_HISTORICAL_SOURCE_CHANGED_BEFORE_IMPORT', observed[0].stderr)
        self.assertNotIn('UNREGISTERED', observed[0].stdout)

    def test_clean_launcher_uses_isolation_without_parent_environment(self):
        with patch.dict(os.environ, {'AGI_ALPHA_SYNTHETIC_PARENT_MARKER': 'NOT_FOR_CHILD'}):
            done = upgrades._run_pinned_historical_python(
                self.root, "import inspected,os,sys;print(inspected.RESULT,sys.flags.isolated,os.environ.get('AGI_ALPHA_SYNTHETIC_PARENT_MARKER','ABSENT'))",
                {}, self.inventory)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), 'PINNED 1 ABSENT')

    def test_no_external_source_inventory_is_accepted_for_existing_files(self):
        other = {'inspected.py': '0' * 64}
        with self.assertRaisesRegex(ValueError, 'CHANGED_BEFORE_STAGE'):
            stage_verified_python_closure(self.root, self.base / 'staged', other,
                                          upgrades.source_inventory)

    def test_disallows_relative_escape(self):
        def invented_reader(_):
            return {'../inspected.py': self.inventory['inspected.py']}
        with self.assertRaisesRegex(ValueError, 'SOURCE_PATH_INVALID'):
            stage_verified_python_closure(self.root, self.base / 'staged',
                                          invented_reader(self.root), invented_reader)


if __name__ == '__main__':
    unittest.main()
