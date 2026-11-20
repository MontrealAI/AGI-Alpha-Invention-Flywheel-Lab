"""Production-facing controller wiring. Requires a separately deployed real treasury.

This path never uses NativeTreasury, never mints simulated buyer wallets and never
claims that provider available balance equals after-obligation profit. It has been
protocol-tested, not qualified against real customer, bank or model accounts.
"""
from __future__ import annotations
import time
from .runtime import Engine,policy as simulation_policy
from .store import State
from .discovery import Discovery
from .commerce import offer
from .core import canonical,digest,identifier,parse,save

class LiveEngine(Engine):
    def __init__(self,root,policy_value,agent,buyer,buyer_keys,treasury,stripe,*,success_url,cancel_url,authorized=False,clock=time.time,retriever=None):
        if not authorized:raise PermissionError('EXTERNAL_ECONOMIC_OPERATION_NOT_AUTHORIZED')
        if policy_value.get('scope') not in ('EXTERNAL_TEST','EXTERNAL_LIVE'):raise ValueError('EXPLICIT_EXTERNAL_SCOPE_REQUIRED')
        validation=dict(policy_value,scope='SIMULATED');simulation_policy(validation)
        mode='live' if policy_value['scope']=='EXTERNAL_LIVE' else 'test'
        if treasury.mode!=mode or stripe.mode!=mode or not treasury.enabled or not stripe.authorized or not buyer.enabled:
            raise ValueError('MODEL_CUSTOMER_PAYMENT_TREASURY_AUTHORITY_MUST_BE_CONFIGURED')
        if getattr(agent,'scope',None)!='CONFIGURED_MODEL' or getattr(buyer,'scope',None)!='EXTERNAL_BUYER_GATEWAY':
            raise ValueError('NO_AUTHORED_MODEL_OR_SYNTHETIC_BUYER_IN_EXTERNAL_MODE')
        if policy_value['opening_microUSD']!=0 or policy_value['startup_microUSD']!=0:
            raise ValueError('EXTERNAL_OPENING_AND_EXPENSES_MUST_COME_FROM_REAL_TREASURY')
        self.policy=policy_value;self.state=State(root,policy_value);self.root=self.state.root
        self.agent,self.buyer,self.keys,self.clock=agent,buyer,buyer_keys,clock
        self.treasury=treasury;self.stripe=stripe;self.success_url=success_url;self.cancel_url=cancel_url
        self.discovery=Discovery(self.state,self.policy,buyer_keys,agent,retriever)
        self._ready=False
    def _open(self):
        if not self._ready:self.treasury.snapshot();self._ready=True
    def close(self):self._ready=False
    def _external_effect(self,key,request,fn):
        # Provider v1 idempotency retention is finite. An old indeterminate POST
        # must be manually reconciled, not blindly repeated after key expiry.
        with self.state.db() as db:r=db.execute('SELECT status,day FROM effects WHERE id=?',(key,)).fetchone()
        if r and r['status']=='PENDING' and self.state.day()-r['day']>=23:
            raise RuntimeError('OLD_EXTERNAL_INTENT_REQUIRES_PROVIDER_RECONCILIATION')
        return self.state.effect(key,request,fn)
    def _advance_one(self,row):
        c,job,data,stage=row['body'],row['id'],row['data'],row['state']
        if stage=='CONSENTED':
            if not data.get('checkout'):
                session=self._external_effect(job+'-checkout',{'operation':'checkout','job':job,'contract':digest(c)},lambda day:self.stripe.checkout(c,self.success_url,self.cancel_url))
                self.state.update(job,{'checkout':session});return True
            if not data.get('payment_notice'):
                notice=self._external_effect(job+'-payment-notice',{'operation':'payment-notice','job':job},lambda day:self.buyer.payment(c,data['checkout']))
                self.state.update(job,{'payment_notice':{'sent':True,'reply':notice}});return True
            paid=self.stripe.checkout_status(c,data['checkout']['id'])
            if paid.get('pending'):return False
            # Persist provider observation before financial recognition. Gateway
            # independently re-verifies the provider reference and actual costs.
            self.state.update(job,{'provider_payment':paid})
            bound=self._external_effect(job+'-fund',{'operation':'begin','job':job,'payment':digest(paid)},lambda day:self.treasury.begin(c,day,data['consent'],paid))
            self.state.move(job,'FUNDED',bound);return True
        if stage=='ACCEPTED':
            payment=self.stripe.reconcile(c,data['provider_payment']['payment_intent'])
            if payment.get('pending'):return False
            receipt=self._external_effect(job+'-release',{'operation':'release','job':job,'acceptance':digest(data['acceptance'])},lambda day:self.treasury.release(c,day,data['acceptance'],payment))
            self.state.move(job,'SETTLED',{'collection':receipt});return True
        if stage=='REFUND_PENDING':
            refund=self._external_effect(job+'-provider-refund',{'operation':'provider-refund','job':job},lambda day:self.stripe.refund(data['provider_payment']['payment_intent'],c['price_microUSD']//10000,job))
            if refund.get('status')!='succeeded':raise RuntimeError('PROVIDER_REFUND_NOT_FINAL_RECONCILIATION_REQUIRED')
            receipt=self._external_effect(job+'-refund',{'operation':'refund','job':job,'provider_refund':refund},lambda day:self.treasury.refund(c,day,refund))
            self.state.move(job,'REFUNDED',{'external_refund':receipt});return True
        if stage=='ADVANCED':
            audit=self.treasury.audit()
            if audit.get('accepted') is not True:raise ValueError('EXTERNAL_TREASURY_AUDIT_NOT_ACCEPTED')
            self.state.move(job,'COMPLETE',{'external_audit':audit});return True
        return super()._advance_one(row)
    def _recover_effects(self):
        with self.state.db() as db:rows=db.execute("SELECT * FROM effects WHERE status='PENDING' ORDER BY day,rowid").fetchall()
        for r in rows:
            req=parse(r['request']);op=req['operation']
            if self.state.day()-r['day']>=23:raise RuntimeError('OLD_EXTERNAL_INTENT_REQUIRES_PROVIDER_RECONCILIATION')
            def finish(day):
                if op=='spend':return self.treasury.spend(req['key'],req['amount'],day,req['work'],req['expected_net'],req['allow_seed'])
                row=self.state.get(req['job']);c,data=row['body'],row['data']
                if op=='checkout':return self.stripe.checkout(c,self.success_url,self.cancel_url)
                if op=='payment-notice':return self.buyer.payment(c,data['checkout'])
                if op=='begin':return self.treasury.begin(c,day,data['consent'],data['provider_payment'])
                if op=='prepare':return self.treasury.prepare(c,data['artifact'],day)
                if op=='release':
                    paid=self.stripe.reconcile(c,data['provider_payment']['payment_intent'])
                    if paid.get('pending'):raise RuntimeError('PAYMENT_RECONCILIATION_PENDING')
                    return self.treasury.release(c,day,data['acceptance'],paid)
                if op=='reinvest':return self.treasury.reinvest(c,data['artifact'],day)
                if op=='provider-refund':return self.stripe.refund(data['provider_payment']['payment_intent'],c['price_microUSD']//10000,req['job'])
                if op=='refund':return self.treasury.refund(c,day,req['provider_refund'])
                raise ValueError('UNKNOWN_EXTERNAL_PENDING_EFFECT')
            self._external_effect(r['id'],req,finish)
    def run(self,**kwargs):
        with self.state.db() as db:
            hour=int(self.clock())//3600
            if hour<self.state.day():raise ValueError('EXTERNAL_CLOCK_REGRESSION')
            db.execute("UPDATE meta SET v=? WHERE k='day'",(str(hour),))
        return super().run(**kwargs)

    def _spend(self,job,label,amount,work,expected_net,allow_seed=None):
        if amount==0:
            raise ValueError('ZERO_EXTERNAL_RESOURCE_PRICE_REQUIRES_REAL_SUPPLIER_QUALIFICATION')
        return super()._spend(job,label,amount,work,expected_net,allow_seed)

    def _provider_notifications(self):
        with self.state.db() as db:
            events=db.execute("SELECT id,body FROM messages WHERE processed=0 AND id LIKE 'evt_%' ORDER BY rowid").fetchall()
        for event in events:
            # Notifications identify reconciliation work, never create revenue.
            body=parse(event['body'])
            result=self.treasury.command('reconcile-provider-notification',
                {'provider':'stripe','event_id':event['id'],'event_type':body.get('type')},'notice-'+event['id'])
            if result.get('obligations_covered') is not True or result.get('investment_allowed') is not True:
                self.state.pause(True)
            with self.state.db() as db:db.execute('UPDATE messages SET processed=1 WHERE id=?',(event['id'],))

    def step(self):
        self._open()
        # External obligations use wall-clock hours, NEVER accelerated test ticks.
        hour=int(self.clock())//3600
        with self.state.db() as db:
            if hour<self.state.day():raise ValueError('EXTERNAL_CLOCK_REGRESSION')
            db.execute("UPDATE meta SET v=? WHERE k='day'",(str(hour),))
        self._recover_effects()
        self._provider_notifications()
        if self.state.paused():return False
        self.treasury.advance(hour)
        for row in self.state.pending():
            if self._advance_one(row):return True
        return False
    def report(self):
        result={'implementation':'ALPHA Economic Engine 0.2.0','scope':self.policy['scope'],
                'state':self.state.summary(),'operating_audit':self.state.audit(),
                'external_treasury':self.treasury.snapshot(),'external_audit':self.treasury.audit(),
                'agent_status':self.agent.status(),'commercial_success':'REQUIRES_INDEPENDENT_CUSTOMER_COST_AND_SETTLEMENT_EVIDENCE',
                'native_simulation_used':False,'external_protocol_qualification':'NOT_A_REAL_PROVIDER_CERTIFICATION'}
        save(self.root/'REPORT.json',result);return result
