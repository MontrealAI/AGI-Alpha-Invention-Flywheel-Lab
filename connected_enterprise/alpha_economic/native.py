"""The only money authority is the repository's JournalAccount / adaptive Account.

This adapter never upgrades simulated balances into real money. Live settlement
observations must use the external gateway, not this deliberately simulated rail.
"""
from __future__ import annotations
from pathlib import Path
import shutil
from connected_enterprise.finance import JournalAccount, source_paths_for_manifest, audit_journal
from commercial.terms_exact_v2 import prospective_terms
from . import service
from .core import read, save, safe, digest, contract, identifier


class NativeTreasury:
    scope='SIMULATED'
    def __init__(self,state,*,opening,working=0):
        self.state=safe(state); self.root=self.state/'source'
        self.manifest_path=self.state/'native-manifest.json'
        if not self.manifest_path.exists():
            if (self.state/'account').exists(): raise ValueError('MISSING_MANIFEST_CANNOT_RESEED_ACCOUNT')
            self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
            src=Path(__file__).resolve().parents[2]
            for name in source_paths_for_manifest({'schema':service.SCHEMA}):
                target=self.root/name; target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(src/name,target)
            save(self.manifest_path,service.prepare_manifest(self.root))
        self.manifest=read(self.manifest_path)
        service.validate_manifest(self.root,self.manifest)
        self.account=JournalAccount(self.root,self.manifest,self.state/'account',opening=opening,
                                    working=working,contract='alpha-economic-engine-v1')

    def admit(self,c): return service.admit(self.root,self.manifest,c)
    def snapshot(self): return self.account.snapshot()['summary']
    def audit(self): return self.account.audit()
    def export(self): return self.account.export()
    def close(self): self.account.close()
    def advance(self,day): return self.account.advance_financial(day)

    def cost(self,key,amount,day): return self.account.cost(key,amount,day)

    def spend(self,key,amount,day,work,expected_net,allow_seed):
        return self.account.spend(key,'alpha-economic-production',amount,day,work,expected_net,allow_seed=allow_seed)

    def begin(self,c,day):
        c=contract(c); job=self.admit(c); order='o-'+job[2:]; buyer='b-'+job[2:]
        # This provisions only an explicit synthetic counterparty in the simulation.
        actions=self.account.export()['ledger']['actions']
        old=[r for r in actions if r['op']=='wallet' and r['args']['buyer']==buyer]
        if old and (len(old)!=1 or old[0]['args']['amount']!=c['buyer_budget_microUSD']):
            raise ValueError('BUYER_PROVISION_CHANGED')
        if not old: self.account.execute('wallet',{'buyer':buyer,'amount':c['buyer_budget_microUSD']},day)
        maturity=day+c['claim_window_hours']+2
        terms=prospective_terms(order,c['price_microUSD'],maturity,day+1,
                               residual=c['residual_microUSD'],fee=0)
        self.account.execute('register_terms',{'id':order+'-terms','terms':terms},day)
        self.account.execute('offer',{'id':order,'buyer':buyer,'price':c['price_microUSD'],
                                     'job_id':job,'deadline':maturity-1,'terms_id':order+'-terms'},day)
        for action in ('consent','fund'):
            self.account.execute('event',{'id':order,'action':action,'event_id':order+'-'+action},day)
        return {'order':order,'job':job,'maturity':maturity,'scope':self.scope}

    def prepare(self,c,artifact,day):
        job=identifier(c); result=service.write_delivery(self.root,self.manifest,job,artifact)
        if not result['accepted']: raise ValueError('INDEPENDENT_ACCEPTANCE_FAILED')
        order='o-'+job[2:]
        self.account.execute('event',{'id':order,'action':'prepare','event_id':order+'-prepare',
                                     'artifact_sha256':digest(artifact)},day)
        return result

    def release(self,c,day):
        order='o-'+identifier(c)[2:]
        self.account.execute('event',{'id':order,'action':'release','event_id':order+'-release'},day)
        return {'order':order,'scope':self.scope,'summary':self.snapshot()}

    def refund(self,c,day):
        order='o-'+identifier(c)[2:]
        return self.account.execute('event',{'id':order,'action':'refund','event_id':order+'-refund'},day)

    def claim(self,c,event_id,amount,day):
        return self.account.execute('claim',{'id':'o-'+identifier(c)[2:], 'claim_id':event_id,
                                            'amount':amount,'kind':'ordinary'},day)

    def reinvest(self,c,artifact,day):
        amount=c['reinvestment_microUSD']; benefit=c['reuse_benefit_microUSD']
        if not amount or benefit<=amount: return {'funding':'NONE','reason':'HOLD_CASH_DOMINATES_DECLARED_PLAN'}
        receipt=self.account.spend('retain-'+identifier(c),'retained_instrument',amount,day,
                                   {'artifact_sha256':digest(artifact),'scope_key':c['scope_key']},
                                   benefit-amount,allow_seed=False)
        if receipt is None: return {'funding':'NONE','reason':'INSUFFICIENT_UNRESTRICTED_EARNINGS'}
        if receipt['funding']!='EARNED': raise ValueError('REINVESTMENT_NOT_EARNED_FUNDED')
        return receipt


def replay(state):
    state=Path(state)
    return audit_journal(read(state/'native-export.json'),root=state/'source',manifest=read(state/'native-manifest.json'))
