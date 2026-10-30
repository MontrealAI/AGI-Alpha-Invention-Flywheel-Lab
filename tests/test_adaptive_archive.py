import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from flywheel import archive_v2

ROOT=Path(__file__).resolve().parents[1]
PART='artifacts/adaptive012-parts/part-000.bin'
COMBINED='artifacts/AGI_ALPHA_Adaptive_012_source_evidence.zip'


class AdaptiveArchiveTests(unittest.TestCase):
    def test_only_exact_transport_is_omitted_and_current_source_remains(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'source';source.mkdir()
            keep={
                'adaptive_enterprise/model.py':(ROOT/'adaptive_enterprise/model.py').read_bytes(),
                'adaptive_enterprise/account.py':(ROOT/'adaptive_enterprise/account.py').read_bytes(),
                'commercial/ledger.py':(ROOT/'commercial/ledger.py').read_bytes(),
                'campaign/adaptive-012/receipt.json':b'{"scope":"SIMULATED"}',
                'artifacts/ADAPTIVE012_PACKAGE.json':b'public archive binding stays included',
                'artifacts/adaptive012-parts-v2/keep.bin':b'lookalike directory',
                'nested/artifacts/adaptive012-parts/keep.bin':b'not the root transport',
                'other/adaptive012-parts/keep.bin':b'other location',
                'artifacts/AGI_ALPHA_Adaptive_012_source_evidence.zip.bak':b'distinct artifact',
                'artifacts/unrelated.zip':b'unrelated archive',
            }
            omitted={PART:b'new transport bytes',COMBINED:b'new combined archive',
                     'artifacts/enterprise011-parts/part-000.bin':b'old transport bytes',
                     'artifacts/AGI_ALPHA_Enterprise_011_source_evidence.zip':b'old combined archive'}
            for name,raw in {**keep,**omitted}.items():
                path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            result=archive_v2.build(source,root/'bounded.zip')
            self.assertEqual(set(result['manifest']['files']),set(keep))
            archive_v2.extract(root/'bounded.zip',root/'extracted')
            for name,raw in keep.items():self.assertEqual((root/'extracted'/name).read_bytes(),raw)
            for name in omitted:self.assertFalse((root/'extracted'/name).exists())

    def test_resource_caps_remain_enforced_for_retained_payloads(self):
        self.assertEqual(archive_v2.MAX_BYTES,512*1024**2)
        self.assertEqual(archive_v2.MAX_FILES,10000)
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/'source';source.mkdir()
            (source/'current.py').write_bytes(b'x'*21)
            path=source/PART;path.parent.mkdir(parents=True);path.write_bytes(b'x'*100)
            with patch.object(archive_v2,'MAX_BYTES',20):
                with self.assertRaisesRegex(ValueError,'RESOURCE_BOUND'):archive_v2.build(source,root/'too-large.zip')
            (source/'second.py').write_bytes(b'x')
            with patch.object(archive_v2,'MAX_FILES',1):
                with self.assertRaisesRegex(ValueError,'RESOURCE_BOUND'):archive_v2.build(source,root/'too-many.zip')

    def test_extract_still_verifies_declared_transport_in_prior_archives(self):
        payloads={'adaptive_enterprise/current.py':b'current source',PART:b'declared prior transport',COMBINED:b'declared combined archive'}
        manifest={'schema':'lab/self-contained-source-archive/v2','files':{name:hashlib.sha256(raw).hexdigest() for name,raw in payloads.items()}}
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for corrupted in [False,True]:
                archive=root/('corrupt.zip' if corrupted else 'valid.zip')
                with zipfile.ZipFile(archive,'w') as z:
                    for name,raw in payloads.items():z.writestr(archive_v2.PREFIX+name,b'changed transport' if corrupted and name==PART else raw)
                    z.writestr(archive_v2.PREFIX+archive_v2.MANIFEST,json.dumps(manifest))
            archive_v2.extract(root/'valid.zip',root/'valid')
            self.assertEqual((root/'valid'/PART).read_bytes(),payloads[PART])
            with self.assertRaisesRegex(ValueError,'CONTENT_IDENTITY'):archive_v2.extract(root/'corrupt.zip',root/'corrupt')

    def test_prior_adapter_retains_its_hash_bound_original_limits(self):
        record=json.loads((ROOT/'historical/adaptive012-prior-policy/ARCHIVE_V2_SOURCE.json').read_text())
        preserved=(ROOT/record['preserved_path']).read_bytes()
        self.assertEqual(record['source_commit'],'daf3ef2ff07a2ba89393038288606f0b61610b92')
        self.assertEqual(record['sha256'],'138f59b545c91fc36ef0d9653b9f94cccf2aaed68f6e879c07387dcd6de88afe')
        self.assertEqual(hashlib.sha256(preserved).hexdigest(),record['sha256'])
        self.assertEqual(len(preserved),record['bytes'])
        namespace={'__name__':'preserved_adaptive_archive_policy'}
        exec(compile(preserved,record['preserved_path'],'exec'),namespace)
        self.assertEqual(record['limits'],{'MAX_BYTES':namespace['MAX_BYTES'],'MAX_FILES':namespace['MAX_FILES']})
        self.assertEqual(record['limits'],{'MAX_BYTES':250*1024**2,'MAX_FILES':10000})
        self.assertNotEqual(preserved,(ROOT/'flywheel/archive_v2.py').read_bytes())


if __name__=='__main__':unittest.main()
