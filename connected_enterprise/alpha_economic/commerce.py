"""Buyer consent, delivery acknowledgment and payment-provider reconciliation.

A Stripe notification is not a completed economic cycle. Refunds/disputes remain
relevant and available funds require a separately authoritative treasury decision.
"""
from __future__ import annotations
import hashlib
import hmac
import time
from urllib.parse import urlencode,urlsplit
from .core import authenticate,canonical,digest,identifier,sign,signature
from .network import request


def offer(c,now):
    return {'kind':'offer','buyer':c['buyer'],'contract_sha256':digest(c),
            'price_microUSD':c['price_microUSD'],'expires_at':c['expires_at'],
            'acceptance':'HOST_CHECKER_AND_CUSTOMER_ACCEPTANCE','payment_terms':'PREPAID_REFUND_IF_UNACCEPTED','rights':c['rights']}


def consent(envelope,c,quoted,key,now):
    body=authenticate(envelope,key,kind='consent',now=now)
    expected={'kind','buyer','contract_sha256','offer_sha256','accepted','expires_at'}
    if set(body)!=expected or body['buyer']!=c['buyer'] or body['contract_sha256']!=digest(c) or body['offer_sha256']!=digest(quoted) or type(body['accepted']) is not bool:
        raise ValueError('BUYER_CONSENT_NOT_BOUND_TO_THIS_OFFER')
    return body


def acceptance(envelope,c,artifact,package,key,now):
    body=authenticate(envelope,key,kind='acceptance',now=now)
    if set(body)!={'kind','buyer','contract_sha256','artifact_sha256','package_sha256','accepted','expires_at'}:
        raise ValueError('EXACT_BUYER_ACCEPTANCE_REQUIRED')
    if body['buyer']!=c['buyer'] or body['contract_sha256']!=digest(c) or body['artifact_sha256']!=digest(artifact) or body['package_sha256']!=package['package_sha256'] or type(body['accepted']) is not bool:
        raise ValueError('BUYER_ACCEPTANCE_BINDING_FAILED')
    return body


class SimulatedBuyer:
    scope='SIMULATED_COUNTERPARTY'
    def __init__(self,keys,decline=False,reject_delivery=False):self.keys=keys;self.decline=decline;self.reject_delivery=reject_delivery
    def quote(self,c,quoted,now):
        accepted=not self.decline and c['price_microUSD']<=c['buyer_budget_microUSD'] and c['price_microUSD']<c['outside_option_microUSD']
        return sign({'kind':'consent','buyer':c['buyer'],'contract_sha256':digest(c),'offer_sha256':digest(quoted),
                     'accepted':accepted,'expires_at':c['expires_at']},self.keys[c['buyer']])
    def deliver(self,c,artifact,package,path,now):
        return sign({'kind':'acceptance','buyer':c['buyer'],'contract_sha256':digest(c),'artifact_sha256':digest(artifact),
                     'package_sha256':package['package_sha256'],'accepted':not self.reject_delivery,
                     'expires_at':c['expires_at']},self.keys[c['buyer']])


class HTTPBuyer:
    """Configured opt-in customer API, not unsolicited outreach or automatic consent."""
    scope='EXTERNAL_BUYER_GATEWAY'
    def __init__(self,endpoints,keys,*,enabled=False,sender=request):
        self.endpoints,self.keys,self.enabled,self.sender=endpoints,keys,enabled,sender
    def _post(self,c,route,body,key):
        if not self.enabled:raise PermissionError('EXTERNAL_CUSTOMER_DELIVERY_NOT_AUTHORIZED')
        base=self.endpoints.get(c['buyer'])
        if not base:raise ValueError('BUYER_ENDPOINT_NOT_REGISTERED')
        host=urlsplit(base).hostname
        payload=canonical(sign(body,self.keys[c['buyer']]))
        return self.sender('POST',base.rstrip('/')+route,{'Content-Type':'application/json','Idempotency-Key':key},payload,hosts=(host,))
    def quote(self,c,quoted,now):return self._post(c,'/offers',quoted,'quote-'+digest(quoted))
    def payment(self,c,checkout):
        body={'kind':'payment-request','contract_sha256':digest(c),'checkout':checkout,'expires_at':c['expires_at']}
        return self._post(c,'/payment-requests',body,'payment-request-'+identifier(c))
    def deliver(self,c,artifact,package,path,now):
        import base64
        body={'kind':'delivery','contract_sha256':digest(c),'artifact':artifact,'package':package,
              'archive_base64':base64.b64encode(path.read_bytes()).decode(),'expires_at':c['expires_at']}
        return self._post(c,'/deliveries',body,'delivery-'+digest(artifact))


