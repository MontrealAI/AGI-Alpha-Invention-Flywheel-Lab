"""Linux local-file safety regressions for the compatibility product."""
import os, pathlib, tempfile, unittest
from omega import compatibility as c

class SafeDelivery(unittest.TestCase):

    def test_pending_symlink_never_followed(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            target = p / 'sentinel'
            target.write_bytes(b'untouched')
            d = p / 'out'
            d.mkdir()
            (d / 'checkpoint.pending').symlink_to(target)
            self.assertTrue(c.build_product(d)['accepted'])
            self.assertEqual(target.read_bytes(), b'untouched')

    def test_manifest_symlink_rejected_without_modification(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            target = p / 'sentinel'
            target.write_bytes(b'untouched')
            d = p / 'out'
            d.mkdir()
            (d / 'manifest.json').symlink_to(target)
            with self.assertRaisesRegex(ValueError, 'REGULAR_LOCAL_FILE_REQUIRED'):
                c.build_product(d)
            self.assertEqual(target.read_bytes(), b'untouched')

    def test_symlink_output_and_ancestor_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            target = p / 'outside'
            target.mkdir()
            (p / 'alias').symlink_to(target, target_is_directory=True)
            for d in [p / 'alias', p / 'alias' / 'new']:
                with self.assertRaises(OSError):
                    c.build_product(d)
            self.assertEqual(list(target.iterdir()), [])

    def test_checkpoint_link_not_read(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            target = p / 'outside'
            target.write_text('private')
            (p / 'checkpoint.json').symlink_to(target)
            with self.assertRaises(OSError):
                c.ActiveLearner(c.local_oracle(), c.package_contract(), checkpoint=p / 'checkpoint.json')
            self.assertEqual(target.read_text(), 'private')

    def test_hardlink_manifest_not_truncated(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            target = p / 'outside'
            target.write_bytes(b'untouched')
            d = p / 'out'
            d.mkdir()
            os.link(target, d / 'manifest.json')
            self.assertTrue(c.build_product(d)['accepted'])
            self.assertEqual(target.read_bytes(), b'untouched')

    def test_failed_atomic_replace_preserves_previous_checkpoint(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t) / 'checkpoint.json'
            p.write_bytes(b'previous')
            with patch.object(c.os, 'replace', side_effect=OSError('simulated interrupted write')):
                with self.assertRaises(OSError):
                    c._write_local(p, b'next')
            self.assertEqual(p.read_bytes(), b'previous')
            self.assertEqual([x.name for x in p.parent.iterdir()], ['checkpoint.json'])

    def test_changed_immutable_payload_preserved(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t) / 'adapter.json'
            p.write_bytes(b'previous')
            with self.assertRaisesRegex(ValueError, 'EXISTING_DELIVERY_CHANGED'):
                c._write_local(p, b'next', immutable=True)
            self.assertEqual(p.read_bytes(), b'previous')

    def test_nonregular_target_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t) / 'fifo'
            os.mkfifo(p)
            with self.assertRaisesRegex(ValueError, 'REGULAR_LOCAL_FILE_REQUIRED'):
                c._write_local(p, b'next')

class ArtifactShapes(unittest.TestCase):

    def test_malformed_adapters_fail_closed_without_oracle_calls(self):
        from unittest.mock import Mock
        import copy
        good = c.ActiveLearner(c.local_oracle(), c.package_contract()).learn()
        cases = [None, [], 42, {}, dict(good, transitions=None), dict(good, initial=True)]
        dangling = copy.deepcopy(good)
        dangling['transitions']['0']['start']['next'] = 100
        cases.append(dangling)
        missing = copy.deepcopy(good)
        del missing['transitions']['0']['start']
        cases.append(missing)
        for a in cases:
            oracle = Mock(side_effect=AssertionError('malformed artifact must not probe'))
            self.assertFalse(c.independent_acceptance(a, c.package_contract(), oracle)['accepted'])
            oracle.assert_not_called()

    def test_coherently_rehashed_invalid_artifact_rejected(self):
        import json, hashlib
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            c.build_product(p)
            (p / 'adapter.json').write_text('[]')
            m = json.loads((p / 'manifest.json').read_text())
            m['files']['adapter.json'] = hashlib.sha256(b'[]').hexdigest()
            (p / 'manifest.json').write_text(json.dumps(m))
            self.assertEqual(c.accept_product(p, c.package_contract())['reason'], 'INVALID_ADAPTER')

class CommandErrors(unittest.TestCase):

    def test_cli_link_failure_is_structured_not_traceback(self):
        import subprocess, sys, json
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            (p / 'real').mkdir()
            (p / 'link').symlink_to(p / 'real', target_is_directory=True)
            r = subprocess.run([sys.executable, c.__file__, '--output', str(p / 'link')], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertEqual(json.loads(r.stdout)['status'], 'LOCAL_BUILD_FAILED')
            self.assertEqual(r.stderr, '')

class AcceptanceFilesystem(unittest.TestCase):

    def test_symlink_manifest_and_all_members_rejected(self):
        for filename in ['manifest.json', 'adapter.json', 'runner.py', 'README.md', 'compatibility.py']:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as t:
                p = pathlib.Path(t)
                d = p / 'package'
                c.build_product(d)
                outside = p / 'outside'
                raw = (d / filename).read_bytes()
                outside.write_bytes(raw)
                (d / filename).unlink()
                (d / filename).symlink_to(outside)
                self.assertFalse(c.accept_product(d, c.package_contract())['accepted'])
                self.assertEqual(outside.read_bytes(), raw)

    def test_fifo_manifest_and_all_members_rejected_without_blocking(self):
        import subprocess, sys, json
        for filename in ['manifest.json', 'adapter.json', 'runner.py', 'README.md', 'compatibility.py']:
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as t:
                p = pathlib.Path(t)
                c.build_product(p)
                (p / filename).unlink()
                os.mkfifo(p / filename)
                script = 'import compatibility as c,json;print(json.dumps(c.accept_product(' + repr(str(p)) + ',c.package_contract())))'
                r = subprocess.run([sys.executable, '-c', script], cwd=pathlib.Path(c.__file__).parent, capture_output=True, text=True, timeout=5)
                self.assertEqual(r.returncode, 0)
                self.assertFalse(json.loads(r.stdout)['accepted'])

    def test_symlink_package_directory_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            c.build_product(p / 'real')
            (p / 'link').symlink_to(p / 'real', target_is_directory=True)
            self.assertFalse(c.accept_product(p / 'link', c.package_contract())['accepted'])

    def test_malformed_manifest_shapes_rejected(self):
        for value in ['[]', 'null', '42', '{"schema":"omega/finite-compatibility/v1","files":[]}']:
            with self.subTest(value=value), tempfile.TemporaryDirectory() as t:
                p = pathlib.Path(t)
                (p / 'manifest.json').write_text(value)
                self.assertFalse(c.accept_product(p, c.package_contract())['accepted'])

class BoundedIO(unittest.TestCase):

    def test_exact_limit_and_over_limit(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t) / 'file'
            p.write_bytes(b'12345')
            self.assertEqual(c._read_local(p, max_bytes=5), b'12345')
            with self.assertRaisesRegex(ValueError, 'LOCAL_FILE_BYTE_LIMIT_EXCEEDED'):
                c._read_local(p, max_bytes=4)

    def test_growth_after_stat_still_bounded(self):
        from unittest.mock import patch
        import types, stat
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t) / 'file'
            p.write_bytes(b'123456')
            with patch.object(c.os, 'fstat', return_value=types.SimpleNamespace(st_mode=stat.S_IFREG, st_size=0)):
                with self.assertRaisesRegex(ValueError, 'LOCAL_FILE_BYTE_LIMIT_EXCEEDED'):
                    c._read_local(p, max_bytes=4)

    def test_oversize_write_preserves_old_file(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t) / 'file'
            p.write_bytes(b'old')
            with self.assertRaisesRegex(ValueError, 'LOCAL_FILE_BYTE_LIMIT_EXCEEDED'):
                c._write_local(p, b'longer', max_bytes=4)
            self.assertEqual(p.read_bytes(), b'old')

    def test_invalid_limits(self):
        for limit in [0, -1, True, None, 1.5]:
            with self.assertRaisesRegex(ValueError, 'POSITIVE_LOCAL_FILE_BYTE_LIMIT_REQUIRED'):
                c._read_local('unused', max_bytes=limit)

    def test_checkpoint_read_limit_and_adjustment(self):
        with tempfile.TemporaryDirectory() as t:
            path = pathlib.Path(t) / 'checkpoint.json'
            a = c.ActiveLearner(c.local_oracle(), c.package_contract(), checkpoint=path)
            a.query(('start',))
            a.save()
            with self.assertRaisesRegex(ValueError, 'LOCAL_FILE_BYTE_LIMIT_EXCEEDED'):
                c.ActiveLearner(c.local_oracle(), c.package_contract(), checkpoint=path, max_checkpoint_bytes=4)
            self.assertEqual(c.ActiveLearner(c.local_oracle(), c.package_contract(), checkpoint=path, max_checkpoint_bytes=path.stat().st_size).cache, a.cache)

    def test_oversize_acceptance_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            (p / 'manifest.json').write_bytes(b' ' * 65)
            self.assertFalse(c.accept_product(p, c.package_contract(), max_file_bytes=64)['accepted'])

    def test_documentation_rejects_links_fifo_bad_utf8_and_limit(self):
        import subprocess, sys, json
        for kind in ['link', 'fifo', 'utf8', 'size']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as t:
                p = pathlib.Path(t)
                d = p / 'README.md'
                if kind == 'link':
                    (p / 'outside').write_text('reset')
                    d.symlink_to(p / 'outside')
                elif kind == 'fifo':
                    os.mkfifo(d)
                elif kind == 'utf8':
                    d.write_bytes(b'\xff')
                else:
                    d.write_bytes(b'reset' * 10)
                code = "import compatibility as c,json;print(json.dumps(c.diagnose('oracle_unavailable'," + repr(str(p)) + ',max_document_bytes=16)))'
                r = subprocess.run([sys.executable, '-c', code], cwd=pathlib.Path(c.__file__).parent, capture_output=True, text=True, timeout=5)
                self.assertEqual(r.returncode, 0)
                self.assertEqual(json.loads(r.stdout)['status'], 'UNRESOLVED')

class Ownership(unittest.TestCase):

    def test_live_other_process_refused_and_lock_released_after_death(self):
        import subprocess, sys, json
        with tempfile.TemporaryDirectory() as t:
            code = 'import compatibility as c,time\nwith c._exclusive_directory(' + repr(t) + "):\n print('locked',flush=True)\n time.sleep(30)"
            p = subprocess.Popen([sys.executable, '-c', code], cwd=pathlib.Path(c.__file__).parent, stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(p.stdout.readline().strip(), 'locked')
                with self.assertRaisesRegex(ValueError, 'OUTPUT_ALREADY_IN_USE'):
                    c.build_product(t)
                self.assertFalse((pathlib.Path(t) / 'checkpoint.json').exists())
            finally:
                p.terminate()
                p.wait(timeout=5)
                p.stdout.close()
            self.assertTrue(c.build_product(t)['accepted'])

    def test_stale_checkpoint_writer_cannot_replace_newer_checkpoint(self):
        with tempfile.TemporaryDirectory() as t:
            path = pathlib.Path(t) / 'checkpoint.json'
            a = c.ActiveLearner(c.local_oracle(), c.package_contract(), checkpoint=path)
            b = c.ActiveLearner(c.local_oracle(), c.package_contract(), checkpoint=path)
            a.query(('start',))
            b.query(('append',))
            a.save()
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, 'CHECKPOINT_CHANGED_BY_ANOTHER_WRITER'):
                b.save()
            self.assertEqual(path.read_bytes(), before)
            a.save()

    def test_lock_link_and_hardlink_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t)
            outside = p / 'outside'
            outside.write_text('unchanged')
            for hard in [False, True]:
                d = p / str(hard)
                d.mkdir()
                lock = d / '.omega-delivery.lock'
                if hard:
                    os.link(outside, lock)
                else:
                    lock.symlink_to(outside)
                with self.assertRaises((OSError, ValueError)):
                    c.build_product(d)
                self.assertEqual(outside.read_text(), 'unchanged')

    def test_immutable_create_race_does_not_clobber_winner(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as t:
            p = pathlib.Path(t) / 'file'
            original = c.os.link

            def race(*args, **kwargs):
                p.write_bytes(b'winner')
                return original(*args, **kwargs)
            with patch.object(c.os, 'link', side_effect=race):
                with self.assertRaises(FileExistsError):
                    c._write_local(p, b'loser', immutable=True)
            self.assertEqual(p.read_bytes(), b'winner')

    def test_no_locking_platform_fails_closed(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as t, patch.object(c, 'fcntl', None):
            with self.assertRaisesRegex(ValueError, 'LOCAL_POSIX_LOCKING_REQUIRED'):
                c.build_product(pathlib.Path(t) / 'output')
            self.assertFalse((pathlib.Path(t) / 'output').exists())

if __name__ == "__main__":
    unittest.main()
