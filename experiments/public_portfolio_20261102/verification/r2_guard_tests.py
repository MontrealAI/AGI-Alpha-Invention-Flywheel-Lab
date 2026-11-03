from __future__ import annotations
import argparse,copy,hashlib,inspect,io,json,shutil,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from commercial.ledger import canonical,digest,_NativePrefixReplay
from connected_enterprise.finance import source_paths_for_manifest,source_identity,audit_journal,_audit_journal
from experiments.public_portfolio_20261102 import service
from experiments.public_portfolio_20261102.native import BusinessAccount

USD=1000000


class R2GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='portfolio-r2-independent-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'source';self.root.mkdir()
        names=set(source_paths_for_manifest({'schema':service.SCHEMA}))|set(service.source_paths(ROOT))
        for name in names:
            target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,target)
        products=json.loads((ROOT/service.PREFIX/'PRODUCTS.json').read_text())
        self.product=next(p for p in products if p['id']=='interface-k1')
        self.manifest=service.prepare_manifest(self.root,[self.product],'independent-r2-'+self._testMethodName)
        self.account_path=Path(self.temp.name)/'account.sqlite'

    def account(self):
        return BusinessAccount(self.root,self.manifest,self.account_path,opening=100*USD,contract='independent-r2')

    def prepared(self,account,*,refund=False):
        artifact=json.loads((self.root/self.product['product_path']).read_text())
        account.cost('research',USD,0)
        account.begin('interface-k1','order','buyer',10*USD,50*USD,1,3,8,USD)
        self.assertTrue(account.deliver('order','interface-k1',artifact,2)['accepted'])
        account.event('order','refund' if refund else 'release',3)
        self.assertTrue(account.account._audit_incremental()['accepted'])
        return artifact

    def test_helper_files_and_initializers_bound(self):
        bound=set(source_paths_for_manifest({'schema':service.SCHEMA}))
        required={'production060/service.py','production060/acceptance.py','production060/__init__.py',
                  'experiments/__init__.py','commercial/__init__.py','commercial/tape_lease.py',
                  'adaptive_enterprise/__init__.py','connected_enterprise/__init__.py','vendor/__init__.py','vendor/alpha_claim/__init__.py'}
        self.assertTrue(required<=bound)
        self.assertIn(Path(inspect.getsourcefile(service.safe_path)).relative_to(ROOT).as_posix(),bound)
        self.assertIn(Path(inspect.getsourcefile(service.read_json)).relative_to(ROOT).as_posix(),bound)

    def test_changed_and_missing_imported_helpers_reject(self):
        for name in ('production060/service.py','production060/acceptance.py','production060/__init__.py'):
            path=self.root/name;original=path.read_bytes()
            try:
                path.write_bytes(original+b'\n')
                with self.assertRaises(ValueError):service.load_contracts(self.root,self.manifest)
                path.unlink()
                with self.assertRaises((ValueError,FileNotFoundError)):service.load_contracts(self.root,self.manifest)
            finally:path.write_bytes(original)
        self.assertEqual(len(service.load_contracts(self.root,self.manifest)),1)

    def test_incremental_matches_full_public_replay(self):
        with self.account() as account:
            account.cost('first',1000,0)
            self.assertIsNotNone(account.account._native_prefix)
            self.assertEqual(account.account._audit_incremental(),account.audit())
            for i in range(3):
                account.cost('next-'+str(i),1000+i,i+1)
                self.assertEqual(account.account._audit_incremental(),account.audit())

    def test_warm_prefix_rejects_changed_helper_then_requalifies(self):
        with self.account() as account:
            account.cost('first',1000,0)
            self.assertTrue(account.account._audit_incremental()['accepted'])
            path=self.root/'production060/service.py';original=path.read_bytes()
            try:
                path.write_bytes(original+b'\n')
                with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):account.account._audit_incremental()
                self.assertIsNone(account.account._native_prefix._replay)
            finally:path.write_bytes(original)
            self.assertEqual(account.account._audit_incremental(),account.audit())

    def test_warm_prefix_rejects_changed_approval(self):
        with self.account() as account:
            account.cost('first',1000,0)
            account.account._audit_incremental()
            path=self.root/service.APPROVAL;original=path.read_bytes()
            try:
                path.write_bytes(original+b'\n')
                with self.assertRaises(ValueError):account.account._audit_incremental()
                self.assertIsNone(account.account._native_prefix._replay)
            finally:path.write_bytes(original)
            self.assertEqual(account.account._audit_incremental(),account.audit())

    def test_refunded_prepared_output_still_rebound(self):
        with self.account() as account:
            artifact=self.prepared(account,refund=True)
            record=account.export();path=self.root/self.manifest['jobs'][0]['delivery_path'];original=path.read_bytes()
            try:
                path.write_bytes(canonical(dict(artifact,function='changed historical output')))
                with self.assertRaises(ValueError):account.account._audit_incremental()
                with self.assertRaises(ValueError):audit_journal(record,root=self.root,manifest=self.manifest)
            finally:path.write_bytes(original)
            self.assertEqual(account.account._audit_incremental(),account.audit())

    def test_changed_prior_action_rejected_with_same_length_and_recomputed_head(self):
        with self.account() as account:
            account.cost('first',1000,0);account.cost('second',1000,1)
            account.account._audit_incremental();record=account.export()
            changed=copy.deepcopy(record);changed['ledger']['actions'][0]['args']['amount']+=1
            changed['ledger']['actions_sha256']=digest(changed['ledger']['actions'])
            with self.assertRaises(ValueError):_audit_journal(changed,root=self.root,manifest=self.manifest,_native_session=account.account._native_prefix)
            self.assertIsNone(account.account._native_prefix._replay)
            self.assertEqual(account.account._audit_incremental(),account.audit())

    def test_changed_config_and_derived_state_rejected(self):
        with self.account() as account:
            account.cost('first',1000,0);record=account.export()
            for kind in ('config','summary'):
                account.account._audit_incremental();changed=copy.deepcopy(record)
                if kind=='config':changed['ledger']['config']['manifest_sha256']='0'*64
                else:changed['ledger']['summary']['cash']+=1
                with self.assertRaises(ValueError):_audit_journal(changed,root=self.root,manifest=self.manifest,_native_session=account.account._native_prefix)
                self.assertIsNone(account.account._native_prefix._replay)
            self.assertEqual(account.account._audit_incremental(),account.audit())

    def test_stale_lease_cannot_reuse_private_prefix(self):
        with self.account() as account:
            account.cost('first',1000,0);account.account._audit_incremental()
            account.account._account._owner.lease.close()
            with self.assertRaises(ValueError):account.account._audit_incremental()
            self.assertIsNone(account.account._native_prefix._replay)

    def test_concurrent_writer_rejected_and_reopen_has_new_cache(self):
        with self.account() as account:
            account.cost('first',1000,0);account.account._audit_incremental()
            with self.assertRaises(ValueError):self.account()
            record=account.export()
        with self.account() as account:
            self.assertIsNone(account.account._native_prefix)
            self.assertEqual(account.export(),record)
            self.assertEqual(account.account._audit_incremental(),account.audit())

    def test_original_v1_schema_not_silently_admitted(self):
        changed=copy.deepcopy(self.manifest);changed['schema']='public-portfolio-20261102/native-services/v1'
        with self.assertRaisesRegex(ValueError,'EXACT_MANIFEST_REQUIRED'):
            BusinessAccount(self.root,changed,self.account_path,opening=100*USD,contract='forbidden-v1-migration')
        self.assertFalse(self.account_path.exists())

    def test_public_final_audit_does_not_use_private_cache(self):
        with self.account() as account:
            self.prepared(account);record=account.export()
        with patch.object(_NativePrefixReplay,'begin',side_effect=AssertionError('public audit used private cache')):
            self.assertTrue(audit_journal(record,root=self.root,manifest=self.manifest)['accepted'])

    def test_fresh_process_runtime_import_closure(self):
        manifest_path=Path(self.temp.name)/'manifest.json';manifest_path.write_bytes(canonical(self.manifest))
        code="""import json,sys\nfrom pathlib import Path\nroot,fixture,manifest_path,account_path=map(Path,sys.argv[1:])\nsys.path.insert(0,str(root))\nfrom experiments.public_portfolio_20261102.native import BusinessAccount\nfrom experiments.public_portfolio_20261102 import service\nfrom connected_enterprise.finance import source_paths_for_manifest\nmanifest=json.loads(manifest_path.read_text())\nwith BusinessAccount(fixture,manifest,account_path,opening=100000000,contract='import-trace') as account:\n account.cost('trace-cost',1000,0)\n account.account._audit_incremental()\nbound=set(source_paths_for_manifest(manifest));observed=[]\nfor name,module in list(sys.modules.items()):\n filename=getattr(module,'__file__',None)\n if not filename or name=='__main__':continue\n path=Path(filename).resolve()\n try:relative=path.relative_to(root).as_posix()\n except ValueError:continue\n observed.append(relative)\nprint(json.dumps({'loaded':sorted(set(observed)),'missing':sorted(set(observed)-bound)}))\n"""
        process=subprocess.run([sys.executable,'-c',code,str(ROOT),str(self.root),str(manifest_path),str(Path(self.temp.name)/'trace-account.sqlite')],capture_output=True,text=True,check=True)
        result=json.loads(process.stdout)
        self.assertEqual(result['missing'],[])

    def test_standard_release_inventory_contains_bound_portfolio(self):
        from connected_enterprise.runner import source_paths
        packaged=set(source_paths(ROOT));required=set(service.source_paths(ROOT))
        self.assertTrue(required<=packaged)
        self.assertTrue({'production060/service.py','production060/acceptance.py','production060/__init__.py'}<=packaged)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    output=Path(args.output)
    if output.exists():raise ValueError('refuse overwrite of independent R2 guard result')
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(R2GuardTests);stream=io.StringIO();started=time.time()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    value={'schema':'public-portfolio-r2-independent-guards/v1','checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['experiments/public_portfolio_20261102/service.py','commercial/ledger.py','connected_enterprise/finance.py','connected_enterprise/runner.py']},
           'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful(),
           'wall_seconds':time.time()-started,'report':stream.getvalue(),
           'scope':'Disposable current-v2 source/account guard fixtures only. No R1 account/source mutation, migration, physical qualification, commerce or formal PR approval.'}
    output.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');print(json.dumps({k:value[k] for k in ('tests_run','failures','errors','passed','wall_seconds')}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
