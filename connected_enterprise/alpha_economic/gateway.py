"""Client for an operator-provided authoritative treasury, NOT a new money ledger.

This protocol needs an independently configured accounting/treasury implementation.
No compatible real gateway is bundled or claimed deployed. A provider notification
alone cannot replace its reconciled accounts and protected-liability decisions.
"""
from __future__ import annotations
import time
import uuid
from urllib.parse import urlsplit
from .core import authenticate,canonical,digest,identifier,sign
from .network import request


class TreasuryGateway:
    scope='EXTERNAL_AUTHORITATIVE_TREASURY'
    def __init__(self,url,request_key,response_key,account,*,enabled=False,mode='live',sender=request,clock=time.time):
        u=urlsplit(url)
        if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('HTTPS_TREASURY_GATEWAY_REQUIRED')
        if mode not in ('test','live'):raise ValueError('EXPLICIT_GATEWAY_MODE_REQUIRED')
        self.url,self.host,self.request_key,self.response_key=url.rstrip('/'),u.hostname,request_key,response_key
        self.account,self.enabled,self.mode,self.sender,self.clock=account,enabled,mode,sender,clock
        self.last_snapshot=None
    def command(self,op,payload,key=None):
        if not self.enabled:raise PermissionError('AUTHORITATIVE_TREASURY_NOT_AUTHORIZED')
        # Read requests have fresh nonces; effect keys remain stable across retries.
        key=key or 'read-'+uuid.uuid4().hex
        body={'kind':'treasury-command','account':self.account,'mode':self.mode,'operation':op,
              'payload':payload,'idempotency_key':key,'expires_at':int(self.clock())+120}
        raw=self.sender('POST',self.url+'/v1/commands',{'Content-Type':'application/json','Idempotency-Key':key},canonical(sign(body,self.request_key)),hosts=(self.host,))
        receipt=authenticate(raw,self.response_key,kind='treasury-receipt',now=int(self.clock()))
        if (receipt.get('request_sha256')!=digest(body) or receipt.get('account')!=self.account
            or receipt.get('mode')!=self.mode or receipt.get('idempotency_key')!=key):
            raise ValueError('TREASURY_RECEIPT_NOT_BOUND_TO_COMMAND')
        if receipt.get('authorized') is not True:raise PermissionError('TREASURY_REFUSED_ACTION')
        result=receipt.get('result')
        if not isinstance(result,dict):raise ValueError('TREASURY_RESULT_REQUIRED')
        return result
    def snapshot(self):
        result=self.command('snapshot',{})
        keys={'cash','available','unrestrictedEarned','payables','custodyReserve','tailReserve','workingCapital','reservedInvestment'}
        if any(type(result.get(k)) is not int or result[k]<0 for k in keys):raise ValueError('EXACT_TREASURY_BALANCES_REQUIRED')
        if result['available']>result['cash'] or result['unrestrictedEarned']>result['available']:
            raise ValueError('TREASURY_CASH_AND_EARNINGS_INVARIANT_FAILED')
        if result['cash']<sum(result[k] for k in ('payables','custodyReserve','tailReserve','workingCapital','reservedInvestment')):
            raise ValueError('TREASURY_OBLIGATIONS_NOT_COVERED')
        if result.get('costs_reconciled') is not True:raise ValueError('ACTUAL_COSTS_NOT_RECONCILED')
        self.last_snapshot=result
        return result
    def cost(self,key,amount,day):
        return self.command('reconcile-cost',{'amount_microUSD':amount,'time_hour':day},key)
    def spend(self,key,amount,day,work,expected_net,allow_seed):
        # Gateway must atomically reserve/pay; a local balance snapshot is never a reservation.
        result=self.command('prepay-resource',{'amount_microUSD':amount,'time_hour':day,'work':work,
                            'expected_net_hypothesis_microUSD':expected_net,'allow_seed':allow_seed},key)
        if result.get('declined'):return None
        if result.get('funding') not in ('EARNED','SEED') or (not allow_seed and result.get('funding')!='EARNED') or result.get('amount_microUSD')!=amount or result.get('obligations_covered') is not True or not result.get('external_transaction_id'):
            raise ValueError('ATOMIC_EXTERNAL_PREPAYMENT_EVIDENCE_REQUIRED')
        return result
    def begin(self,c,day,consent,payment):
        if payment.get('scope')!='STRIPE_'+self.mode.upper():raise ValueError('PAYMENT_AND_TREASURY_MODE_MISMATCH')
        result=self.command('begin-funded-contract',{'contract':c,'buyer_consent':consent,'provider_observation':payment,'time_hour':day},'begin-'+identifier(c))
        if result.get('contract_sha256')!=digest(c) or type(result.get('maturity')) is not int or result['maturity']<=day:
            raise ValueError('FUNDED_CONTRACT_AND_REAL_TIME_BOUNDARY_REQUIRED')
        return result
    def prepare(self,c,artifact,day):
        from .checker import verify
        checked=verify(c,artifact)
        if not checked['accepted']:raise ValueError('INDEPENDENT_ACCEPTANCE_FAILED')
        return self.command('prepare-delivery',{'contract_sha256':digest(c),'artifact_sha256':digest(artifact),'verification':checked,'time_hour':day},'prepare-'+identifier(c))
    def release(self,c,day,acceptance,payment):
        return self.command('recognize-accepted-collection',{'contract':c,'acceptance':acceptance,'provider_observation':payment,'time_hour':day},'release-'+identifier(c))
    def refund(self,c,day,provider_refund):
        return self.command('reconcile-refund',{'contract_sha256':digest(c),'provider_refund':provider_refund,'time_hour':day},'refund-'+identifier(c))
    def reinvest(self,c,artifact,day):
        if c['reuse_benefit_microUSD']<=c['reinvestment_microUSD'] or c['reinvestment_microUSD']==0:return {'funding':'NONE','reason':'HOLD_CASH'}
        snapshot=self.snapshot()
        if snapshot['unrestrictedEarned']<c['reinvestment_microUSD']:return {'funding':'NONE','reason':'INSUFFICIENT_UNRESTRICTED_EARNINGS'}
        return self.spend('retain-'+identifier(c),c['reinvestment_microUSD'],day,{'artifact_sha256':digest(artifact),'scope':c['scope_key']},c['reuse_benefit_microUSD']-c['reinvestment_microUSD'],False) or {'funding':'NONE'}
    def advance(self,day):
        # An authenticated transport ACK is not a positive financial clearance.
        # LiveEngine.step() invokes this before new production transitions; a
        # negative or ambiguous signed business result must stop that step.
        result=self.command('reconcile-obligations',{'time_hour':day},'reconcile-hour-'+str(day))
        if result.get('obligations_covered') is not True:
            raise PermissionError('TREASURY_OBLIGATIONS_NOT_COVERED')
        if result.get('costs_reconciled') is not True:
            raise PermissionError('TREASURY_COSTS_NOT_RECONCILED')
        return result
    def audit(self):return self.command('audit',{})
    def close(self):pass
