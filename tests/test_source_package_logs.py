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

    def test_narrow_additional_engineering_locations(self):
        for name in ('evidence/connected014/engineering/finished.log',
                     'evidence/enterprise011/baseline-tests.log',
                     'evidence/commercial010/qualification/tests.log',
                     'evidence/adaptive012/CI-public-package.log'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                root=Path(d)/'source';root.mkdir();old,p,m=self.fixture(root)
                raw=p.read_bytes();target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
                record=json.loads(m.read_text());record['files']={name:record['files'][old]};m.write_text(json.dumps(record))
                out=a.build(root,Path(d)/'new.zip');self.assertNotIn(name,out['manifest']['files'])
                self.assertTrue(target.exists());self.assertIn(old,out['manifest']['files'])
                target.write_bytes(b'changed log')
                with self.assertRaisesRegex(ValueError,'SOURCE_LOG_OMISSION_IDENTITY_CHANGED'):a.build(root,Path(d)/'changed.zip')

    def test_financial_recovery_and_interruption_locations_stay_required(self):
        for name in ('evidence/connected014/recovery/REJECTED_RESUME.log',
                     'evidence/adaptive012/confirmation001-interruption.log',
                     'evidence/enterprise011/RESULT.json',
                     'evidence/commercial010/qualification/nested/producer.log',
                     'connected_enterprise/engine.py'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                root=Path(d)/'source';root.mkdir();old,_,m=self.fixture(root)
                record=json.loads(m.read_text());record['files']={name:record['files'][old]};m.write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError,'SOURCE_LOG_OMISSION_SCOPE'):a.build(root,Path(d)/'bad.zip')

if __name__=='__main__':unittest.main()
