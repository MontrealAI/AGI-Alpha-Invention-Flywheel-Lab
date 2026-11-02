"""Canonical native account adapter; no independent cash ledger."""
from connected_enterprise.finance import JournalAccount,audit_journal
from commercial.terms_exact_v2 import prospective_terms
from commercial.ledger import digest,canonical
from commercial.persistence import atomic_bytes
from .service import safe,load_contracts
from .service import write_delivery,validate_prepared_order,read_decision

MICRO=1_000_000

class Native:
    def __init__(self,root,manifest,path,opening):
        self.root,self.manifest=root,manifest
        self.book=JournalAccount(root,manifest,path,opening=opening,working=0,contract='growth067-bulk-sim')
    def summary(self):return self.book.snapshot()['summary']
    def spend(self,ident,amount,hour,work,expected,seed=False):
        if not amount:return None
        return self.book.spend(ident,'reconciliation_bulk_resource',amount,hour,work,expected,allow_seed=seed)
    def cost(self,ident,amount,hour):
        if amount:self.book.cost(ident,amount,hour)
    def advance(self,hour):return self.book.advance_financial(hour)
    def offer(self,ident,job,quantity,unit_price,hour,collection,maturity,residual_per_unit=0):
        price=quantity*unit_price
        # One modeled wholesale purchaser, explicitly not n individual buyer receipts.
        terms=prospective_terms(ident,price,maturity,collection,exposure=quantity*(unit_price+200_000),residual=quantity*residual_per_unit,fee=0,counterparty_obligations='SIM bulk model only; accepted actual template plus declared homogeneous modeled quantity. No individually rendered output or secured customer. All claims retained through explicit maturity.')
        b=self.book;b.execute('wallet',{'buyer':ident,'amount':price},hour)
        b.execute('register_terms',{'id':ident+'-terms','terms':terms},hour)
        extra={} if self.manifest['configuration']['mode']=='TECHNICAL_UNIT_TEST' else {'decision_sha256':digest(read_decision(self.root,self.manifest,job))}
        b.execute('offer',{'id':ident,'buyer':ident,'price':price,'job_id':job,'deadline':collection+24,'terms_id':ident+'-terms',**extra},hour)
        for action in ['consent','fund']:b.execute('event',{'id':ident,'action':action,'event_id':ident+'-'+action},hour)
    def prepare(self,ident,job,artifact,hour):
        rows=[a for a in self.book.export()['ledger']['actions'] if a['op']=='offer' and a['args']['id']==ident]
        if len(rows)!=1:raise ValueError('UNIQUE_FUNDED_BULK_ORDER_REQUIRED')
        validate_prepared_order(self.root,self.manifest,job,artifact,rows[0]['args']['price'])
        write_delivery(self.root,self.manifest,job,artifact)
        self.book.execute('event',{'id':ident,'action':'prepare','event_id':ident+'-prepare','artifact_sha256':digest(artifact)},hour)
    def release(self,ident,hour):return self.book.execute('event',{'id':ident,'action':'release','event_id':ident+'-release'},hour)
    def refund(self,ident,hour):return self.book.execute('event',{'id':ident,'action':'refund','event_id':ident+'-refund'},hour)
    def export(self):return self.book.export()
    def audit(self):return self.book.audit()
    def close(self):self.book.close()
