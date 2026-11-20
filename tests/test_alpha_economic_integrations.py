"""Protocol/security tests. All HTTP/provider messages here are authored fixtures."""
import copy
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
from connected_enterprise.alpha_economic.core import canonical,digest,identifier,parse,sign,harness
from connected_enterprise.alpha_economic.commerce import Stripe,HTTPBuyer,consent,acceptance,offer,SimulatedBuyer
from connected_enterprise.alpha_economic.demo import example,instrument
from connected_enterprise.alpha_economic.agents import HarnessAgent,AuthoredFixtureAgent
from connected_enterprise.alpha_economic.gateway import TreasuryGateway
from connected_enterprise.alpha_economic.runtime import Engine,default_policy
from connected_enterprise.alpha_economic.discovery import Discovery
from connected_enterprise.alpha_economic.store import State
from connected_enterprise.alpha_economic.server import make_server
from connected_enterprise.alpha_economic.__main__ import doctor

KEY=b'protocol-fixture-signing-key-not-production-0123456789'

class StripeTests(unittest.TestCase):
    def setUp(self):
        self.c=example();self.calls=[]
        self.pi={'livemode':False,'currency':'usd','metadata':{'alpha_contract':digest(self.c)},'amount_received':1200,'status':'succeeded','latest_charge':'ch_example'}
        self.ch={'livemode':False,'currency':'usd','amount':1200,'payment_intent':'pi_example','paid':True,'amount_refunded':0,'refunded':False,'disputed':False,'balance_transaction':'txn_example'}
        self.tx={'currency':'usd','source':'ch_example','status':'available','amount':1200,'fee':60,'net':1140,'available_on':1790000000}
        self.session={'id':'cs_test_example','url':'https://checkout.stripe.com/c/pay/cs_test_example','livemode':False,'currency':'usd','amount_total':1200,'client_reference_id':identifier(self.c),'metadata':{'alpha_contract':digest(self.c)},'payment_status':'paid','status':'complete','payment_intent':'pi_example','expires_at':int(time.time())+3600}
        def send(method,url,headers,body,hosts):
            self.calls.append((method,url,headers,body,hosts))
            path=urlsplit(url).path
            return copy.deepcopy(self.pi if '/payment_intents/' in path else self.ch if '/charges/' in path else self.tx if '/balance_transactions/' in path else self.session if '/checkout/sessions' in path else {'id':'re_example','status':'succeeded'})
        self.stripe=Stripe('sk_test_not_real_credential_0123456789','whsec_authored_fixture_only',authorized=True,sender=send)
    def test_reconciliation_requires_provider_reads_and_fee_arithmetic(self):
        x=self.stripe.reconcile(self.c,'pi_example')
        self.assertEqual(x['net_microUSD'],11_400_000);self.assertEqual(x['fee_microUSD'],600_000)
        self.assertIsNone(x['complete_cost_profit']);self.assertIsNone(x['spendable_earned_capital']);self.assertEqual(len(self.calls),3)
    def test_pending_balance_is_not_spendable(self):
        self.tx['status']='pending';self.assertTrue(self.stripe.reconcile(self.c,'pi_example')['pending'])
    def test_failed_payment_rejected(self):
        self.pi['status']='requires_payment_method'
        with self.assertRaisesRegex(ValueError,'NOT_MATCHED'):self.stripe.reconcile(self.c,'pi_example')
    def test_wrong_contract_amount_mode_or_currency_rejected(self):
        for field,value in [('livemode',True),('currency','cad'),('amount_received',1199),('metadata',{'alpha_contract':'0'*64})]:
            with self.subTest(field=field):
                old=self.pi[field];self.pi[field]=value
                with self.assertRaises(ValueError):self.stripe.reconcile(self.c,'pi_example')
                self.pi[field]=old
    def test_refund_dispute_partial_refund_are_not_earnings(self):
        for field,value in [('refunded',True),('disputed',True),('amount_refunded',1),('paid',False)]:
            with self.subTest(field=field):
                old=self.ch[field];self.ch[field]=value
                with self.assertRaisesRegex(ValueError,'REFUNDED_DISPUTED_OR_UNPAID'):self.stripe.reconcile(self.c,'pi_example')
                self.ch[field]=old
    def test_fee_arithmetic_rejected(self):
        self.tx['net']=1200
        with self.assertRaisesRegex(ValueError,'ARITHMETIC'):self.stripe.reconcile(self.c,'pi_example')
    def test_disabled_adapter_makes_no_calls(self):
        self.stripe.authorized=False
        with self.assertRaises(PermissionError):self.stripe.checkout(self.c,'https://example.org/yes','https://example.org/no')
        self.assertEqual(self.calls,[])
    def test_checkout_is_contract_bound_and_idempotent(self):
        self.stripe.checkout(self.c,'https://example.org/yes','https://example.org/no')
        self.stripe.checkout(self.c,'https://example.org/yes','https://example.org/no')
        self.assertEqual(self.calls[0][2]['Idempotency-Key'],self.calls[1][2]['Idempotency-Key'])
        self.assertEqual(self.stripe.checkout_status(self.c,'cs_test_example')['payment_intent'],'pi_example')
    def test_checkout_success_url_does_not_prove_payment(self):
        self.session['payment_status']='unpaid'
        self.assertTrue(self.stripe.checkout_status(self.c,'cs_test_example')['pending'])
    def test_price_not_silently_rounded(self):
        self.c['price_microUSD']+=1
        with self.assertRaisesRegex(ValueError,'EXACT_CENTS'):self.stripe.checkout(self.c,'https://example.org/yes','https://example.org/no')
    def test_refund_idempotency(self):
        self.stripe.refund('pi_example',1200,'refund1');self.stripe.refund('pi_example',1200,'refund1')
        self.assertEqual(self.calls[0][2]['Idempotency-Key'],self.calls[1][2]['Idempotency-Key'])
    def header(self,raw,stamp):return 't='+str(stamp)+',v1='+hmac.new(self.stripe.secret.encode(),str(stamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
    def test_webhook_raw_signature_and_timestamp(self):
        raw=canonical({'id':'evt_example','livemode':False,'type':'payment_intent.succeeded'});now=int(time.time())
        self.assertEqual(self.stripe.webhook(raw,self.header(raw,now),now)['id'],'evt_example')
        for data,header in [(raw+b' ',self.header(raw,now)),(raw,self.header(raw,now-301)),(raw,'t=0,v1=fake')]:
            with self.assertRaises(ValueError):self.stripe.webhook(data,header,now)
    def test_webhook_test_cannot_be_live(self):
        raw=canonical({'id':'evt_example','livemode':True});now=int(time.time())
        with self.assertRaisesRegex(ValueError,'MODE'):self.stripe.webhook(raw,self.header(raw,now),now)

class IntegrationTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'machine';self.c=example()
    def tearDown(self):self.tmp.cleanup()
    def test_buyer_consent_bound_to_quote(self):
        q=offer(self.c,0);buyer=SimulatedBuyer({'buyer-demo':KEY});e=buyer.quote(self.c,q,0)
        self.assertTrue(consent(e,self.c,q,KEY,0)['accepted'])
        q['price_microUSD']+=1
        with self.assertRaisesRegex(ValueError,'BOUND'):consent(e,self.c,q,KEY,0)
    def test_delivery_ack_bound_to_exact_bytes(self):
        buyer=SimulatedBuyer({'buyer-demo':KEY});a={'instrument':'test'};p={'package_sha256':'1'*64}
        e=buyer.deliver(self.c,a,p,None,0)
        self.assertTrue(acceptance(e,self.c,a,p,KEY,0)['accepted'])
        with self.assertRaisesRegex(ValueError,'BINDING'):acceptance(e,self.c,a,{'package_sha256':'2'*64},KEY,0)
    def test_remote_customer_delivery_requires_opt_in(self):
        b=HTTPBuyer({'buyer-demo':'https://example.org'},{'buyer-demo':KEY})
        with self.assertRaises(PermissionError):b.quote(self.c,offer(self.c,0),0)
    def test_frontier_change_is_a_hypothesis_not_revenue(self):
        p=default_policy();p['frontier_urls']=['https://example.org/frontier'];p['source_hosts']=['example.org']
        s=State(self.root,p);agent=AuthoredFixtureAgent()
        text='New source';sha=hashlib.sha256(text.encode()).hexdigest()
        def retrieve(*a,**kw):return {'url':p['frontier_urls'][0],'sha256':sha,'text':text,'retrieved_at':'2026-11-16'}
        d=Discovery(s,p,{},agent,retrieve);changed=d.poll();d.hypotheses(changed,'research1')
        self.assertEqual(s.summary()['hypotheses'],1);self.assertEqual(s.summary()['jobs'],[]);self.assertEqual(d.poll(),[])
    def test_fabricated_source_reference_rejected(self):
        p=default_policy();s=State(self.root,p)
        a=AuthoredFixtureAgent();d=Discovery(s,p,{},a)
        with patch.object(a,'discover',return_value=({'hypotheses':[{'title':'x','beneficiary':'x','test':'x','evidence_sha256':'f'*64}]},{})):
            with self.assertRaisesRegex(ValueError,'ACTUAL_RETRIEVED'):d.hypotheses([{'sha256':'a'*64}],'run')
    def test_treasury_balances_are_authenticated_and_not_locally_invented(self):
        result={'cash':100,'available':70,'unrestrictedEarned':30,'payables':0,'custodyReserve':10,'tailReserve':10,'workingCapital':10,'reservedInvestment':0,'costs_reconciled':True}
        def send(method,url,headers,body,hosts):
            b=parse(body)['body']
            return sign({'kind':'treasury-receipt','account':'test-account','mode':'test','request_sha256':digest(b),'idempotency_key':b['idempotency_key'],'authorized':True,'result':result,'expires_at':int(time.time())+90},KEY)
        t=TreasuryGateway('https://example.org',KEY,KEY,'test-account',enabled=True,mode='test',sender=send)
        self.assertEqual(t.snapshot()['unrestrictedEarned'],30)
        result['unrestrictedEarned']=100
        with self.assertRaisesRegex(ValueError,'INVARIANT'):t.snapshot()
        result['unrestrictedEarned']=30;result['costs_reconciled']=False
        with self.assertRaisesRegex(ValueError,'COSTS'):t.snapshot()
    def test_treasury_disabled_makes_no_external_action(self):
        t=TreasuryGateway('https://example.org',KEY,KEY,'test-account')
        with self.assertRaises(PermissionError):t.snapshot()
    def test_treasury_rejects_unbound_receipt(self):
        def sender(*a,**kw):return sign({'kind':'treasury-receipt','account':'someone-else','mode':'live','request_sha256':'f'*64,'idempotency_key':'bad','authorized':True,'result':{},'expires_at':int(time.time())+90},KEY)
        t=TreasuryGateway('https://example.org',KEY,KEY,'test-account',enabled=True,sender=sender)
        with self.assertRaisesRegex(ValueError,'NOT_BOUND'):t.snapshot()
    def test_live_mode_requires_explicit_authority(self):
        from connected_enterprise.alpha_economic.live import LiveEngine
        with self.assertRaises(PermissionError):LiveEngine(self.root,{},None,None,None,None,None,success_url='',cancel_url='')
    def test_doctor_does_not_claim_live_readiness(self):
        cfg={'schema':'alpha-economic/config/v1','policy':{'scope':'EXTERNAL_LIVE'},'agent':{'kind':'harness'}}
        x=doctor(cfg);self.assertFalse(x['offline_readiness']);self.assertEqual(x['network_calls'],0)

class LocalHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.key={'buyer-demo':KEY};self.token='local-api-token-fixture-01234567890123456789'
        self.engine=Engine(Path(self.tmp.name)/'engine',default_policy(),AuthoredFixtureAgent(),SimulatedBuyer(self.key),self.key)
        self.stripe=Stripe('sk_test_not_a_real_account_key_fixture','whsec_local_fixture',authorized=False)
        self.server=make_server(self.engine,self.token,stripe=self.stripe);self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.engine.close();self.tmp.cleanup()
    def request(self,method,path,data=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        h={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'};h.update(headers or {})
        conn.request(method,path,data,h);response=conn.getresponse();result=(response.status,json.loads(response.read()));conn.close();return result
    def test_actual_http_submit_pause_status(self):
        c=example();e=sign({'kind':'request','buyer':c['buyer'],'expires_at':c['expires_at'],'contract':c},KEY)
        status,body=self.request('POST','/v1/requests',canonical(e));self.assertEqual(status,202)
        self.assertEqual(self.request('GET','/v1/orders/'+body['job'])[1]['state'],'DISCOVERED')
        self.assertTrue(self.request('POST','/v1/pause',b'{}')[1]['paused'])
        self.assertFalse(self.request('POST','/v1/resume',b'{}')[1]['paused'])
    def test_control_api_requires_token_and_refuses_browser_origin(self):
        self.assertEqual(self.request('GET','/v1/status',headers={'Authorization':'Bearer wrong'})[0],401)
        self.assertEqual(self.request('GET','/v1/status',headers={'Origin':'https://evil.example'})[0],401)
        self.assertEqual(self.request('GET','/v1/status',headers={'Host':'evil.example'})[0],401)
    def test_webhooks_deduplicated_without_booking_revenue(self):
        raw=canonical({'id':'evt_one','livemode':False,'type':'payment_intent.succeeded'});stamp=int(time.time())
        sig=hmac.new(self.stripe.secret.encode(),str(stamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
        head={'Stripe-Signature':f't={stamp},v1={sig}'}
        x=self.request('POST','/v1/payments/stripe',raw,head);y=self.request('POST','/v1/payments/stripe',raw,head)
        self.assertEqual(x[0],200);self.assertFalse(x[1]['duplicate']);self.assertTrue(y[1]['duplicate']);self.assertFalse(y[1]['booked_as_revenue'])
    def test_invalid_body_refused(self):
        self.assertEqual(self.request('POST','/v1/requests',b'{"a":1,"a":2}')[0],400)

class ModelProtocolTests(unittest.TestCase):
    def test_real_local_http_adapter_with_authored_response_no_inference_claim(self):
        seen=[];answer=instrument()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));seen.append(body)
                raw=json.dumps({'model':'fixture','choices':[{'message':{'content':json.dumps(answer)},'finish_reason':'stop'}],'usage':{'prompt_tokens':100,'completion_tokens':80}}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);t=threading.Thread(target=server.serve_forever);t.start()
        try:
            cfg={'kind':'harness','max_output_tokens':500,'runtime':{'local_only':True,'allow_paid':False,'providers':{'local':{'kind':'openai','base_url':f'http://127.0.0.1:{server.server_port}/v1','models':{'fixture':{'input_per_million':0,'output_per_million':0,'json_mode':True,'max_output_tokens':500}}}}},'routes':{'construct':{'provider':'local','model':'fixture'}}}
            a=HarnessAgent(cfg);c=example();result,provenance=a.construct(c,[],'model-protocol1')
            self.assertEqual(result,answer);self.assertEqual(provenance['usage_class'],'local_compute')
            prompt=seen[0]['messages'][-1]['content']
            self.assertNotIn('confirmation',prompt);self.assertIn('training',prompt)
            self.assertNotIn(canonical(c['confirmation']).decode(),prompt)
        finally:server.shutdown();server.server_close();t.join()
    def test_paid_remote_not_implicitly_enabled(self):
        cfg={'kind':'harness','runtime':{'allow_paid':False,'providers':{'remote':{'kind':'openai','base_url':'https://example.org/v1','models':{'m':{'input_per_million':1,'output_per_million':1,'json_mode':True}}}}},'routes':{'construct':{'provider':'remote','model':'m'}}}
        a=HarnessAgent(cfg)
        with self.assertRaises(ValueError):a.construct(example(),[],'no-paid-call')

if __name__=='__main__':unittest.main()
