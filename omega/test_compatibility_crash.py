"""Local Linux process-crash qualification, not power-loss durability."""
import os
import pathlib
import selectors
import subprocess
import sys
import tempfile
import unittest

from omega import compatibility as c

ROOT = pathlib.Path(c.__file__).resolve().parent.parent
FILES = ["checkpoint.json", "adapter.json", "runner.py", "compatibility.py", "README.md", "manifest.json"]

@unittest.skipUnless(sys.platform == 'linux', 'Local Linux crash qualification only')
class PackageCrashes(unittest.TestCase):

    def test_all_publication_boundaries(self):
        for target in FILES:
            for when in ['before', 'after']:
                with self.subTest(target=target, when=when), tempfile.TemporaryDirectory(prefix='omega-owned-crash-') as d:
                    code = "from omega import compatibility as c; import os,sys\noriginal=c._write_local\ndef crash(path,raw,**kwargs):\n if path.name==sys.argv[2] and sys.argv[3]=='before':os._exit(77)\n original(path,raw,**kwargs)\n if path.name==sys.argv[2] and sys.argv[3]=='after':os._exit(77)\nc._write_local=crash\nc.build_product(sys.argv[1])\n"
                    r = subprocess.run([sys.executable, '-B', '-c', code, d, target, when], cwd=ROOT, capture_output=True, timeout=15)
                    self.assertEqual(r.returncode, 77, r.stderr)
                    before = c.accept_product(d, c.package_contract())
                    self.assertEqual(before['accepted'], target == 'manifest.json' and when == 'after')
                    originals = {p.name: p.read_bytes() for p in pathlib.Path(d).iterdir() if p.name in FILES and p.name != 'checkpoint.json'}
                    result = c.build_product(d)
                    self.assertTrue(result['accepted'], result)
                    for name, raw in originals.items():
                        self.assertEqual((pathlib.Path(d) / name).read_bytes(), raw)
                    self.assertTrue(c.accept_product(d, c.package_contract())['accepted'])

    def test_mid_atomic_fsync_crashes(self):
        for n in range(1, 13):
            with self.subTest(fsync=n), tempfile.TemporaryDirectory(prefix='omega-owned-crash-') as d:
                code = 'from omega import compatibility as c; import os,sys\noriginal=c.os.fsync\ncalls=0\ndef crash(fd):\n global calls\n original(fd)\n calls+=1\n if calls==int(sys.argv[2]):os._exit(78)\nc.os.fsync=crash\nc.build_product(sys.argv[1])\n'
                r = subprocess.run([sys.executable, '-B', '-c', code, d, str(n)], cwd=ROOT, capture_output=True, timeout=15)
                self.assertEqual(r.returncode, 78, r.stderr)
                before = c.accept_product(d, c.package_contract())
                self.assertEqual(before['accepted'], n == 12)
                self.assertTrue(c.build_product(d)['accepted'])

    def test_reader_during_each_publication_boundary(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='omega-owned-crash-') as d:
            observed = []
            original = c._write_local

            def observe(path, raw, **kw):
                observed.append((path.name, 'before', c.accept_product(d, c.package_contract())['accepted']))
                original(path, raw, **kw)
                observed.append((path.name, 'after', c.accept_product(d, c.package_contract())['accepted']))
            with patch.object(c, '_write_local', side_effect=observe):
                result = c.build_product(d)
            self.assertTrue(result['accepted'])
            self.assertEqual([x for x in observed if x[2]], [('manifest.json', 'after', True)])

    def test_rebuild_crash_preserves_accepted_package(self):
        with tempfile.TemporaryDirectory(prefix='omega-owned-crash-') as d:
            c.build_product(d)
            original = {name: (pathlib.Path(d) / name).read_bytes() for name in FILES}
            code = "from omega import compatibility as c; import os,sys\noriginal=c._write_local\ndef crash(path,raw,**kw):\n original(path,raw,**kw)\n if path.name=='runner.py':os._exit(79)\nc._write_local=crash\nc.build_product(sys.argv[1])\n"
            r = subprocess.run([sys.executable, '-B', '-c', code, d], cwd=ROOT, capture_output=True, timeout=15)
            self.assertEqual(r.returncode, 79, r.stderr)
            self.assertTrue(c.accept_product(d, c.package_contract())['accepted'])
            for name, raw in original.items():
                self.assertEqual((pathlib.Path(d) / name).read_bytes(), raw)
            self.assertTrue(c.build_product(d)['accepted'])

@unittest.skipUnless(sys.platform == 'linux', 'Local Linux crash qualification only')
class ConcurrentPackage(unittest.TestCase):

    def test_readers_and_competing_builder_while_writer_paused(self):
        for prior in [False, True]:
            with self.subTest(prior_package=prior), tempfile.TemporaryDirectory(prefix='omega-owned-crash-') as d:
                if prior:
                    c.build_product(d)
                code = "from omega import compatibility as c; import sys\noriginal=c._write_local\ndef pause(path,raw,**kw):\n original(path,raw,**kw)\n if path.name=='adapter.json':\n  print('paused',flush=True)\n  sys.stdin.readline()\nc._write_local=pause\nc.build_product(sys.argv[1])\n"
                p = subprocess.Popen([sys.executable, '-B', '-c', code, d], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    with selectors.DefaultSelector() as ready:
                        ready.register(p.stdout, selectors.EVENT_READ)
                        self.assertTrue(ready.select(timeout=15), 'Writer did not reach publication boundary')
                    self.assertEqual(p.stdout.readline().strip(), 'paused')
                    self.assertEqual(c.accept_product(d, c.package_contract())['accepted'], prior)
                    before = {x.name: x.read_bytes() for x in pathlib.Path(d).iterdir() if x.is_file()}
                    with self.assertRaisesRegex(ValueError, 'OUTPUT_ALREADY_IN_USE'):
                        c.build_product(d)
                    after = {x.name: x.read_bytes() for x in pathlib.Path(d).iterdir() if x.is_file()}
                    self.assertEqual(before, after)
                    p.kill()
                    p.wait(timeout=5)
                    self.assertEqual(p.returncode, -9)
                    self.assertTrue(c.build_product(d)['accepted'])
                    self.assertTrue(c.accept_product(d, c.package_contract())['accepted'])
                finally:
                    if p.poll() is None:
                        p.kill()
                        p.wait(timeout=5)
                    for stream in [p.stdin, p.stdout, p.stderr]:
                        stream.close()
