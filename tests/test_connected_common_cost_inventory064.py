"""Path-independent comparison identity preserves native admission authority."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest

from adaptive_enterprise import instruments
from commercial.ledger import canonical, digest
from scripts.run_commoncost026 import inventory_content_fingerprint, PROTOCOL

ROOT=Path(__file__).resolve().parents[1]


class CommonCostInventoryContent064(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='commoncost-content064-')
        cls.root=Path(cls.temporary.name)
        for name in instruments.SOURCE_PATHS:
            target=cls.root/name
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,target)
        cls.first=instruments.prepare_services(cls.root,'incumbent',cohort_seed=PROTOCOL['service_cohort_seed'])
        cls.second=instruments.prepare_services(cls.root,'joint',cohort_seed=PROTOCOL['service_cohort_seed'])

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def reseal(self,manifest):
        admission=manifest['cohort_provenance']['finite_admission']
        instruments._seal_admission(manifest,admission['primitive_jobs_per_service'],
            admission['packet_jobs'],admission['packet_rows_per_kind'],admission['chunk_size'])
        return manifest

    def test_identical_executed_content_in_different_folders_has_same_identity(self):
        self.assertEqual(len(self.first['jobs']),104)
        self.assertEqual(instruments.load_jobs(self.root,self.first).keys(),instruments.load_jobs(self.root,self.second).keys())
        self.assertNotEqual(self.first['jobs'][0]['input'],self.second['jobs'][0]['input'])
        self.assertNotEqual(self.first['cohort_provenance']['finite_admission']['chunks'],
                            self.second['cohort_provenance']['finite_admission']['chunks'])
        self.assertEqual(inventory_content_fingerprint(self.first),inventory_content_fingerprint(self.second))

    def test_normalization_does_not_mutate_native_manifest_or_admission(self):
        before=canonical(self.first)
        native_chunks=copy.deepcopy(self.first['cohort_provenance']['finite_admission']['chunks'])
        inventory_content_fingerprint(self.first)
        self.assertEqual(canonical(self.first),before)
        self.assertEqual(self.first['cohort_provenance']['finite_admission']['chunks'],native_chunks)

    def test_changed_content_hash_or_job_identity_remains_different(self):
        original=inventory_content_fingerprint(self.first)
        for field in ('input_sha256','artifact_sha256','receipt_sha256','id','work_keys','accepted'):
            changed=copy.deepcopy(self.first)
            if field=='work_keys':changed['jobs'][0][field]=['different-accepted-work']
            elif field=='accepted':changed['jobs'][0][field]=not changed['jobs'][0][field]
            elif field=='id':changed['jobs'][0][field]+='-different'
            else:changed['jobs'][0][field]='0'*64
            self.reseal(changed)
            with self.subTest(field=field):
                self.assertNotEqual(inventory_content_fingerprint(changed),original)

    def test_changed_source_seed_count_and_chunk_boundaries_are_not_erased(self):
        original=inventory_content_fingerprint(self.first)
        for mode in ('source','seed','chunk-size','count'):
            changed=copy.deepcopy(self.first)
            admission=changed['cohort_provenance']['finite_admission']
            if mode=='source':changed['source_hashes'][next(iter(changed['source_hashes']))]='0'*64
            elif mode=='seed':changed['cohort_provenance']['cohort_seed_sha256']=digest('changed-source-seed')
            elif mode=='chunk-size':admission['chunk_size']-=1
            else:admission['total_jobs']-=1
            if mode=='count':
                with self.assertRaises(ValueError):inventory_content_fingerprint(changed)
            else:
                self.reseal(changed)
                with self.subTest(mode=mode):self.assertNotEqual(inventory_content_fingerprint(changed),original)

    def test_invalid_raw_path_commitment_cannot_be_hidden_by_normalization(self):
        changed=copy.deepcopy(self.first)
        changed['cohort_provenance']['finite_admission']['chunks'][0]['jobs_sha256']='0'*64
        with self.assertRaises(ValueError):inventory_content_fingerprint(changed)

    def test_extra_cost_and_provenance_metadata_are_retained(self):
        original=inventory_content_fingerprint(self.first)
        for mode in ('job','cohort'):
            changed=copy.deepcopy(self.first)
            target=changed['jobs'][0] if mode=='job' else changed['cohort_provenance']
            target['declared_cost_metadata']={'verification_microUSD':123,'incurred_failures_microUSD':456}
            if mode=='job':self.reseal(changed)
            self.assertNotEqual(inventory_content_fingerprint(changed),original)

    def test_actual_input_tampering_is_rejected_by_native_content_check(self):
        path=self.root/self.first['jobs'][0]['input']
        original=path.read_bytes()
        try:
            path.write_bytes(original+b' ')
            with self.assertRaises(ValueError):instruments.load_jobs(self.root,self.first)
        finally:path.write_bytes(original)
        self.assertEqual(inventory_content_fingerprint(self.first),inventory_content_fingerprint(self.second))
