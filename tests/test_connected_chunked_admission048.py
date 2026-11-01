import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from adaptive_enterprise import instruments as ins
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS, audit_journal
from enterprise.services import SOURCE_PATHS as LEGACY_SOURCES

ROOT=Path(__file__).resolve().parents[1]
SEED=2611014801


def copy_sources(root):
    for name in set(SOURCE_PATHS)|set(ins.SOURCE_PATHS)|set(LEGACY_SOURCES):
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)


def settle(root,manifest,path,jobs):
    with JournalAccount(root,manifest,path,opening=100_000_000_000,working=0,contract='chunked-admission048') as a:
        a.cost('setup',750_000,0)
        a.execute('wallet',{'buyer':'finite-buyer','amount':20_000_000},0)
        for i,job in enumerate(jobs):
            if not ins.execute_job(root,job)['accepted']:raise ValueError('REEXECUTION_FAILED')
            ident='delivery-'+str(i)
            a.cost('production-'+str(i),250_000,i)
            a.execute('offer',{'id':ident,'buyer':'finite-buyer','price':2_000_000,'job_id':job['id'],'deadline':100},i)
            for action in ('consent','fund','prepare','release'):
                a.execute('event',{'id':ident,'action':action,'event_id':ident+'-'+action},i)
        record=a.export();checked=a.audit()
    return record,checked


class ChunkedAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='admission048-');cls.root=Path(cls.tmp.name);copy_sources(cls.root)
        cls.manifest=ins.prepare_complete_offer_services(cls.root,'large',cohort_seed=SEED,jobs_per_service=300,packet_jobs=129,packet_rows=4,chunk_size=37)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_beyond_old_limits_reconstructs_origins_and_settles_real_artifacts(self):
        m=self.manifest
        self.assertEqual(len(m['jobs']),1037)
        self.assertTrue(ins.audit_admission(self.root,m,cohort_seed=SEED)['accepted'])
        selected=[m['jobs'][299],m['jobs'][-1]]
        self.assertEqual(selected[1]['service_id'],'receivables_packet')
        self.assertEqual(ins._read(self.root,selected[1]['input'],selected[1]['input_sha256'])['order_id'],selected[1]['id'])
        with tempfile.TemporaryDirectory(prefix='admission048-native-') as folder:
            record,checked=settle(self.root,m,Path(folder)/'account.sqlite',selected)
            self.assertTrue(checked['accepted']);self.assertTrue(audit_journal(record,root=self.root,manifest=m)['accepted'])
            summary=record['ledger']['summary']
            self.assertEqual(summary['collections'],4_000_000)
            self.assertEqual(summary['expenses'],1_250_000)
            self.assertEqual(summary['profit'],2_750_000)
            self.assertEqual(summary['cash'],100_002_750_000)
            self.assertEqual(summary['payables'],0)
            self.assertGreater(summary['tailReserve'],0)
            self.assertEqual(len(record['ledger']['orders']),2)

    def test_chunk_windows_are_execution_windows_not_count_ceilings(self):
        chunks=list(ins.iter_checked_job_chunks(self.root,self.manifest))
        self.assertEqual(sum(map(len,chunks)),1037)
        self.assertTrue(all(1<=len(c)<=37 for c in chunks))
        self.assertEqual([c['job']['id'] for chunk in chunks for c in chunk],[j['id'] for j in self.manifest['jobs']])

    def test_missing_count_digest_and_order_tampering_fail(self):
        mutations=[lambda m:m['cohort_provenance']['finite_admission']['chunks'].pop(),
                   lambda m:m['cohort_provenance']['finite_admission'].__setitem__('total_jobs',1036),
                   lambda m:m['cohort_provenance']['finite_admission']['chunks'][0].__setitem__('jobs_sha256','0'*64),
                   lambda m:m['jobs'].__setitem__(slice(0,2),list(reversed(m['jobs'][:2]))),
                   lambda m:m['cohort_provenance']['finite_admission'].__setitem__('source_sha256','0'*64),
                   lambda m:m['cohort_provenance']['finite_admission']['chunks'][-1].__setitem__('count',True),
                   lambda m:m['cohort_provenance'].__setitem__('cohort_seed_sha256','0'*64)]
        for mutation in mutations:
            m=copy.deepcopy(self.manifest);mutation(m)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):ins.load_jobs(self.root,m)

    def test_rehashed_duplicate_and_wrong_service_order_fail(self):
        for mutation in (lambda m:m['jobs'].__setitem__(1,copy.deepcopy(m['jobs'][0])),
                         lambda m:m['jobs'].__setitem__(slice(0,2),[m['jobs'][300],m['jobs'][1]])):
            m=copy.deepcopy(self.manifest);mutation(m)
            ins._seal_admission(m,300,129,4,37)
            with self.assertRaises(ValueError):ins.load_jobs(self.root,m)

    def test_rehashed_wrong_generation_origin_is_independently_rejected(self):
        m=copy.deepcopy(self.manifest);m['jobs'][0],m['jobs'][1]=m['jobs'][1],m['jobs'][0]
        ins._seal_admission(m,300,129,4,37)
        with self.assertRaisesRegex(ValueError,'GENERATION_ORIGIN'):ins.audit_admission(self.root,m,cohort_seed=SEED)
        with self.assertRaisesRegex(ValueError,'DECLARED_GENERATION_ORIGIN'):ins.audit_admission(self.root,self.manifest,cohort_seed=SEED+1)

    def test_legacy_oversized_manifest_cannot_skip_admission(self):
        m=copy.deepcopy(self.manifest);m['cohort_provenance'].pop('finite_admission')
        with self.assertRaisesRegex(ValueError,'FINITE_SOURCE_BOUND_ADMISSION_REQUIRED'):ins.load_jobs(self.root,m)

    def test_bad_counts_windows_and_packet_rows_fail_before_writes(self):
        for value in (0,31,True,1.5,'300',None):
            with self.assertRaises(ValueError):ins.prepare_services(self.root,'must-not-exist',jobs_per_service=value)
        for value in (0,True,-1,1.5,None):
            with self.assertRaises(ValueError):ins.prepare_services(self.root,'must-not-exist',chunk_size=value)
        for rows in (0,3,1001,True):
            with self.assertRaises(ValueError):ins.prepare_complete_offer_services(self.root,'must-not-exist',packet_rows=rows)
        self.assertFalse((self.root/'must-not-exist').exists())


