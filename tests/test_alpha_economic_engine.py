"""Source-matched full-cycle regression tests. No real buyers/payments/model calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from connected_enterprise.alpha_economic.agents import AuthoredFixtureAgent
from connected_enterprise.alpha_economic.commerce import SimulatedBuyer
from connected_enterprise.alpha_economic.core import contract,digest,identifier,read,sign
from connected_enterprise.alpha_economic.demo import example,instrument
from connected_enterprise.alpha_economic.runtime import Engine,default_policy
from connected_enterprise.alpha_economic.store import State

KEYS={'buyer-demo':b'unit-test-buyer-key-no-real-customer-01234567'}

def envelope(c):return sign({'kind':'request','buyer':c['buyer'],'expires_at':c['expires_at'],'contract':c},KEYS[c['buyer']])

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'machine'
        self.agent=AuthoredFixtureAgent({'capacity-fulfillment-v1':instrument()})
        self.policy=default_policy();self.buyer=SimulatedBuyer(KEYS)
        self.engine=Engine(self.root,self.policy,self.agent,self.buyer,KEYS)
    def tearDown(self):self.engine.close();self.tmp.cleanup()
    def finish(self,c=None):
        c=c or example();job=self.engine.submit(envelope(c));result=self.engine.run(max_ticks=90)
        return job,result
    def until(self,job,target):
        self.engine._open()
        for _ in range(90):
            if self.engine.state.get(job)['state']==target:return
            self.engine.step()
        self.fail('Did not reach '+target)

    def test_complete_cycle_has_actual_artifact_native_settlement_and_earned_reinvestment(self):
        job,r=self.finish()
        self.assertEqual(self.engine.state.get(job)['state'],'COMPLETE')
        self.assertTrue(r['native_audit']['accepted']);self.assertTrue(r['operating_audit']['accepted'])
        self.assertEqual(r['native_summary']['collections'],12_000_000)
        self.assertGreater(r['native_summary']['profit'],0)
        self.assertEqual(r['actual_collections'],0)
        self.assertEqual(self.engine.state.get(job)['data']['reinvestment']['funding'],'EARNED')
        self.assertTrue((self.root/'outbox'/job/'solution.zip').is_file())

    def test_fresh_successor_same_account_no_new_seed(self):
        first,r=self.finish()
        second,r2=self.finish(example(2))
        self.assertEqual(r2['native_summary']['collections'],24_000_000)
        self.assertEqual(self.engine.state.get(second)['data']['artifact']['provenance']['kind'],'REVALIDATED_REUSE')
        self.assertEqual(len(self.engine.state.attempts(second)),0)
        record=read(self.root/'native-export.json')
        self.assertEqual(record['ledger']['config']['opening'],self.policy['opening_microUSD'])
        self.assertTrue(all(x['funding']=='EARNED' for x in r2['funding'] if x['id'].startswith(second)))

    def test_declined_purchase_does_not_collect(self):
        job,r=self.finish(example(outside=10_000_000))
        self.assertEqual(self.engine.state.get(job)['state'],'DECLINED')
        self.assertEqual(r['native_summary']['collections'],0)
        self.assertEqual(r['state']['capabilities'],0)
        self.assertGreater(r['native_summary']['expenses'],0)

    def test_customer_rejection_refunds_and_retains_incurred_cost(self):
        self.buyer.reject_delivery=True
        job,r=self.finish()
        self.assertEqual(self.engine.state.get(job)['state'],'REFUNDED')
        self.assertEqual(r['native_summary']['collections'],0)
        self.assertGreater(r['native_summary']['expenses'],0)
        self.assertEqual(r['state']['capabilities'],0)
        self.assertTrue(r['native_audit']['accepted'])

    def test_nonviable_request_declined_before_production(self):
        c=example();c['costs_microUSD']['research']=20_000_000
        job,r=self.finish(c)
        self.assertEqual(self.engine.state.get(job)['state'],'DECLINED');self.assertEqual(self.agent.calls,0)

    def test_failed_attempts_charged_and_ordinary_fallback_valid(self):
        self.agent.candidates={'capacity-fulfillment-v1':{'inputs':['demand'],'outputs':{'served':-1}}}
        job,r=self.finish()
        self.assertEqual(len(self.engine.state.attempts(job)),3)
        self.assertEqual(self.engine.state.get(job)['data']['artifact']['provenance']['kind'],'CONVENTIONAL_FALLBACK')
        spends=[x for x in r['funding'] if '-construction-' in x['id']]
        self.assertEqual(sum(x['amount_microUSD'] for x in spends),1_500_000)

    def test_no_positive_incremental_case_holds_cash(self):
        c=example();c['reuse_benefit_microUSD']=c['reinvestment_microUSD']
        job,r=self.finish(c)
        self.assertEqual(r['state']['capabilities'],0)
        self.assertEqual(self.engine.state.get(job)['data']['reinvestment']['reason'],'HOLD_CASH_DOMINATES_DECLARED_PLAN')

    def test_request_authentication_expiry_and_replay(self):
        c=example();good=envelope(c);job=self.engine.submit(good)
        self.assertEqual(self.engine.submit(good),job)
        bad=copy.deepcopy(good);bad['body']['contract']['price_microUSD']+=1
        with self.assertRaisesRegex(ValueError,'AUTHENTICATION'):self.engine.submit(bad)
        c['expires_at']=int(time.time())-1
        with self.assertRaisesRegex(ValueError,'EXPIRY'):self.engine.submit(envelope(c))
        self.assertEqual(len(self.engine.state.summary()['jobs']),1)

    def test_real_buyer_forbidden_on_simulated_financial_rail(self):
        real=type('RealBuyer',(),{'scope':'EXTERNAL_BUYER_GATEWAY'})()
        with self.assertRaisesRegex(ValueError,'REAL_BUYER'):
            Engine(Path(self.tmp.name)/'other',self.policy,self.agent,real,KEYS)

    def test_altered_policy_cannot_reseed_or_reinterpret(self):
        self.finish();p=copy.deepcopy(self.policy);p['opening_microUSD']*=2
        with self.assertRaisesRegex(ValueError,'POLICY_CHANGED'):Engine(self.root,p,self.agent,self.buyer,KEYS)

    def test_pause_does_not_advance_money_or_model(self):
        job=self.engine.submit(envelope(example()));self.engine.state.pause()
        self.engine.run(max_ticks=5);hour=self.engine.state.day()
        self.engine.run(max_ticks=5)
        self.assertEqual(self.engine.state.day(),hour);self.assertEqual(self.agent.calls,0)
        self.engine.state.pause(False);self.engine.run(max_ticks=90)
        self.assertEqual(self.engine.state.get(job)['state'],'COMPLETE')

    def test_duplicate_run_preserves_financial_history(self):
        self.finish();before=read(self.root/'native-export.json')['ledger']['actions_sha256']
        self.engine.run(max_ticks=1)
        after=read(self.root/'native-export.json')['ledger']['actions_sha256']
        self.assertEqual(before,after)

    def test_recover_after_native_commit_before_effect_ack_no_double_charge(self):
        job=self.engine.submit(envelope(example()));self.until(job,'QUALIFIED')
        original=self.engine.treasury.spend
        def crash(*args,**kwargs):
            original(*args,**kwargs);raise KeyboardInterrupt('crash after real native commit')
        with patch.object(self.engine.treasury,'spend',side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):self.engine.step()
        self.engine.close()
        result=self.engine.run(max_ticks=90)
        acq=[x for x in result['funding'] if x['id']==job+'-acquisition']
        self.assertEqual(len(acq),1);self.assertEqual(result['state']['effects_pending'],0)
        self.assertEqual(self.engine.state.get(job)['state'],'COMPLETE')

    def test_interrupted_paid_construction_recovers_no_free_attempt(self):
        job=self.engine.submit(envelope(example()));self.until(job,'BUILDING')
        with patch.object(self.agent,'construct',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.engine.step()
        self.engine.close();r=self.engine.run(max_ticks=90)
        self.assertEqual(len(self.engine.state.attempts(job)),2)
        self.assertEqual(self.engine.state.attempts(job)[0]['status'],'INTERRUPTED')
        self.assertEqual(sum(x['amount_microUSD'] for x in r['funding'] if '-construction-' in x['id']),1_000_000)

    def test_interrupted_native_construction_spend_resolves_old_intent(self):
        job=self.engine.submit(envelope(example()));self.until(job,'BUILDING')
        original=self.engine.treasury.spend
        def crash(*args,**kwargs):original(*args,**kwargs);raise KeyboardInterrupt
        with patch.object(self.engine.treasury,'spend',side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):self.engine.step()
        self.engine.close();r=self.engine.run(max_ticks=90)
        self.assertEqual(r['state']['effects_pending'],0)
        self.assertEqual(self.engine.state.get(job)['state'],'COMPLETE')
        self.assertEqual(len(self.engine.state.attempts(job)),2)

    def test_package_tampering_is_not_silently_overwritten(self):
        job=self.engine.submit(envelope(example()));self.until(job,'VERIFIED')
        # Crash after deterministic package publication, before stage transition.
        original=self.engine.state.move
        def crash(j,target,u=None):
            if target=='DELIVERED':raise KeyboardInterrupt
            return original(j,target,u)
        with patch.object(self.engine.state,'move',side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):self.engine.step()
        p=self.root/'outbox'/job/'solution.zip';p.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'CHANGED'):self.engine.step()

    def test_source_change_refuses_account_reopen(self):
        self.finish();p=self.root/'source/connected_enterprise/alpha_economic/checker.py';p.write_text(p.read_text()+'\n# changed\n')
        with self.assertRaisesRegex(ValueError,'SOURCE'):self.engine.run(max_ticks=1)

    def test_native_delivery_change_refuses_audit(self):
        job,r=self.finish()
        p=self.root/'source/alpha-economic-data/deliveries'/f'{job}.json'
        artifact=read(p);artifact['instrument']['outputs']['served']=0;p.write_text(json.dumps(artifact))
        with self.assertRaises(ValueError):self.engine.run(max_ticks=1)

    def test_confirmation_cases_not_used_for_training_repair(self):
        c=example();c['confirmation'][0]['expected']['served']=999999
        # A structurally valid request with no qualifying conventional control must be declined.
        job,r=self.finish(c)
        self.assertEqual(self.agent.calls,0);self.assertEqual(self.engine.state.get(job)['state'],'DECLINED')

    def test_single_worker_lock(self):
        with self.engine.state.lock():
            with self.assertRaisesRegex(RuntimeError,'ENGINE_ALREADY_RUNNING'):
                self.engine.run(max_ticks=1)

    def test_contract_injection_rejected_by_bounded_evaluator(self):
        c=example();c['ordinary']={'inputs':c['inputs'],'outputs':{'x':{'formula':'__import__("os").system("false")'}}}
        job,r=self.finish(c)
        self.assertEqual(self.engine.state.get(job)['state'],'DECLINED')

    def test_operations_hash_chain_tampering(self):
        self.finish()
        with self.engine.state.db() as db:db.execute("UPDATE events SET body='{}' WHERE seq=1")
        with self.assertRaisesRegex(ValueError,'CHAIN'):self.engine.state.audit()

if __name__=='__main__':unittest.main()
