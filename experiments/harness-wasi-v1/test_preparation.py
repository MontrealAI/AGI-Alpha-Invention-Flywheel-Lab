"""Preparation-only checks: no downloads, build, Wasmtime import or guest execution."""
import ast
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import random
import tarfile
import tempfile
import unittest
from unittest.mock import Mock, patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
spec = importlib.util.spec_from_file_location('wasi_preparation_runner', HERE / 'run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class Preparation(unittest.TestCase):
    def test_registered_cases_are_exact_pinned_foundry_protocol(self):
        protocol = json.loads((HERE / 'PROTOCOL.json').read_text())
        for path, digest in protocol['baseline_source_sha256'].items():
            self.assertEqual(runner.sha(REPO / path), digest)
        source = REPO / 'products/alpha-genesis-harness/bridge/upgrade_foundry.py'
        tree = ast.parse(source.read_text())
        function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == '_protocol')
        namespace = {'random': random, 'copy': copy}
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), 'exec'), namespace)
        cases = json.loads((HERE / 'CASES.json').read_text())
        self.assertEqual(cases, namespace['_protocol']('harness-wasi-baseline-v1-20261110'))
        self.assertEqual(len(cases['cases']), 64)
        self.assertEqual(runner.sha(HERE / 'CASES.json'), protocol['cases_sha256'])
        affine = [row for row in cases['cases'] if 'reference' in row]
        self.assertEqual(len(affine), 48)
        for row in affine:
            x = row['reference']
            self.assertEqual(row['expected'], {'result': x['x'] * x['gain'] + x['offset']})

    def test_host_parser_and_oracle_reject_ambiguous_guest_claims(self):
        for text in ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}']:
            with self.assertRaises(ValueError):
                runner.strict_json(text)
        self.assertFalse(runner.same_json({'x':[True]}, {'x':[1]}))
        self.assertTrue(runner.same_json({'x':[1]}, {'x':[1.0]}))
        successful = {'worker_returncode':0, 'outcome':'EXIT', 'exit_code':0, 'stdout':'{"result":2}'}
        self.assertEqual(runner.guest_payload(successful), {'result':2})
        for change in [{'outcome':'ERROR'}, {'worker_returncode':1}, {'exit_code':1}, {'output_overflow':True}]:
            with self.assertRaises(ValueError):
                runner.guest_payload({**successful, **change})

    def test_archive_escape_refused_before_extract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); archive = root / 'bad.tar'
            with tarfile.open(archive, 'w') as tar:
                item = tarfile.TarInfo('../outside'); item.size = 1
                tar.addfile(item, io.BytesIO(b'x'))
            with self.assertRaises(ValueError):
                runner.extract(archive, root / 'extract')
            self.assertFalse((root / 'outside').exists())

    def test_only_explicit_readonly_preopen_and_no_inherit_calls(self):
        tree = ast.parse((HERE / 'worker.py').read_text())
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)]
        preopens = [node for node in calls if node.func.attr == 'preopen_dir']
        self.assertEqual(len(preopens), 1)
        self.assertTrue(any(kw.arg == 'fs_mutable' and isinstance(kw.value, ast.Constant) and kw.value.value is False for kw in preopens[0].keywords))
        self.assertFalse(any(node.func.attr.startswith('inherit_') for node in calls))
        self.assertEqual(json.loads((HERE / 'PROTOCOL.json').read_text())['model_calls'], 0)

    def test_sources_compile_without_running_guest(self):
        for path in HERE.glob('*.py'):
            compile(path.read_text(), str(path), 'exec')

    def test_worker_reaped_on_unexpected_wait_failure(self):
        child = Mock(pid=54321)
        child.poll.return_value = None
        child.communicate.side_effect = RuntimeError('synthetic unexpected host wait failure')
        with patch.object(runner.os, 'killpg') as kill:
            with self.assertRaisesRegex(RuntimeError, 'synthetic'):
                runner.wait_owned_process(child, 1, capture=True)
            kill.assert_called_once_with(54321, runner.signal.SIGKILL)
            child.wait.assert_called_once_with()

    def test_attempt002_preserves_previous_protocol_and_actual_failure(self):
        history = HERE / 'evidence/attempt001'
        previous = json.loads((history / 'PROTOCOL.json').read_text())
        current = json.loads((HERE / 'PROTOCOL.json').read_text())
        self.assertEqual(runner.sha(history / 'PROTOCOL.json'),
                         'dbb270d343a2ff0fb0615721d577bf3b282e0ff3e1feac9943b1b63cf4e51108')
        self.assertEqual(current['schema'], 'harness-wasi-baseline-preregistration/v2')
        self.assertEqual(current['attempt_id'], 'wasi-baseline-002')
        for key, value in previous.items():
            if key != 'schema':
                self.assertEqual(current[key], value, key)
        summary = json.loads((history / 'SUMMARY.json').read_text())
        self.assertEqual(summary['status'], 'FAIL')
        self.assertEqual(summary['stage'], 'trusted_build')
        self.assertEqual(summary['source_revision'], current['previous_attempt']['source_revision'])
        self.assertEqual(summary['protocol_sha256'], current['previous_attempt']['protocol_sha256'])
        self.assertEqual(summary['artifact']['sha256'], current['previous_attempt']['artifact_sha256'])
        self.assertEqual(summary['artifact']['raw_member_count'], 8)
        self.assertEqual(summary['baseline_cases_executed'], 0)
        self.assertEqual(summary['model_calls'], 0)
        self.assertFalse(summary['candidate_execution'])
        workflow = (REPO / '.github/workflows/harness-wasi-v1.yml').read_text()
        self.assertIn('PROTOCOL_SHA256: ' + runner.sha(HERE / 'PROTOCOL.json'), workflow)

    def test_direct_make_matches_upstream_build_without_launcher(self):
        command = Mock()
        environment = {'PATH': '/public/bin', 'PYTHONDONTWRITEBYTECODE': '1'}
        source = Path('/synthetic-public-source/Python-3.15.2')
        with patch.object(runner.os, 'process_cpu_count', return_value=2, create=True):
            runner.build_wasi_all(source, command, environment)
        command.assert_called_once_with(
            ['make', '--jobs', '2', 'all'],
            source / 'cross-build/wasm32-wasip1', environment)
        self.assertIs(command.call_args.args[2], environment)
        text = (HERE / 'run.py').read_text()
        self.assertNotIn("'make-host'", text)
        self.assertIn("'--host-runner', 'false'", text)


if __name__ == '__main__':
    unittest.main()
