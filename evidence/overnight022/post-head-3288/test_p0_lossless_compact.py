import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

p = Path(__file__).with_name('p0_lossless_compact.py')
spec = importlib.util.spec_from_file_location('compact', p)
compact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compact)

class BundleTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = Path(self.scratch.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        subprocess.run(['git', '-C', str(self.root), 'config', 'user.email', 'local@example.test'], check=True)
        subprocess.run(['git', '-C', str(self.root), 'config', 'user.name', 'EphemeralTest'], check=True)
        (self.root / 'evidence').mkdir()
        for i in range(6):
            (self.root / 'evidence' / f'trace{i}.json').write_text(json.dumps({'i':i,'failed':i==2}))
        (self.root / 'README.md').write_text('Immutable runtime root marker\n')
        subprocess.run(['git', '-C', str(self.root), 'add', '.'], check=True)
        subprocess.run(['git', '-C', str(self.root), 'commit', '-qm', 'historical traces'], check=True)
        self.ref = compact.git(self.root, 'rev-parse', 'HEAD').decode().strip()
        self.paths = [f'evidence/trace{i}.json' for i in range(4)]
    def tearDown(self):
        self.scratch.cleanup()
    def proposal(self, paths=None):
        return compact.candidate(self.root, self.paths if paths is None else paths, self.ref,
                                 'evidence/bundle.zip', 'evidence/bundle.json')
    def test_insufficient_compaction_rejected(self):
        with patch.object(compact, 'MAX_FILES', 5):
            with self.assertRaisesRegex(ValueError, 'INSUFFICIENT'):
                self.proposal(self.paths[:3])
    def test_roundtrip_and_original_git_history_after_removal(self):
        with patch.object(compact, 'MAX_FILES', 5):
            result = compact.build(self.root, self.proposal())
            self.assertEqual(result['archive_files_after_removal'], 5)
            self.assertTrue(compact.verify(self.root, self.root / 'evidence/bundle.json')['verified'])
            for path in self.paths:
                self.assertTrue((self.root / path).exists())
            subprocess.run(['git','-C',str(self.root),'rm','-q','--',*self.paths],check=True)
            self.assertTrue(compact.verify(self.root, self.root / 'evidence/bundle.json')['verified'])
            self.assertEqual((self.root/'README.md').read_text(),'Immutable runtime root marker\n')
    def test_modified_historical_trace_refused(self):
        (self.root/self.paths[0]).write_text('rewritten failure')
        with self.assertRaisesRegex(ValueError, 'CLEAN_COMMITTED_CHECKOUT_REQUIRED'):
            self.proposal()
    def test_scope_and_duplicates_refused(self):
        for values in [[self.paths[0],self.paths[0]], ['README.md'], ['evidence/../README.md']]:
            with self.subTest(values=values),self.assertRaises(ValueError):
                self.proposal(values)
    def test_tamper_bundle_rejected(self):
        with patch.object(compact, 'MAX_FILES', 5):
            result=compact.build(self.root,self.proposal())
            b=self.root/result['bundle']; data=bytearray(b.read_bytes());data[-1]^=1;b.write_bytes(data)
            with self.assertRaisesRegex(ValueError, 'ARCHIVE_CHANGED'):
                compact.verify(self.root,self.root/result['index_path'])
    def test_tamper_index_rejected(self):
        with patch.object(compact, 'MAX_FILES', 5):
            result=compact.build(self.root,self.proposal())
            index=self.root/result['index_path']; meta=json.loads(index.read_text()); meta['packed'][self.paths[0]]['sha256']='0'*64
            index.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError, 'MEMBER_CHANGED'):
                compact.verify(self.root,index)

if __name__=='__main__':
    unittest.main(verbosity=2)
