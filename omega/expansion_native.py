"""Native compatibility commerce bridge; one account, content-addressed orders.

This is an optional adapter, not a second ledger. A fixed source-bound request
factory admits fresh immutable order requests as paid reach finds buyers. There
is no catalogue-size or customer-count ceiling. Only actual native actions earn
revenue. The supplied market remains a conditional authored simulation.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from collections.abc import Mapping
from commercial.ledger import canonical, digest, strict_json, read_bound
from commercial.persistence import atomic_bytes

SCHEMA = 'omega/expansion-native/v1'
CENT = 10_000
SOURCE_PATHS = ('omega/expansion_native.py', 'omega/compatibility.py', 'omega/expansion_market.py', 'omega/expansion_audit.py', 'connected_enterprise/channels.py')
ORDER_KEYS = {'id','buyer','budget_cents','price_cents','hour','choice','acquired','pay','accept','delivery_ok','collection_delay_hours'}


def default_config():
    return {'currency':'USD','opening_cents':10_000_000,'engineering_fixture':False,'cost_batching':True,
            'unit_costs_cents':{'compute':20,'verification':20,'hosting':10,'security':10,
                                'self_service':20,'retry_envelope':20},
            'payment_bps':290,'payment_fixed_cents':30,'claim_hours':720,
            'residual_bps':100,'income_tax_bps':2500,'operating_hours':8760}


def validate_config(raw):
    c=copy.deepcopy(raw)
    if not isinstance(c,dict) or set(c)!=set(default_config()) or c['currency']!='USD':
        raise ValueError('EXACT_USD_NATIVE_CONFIGURATION_REQUIRED')
    if type(c['cost_batching']) is not bool or type(c['engineering_fixture']) is not bool or not isinstance(c['unit_costs_cents'],dict) or not c['unit_costs_cents']:
        raise ValueError('EXPLICIT_COST_AND_FIXTURE_SCOPE_REQUIRED')
    for key in ('opening_cents','payment_bps','payment_fixed_cents','claim_hours','residual_bps','income_tax_bps','operating_hours'):
        if type(c[key]) is not int or c[key]<0:raise ValueError('NONNEGATIVE_INTEGER_NATIVE_CONFIGURATION_REQUIRED')
    if any(c[k]>10000 for k in ('payment_bps','residual_bps','income_tax_bps')) or c['claim_hours']<1 or c['operating_hours']<1:
        raise ValueError('VALID_PROBABILITY_AND_HORIZON_REQUIRED')
    if c['opening_cents']!=10_000_000 and not c['engineering_fixture']:
        raise ValueError('PRIMARY_REQUIRES_EXACTLY_100000_USD')
    if any(not isinstance(k,str) or not re.fullmatch(r'[a-z_]{1,40}',k) or type(v)is not int or v<0 for k,v in c['unit_costs_cents'].items()):
        raise ValueError('ITEMIZED_COSTS_REQUIRED')
    return c


def _write(path,value,immutable=False):
    path=Path(path);raw=canonical(value)+b'\n'
    if immutable and path.exists():
        if path.read_bytes()!=raw:raise ValueError('IMMUTABLE_EXPANSION_BYTES_CHANGED')
        return
    atomic_bytes(path,raw)


def _hashes(root):
    result={}
    for name in SOURCE_PATHS:
        p=Path(root)/name
        if not p.is_file() or p.is_symlink():raise ValueError('EXPANSION_SOURCE_REQUIRED:'+name)
        result[name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def validate_order(raw):
    if not isinstance(raw,dict) or set(raw)!=ORDER_KEYS:raise ValueError('EXACT_ENVIRONMENT_ORDER_REQUIRED')
    r=copy.deepcopy(raw)
    for key in ('id','buyer'):
        if not isinstance(r[key],str) or not re.fullmatch(r'[A-Za-z0-9_:-]{1,72}',r[key]):raise ValueError('SAFE_ORDER_ID_REQUIRED')
    for key in ('budget_cents','price_cents','hour','collection_delay_hours'):
        if type(r[key])is not int or r[key]<0:raise ValueError('EXPLICIT_BUYER_BUDGET_AND_TIMING_REQUIRED')
    for key in ('choice','acquired','pay','accept','delivery_ok'):
        if type(r[key])is not bool:raise ValueError('EXPLICIT_ORDER_DECISIONS_REQUIRED')
    if r['price_cents']<1:raise ValueError('POSITIVE_PRICE_REQUIRED')
    return r


def _request(root,job_id):
    if not isinstance(job_id,str) or not re.fullmatch(r'[0-9a-f]{64}',job_id):raise ValueError('CONTENT_ADDRESSED_ORDER_REQUIRED')
    return validate_order(read_bound(root,'expansion-requests/'+job_id+'.json',job_id))


class RequestCatalog(Mapping):
    """Source-bound lazy request factory, not a preallocated customer population."""
    def __init__(self,root,manifest):self.root=Path(root);self.manifest=copy.deepcopy(manifest)
    def __getitem__(self,key):
        r=_request(self.root,key)
        job={'id':key,'artifact_sha256':digest({'request':key,'contract':self.manifest['contract']}),
             'receipt_sha256':digest({'request':key,'checker':self.manifest['source_hashes']})}
        return {'job':job,'artifact':{'unproduced_request':key},'receipt':{'accepted':False}}
    def __contains__(self,key):
        try:self[key];return True
        except (ValueError,OSError):return False
    def __iter__(self):return iter(())
    def __len__(self):return 0
    def __eq__(self,other):return isinstance(other,RequestCatalog) and self.root==other.root and self.manifest==other.manifest


def load_contracts(root,manifest):
    if not isinstance(manifest,dict) or set(manifest)!={'schema','account_namespace','native_engine','config','contract','source_hashes','rights_scope'}:
        raise ValueError('EXACT_EXPANSION_MANIFEST_REQUIRED')
    if manifest['schema']!=SCHEMA or manifest['native_engine']!='exact-prospective-v2' or manifest['account_namespace']!='adaptive012':
        raise ValueError('EXPLICIT_EXPANSION_NATIVE_ENGINE_REQUIRED')
    if manifest['rights_scope']!='HYPOTHETICAL_DISTRIBUTION_RIGHTS_NOT_LICENSE_GRANT':raise ValueError('EXPLICIT_HYPOTHETICAL_RIGHTS_REQUIRED')
    validate_config(manifest['config'])
    if manifest['source_hashes']!=_hashes(root) or manifest['source_hashes']!=_hashes(Path(__file__).resolve().parents[1]):raise ValueError('EXPANSION_SOURCE_CHANGED')
    return RequestCatalog(root,manifest)


def _files(path):
    files={}
    for p in sorted(Path(path).rglob('*')):
        if '__pycache__' in p.parts:continue
        if p.is_symlink():raise ValueError('PACKAGE_SYMLINK_REFUSED')
        if p.is_file():files[str(p.relative_to(path))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return files


def delivery(root,manifest,job_id):
    _request(root,job_id)
    p=Path(root)/'expansion-deliveries'/(job_id+'.json')
    if p.is_symlink():raise ValueError('DELIVERY_SYMLINK_REFUSED')
    return strict_json(p.read_bytes())


_ACCEPTED_PACKAGES={}

def _package_snapshot(root,manifest):
    from omega.compatibility import accept_product
    files=_files(Path(root)/'expansion-package')
    cache_key=digest({'files':files,'contract':manifest['contract'],'sources':manifest['source_hashes']})
    if cache_key not in _ACCEPTED_PACKAGES:
        _ACCEPTED_PACKAGES[cache_key]=accept_product(Path(root)/'expansion-package',manifest['contract'])['accepted']
    return files,_ACCEPTED_PACKAGES[cache_key]


def _check_bound_delivery(root,manifest,job_id,artifact,jobs,package):
    r=_request(root,job_id);files,independently_accepted=package
    expected={'schema':'omega/compatibility-delivery/v1','request_sha256':job_id,
              'package':'expansion-package','contract':manifest['contract'],'files':files}
    accepted=(artifact==expected and artifact==delivery(root,manifest,job_id)
              and independently_accepted and r['choice'] and r['acquired'] and r['pay'] and r['accept']
              and r['delivery_ok'] and r['budget_cents']>=r['price_cents'])
    return {'accepted':bool(accepted),'decisive':True,'scope':'SIMULATED','authority':jobs[job_id]['job']['receipt_sha256']}


def check_delivery(root,manifest,job_id,artifact):
    # Fresh source and package bytes precede any cached semantic result.
    return _check_bound_delivery(root,manifest,job_id,artifact,load_contracts(root,manifest),_package_snapshot(root,manifest))


def _cost_rows(request,config):
    rows=dict(config['unit_costs_cents'])
    rows['payment_processing']=((request['price_cents']*config['payment_bps']+9999)//10000+config['payment_fixed_cents'])
    return dict(sorted(rows.items()))


def _invoice_rows(request,config):
    rows=_cost_rows(request,config)
    return {'fulfillment_invoice':sum(rows.values())} if config['cost_batching'] else rows


def _terms(manifest,request):
    from commercial.terms_exact_v2 import prospective_terms
    cfg=manifest['config'];price=request['price_cents']*CENT;hour=request['hour']
    return prospective_terms(request['id'],price,hour+request['collection_delay_hours']+cfg['claim_hours'],hour+request['collection_delay_hours'],
        residual=price*cfg['residual_bps']//10000,
        counterparty_obligations='Hypothetical USD software edition; declared self-service resources prepaid; no personal support or continuing updates; valid claims remain obligations.')


def require_costs(root,manifest,actions,order):
    job_id=json.loads(order['task'])['job_id'];r=_request(root,job_id)
    if order['id']!=r['id'] or order['buyer']!=r['buyer'] or int(order['price'])!=r['price_cents']*CENT:
        raise ValueError('ORDER_REQUEST_BINDING_CHANGED')
    paid={a['args']['id']:a['args']['amount'] for a in actions if a['op']=='cost' and a['after']['expensePaid']-a['before']['expensePaid']==a['args']['amount']}
    if any(paid.get('exp-order:'+r['id']+':'+k)!=v*CENT for k,v in _invoice_rows(r,manifest['config']).items()):
        raise ValueError('COMPLETE_ACTION_COSTS_REQUIRED')
    offers=[a for a in actions if a['op']=='offer' and a['args']['id']==r['id']]
    wallets=[a for a in actions if a['op']=='wallet' and a['args']['buyer']==r['buyer']]
    terms=[a['args']['terms'] for a in actions if a['op']=='register_terms' and a['args']['id']==r['id']+':terms']
    if len(offers)!=1 or offers[0]['day']!=r['hour'] or wallets!=[next((a for a in wallets if a['args']['amount']==r['budget_cents']*CENT),None)] or terms!=[_terms(manifest,r)]:
        raise ValueError('EXPLICIT_BUDGET_AND_PRECOMMITTED_TERMS_REQUIRED')
    if not (r['choice'] and r['acquired'] and r['pay'] and r['accept'] and r['delivery_ok'] and r['budget_cents']>=r['price_cents']):
        raise ValueError('VOLUNTARY_ACCEPTED_FUNDED_ORDER_REQUIRED')


def rebind_prepared(root,manifest,actions,jobs):
    # One fresh package read per audit, then every individual request/output is
    # rebound. No observation, financial action or buyer is aggregated away.
    package=None
    offers={a['args']['id']:a['args']['job_id'] for a in actions if a['op']=='offer'}
    for a in actions:
        if a['op']=='event' and a['args']['action']=='prepare':
            if package is None:package=_package_snapshot(root,manifest)
            jid=offers[a['args']['id']];artifact=delivery(root,manifest,jid)
            if digest(artifact)!=a['args']['artifact_sha256'] or not _check_bound_delivery(root,manifest,jid,artifact,jobs,package)['accepted']:
                raise ValueError('PREPARED_COMPATIBILITY_BYTES_CHANGED')


class NativeBridge:
    """Sequential financial admission and recoverable individual transactions."""
    def __init__(self,output,*,root=None,config=None,resume=False,interrupt_after=None):
        from connected_enterprise.finance import JournalAccount,source_paths_for_manifest
        from experiments.commerce006 import PINS
        from omega.compatibility import package_contract
        self.output=Path(output).resolve();self.root=Path(root or Path(__file__).resolve().parents[1]).resolve()
        self.source=self.output/'source';self.interrupt_after=interrupt_after
        cfg=validate_config(config or default_config())
        if not resume:
            self.output.mkdir(parents=True,exist_ok=False)
            for name in sorted(set(source_paths_for_manifest({'schema':SCHEMA}))|set(PINS)):
                destination=self.source/name;destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(self.root/name,destination)
            self.manifest={'schema':SCHEMA,'account_namespace':'adaptive012','native_engine':'exact-prospective-v2',
                           'config':cfg,'contract':package_contract(),'source_hashes':_hashes(self.source),
                           'rights_scope':'HYPOTHETICAL_DISTRIBUTION_RIGHTS_NOT_LICENSE_GRANT'}
            _write(self.output/'manifest.json',self.manifest,True)
        else:
            self.manifest=strict_json((self.output/'manifest.json').read_bytes())
            if config is not None and cfg!=self.manifest['config']:raise ValueError('RESUME_CONFIGURATION_CHANGED')
            cfg=self.manifest['config']
            for suffix in ('.actions.jsonl','.adaptive-account.json','.connected-journal.json','.adaptive-simulation-key'):
                if not (self.output/('account.sqlite'+suffix)).is_file():raise ValueError('EXISTING_AUTHORITY_REQUIRED')
        self.config=cfg
        self.account=JournalAccount(self.source,self.manifest,self.output/'account.sqlite',opening=cfg['opening_cents']*CENT,working=0,
                                    contract='omega-expandable:'+digest(self.manifest))
        if resume:
            self.state=self.account.verify_checkpoint(strict_json((self.output/'STATE.json').read_bytes()))
        else:
            self.state={'schema':'omega/expansion-operator/v1','hour':0,'active':None,'pending':[],
                        'orders':{},'spends':{},'tax_accrued':0,'tax_intent':None,'complete':False}
            self._save()
        if self.state['active'] is not None:self._continue_delivery()
        if self.state['tax_intent'] is not None:self._tax(self.state['tax_intent']['hour'])

    def _save(self):_write(self.output/'STATE.json',self.account.seal_checkpoint(self.state))
    def close(self):self.account.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
    def snapshot(self):
        snap=self.account.snapshot();s=snap['summary']
        return {**{k+'_cents':s[n]//CENT for k,n in [('available','available'),('cash','cash'),('profit','profit'),('unrestricted_earned','unrestrictedEarned'),('payables','payables'),('tail_reserve','tailReserve')]},'hour':self.state['hour'],'native_actions_count':snap['sequence'],'native_actions_sha256':snap['actions_sha256']}
    def _native(self,op,args,hour):return self.account.execute(op,args,hour)
    def _event(self,r,action,hour=None,**extra):
        return self._native('event',{'id':r['id'],'action':action,'event_id':r['id']+':'+action,**extra},r['hour'] if hour is None else hour)
    def _tax(self,hour,trigger=None):
        if self.state['tax_intent'] is None:
            pretax=self.account.snapshot()['summary']['profit']+self.state['tax_accrued']
            amount=max(0,max(0,pretax)*self.config['income_tax_bps']//10000-self.state['tax_accrued'])
            if not amount:return
            self.state['tax_intent']={'id':'exp-tax:'+str(trigger or (str(hour)+':'+str(self.account.snapshot()['sequence']))),'amount':amount,'hour':hour}
            self._save()
        t=self.state['tax_intent'];self.account.cost(t['id'],t['amount'],t['hour'])
        if self.interrupt_after=='tax':os._exit(75)
        self.state['tax_accrued']+=t['amount'];self.state['tax_intent']=None;self._save()
    def advance(self,hour):
        if type(hour)is not int or hour<self.state['hour']:raise ValueError('NONDECREASING_OPERATING_CLOCK_REQUIRED')
        while self.state['pending'] and self.state['pending'][0]['due']<=hour:
            p=self.state['pending'][0];r=p['order'];self.account.advance_financial(p['due'])
            tax_before=self.state['tax_accrued']
            self._event(r,'release',p['due']);self._tax(p['due'],r['id'])
            self.state['orders'][r['id']]['status']='released';self.state['orders'][r['id']]['collected_cents']=r['price_cents']
            self.state['orders'][r['id']]['collected']=True
            self.state['orders'][r['id']]['contribution_cents']=self._contribution(r,True)
            self.state['pending'].pop(0);self._save()
        self.account.advance_financial(hour);self.state['hour']=hour;self._save()
        return self.snapshot()
    def spend(self,event_id,cents,hour,category,expected_net_cents=1,allow_seed=True):
        if not isinstance(event_id,str) or not re.fullmatch(r'[A-Za-z0-9_:-]{1,100}',event_id) or type(cents)is not int or cents<0:
            raise ValueError('EXPLICIT_RESOURCE_QUOTE_REQUIRED')
        prior=self.state['spends'].get(event_id)
        request={'amount_cents':cents,'hour':hour,'category':category,'expected_net_cents':expected_net_cents,'allow_seed':allow_seed}
        if prior:
            if prior['request']!=request:raise ValueError('SPEND_IDENTITY_CHANGED')
            return prior['funded']
        self.advance(hour)
        receipt=self.account.spend(event_id,category,cents*CENT,hour,{'resource':category,'quote_cents':cents},expected_net_cents*CENT,allow_seed=allow_seed)
        funded=receipt is not None or cents==0
        self.state['spends'][event_id]={'request':request,'funded':funded,'receipt':receipt};self._save()
        return funded
    def _contribution(self,r,collected):
        actions=self.account.export()['ledger']['actions']
        paid=sum(a['args']['amount'] for a in actions if a['op']=='cost' and (a['args']['id'].startswith('exp-order:'+r['id']+':') or a['args']['id']=='exp-tax:'+r['id']))
        return ((r['price_cents']*CENT if collected else 0)-paid)//CENT
    def order_receipt(self,order_id):
        return copy.deepcopy(self.state['orders'][order_id])
    def deliver(self,order):
        r=validate_order(order)
        if r['id'] in self.state['orders']:
            previous=self.state['orders'][r['id']]
            if previous['request']!=r:raise ValueError('ORDER_IDENTITY_CHANGED')
            return copy.deepcopy(previous)
        self.advance(r['hour'])
        status=None
        if not r['choice'] or not r['acquired'] or r['budget_cents']<r['price_cents']:status='declined'
        # Protect a single order and its costs; later buyers see the new cash.
        required=(r['price_cents']+sum(_cost_rows(r,self.config).values())+20)*CENT
        if status is None and self.account.snapshot()['summary']['available']<required:status='liquidity_deferred'
        if status:
            result={'request':r,'status':status,'collected_cents':0,'collected':False,'contribution_cents':0};self.state['orders'][r['id']]=result;self._save();return copy.deepcopy(result)
        jid=hashlib.sha256(canonical(r)+b'\n').hexdigest();_write(self.source/'expansion-requests'/(jid+'.json'),r,True)
        self.state['active']={'request':r,'job_id':jid,'step':0};self._save()
        self._continue_delivery()
        return copy.deepcopy(self.state['orders'][r['id']])
    def _continue_delivery(self):
        from omega.compatibility import build_product,accept_product
        a=self.state['active'];r=a['request'];jid=a['job_id'];hour=r['hour']
        commands=[('register_terms',{'id':r['id']+':terms','terms':_terms(self.manifest,r)}),
                  ('wallet',{'buyer':r['buyer'],'amount':r['budget_cents']*CENT}),
                  ('offer',{'id':r['id'],'buyer':r['buyer'],'price':r['price_cents']*CENT,'job_id':jid,
                            'deadline':hour+r['collection_delay_hours']+min(24,self.config['claim_hours']-1),'terms_id':r['id']+':terms'}),
                  ('event',{'id':r['id'],'action':'consent','event_id':r['id']+':consent'})]
        if r['pay']:commands += [('event',{'id':r['id'],'action':'fund','event_id':r['id']+':fund'})]
        else:commands += [('event',{'id':r['id'],'action':'cancel','event_id':r['id']+':cancel'})]
        if r['pay']:
            commands += [('cost',{'id':'exp-order:'+r['id']+':'+k,'amount':v*CENT}) for k,v in _invoice_rows(r,self.config).items()]
        while a['step']<len(commands):
            op,args=commands[a['step']];self._native(op,args,hour)
            if self.interrupt_after=='fund' and op=='event' and args['action']=='fund':os._exit(75)
            a['step']+=1;self._save()
        status='nonpayment' if not r['pay'] else None
        tax_before=self.state['tax_accrued']
        if r['pay']:
            package=self.source/'expansion-package'
            if not package.exists() or not accept_product(package,self.manifest['contract']).get('accepted',False):
                build_product(package,self.manifest['contract'])
            artifact={'schema':'omega/compatibility-delivery/v1','request_sha256':jid,'package':'expansion-package',
                      'contract':self.manifest['contract'],'files':_files(package)}
            _write(self.source/'expansion-deliveries'/(jid+'.json'),artifact,True)
            accepted=check_delivery(self.source,self.manifest,jid,artifact)['accepted']
            if not accepted:self._event(r,'refund');status='refunded'
            else:
                self._event(r,'prepare',artifact_sha256=digest(artifact))
                if r['collection_delay_hours']:
                    due=hour+r['collection_delay_hours']
                    if not any(p['order']['id']==r['id'] for p in self.state['pending']):
                        self.state['pending'].append({'order':r,'due':due});self.state['pending'].sort(key=lambda p:(p['due'],p['order']['id']))
                    status='accepted_uncollected'
                else:self._event(r,'release');self._tax(hour,r['id']);status='released'
        self.state['orders'][r['id']]={'request':r,'status':status,'collected_cents':r['price_cents'] if status=='released' else 0,
            'collected':status=='released','contribution_cents':self._contribution(r,status=='released'),'job_id':jid}
        self.state['active']=None;self._save()
    def finish(self,*,settle=True):
        horizon=self.config['operating_hours']
        if not self.state['complete']:
            self.advance(horizon-1);self.account.cost('exp-operating-complete',0,horizon-1)
            self.state['complete']=True;self._save()
        if settle:
            end=max([horizon]+[p['due'] for p in self.state['pending']]+[r['request']['hour']+r['request']['collection_delay_hours']+self.config['claim_hours']+1 for r in self.state['orders'].values()])
            self.advance(end)
        return self.report()
    def report(self):
        from connected_enterprise.finance import audit_journal
        from connected_enterprise.scale import trailing_profit
        record=self.account.export();audit=audit_journal(record,root=self.source,manifest=self.manifest)
        year=trailing_profit(record['ledger'],operating_end_hour=self.config['operating_hours'],operating_complete=self.state['complete'])
        summary=record['ledger']['summary'];taxactions=[a for a in record['ledger']['actions'] if a['op']=='cost' and a['args']['id'].startswith('exp-tax:')]
        result={'schema':'omega/expansion-native-result/v1','scope':'NATIVE_CONDITIONAL_SIMULATION','accepted':audit['accepted'],
                'summary':summary,'rolling_year':year,'native_actions_sha256':record['ledger']['actions_sha256'],
                'source_sha256':self.account.source['sha256'],'orders':copy.deepcopy(self.state['orders']),
                'spends':copy.deepcopy(self.state['spends']),'pending_collections':len(self.state['pending']),
                'tax':{'policy':'Registered income-tax rate on positive cumulative modeled profit. Expense and payment occur together when liquid; any unpaid expense remains a native payable. No delayed tax-reserve API.',
                       'incurred_microUSD':sum(a['args']['amount'] for a in taxactions),
                       'paid_microUSD':sum(a['after']['expensePaid']-a['before']['expensePaid'] for a in taxactions),
                       'reserve_microUSD':0},
                'audit_scope':'Native financial conservation, obligations and actual package acceptance; paid exposure and voluntary economic choice require separate market replay.',
                'actual_complete_cost_profit':None,'model_calls':0,'founder_service_minutes':0}
        _write(self.output/'PUBLIC_ACCOUNT.json',record);_write(self.output/'RESULT.json',result)
        return result


def audit_output(output):
    from connected_enterprise.finance import audit_journal
    p=Path(output);m=strict_json((p/'manifest.json').read_bytes());r=strict_json((p/'PUBLIC_ACCOUNT.json').read_bytes())
    return audit_journal(r,root=p/'source',manifest=m)


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--audit',action='store_true');p.add_argument('--resume',action='store_true');p.add_argument('--interrupt-after',choices=['fund','tax']);p.add_argument('--order-json');args=p.parse_args()
    if args.audit:result=audit_output(args.output)
    else:
        with NativeBridge(args.output,resume=args.resume,interrupt_after=args.interrupt_after) as bridge:
            if args.order_json:bridge.deliver(strict_json(Path(args.order_json).read_bytes()))
            result=bridge.finish()
    print(json.dumps({'accepted':result['accepted'],'native_actions_sha256':result.get('native_actions_sha256')},sort_keys=True))

if __name__=='__main__':main()
