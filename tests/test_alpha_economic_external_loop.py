"""End-to-end EXTERNAL_TEST interface fixture; no real provider or model invocation."""
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from connected_enterprise.alpha_economic.live import LiveEngine
from connected_enterprise.alpha_economic.agents import HarnessAgent
from connected_enterprise.alpha_economic.commerce import HTTPBuyer,SimulatedBuyer
from connected_enterprise.alpha_economic.core import digest,identifier,sign
from connected_enterprise.alpha_economic.demo import example,instrument
from connected_enterprise.alpha_economic.runtime import default_policy

KEY=b'external-interface-fixture-key-not-production-0123456789'

class ProtocolTreasury:
    mode='test';enabled=True
    def __init__(self):self.operations=[];self.released=False
    def snapshot(self):return {'cash':20000000,'available':15000000,'unrestrictedEarned':10000000 if self.released else 0,'costs_reconciled':True}
    def spend(self,key,amount,day,work,expected_net,allow_seed):
        self.operations.append(('spend',key,amount,day))
        return {'funding':'EARNED' if self.released else 'SEED','amount_microUSD':amount,'external_transaction_id':'fixture-'+key,'obligations_covered':True}
    def begin(self,c,day,consent,payment):
        self.operations.append(('begin',identifier(c),day))
        return {'order':identifier(c),'contract_sha256':digest(c),'maturity':day+25}
    def prepare(self,c,artifact,day):self.operations.append(('prepare',identifier(c),day));return {'accepted':True}
    def release(self,c,day,acceptance,payment):self.operations.append(('release',identifier(c),day));self.released=True;return {'scope':'PROTOCOL_FIXTURE_NOT_MONEY','accepted':True}
    def reinvest(self,c,artifact,day):self.operations.append(('reinvest',identifier(c),day));return {'funding':'EARNED','source':'PROTOCOL_FIXTURE_NOT_MONEY'}
    def advance(self,day):return {'time':day}
    def audit(self):return {'accepted':True,'scope':'PROTOCOL_FIXTURE_NOT_REAL_AUDIT'}
    def command(self,op,payload,key):return {'obligations_covered':False,'investment_allowed':False}

class ProtocolPayments:
    mode='test';authorized=True
    def checkout(self,*a):return {'id':'cs_test_fixture','url':'https://checkout.stripe.com/c/pay/fixture','expires_at':int(time.time())+3600}
    def reconcile(self,c,pi):return {'scope':'STRIPE_TEST','contract_sha256':digest(c),'payment_intent':'pi_fixture','gross_microUSD':c['price_microUSD'],'fee_microUSD':0,'net_microUSD':c['price_microUSD']}
    def checkout_status(self,c,session):return self.reconcile(c,'pi_fixture')

class ExternalLoopTests(unittest.TestCase):
    def test_all_external_stages_are_wired_without_native_simulated_wallet(self):
        with tempfile.TemporaryDirectory() as temp:
            now=[int(time.time())];policy=default_policy();policy.update(scope='EXTERNAL_TEST',opening_microUSD=0,startup_microUSD=0)
            agent=HarnessAgent({'kind':'harness','runtime':{},'routes':{}})
            buyer=HTTPBuyer({'buyer-demo':'https://example.org'},{'buyer-demo':KEY},enabled=True)
            counterpart=SimulatedBuyer({'buyer-demo':KEY});treasury=ProtocolTreasury();stripe=ProtocolPayments()
            with patch.object(agent,'construct',return_value=(instrument(),{'scope':'AUTHORED_PROTOCOL_FIXTURE_NO_MODEL_INFERENCE'})),patch.object(buyer,'quote',side_effect=counterpart.quote),patch.object(buyer,'deliver',side_effect=counterpart.deliver),patch.object(buyer,'payment',return_value={'received':True}):
                e=LiveEngine(Path(temp)/'engine',policy,agent,buyer,{'buyer-demo':KEY},treasury,stripe,success_url='https://example.org/yes',cancel_url='https://example.org/no',authorized=True,clock=lambda:now[0])
                c=example();job=e.submit(sign({'kind':'request','buyer':c['buyer'],'expires_at':c['expires_at'],'contract':c},KEY))
                with e.state.lock():
                    for _ in range(40):
                        state=e.state.get(job)['state']
                        if state=='SETTLED':now[0]+=26*3600
                        if state=='COMPLETE':break
                        e.step()
                self.assertEqual(e.state.get(job)['state'],'COMPLETE')
                self.assertEqual([x[0] for x in treasury.operations if x[0] in ('begin','prepare','release','reinvest')],['begin','prepare','release','reinvest'])
                self.assertFalse((e.root/'account').exists());self.assertFalse((e.root/'native-export.json').exists())
                self.assertEqual(e.state.get(job)['data']['artifact']['provenance']['scope'],'AUTHORED_PROTOCOL_FIXTURE_NO_MODEL_INFERENCE')
                with e.state.db() as db:db.execute('INSERT INTO messages VALUES(?,?,0)',('evt_adverse','{"type":"charge.dispute.created"}'))
                e.step();self.assertTrue(e.state.paused())
                e.close()

if __name__=='__main__':unittest.main()
