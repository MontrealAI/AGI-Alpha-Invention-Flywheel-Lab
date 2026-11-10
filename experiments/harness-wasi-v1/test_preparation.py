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
import threading
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
        successful = {'worker_returncode':0, 'outcome':'EXIT', 'exit_code':0, 'stdout':'{"result":2}', 'cleanup':{'complete':True}}
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

    def test_attempt003_preserves_previous_limits_and_failures(self):
        history = HERE / 'evidence/attempt002'
        previous = json.loads((history / 'PROTOCOL.json').read_text())
        current = json.loads((HERE / 'PROTOCOL.json').read_text())
        self.assertEqual(runner.sha(history / 'PROTOCOL.json'),
                         '0fb753c1e94c93b712b6f9f4008cd1ee61f74e647ea85008ad5d556a3d1872de')
        self.assertEqual(current['schema'], 'harness-wasi-baseline-preregistration/v3')
        self.assertEqual(current['attempt_id'], 'wasi-baseline-003')
        for key in ('baseline_revision', 'baseline_source_sha256', 'cases_sha256', 'downloads',
                    'wasmtime_python_wasi_source_sha256', 'readonly_api', 'readonly_native_mapping',
                    'guest_limits', 'required_capability_checks', 'resource_checks', 'limit_scope',
                    'attempts', 'platform', 'model_calls', 'current_codex_controls', 'claims_excluded'):
            self.assertEqual(current[key], previous[key], key)
        self.assertEqual(current['guest_limits']['fuel'], 2000000000)
        self.assertEqual(current['output_lifecycle']['required_probes'],
                         ['lifecycle_return', 'lifecycle_trap'])
        summary = json.loads((history / 'SUMMARY.json').read_text())
        self.assertEqual(summary['status'], 'FAIL')
        self.assertEqual(summary['observations']['worker_returncode'], -6)
        self.assertEqual(summary['observations']['remaining_fuel'], 0)
        self.assertEqual(summary['observations']['baseline_cases_executed'], 0)
        self.assertEqual(summary['source_revision'], current['previous_attempt']['source_revision'])
        self.assertEqual(runner.sha(HERE / 'evidence/attempt001/PROTOCOL.json'),
                         'dbb270d343a2ff0fb0615721d577bf3b282e0ff3e1feac9943b1b63cf4e51108')
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

    def test_cache_manifest_must_match_exact_staging_delta(self):
        name = 'python/lib/python3.15/public.py'
        cache_name = 'python/lib/python3.15/__pycache__/public.cpython-315.pyc'
        before = {name: {'sha256': 'source'}}
        after = {**before, cache_name: {'sha256': 'cache'}}
        manifest = {'compiled': [{'source': 'public.py', 'source_sha256': 'source',
                                 'pyc': '__pycache__/public.cpython-315.pyc', 'pyc_sha256': 'cache'}]}
        self.assertTrue(runner.verify_cache_manifest(before, after, manifest))
        self.assertFalse(runner.verify_cache_manifest(before, {**after, 'extra.pyc': {'sha256': 'x'}}, manifest))
        self.assertFalse(runner.verify_cache_manifest(before, {**after, cache_name: {'sha256': 'wrong'}}, manifest))
        self.assertFalse(runner.verify_cache_manifest(before, after, {'compiled': manifest['compiled'] * 2}))

    def test_completed_worker_requires_cleanup_and_ordinary_exit(self):
        clean = {'worker_returncode': 0, 'cleanup': {'complete': True}}
        self.assertTrue(runner.worker_clean(clean))
        for changed in ({'worker_returncode': -6}, {'cleanup': {'complete': False}}, {'cleanup': {}}):
            self.assertFalse(runner.worker_clean({**clean, **changed}))

    def test_supported_closes_preserve_order_and_failure(self):
        worker_spec = importlib.util.spec_from_file_location('wasi_worker_preparation', HERE / 'worker.py')
        worker = importlib.util.module_from_spec(worker_spec); worker_spec.loader.exec_module(worker)
        first, second, third = Mock(), Mock(), Mock()
        second.close.side_effect = ValueError('synthetic close failure')
        result = worker.close_resources([('store', first), ('linker', second), ('module', third), ('absent', None)])
        self.assertFalse(result['complete'])
        self.assertEqual(result['closed'], ['store', 'module'])
        self.assertEqual(result['errors'][0]['resource'], 'linker')
        first.close.assert_called_once_with(); second.close.assert_called_once_with(); third.close.assert_called_once_with()

    def test_concurrent_output_callbacks_share_one_atomic_capacity(self):
        worker_spec = importlib.util.spec_from_file_location('wasi_worker_collector', HERE / 'worker.py')
        worker = importlib.util.module_from_spec(worker_spec); worker_spec.loader.exec_module(worker)
        entered, second_extended = threading.Event(), threading.Event()
        class FirstBuffer(bytearray):
            def extend(self, data):
                entered.set()
                # Force the previous unlocked check/extend race. A locked second
                # writer waits until this finite test-only pause ends.
                second_extended.wait(0.2)
                super().extend(data)
        class SecondBuffer(bytearray):
            def extend(self, data):
                super().extend(data)
                second_extended.set()
        output = {'stdout': FirstBuffer(), 'stderr': SecondBuffer()}
        overflow, lock, returned = [], threading.Lock(), {}
        def write(stream):
            returned[stream] = worker.collect_output(output, overflow, lock, 1, stream, b'x')
        first = threading.Thread(target=write, args=('stdout',), daemon=True)
        second = threading.Thread(target=write, args=('stderr',), daemon=True)
        first.start()
        self.assertTrue(entered.wait(1))
        second.start(); first.join(1); second.join(1)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual(sum(map(len, output.values())), 1)
        self.assertEqual(returned, {'stdout': 1, 'stderr': -1})
        self.assertTrue(overflow)

    def test_stdlib_selection_source_equality_symlinks_and_header(self):
        helper_spec = importlib.util.spec_from_file_location('wasi_stdlib_preparation', HERE / 'prepare_stdlib.py')
        helper = importlib.util.module_from_spec(helper_spec); helper_spec.loader.exec_module(helper)
        self.assertTrue(helper.selected(Path('json/decoder.py')))
        for path in ('test/bad.py', 'unittest/test/fixture.py', 'idlelib/idle_test/test_x.py',
                     'badsyntax_123.py', 'site-packages/external.py', 'module.txt'):
            self.assertFalse(helper.selected(Path(path)))
        # This checks header validation logic only, not cross-runtime bytecode compatibility.
        source = b'x = 1\n'
        header = helper.MAGIC + (3).to_bytes(4, 'little') + helper.importlib.util.source_hash(source) + b'body'
        helper.check_header(header, source)
        for damaged in (b'bad!' + header[4:], header[:4] + (1).to_bytes(4, 'little') + header[8:]):
            with self.assertRaises(ValueError):
                helper.check_header(damaged, source)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); original = root / 'Lib'; staged = root / 'stage'
            original.mkdir(); staged.mkdir()
            (original / 'public.py').write_bytes(source); (staged / 'public.py').write_bytes(source)
            self.assertEqual(len(helper.source_files(original, staged)), 1)
            (staged / 'public.py').write_text('changed')
            with self.assertRaises(ValueError):
                helper.source_files(original, staged)
            (staged / 'public.py').write_bytes(source)
            (staged / '__pycache__').symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                helper.source_files(original, staged)


if __name__ == '__main__':
    unittest.main()