class ChunkEquivalence(unittest.TestCase):
    def test_small_native_events_and_all_artifacts_equal_across_windows(self):
        with tempfile.TemporaryDirectory(prefix='admission048-equivalence-') as folder:
            root=Path(folder);copy_sources(root);manifests=[];records=[]
            for window in (1,17):
                m=ins.prepare_complete_offer_services(root,'jobs-'+str(window),cohort_seed=SEED,packet_jobs=4,packet_rows=4,chunk_size=window)
                self.assertTrue(ins.audit_admission(root,m,cohort_seed=SEED)['accepted']);manifests.append(m)
                selected=[m['jobs'][0],m['jobs'][-1]]
                record,checked=settle(root,m,root/('account-'+str(window)+'.sqlite'),selected)
                self.assertTrue(checked['accepted']);records.append(record)
            for first,second in zip(manifests[0]['jobs'],manifests[1]['jobs']):
                self.assertEqual({k:v for k,v in first.items() if k not in ('input','artifact','receipt')},{k:v for k,v in second.items() if k not in ('input','artifact','receipt')})
            self.assertEqual(records[0]['ledger']['summary'],records[1]['ledger']['summary'])
            actions=lambda r:[{k:a[k] for k in ('op','args','day','after')} for a in r['ledger']['actions']]
            self.assertEqual(actions(records[0]),actions(records[1]))

if __name__=='__main__':unittest.main()
