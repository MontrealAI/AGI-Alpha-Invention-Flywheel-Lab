"""Actual native order acceptance and adversarial public replay tests."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from commercial.ledger import canonical, digest
from connected_enterprise.finance import JournalAccount
from omega.product import (MICRO, PRICE, DEFAULT_COSTS, prepare_manifest, fulfill,
                           produce, delivery, replay, cost_rows, terms_for)

ROOT = Path(__file__).resolve().parents[1]


class ProductTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self, **kwargs):
        return prepare_manifest(ROOT, self.path/'products', hypothetical_rights=True, **kwargs)

    def account(self, manifest):
        return JournalAccount(ROOT, manifest, self.path/'account.sqlite', opening=100_000*MICRO,
                              working=0, contract='omega-test')

    def fulfill(self, a, m, index=0, **kwargs):
        return fulfill(a, ROOT, m, m['jobs'][index]['id'], order_id='order-'+str(index),
                       buyer='synthetic-'+str(index), hour=0, **kwargs)

    def test_three_products_idempotent_and_replay(self):
        m = self.manifest(jobs=list(PRICE))
        with self.account(m) as a:
            for index in range(3):
                self.assertEqual(self.fulfill(a,m,index)['status'], 'released')
            before = a.export()
            for index in range(3):
                self.fulfill(a,m,index)
            self.assertEqual(a.export(), before)
            self.assertEqual(before['ledger']['summary']['collections'], sum(PRICE.values()))
            self.assertTrue(replay(before,root=ROOT,manifest=m)['accepted'])
        with self.account(m) as a:
            self.assertEqual(a.export(), before)

    def test_decline_never_collects(self):
        m = self.manifest()
        with self.account(m) as a:
            before = a.export()
            self.assertEqual(self.fulfill(a,m,consent=False)['status'], 'declined')
            self.assertEqual(a.export(),before)

    def test_failed_acceptance_refunds_and_keeps_costs(self):
        m = self.manifest(jobs=list(PRICE), outcomes=[{'accepted':False},{'attended':False},{'completed':False}])
        with self.account(m) as a:
            for index in range(3):
                self.assertEqual(self.fulfill(a,m,index)['status'], 'refunded')
            record = a.export()
            self.assertEqual(record['ledger']['summary']['collections'],0)
            self.assertGreater(record['ledger']['summary']['expensePaid'],0)
            self.assertTrue(replay(record,root=ROOT,manifest=m)['accepted'])

    def test_tampered_output_invalidates_replay(self):
        m = self.manifest()
        with self.account(m) as a:
            self.fulfill(a,m)
            record = a.export()
            path = ROOT/m['jobs'][0]['output']
            payload = json.loads(path.read_text())
            payload['buyer_result']['plan']['freshwater'][0] += 1
            path.write_bytes(canonical(payload))
            with self.assertRaises(ValueError):
                replay(record,root=ROOT,manifest=m)

    def test_native_prepare_cannot_bypass_costs(self):
        m = self.manifest()
        with self.account(m) as a:
            job = m['jobs'][0]
            a.execute('register_terms',{'id':'order:terms','terms':terms_for(m,'order',job['product'],0)},0)
            a.execute('wallet',{'buyer':'synthetic','amount':PRICE['self_hosted']},0)
            a.execute('offer',{'id':'order','buyer':'synthetic','price':PRICE['self_hosted'],'job_id':job['id'],'deadline':24,'terms_id':'order:terms'},0)
            for action in ['consent','fund']:
                a.execute('event',{'id':'order','action':action,'event_id':action},0)
            artifact = produce(ROOT,m,job['id'])
            with self.assertRaisesRegex(ValueError,'COMPLETE_PRODUCT_COSTS'):
                a.execute('event',{'id':'order','action':'prepare','event_id':'prepare','artifact_sha256':digest(artifact)},0)
            self.assertEqual(a.export()['ledger']['summary']['collections'],0)
            self.assertTrue(replay(a.export(),root=ROOT,manifest=m)['accepted'])

    def test_native_refusal_cannot_collect(self):
        m = self.manifest(outcomes=[{'accepted':False}])
        with self.account(m) as a:
            job = m['jobs'][0]
            for ident, amount in cost_rows(job, 'order', m['costs']):
                a.cost(ident,amount,0)
            a.execute('register_terms',{'id':'order:terms','terms':terms_for(m,'order',job['product'],0)},0)
            a.execute('wallet',{'buyer':'synthetic','amount':PRICE['self_hosted']},0)
            a.execute('offer',{'id':'order','buyer':'synthetic','price':PRICE['self_hosted'],'job_id':job['id'],'deadline':24,'terms_id':'order:terms'},0)
            for action in ['consent','fund']:
                a.execute('event',{'id':'order','action':action,'event_id':action},0)
            artifact = produce(ROOT,m,job['id'])
            with self.assertRaisesRegex(ValueError,'independent acceptance failed'):
                a.execute('event',{'id':'order','action':'prepare','event_id':'prepare','artifact_sha256':digest(artifact)},0)
            with self.assertRaisesRegex(ValueError,'unassured'):
                a.execute('event',{'id':'order','action':'release','event_id':'release'},0)
            self.assertEqual(a.export()['ledger']['summary']['collections'],0)
            self.assertTrue(replay(a.export(),root=ROOT,manifest=m)['accepted'])

    def test_input_change_and_missing_bytes_block_replay(self):
        m = self.manifest()
        with self.account(m) as a:
            self.fulfill(a,m)
            record = a.export()
            path = ROOT/m['jobs'][0]['input']
            original = path.read_bytes()
            path.write_bytes(original+b' ')
            with self.assertRaisesRegex(ValueError,'SOURCE_OR_ARTIFACT_CHANGED'):
                replay(record,root=ROOT,manifest=m)
            path.write_bytes(original)
            (ROOT/m['jobs'][0]['output']).unlink()
            with self.assertRaises(OSError):
                replay(record,root=ROOT,manifest=m)

    def test_costs_incurred_but_unpaid_cannot_collect(self):
        m = self.manifest()
        job = m['jobs'][0]
        price = PRICE['self_hosted']
        with JournalAccount(ROOT,m,self.path/'account.sqlite',opening=price,working=0,contract='unpaid-regression') as a:
            a.execute('register_terms',{'id':'order:terms','terms':terms_for(m,'order','self_hosted',0)},0)
            a.execute('wallet',{'buyer':'synthetic','amount':price},0)
            a.execute('offer',{'id':'order','buyer':'synthetic','price':price,'job_id':job['id'],'deadline':24,'terms_id':'order:terms'},0)
            for action in ['consent','fund']:
                a.execute('event',{'id':'order','action':action,'event_id':action},0)
            for ident,amount in cost_rows(job,'order',m['costs']):
                a.cost(ident,amount,0)
            self.assertEqual(a.snapshot()['summary']['expensePaid'],0)
            self.assertGreater(a.snapshot()['summary']['payables'],0)
            artifact = produce(ROOT,m,job['id'])
            with self.assertRaisesRegex(ValueError,'COMPLETE_PRODUCT_COSTS'):
                a.execute('event',{'id':'order','action':'prepare','event_id':'prepare','artifact_sha256':digest(artifact)},0)
            self.assertEqual(a.snapshot()['summary']['collections'],0)
            self.assertTrue(replay(a.export(),root=ROOT,manifest=m)['accepted'])

    def test_cost_override_and_shared_session(self):
        costs = copy.deepcopy(DEFAULT_COSTS)
        costs['group_webinar'] = {'all_per_seat':7*MICRO}
        costs['group_session'] = {'all_session':13*MICRO}
        m = self.manifest(jobs=['group_webinar']*2,costs=costs)
        with self.account(m) as a:
            self.fulfill(a,m,0); self.fulfill(a,m,1)
            self.assertEqual(a.export()['ledger']['summary']['expensePaid'],27*MICRO)
            self.assertTrue(replay(a.export(),root=ROOT,manifest=m)['accepted'])

    def test_explicit_sessions_have_separate_costs(self):
        costs = copy.deepcopy(DEFAULT_COSTS)
        costs['group_webinar'] = {'seat':7*MICRO}
        costs['group_session'] = {'session':13*MICRO}
        m = self.manifest(jobs=['group_webinar']*2,costs=costs,session_ids=['quarter1','quarter2'])
        with self.account(m) as a:
            self.fulfill(a,m,0)
            fulfill(a,ROOT,m,m['jobs'][1]['id'],order_id='order-1',buyer='synthetic-1',hour=800)
            self.assertEqual(a.export()['ledger']['summary']['expensePaid'],40*MICRO)
            self.assertTrue(replay(a.export(),root=ROOT,manifest=m)['accepted'])

    def test_bundle_runs_without_repository(self):
        m = self.manifest()
        artifact = produce(ROOT,m,m['jobs'][0]['id'])
        bundle = self.path/'extracted'
        for name,content in artifact['files'].items():
            path = bundle/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content)
        command = 'import json; from omega.runner import buyer; print(json.dumps(buyer(json.load(open("omega/request.json")))))'
        ran = subprocess.run([sys.executable,'-c',command],cwd=bundle,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(ran.stdout),artifact['buyer_result'])
        subprocess.run([sys.executable,'-m','omega','solve','--request','omega/request.json','--output','solved.json'],cwd=bundle,capture_output=True,text=True,check=True)
        self.assertEqual(json.loads((bundle/'solved.json').read_text()),artifact['buyer_result'])
        env = {k:v for k,v in os.environ.items() if k != 'PYTHONPATH'}
        help_run = subprocess.run([sys.executable,'-m','omega.help','model unavailable'],
                                  cwd=bundle,env=env,capture_output=True,text=True,check=True)
        help_result = json.loads(help_run.stdout)
        self.assertEqual(help_result['status'],'DOCUMENTED')
        self.assertEqual(help_result['network_calls'],0)
        self.assertTrue(help_result['citations'])

    def test_maturity_releases_capital_not_income_and_late_claim_stops(self):
        m = self.manifest()
        with self.account(m) as a:
            self.fulfill(a,m)
            before = a.snapshot()['summary']
            boundary = a.advance_financial(720)['summary']
            self.assertEqual(before,boundary)
            after = a.advance_financial(721)['summary']
            self.assertEqual(after['tailReserve'], PRICE['self_hosted']//100)
            self.assertEqual(after['profit'], before['profit'])
            self.assertEqual(after['cash'], before['cash'])
            self.assertEqual(after['available']-before['available'],before['tailReserve']-after['tailReserve'])
            receipt = a.spend('earned-research','research',MICRO,721,{'purpose':'hypothetical successor feasibility'},2*MICRO)
            self.assertEqual(receipt['funding'],'EARNED')
            record = a.export()
            a.advance_financial(721)
            self.assertEqual(a.export(),record)
            a.execute('claim',{'id':'order-0','claim_id':'late','amount':4*MICRO,'kind':'ordinary'},722)
            summary = a.snapshot()['summary']
            self.assertTrue(summary['investmentStopped'])
            self.assertEqual(summary['unrestrictedEarned'],0)
            self.assertEqual(summary['payables'],4*MICRO)
            self.assertIsNone(a.spend('blocked','production',1,722,{},1,allow_seed=True))
            self.assertTrue(replay(a.export(),root=ROOT,manifest=m)['accepted'])

    def test_rights_default_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'HYPOTHETICAL_DISTRIBUTION_RIGHTS'):
            prepare_manifest(ROOT,self.path/'products')


if __name__ == '__main__':
    unittest.main()
