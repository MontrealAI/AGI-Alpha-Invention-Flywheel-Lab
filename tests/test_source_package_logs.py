"""Lean package selection never removes code or weakens old extraction checks."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from flywheel import archive_v2 as a

class SourcePackageLogTests(unittest.TestCase):
    def fixture(self, root):
        name = 'evidence/completion015/engineering/finished.log'
        raw = b'historical engineering output\n'
        p = root / name; p.parent.mkdir(parents=True); p.write_bytes(raw)
        (root / 'current.py').write_text('pass\n')
        manifest = root / a.OMISSIONS; manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({'schema':'lab/source-package-omissions/v1',
            'files':{name:{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}}}))
        return name, p, manifest

    def test_new_package_omits_only_named_hash_bound_log_and_rebuilds(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'source';root.mkdir();name,p,_=self.fixture(root)
            receipt=a.build(root,Path(d)/'a.zip')
            self.assertNotIn(name,receipt['manifest']['files']);self.assertTrue(p.exists())
            self.assertIn('current.py',receipt['manifest']['files'])
            self.assertEqual(set(receipt['manifest']['omitted_historical_engineering_logs']),{name})
            a.extract(Path(d)/'a.zip',Path(d)/'copy')
            a.build(Path(d)/'copy',Path(d)/'b.zip')

    def test_changed_log_not_silently_omitted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'source';root.mkdir();_,p,_=self.fixture(root);p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'SOURCE_LOG_OMISSION_IDENTITY_CHANGED'):
                a.build(root,Path(d)/'a.zip')
            self.assertFalse((Path(d)/'a.zip').exists())

    def test_runtime_omission_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'source';root.mkdir();name,p,m=self.fixture(root)
            x=json.loads(m.read_text());x['files']['current.py']=x['files'].pop(name);m.write_text(json.dumps(x))
            with self.assertRaisesRegex(ValueError,'SOURCE_LOG_OMISSION_SCOPE'):
                a.build(root,Path(d)/'a.zip')

    def test_old_archive_still_checks_every_declared_log(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'source';root.mkdir();name,p,m=self.fixture(root);m.unlink()
            a.build(root,Path(d)/'old.zip');a.extract(Path(d)/'old.zip',Path(d)/'copy')
            self.assertEqual((Path(d)/'copy'/name).read_bytes(),p.read_bytes())
            with zipfile.ZipFile(Path(d)/'old.zip') as z:
                items={n:z.read(n) for n in z.namelist()}
            items[a.PREFIX+name]=b'corrupt'
            with zipfile.ZipFile(Path(d)/'bad.zip','w') as z:
                for n,b in items.items():z.writestr(n,b)
            with self.assertRaisesRegex(ValueError,'ARCHIVE_CONTENT_IDENTITY_MISMATCH'):
                a.extract(Path(d)/'bad.zip',Path(d)/'bad')

if __name__=='__main__':unittest.main()