class Stripe:
    """Explicit test/live adapter. No credentials are discovered or billing enabled."""
    def __init__(self,key,webhook_secret,*,mode='test',authorized=False,sender=request):
        if mode not in ('test','live'):raise ValueError('EXPLICIT_STRIPE_MODE_REQUIRED')
        self.mode,self.key,self.secret,self.authorized,self.sender=mode,key,webhook_secret,authorized,sender
        self.scope='STRIPE_'+mode.upper()
    def _api(self,method,path,form=None,key=None):
        if not self.authorized:raise PermissionError('PAYMENT_PROVIDER_NOT_AUTHORIZED')
        if not isinstance(self.key,str) or not self.key.startswith('sk_'+self.mode+'_'):
            raise ValueError('PAYMENT_CREDENTIAL_MODE_MISMATCH')
        headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/x-www-form-urlencoded'}
        if key:headers['Idempotency-Key']=key
        body=urlencode(form or {}).encode() if method=='POST' else None
        return self.sender(method,'https://api.stripe.com'+path,headers,body,hosts=('api.stripe.com',))
    def checkout(self,c,success_url,cancel_url):
        # Stripe USD uses integer cents: never round a contract price silently.
        if c['price_microUSD']%10000:raise ValueError('USD_PRICE_MUST_BE_EXACT_CENTS')
        for url in (success_url,cancel_url):
            u=urlsplit(url)
            if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('HTTPS_CHECKOUT_RETURN_URL_REQUIRED')
        order=identifier(c)
        data={'mode':'payment','success_url':success_url,'cancel_url':cancel_url,'client_reference_id':order,
              'metadata[alpha_contract]':digest(c),'payment_intent_data[metadata][alpha_contract]':digest(c),
              'line_items[0][price_data][currency]':'usd','line_items[0][price_data][unit_amount]':c['price_microUSD']//10000,
              'line_items[0][price_data][product_data][name]':'Verified digital instrument','line_items[0][quantity]':1}
        result=self._api('POST','/v1/checkout/sessions',data,'checkout-'+order)
        self._session_bound(c,result)
        u=urlsplit(result.get('url',''))
        if u.scheme!='https' or u.hostname!='checkout.stripe.com' or u.username or u.password:raise ValueError('EXPECTED_STRIPE_CHECKOUT_URL')
        return {k:result[k] for k in ('id','url','expires_at')}
    def _session_bound(self,c,s):
        if (s.get('livemode')!=(self.mode=='live') or s.get('currency')!='usd'
            or s.get('client_reference_id')!=identifier(c) or s.get('metadata',{}).get('alpha_contract')!=digest(c)
            or type(s.get('amount_total')) is not int or s['amount_total']*10000!=c['price_microUSD']):
            raise ValueError('CHECKOUT_NOT_BOUND_TO_CONTRACT')
    def checkout_status(self,c,session):
        if not isinstance(session,str) or not session.startswith('cs_') or not session.replace('_','').isalnum():raise ValueError('CHECKOUT_SESSION_IDENTIFIER_REQUIRED')
        s=self._api('GET','/v1/checkout/sessions/'+session);self._session_bound(c,s)
        if s.get('payment_status')!='paid':return {'pending':True,'expired':s.get('status')=='expired'}
        return self.reconcile(c,s.get('payment_intent'))
    def webhook(self,raw,header,now=None):
        now=int(time.time()) if now is None else now
        if not isinstance(self.secret,str) or not self.secret or len(raw)>2_000_000:raise ValueError('WEBHOOK_SECRET_AND_BOUNDED_BODY_REQUIRED')
        parts={}
        for item in header.split(','):
            k,sep,v=item.partition('=')
            if sep:parts.setdefault(k,[]).append(v)
        if len(parts.get('t',[]))!=1:raise ValueError('WEBHOOK_TIMESTAMP_REQUIRED')
        stamp=int(parts['t'][0])
        if abs(now-stamp)>300:raise ValueError('STALE_WEBHOOK_SIGNATURE')
        expected=hmac.new(self.secret.encode(),str(stamp).encode()+b'.'+raw,hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected,v) for v in parts.get('v1',[])):raise ValueError('WEBHOOK_SIGNATURE_FAILED')
        from .core import parse
        event=parse(raw)
        if type(event.get('livemode')) is not bool or event['livemode']!=(self.mode=='live'):
            raise ValueError('PAYMENT_EVENT_MODE_MISMATCH')
        if not isinstance(event.get('id'),str) or not event['id'].startswith('evt_'):raise ValueError('PAYMENT_EVENT_ID_REQUIRED')
        return event
    def reconcile(self,c,payment_intent):
        if not isinstance(payment_intent,str) or not payment_intent.startswith('pi_') or not payment_intent.replace('_','').isalnum():raise ValueError('PAYMENT_INTENT_IDENTIFIER_REQUIRED')
        pi=self._api('GET','/v1/payment_intents/'+payment_intent)
        if c['price_microUSD']%10000:raise ValueError('USD_PRICE_MUST_BE_EXACT_CENTS')
        if pi.get('livemode')!=(self.mode=='live') or pi.get('currency')!='usd' or pi.get('metadata',{}).get('alpha_contract')!=digest(c) or pi.get('amount_received')!=c['price_microUSD']//10000 or pi.get('status')!='succeeded':
            raise ValueError('PROVIDER_PAYMENT_NOT_MATCHED_TO_CONTRACT')
        charge=pi.get('latest_charge')
        if not isinstance(charge,str) or not charge.startswith('ch_') or not charge.replace('_','').isalnum():raise ValueError('PROVIDER_CHARGE_REQUIRED')
        ch=self._api('GET','/v1/charges/'+charge)
        if ch.get('livemode')!=(self.mode=='live') or ch.get('currency')!='usd' or (ch.get('amount') if type(ch.get('amount')) is int else -1)*10000!=c['price_microUSD'] or ch.get('payment_intent')!=payment_intent or ch.get('refunded') or ch.get('disputed') or ch.get('amount_refunded',0) or ch.get('paid') is not True:
            raise ValueError('PAYMENT_REFUNDED_DISPUTED_OR_UNPAID')
        tx=ch.get('balance_transaction')
        if not isinstance(tx,str) or not tx.startswith('txn_') or not tx.replace('_','').isalnum():raise ValueError('BALANCE_TRANSACTION_REQUIRED')
        balance=self._api('GET','/v1/balance_transactions/'+tx)
        if balance.get('currency')!='usd' or balance.get('source')!=charge or balance.get('status')!='available':
            return {'pending':True,'reason':'PAYMENT_NOT_AVAILABLE','scope':self.scope}
        if type(balance.get('amount')) is not int or type(balance.get('fee')) is not int or balance['amount']!=c['price_microUSD']//10000 or balance['fee']<0 or balance.get('net')!=balance['amount']-balance['fee']:
            raise ValueError('PROVIDER_BALANCE_ARITHMETIC_MISMATCH')
        return {'scope':self.scope,'payment_intent':payment_intent,'charge':charge,'balance_transaction':tx,
                'gross_microUSD':balance['amount']*10000,'fee_microUSD':balance['fee']*10000,
                'net_microUSD':balance['net']*10000,'available_on':balance.get('available_on'),
                'contract_sha256':digest(c),'future_reversal_risk':'REMAINS',
                'complete_cost_profit':None,'spendable_earned_capital':None}
    def refund(self,payment_intent,amount_cents,request_id):
        if type(amount_cents) is not int or amount_cents<=0:raise ValueError('EXACT_REFUND_AMOUNT_REQUIRED')
        if not isinstance(payment_intent,str) or not payment_intent.startswith('pi_') or not payment_intent.replace('_','').isalnum():raise ValueError('PAYMENT_INTENT_IDENTIFIER_REQUIRED')
        return self._api('POST','/v1/refunds',{'payment_intent':payment_intent,'amount':amount_cents},'refund-'+digest({'id':request_id,'payment_intent':payment_intent,'amount':amount_cents}))
