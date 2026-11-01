"""Finite authored geometry admission, not demand or financial authority."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from adaptive_enterprise import instruments as inst
from connected_enterprise.packet_contract import synthetic_input
from connected_enterprise.receivables_packet import produce

ROOT = Path(__file__).resolve().parents[1]
SEED = 261101051


class PacketGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='.geometry051-', dir=ROOT)
        cls.relative = Path(cls.temp.name).relative_to(ROOT)
        cls.manifest = inst.prepare_complete_offer_services(
            ROOT, str(cls.relative/'mixed'), cohort_seed=SEED, packet_jobs=2,
            packet_rows_by_job=[12, 1000], chunk_size=17)
        cls.legacy = inst.prepare_complete_offer_services(
            ROOT, str(cls.relative/'legacy'), cohort_seed=SEED, packet_jobs=2)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_mixed_current_source_acceptance_and_reload(self):
        m = self.manifest
        self.assertEqual(m['cohort_provenance']['finite_admission']['schema'], inst.PACKET_GEOMETRY_SCHEMA)
        packets = [j for j in m['jobs'] if j['service_id'] == 'receivables_packet']
        for index, (job, rows) in enumerate(zip(packets, [12, 1000])):
            raw = json.loads((ROOT/job['input']).read_text())
            self.assertEqual(raw, synthetic_input(index=index, cohort_seed=SEED, rows=rows))
            self.assertTrue(inst.check_job(ROOT, m, job, artifact=produce(raw))['receipt']['accepted'])
        saved = json.loads((ROOT/self.relative/'mixed/MANIFEST.json').read_text())
        self.assertEqual(saved, m)
        self.assertTrue(inst.audit_admission(ROOT, saved, cohort_seed=SEED)['accepted'])
        self.assertEqual(inst.load_jobs(ROOT, saved).keys(), inst.load_jobs(ROOT, m).keys())

    def test_legacy_defaults_and_explicit_scalar(self):
        admission = self.legacy['cohort_provenance']['finite_admission']
        self.assertEqual(admission['schema'], inst.ADMISSION_SCHEMA)
        self.assertEqual(admission['packet_rows_per_kind'], 40)
        self.assertNotIn('packet_rows_by_job', admission)
        self.assertEqual(self.legacy['cohort_provenance']['packet_inventory']['rows_per_kind'], 40)
        self.assertTrue(inst.audit_admission(ROOT, self.legacy, cohort_seed=SEED)['accepted'])
        explicit = inst.prepare_complete_offer_services(
            ROOT, str(self.relative/'explicit'), cohort_seed=SEED, packet_jobs=1, packet_rows=12)
        self.assertEqual(explicit['cohort_provenance']['finite_admission']['packet_rows_per_kind'], 12)
        self.assertTrue(inst.audit_admission(ROOT, explicit, cohort_seed=SEED)['accepted'])

    def test_invalid_geometry_preflight_has_no_output(self):
        values = [[], [12], [12, 1000, 4], [True, 1000], [12.0, 1000], [3, 1000], [12, 1001], (12, 1000), '12,1000', False]
        for index, value in enumerate(values):
            target = self.relative/f'invalid-{index}'
            with self.subTest(vector=value), self.assertRaises(ValueError):
                inst.prepare_complete_offer_services(ROOT, str(target), packet_jobs=2, packet_rows_by_job=value)
            self.assertFalse((ROOT/target).exists())
        for index, scalar in enumerate([40, 12, None, True]):
            target = self.relative/f'conflict-{index}'
            with self.assertRaisesRegex(ValueError, 'CONFLICT'):
                inst.prepare_complete_offer_services(ROOT, str(target), packet_jobs=2,
                    packet_rows=scalar, packet_rows_by_job=[12, 1000])
            self.assertFalse((ROOT/target).exists())
        with self.assertRaises(ValueError):
            inst.prepare_complete_offer_services(ROOT, str(self.relative/'bool-count'), packet_jobs=True, packet_rows_by_job=[12])

    def test_vector_and_inventory_binding(self):
        for mutate in [lambda a: a['packet_rows_by_job'].pop(),
                       lambda a: a['packet_rows_by_job'].__setitem__(0, True),
                       lambda a: a.update(packet_rows_per_kind=12),
                       lambda a: a.update(schema=inst.ADMISSION_SCHEMA)]:
            bad = copy.deepcopy(self.manifest)
            mutate(bad['cohort_provenance']['finite_admission'])
            with self.assertRaises(ValueError): inst.load_jobs(ROOT, bad)
        bad = copy.deepcopy(self.manifest)
        bad['cohort_provenance']['packet_inventory']['rows_by_job'][0] = 13
        with self.assertRaisesRegex(ValueError, 'INVENTORY_GEOMETRY'):
            inst.load_jobs(ROOT, bad)

    def test_coherent_vector_drift_rejected_by_origin(self):
        bad = copy.deepcopy(self.manifest)
        bad['cohort_provenance']['finite_admission']['packet_rows_by_job'][0] = 13
        bad['cohort_provenance']['packet_inventory']['rows_by_job'][0] = 13
        with self.assertRaisesRegex(ValueError, 'PACKET_ORIGIN'):
            inst.audit_admission(ROOT, bad, cohort_seed=SEED)

    def test_chunk_source_and_generation_binding(self):
        bad = copy.deepcopy(self.manifest)
        bad['cohort_provenance']['finite_admission']['chunks'][0]['jobs_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'ADMISSION_BINDING'):
            inst.load_jobs(ROOT, bad)
        bad = copy.deepcopy(self.manifest)
        bad['source_hashes']['adaptive_enterprise/instruments.py'] = '0'*64
        bad['cohort_provenance']['finite_admission']['source_sha256'] = inst.digest(bad['source_hashes'])
        with self.assertRaisesRegex(ValueError, 'EXECUTING_SOURCE'):
            inst.load_jobs(ROOT, bad)
        with self.assertRaisesRegex(ValueError, 'GENERATION_ORIGIN'):
            inst.audit_admission(ROOT, self.manifest, cohort_seed=SEED+1)

    def test_input_bytes_and_duplicate_output_rejected(self):
        job = self.manifest['jobs'][-1]
        path = ROOT/job['input']
        original = path.read_bytes()
        try:
            path.write_bytes(original+b' ')
            with self.assertRaises(ValueError): inst.load_jobs(ROOT, self.manifest)
        finally:
            path.write_bytes(original)
        with self.assertRaisesRegex(ValueError, 'NEW_RELATIVE'):
            inst.prepare_complete_offer_services(ROOT, str(self.relative/'mixed'),
                cohort_seed=SEED, packet_jobs=2, packet_rows_by_job=[12, 1000])
        self.assertTrue(inst.audit_admission(ROOT, self.manifest, cohort_seed=SEED)['accepted'])


if __name__ == '__main__':
    unittest.main()
