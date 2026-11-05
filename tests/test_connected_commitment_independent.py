"""Independent challenge of registered policy, cash chronology and public exports.

Only disposable synthetic accounts are used. Tampering copies are public audit
copies with no signing authority, never account continuations or pooled capital.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from campaign.genesis_commitment001 import service
from campaign.genesis_commitment001.delivery import default_requests
from campaign.genesis_commitment001.native import BusinessAccount
from connected_enterprise.finance import source_paths_for_manifest

ROOT = Path(service.__file__).resolve().parents[2]
USD = 1_000_000


def load(path):
    return json.loads(Path(path).read_text())


def command(source, *args):
    return subprocess.run([sys.executable, '-m', 'campaign.genesis_commitment001.runner', *map(str,args)],
                          cwd=source, text=True, capture_output=True)


def public_copy(original, target):
    target.mkdir()
    for path in original.iterdir():
        if path.name == 'private':
            continue
        if path.is_dir():
            shutil.copytree(path,target/path.name)
        else:
            shutil.copyfile(path,target/path.name)


class IndependentCommitmentChallenge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='commitment-independent-')
        cls.home = Path(cls.temporary.name)
        cls.source = cls.home/'source'
        for name in source_paths_for_manifest({'schema':service.SCHEMA}):
            target=cls.source/name;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,target)
        cls.base=cls.home/'favorable'
        result=command(cls.source,'run','--output',cls.base,'--scenario','favorable_envelope')
        if result.returncode:
            raise RuntimeError(result.stdout+result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def fresh_public(self,name):
        path=self.home/name;public_copy(self.base,path);return path

    def test_favorable_costs_and_both_collections_independently_reconciled(self):
        report=load(self.base/'REPORT.json');p=load(self.base/'REGISTRATION.json')['protocol']
        b=p['scenario_economics']['favorable_envelope']['first_buyer']
        revenue=(b['price_usd']+p['buyer']['successor']['price_usd'])*USD
        pretax_cost=(sum(p['setup_costs_usd'].values())+sum(p['acquisition_costs_usd'].values())+
                     sum(p['first_costs_usd'].values())+p['successor_development_usd']+
                     p['successor_acquisition_usd']+sum(p['successor_costs_usd'].values())+
                     2*p['payment_fee_usd']+p['closing_maintenance_usd'])*USD
        tax=max(0,revenue-pretax_cost)*p['tax_numerator']//p['tax_denominator']
        summary=report['native_summary']
        self.assertEqual(report['opening_microUSD'],100_000*USD)
        self.assertEqual(report['actual_revenue_microUSD'],0)
        self.assertEqual(summary['collections'],revenue)
        self.assertEqual(summary['revenue'],revenue)
        self.assertEqual(summary['expenses'],pretax_cost+tax)
        self.assertEqual(summary['profit'],revenue-pretax_cost-tax)
        self.assertEqual(report['first_state'],'released')
        self.assertEqual(report['successor_state'],'released')
        self.assertEqual(report['successor_development_funding'],'EARNED')
        self.assertTrue(report['complete_simulated_turn'])
        self.assertIsNone(report['trailing_365_day_profit'])

    def test_package_excludes_unregistered_root_artifact_marker(self):
        out=self.fresh_public('wildcard');marker=b'INDEPENDENT_HARMLESS_PRIVATE_MARKER'
        (out/'PRIVATE_ARTIFACT.json').write_bytes(marker)
        archive=self.home/'wildcard.zip'
        result=command(self.source,'package','--output',out,'--archive',archive)
        if archive.exists():
            with zipfile.ZipFile(archive) as z:
                self.assertNotIn('PRIVATE_ARTIFACT.json',z.namelist())
                self.assertFalse(any(marker in z.read(name) for name in z.namelist()))
        if result.returncode:
            self.assertRegex(result.stdout+result.stderr,'UNREGISTERED|PUBLIC|ALLOWLIST')

    def test_package_refuses_artifact_symlink_without_reading_target(self):
        out=self.fresh_public('symlink');marker=self.home/'outside-marker.txt'
        marker.write_text('INDEPENDENT_HARMLESS_LINK_TARGET')
        (out/'FIRST_ARTIFACT.json').unlink();(out/'FIRST_ARTIFACT.json').symlink_to(marker)
        archive=self.home/'symlink.zip'
        result=command(self.source,'package','--output',out,'--archive',archive)
        self.assertNotEqual(result.returncode,0)
        if archive.exists():
            with zipfile.ZipFile(archive) as z:
                self.assertFalse(any(marker.read_bytes() in z.read(name) for name in z.namelist()))

    def test_forged_actual_revenue_is_rejected(self):
        out=self.fresh_public('forged-report');path=out/'REPORT.json';r=load(path)
        r['actual_revenue_microUSD']=1_000_000*USD;path.write_text(json.dumps(r))
        result=command(self.source,'audit','--output',out)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('REPORT_CLAIM_CHANGED',result.stdout+result.stderr)

    def test_coherent_native_terms_and_wallet_deviations_are_rejected(self):
        # Mutations use genuine native APIs/signatures, rather than corrupting JSON.
        code='''
import sys
from campaign.genesis_commitment001 import runner,native
mode=sys.argv[2]
if mode=='terms':
 old=native.prospective_terms
 def changed(*args,**kwargs):
  kwargs['residual']=0
  return old(*args,**kwargs)
 native.prospective_terms=changed
else:
 old=native.BusinessAccount.begin
 def changed(self,job,order,buyer,price,budget,hour,collect,maturity):
  return old(self,job,order,buyer,price,budget+17,hour,collect,maturity)
 native.BusinessAccount.begin=changed
runner.run(sys.argv[1],scenario='favorable_envelope')
'''
        for mode in ('terms','wallet'):
            with self.subTest(mode=mode):
                result=subprocess.run([sys.executable,'-c',code,str(self.home/('coherent-'+mode)),mode],
                                      cwd=self.source,text=True,capture_output=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn('REGISTERED_NATIVE_CHRONOLOGY_OR_TERMS_CHANGED',result.stdout+result.stderr)

    def test_changed_default_request_rejected_by_clean_independent_process(self):
        out=self.home/'changed-request'
        code='''
import sys,copy
from campaign.genesis_commitment001 import runner
old=runner.default_requests

def changed():
 r=copy.deepcopy(old());r[0]['records'][0]['balance_cents']+=37
 return r
runner.default_requests=changed
runner.run(sys.argv[1],scenario='favorable_envelope')
'''
        result=subprocess.run([sys.executable,'-c',code,str(out)],cwd=self.source,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        checked=command(self.source,'audit','--output',out)
        self.assertNotEqual(checked.returncode,0)
        self.assertIn('REGISTERED_DEFAULT_REQUESTS_CHANGED',checked.stdout+checked.stderr)

    def test_delayed_collection_checkpoint_cannot_spend_future_earnings(self):
        out=self.home/'delayed'
        result=command(self.source,'run','--output',out,'--scenario','payment_delay','--max-steps',7)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        record=load(out/'NATIVE_EXPORT.json');summary=record['ledger']['summary']
        self.assertEqual(summary['collections'],0)
        self.assertEqual(summary['unrestrictedEarned'],0)
        self.assertFalse(any(e['request'].get('id')=='successor-development' for e in record['connected_journal']['entries']))
        result=command(self.source,'resume','--output',out,'--scenario','payment_delay')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        report=load(out/'REPORT.json');self.assertTrue(report['complete_simulated_turn'])
        self.assertEqual(report['successor_development_funding'],'EARNED')
        actions=load(out/'NATIVE_EXPORT.json')['ledger']['actions']
        first_release=next(a for a in actions if a['op']=='event' and a['args']['id']=='turn-first' and a['args']['action']=='release')
        self.assertEqual(first_release['day'],80)
        self.assertTrue(load(out/'EXECUTION.json')['pending_collection_observed'])

    def test_native_promise_capacity_and_retry_boundaries(self):
        requests=[{'id':r['id'],'request':r,'delivery_path':service.DELIVERIES+r['id']+'.json'} for r in default_requests()]
        manifest=service.prepare_manifest(self.source,requests)
        suppliers={'fresh-supplier':{'units':1,'consent':'AUTHORED_SIMULATED_ACCEPTANCE'}}
        work={'capacity':{'supplier':'fresh-supplier','start':37,'end':43,'units':1},
              'costs':{'production':7*USD},'expected_net':USD,'job':'restore-first','order':'fresh-order','buyer':'fresh-buyer'}
        with BusinessAccount(self.source,manifest,self.home/'native-boundary'/'account.sqlite',
                             contract='independent-fresh-boundary',suppliers=suppliers) as business:
            before=business.account.export()
            with self.assertRaisesRegex(ValueError,'FUNDED_CAPACITY_REQUIRED'):
                business.begin('restore-first','fresh-order','fresh-buyer',300*USD,400*USD,32,60,69)
            self.assertEqual(before,business.account.export())
            receipt=business.reserve_delivery('capacity-fresh-order',7*USD,31,work,allow_seed=True)
            after=business.account.export()
            self.assertEqual(receipt,business.reserve_delivery('capacity-fresh-order',7*USD,31,work,allow_seed=True))
            self.assertEqual(after,business.account.export())
            changed=copy.deepcopy(work);changed.update(order='collision',buyer='other')
            self.assertIsNone(business.reserve_delivery('capacity-collision',7*USD,31,changed,allow_seed=True))
            self.assertEqual(after,business.account.export())
            business.begin('restore-first','fresh-order','fresh-buyer',300*USD,400*USD,32,60,69)
            self.assertEqual(len(business.account.export()['ledger']['orders']),1)


if __name__=='__main__':
    unittest.main()
