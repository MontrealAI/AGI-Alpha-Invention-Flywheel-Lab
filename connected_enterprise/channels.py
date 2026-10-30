"""Finite, expiring simulated channel contracts; slots never constitute orders."""
from __future__ import annotations
import copy
import hashlib
import json

SCHEMA = 'agi-alpha/connected014-channel-book/v1'
MICRO = 1_000_000
REQUIRED = {'price_microUSD','slots_per_day','duration_days','lead_days','activation_reliability_bps','realization_bps','overlap_bps','support_microUSD'}
OPTIONAL = {'failure_credit_bps','max_active_tranches','contact_cooldown_days','max_contacts_per_customer','owned_audience_count','prepaid_retry_attempts','retry_delay_days'}


def _digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()).hexdigest()


def _draw(seed, day, identity, stage):
    return int.from_bytes(hashlib.sha256(json.dumps(['connected014-channel',seed,day,identity,stage],separators=(',',':')).encode()).digest()[:8],'big') % 10000


def default_contracts():
    return {
        'pilot': {'price_microUSD':6*MICRO,'slots_per_day':2,'duration_days':21,'lead_days':2,'activation_reliability_bps':9500,'realization_bps':7500,'overlap_bps':2500,'support_microUSD':250_000,'failure_credit_bps':0,'prepaid_retry_attempts':1,'retry_delay_days':1,'max_active_tranches':2,'contact_cooldown_days':7,'max_contacts_per_customer':3,'owned_audience_count':4},
        'extended': {'price_microUSD':20*MICRO,'slots_per_day':4,'duration_days':21,'lead_days':3,'activation_reliability_bps':9000,'realization_bps':6500,'overlap_bps':5000,'support_microUSD':500_000,'failure_credit_bps':0,'prepaid_retry_attempts':1,'retry_delay_days':1,'max_active_tranches':2,'contact_cooldown_days':7,'max_contacts_per_customer':3,'owned_audience_count':4},
    }


def validate_contracts(contracts):
    if not isinstance(contracts,dict) or not contracts:
        raise ValueError('NONEMPTY_CHANNEL_CONTRACTS_REQUIRED')
    result = copy.deepcopy(contracts)
    for ident, terms in result.items():
        if not isinstance(ident,str) or not ident or len(ident)>120 or not isinstance(terms,dict) or not REQUIRED <= set(terms) or set(terms)-REQUIRED-OPTIONAL:
            raise ValueError('EXACT_CHANNEL_TERMS_REQUIRED')
        for key,value in terms.items():
            if type(value) is not int or value<0 or value>10**12:
                raise ValueError('BOUNDED_INTEGER_CHANNEL_TERMS_REQUIRED')
            if key.endswith('_bps') and value>10000:
                raise ValueError('CHANNEL_BASIS_POINTS_REQUIRED')
        if not 1<=terms['slots_per_day']<=100000 or not 1<=terms['duration_days']<=3650 or terms['lead_days']>3650 or terms['price_microUSD']<1:
            raise ValueError('FINITE_PAID_CHANNEL_CAPACITY_REQUIRED')
        terms.setdefault('failure_credit_bps',0)
        terms.setdefault('max_active_tranches',2)
        terms.setdefault('contact_cooldown_days',7)
        terms.setdefault('max_contacts_per_customer',3)
        terms.setdefault('owned_audience_count',4)
        terms.setdefault('prepaid_retry_attempts',0)
        terms.setdefault('retry_delay_days',1)
        if terms['prepaid_retry_attempts']>10 or not 1<=terms['retry_delay_days']<=365:
            raise ValueError('BOUNDED_PREPAID_CHANNEL_RETRY_REQUIRED')
        if not 1<=terms['max_active_tranches']<=1000 or not 1<=terms['max_contacts_per_customer']<=1000:
            raise ValueError('FINITE_SUPPLIER_AND_CONTACT_LIMIT_REQUIRED')
    return result


class ChannelBook:
    """Serializable environment, with explicit external-finance purchase boundary.

    Caller must settle the source-plan invoice before ``purchase``. Failure credits
    are provider receivables only: this object cannot mutate an enterprise account.
    """
    def __init__(self,seed,contracts,state=None):
        if type(seed) is not int or seed<0:
            raise ValueError('NONNEGATIVE_CHANNEL_SEED_REQUIRED')
        self.seed=seed
        self.contracts=validate_contracts(contracts)
        binding=_digest({'seed':seed,'contracts':self.contracts})
        if state is None:
            self.state={'schema':SCHEMA,'binding_sha256':binding,'instances':{},'contacts':{},'events':[],'last_day':-1,'exposures_by_day':{},'purchase_receipts':{}}
        else:
            self.state=copy.deepcopy(state)
            if self.state.get('schema')!=SCHEMA or self.state.get('binding_sha256')!=binding:
                raise ValueError('CHANNEL_SOURCE_OR_SEED_BINDING_CHANGED')
            if set(self.state)!={'schema','binding_sha256','instances','contacts','events','last_day','exposures_by_day','purchase_receipts'}:
                raise ValueError('EXACT_CHANNEL_STATE_REQUIRED')
            if not isinstance(self.state['instances'],dict) or not isinstance(self.state['contacts'],dict) or not isinstance(self.state['events'],list):
                raise ValueError('SERIALIZABLE_CHANNEL_RECORDS_REQUIRED')
            for plan,instance in self.state['instances'].items():
                if plan!=instance.get('source_plan_id') or instance.get('contract_id') not in self.contracts or instance.get('terms')!=self.contracts[instance['contract_id']]:
                    raise ValueError('CHANNEL_CONTRACT_INSTANCE_BINDING_CHANGED')

    def purchase(self,contract_id,day,source_plan_id):
        if contract_id not in self.contracts or type(day) is not int or day<0 or not isinstance(source_plan_id,str) or not source_plan_id or len(source_plan_id)>160:
            raise ValueError('BOUND_PAID_CHANNEL_PURCHASE_REQUIRED')
        if source_plan_id in self.state['purchase_receipts']:
            prior=self.state['purchase_receipts'][source_plan_id]
            if prior['contract_id']!=contract_id or prior['purchased_day']!=day:
                raise ValueError('CHANNEL_PURCHASE_IDEMPOTENCY_COLLISION')
            return copy.deepcopy(prior)
        if day<self.state['last_day']:
            raise ValueError('CHANNEL_PURCHASE_CANNOT_CHANGE_PAST')
        terms=self.contracts[contract_id]
        live=[i for i in self.state['instances'].values() if i['contract_id']==contract_id and i['expiry_day']>day and i['state'] not in {'FAILED','EXPIRED'}]
        if len(live)>=terms['max_active_tranches']:
            raise ValueError('CHANNEL_SUPPLIER_TRANCHE_LIMIT')
        activate=day+terms['lead_days']
        receipt={'schema':'agi-alpha/connected014-channel-purchase/v1','scope':'SIMULATED_CONTRACT_NOT_RECEIPT_OF_DEMAND','contract_id':contract_id,'source_plan_id':source_plan_id,'purchased_day':day,'activation_day':activate,'expiry_day':activate+terms['duration_days'],'terms':copy.deepcopy(terms),'invoice_microUSD':terms['price_microUSD']+terms['support_microUSD'],'finance_requirement':'Native earned-funded invoice must precede this contract; ChannelBook has no financial authority.','failure_remedy':'Prepaid bounded activation retries within original expiry, with no guaranteed reach. Any declared failure credit remains a provider receivable until separately collected.','potential_slots':terms['slots_per_day']*terms['duration_days']}
        self.state['purchase_receipts'][source_plan_id]=copy.deepcopy(receipt)
        self.state['instances'][source_plan_id]={**copy.deepcopy(receipt),'state':'SCHEDULED','potential_slots_used':0,'realized_exposures':0,'unused_slots':0,'failure_credit_due_microUSD':0,'activation_attempts':0,'next_activation_day':activate}
        self.state['events'].append({'day':day,'kind':'PAID_CHANNEL_PURCHASED','contract_id':contract_id,'source_plan_id':source_plan_id,'invoice_microUSD':receipt['invoice_microUSD']})
        return copy.deepcopy(receipt)

    def expose(self,day,prospects):
        if type(day) is not int or day<0 or not isinstance(prospects,list) or any(not isinstance(p,dict) or not isinstance(p.get('id'),str) or not p['id'] for p in prospects):
            raise ValueError('DATED_FINITE_PROSPECT_LIST_REQUIRED')
        ids=sorted(p['id'] for p in prospects)
        if len(ids)!=len(set(ids)):
            raise ValueError('UNIQUE_PROSPECT_IDENTITIES_REQUIRED')
        population_digest=_digest(ids)
        cached=self.state['exposures_by_day'].get(str(day))
        if cached is not None:
            if cached['population_sha256']!=population_digest:
                raise ValueError('EXPOSURE_DAY_POPULATION_CHANGED')
            return copy.deepcopy(cached['exposures'])
        if day<self.state['last_day']:
            raise ValueError('CHANNEL_EXPOSURE_CANNOT_CHANGE_PAST')
        result=[]; exposed=set(); attempted_slots=0;unused_slots=0
        for plan,instance in sorted(self.state['instances'].items()):
            terms=instance['terms']
            while day>=instance['next_activation_day'] and instance['state'] in {'SCHEDULED','RETRY_SCHEDULED'}:
                attempt_day=instance['next_activation_day']
                if attempt_day>=instance['expiry_day']:
                    instance['state']='FAILED';break
                attempt=instance['activation_attempts']
                active=_draw(self.seed,attempt_day,plan,'activation' if attempt==0 else 'prepaid-activation-retry-'+str(attempt))<terms['activation_reliability_bps']
                instance['activation_attempts']+=1
                retry_day=attempt_day+terms['retry_delay_days']
                retry=not active and attempt<terms['prepaid_retry_attempts'] and retry_day<instance['expiry_day']
                instance['state']='ACTIVE' if active else 'RETRY_SCHEDULED' if retry else 'FAILED'
                if retry:instance['next_activation_day']=retry_day
                if not active and not retry:
                    instance['failure_credit_due_microUSD']=terms['price_microUSD']*terms['failure_credit_bps']//10000
                self.state['events'].append({'day':attempt_day,'kind':'CHANNEL_ACTIVATED' if active else 'CHANNEL_ACTIVATION_FAILED_RETRY_SCHEDULED' if retry else 'CHANNEL_ACTIVATION_FAILED','source_plan_id':plan,'contract_id':instance['contract_id'],'activation_attempt':attempt+1,'next_retry_day':retry_day if retry else None,'failure_credit_due_microUSD':instance['failure_credit_due_microUSD'],'credit_status':'RECEIVABLE_NOT_CASH' if not active and not retry else 'NOT_APPLICABLE'})
            if day>=instance['expiry_day'] and instance['state']=='ACTIVE':
                instance['state']='EXPIRED'
                self.state['events'].append({'day':instance['expiry_day'],'kind':'CHANNEL_EXPIRED','source_plan_id':plan,'contract_id':instance['contract_id'],'realized_exposures':instance['realized_exposures'],'potential_slots_used':instance['potential_slots_used'],'potential_slots':instance['potential_slots']})
            if instance['state']!='ACTIVE' or day<instance['activation_day'] or day>=instance['expiry_day']:
                continue
            pool=ids[terms['owned_audience_count']:]
            for slot in range(terms['slots_per_day']):
                instance['potential_slots_used']+=1;attempted_slots+=1
                identity=f'{plan}/{slot}'
                if not pool or _draw(self.seed,day,identity,'reach-realization')>=terms['realization_bps']:
                    instance['unused_slots']+=1;unused_slots+=1;continue
                shared=_draw(self.seed,day,identity,'overlapping-audience')<terms['overlap_bps']
                ranking=sorted(pool,key=lambda customer:(_draw(self.seed,day,customer,'shared-audience' if shared else instance['contract_id']+'-audience'),customer))
                candidate=ranking[slot % len(ranking)]
                history=self.state['contacts'].get(candidate,[])
                fatigue=len(history)>=terms['max_contacts_per_customer']
                cooldown=bool(history and day-history[-1]['day']<terms['contact_cooldown_days'])
                if candidate in exposed or fatigue or cooldown:
                    instance['unused_slots']+=1;unused_slots+=1;continue
                exposure_id='channel-exposure-'+_digest([plan,day,slot,candidate])[:24]
                row={'customer_id':candidate,'source_plan_id':plan,'contract_id':instance['contract_id'],'exposure_id':exposure_id}
                result.append(row);exposed.add(candidate)
                self.state['contacts'].setdefault(candidate,[]).append({'day':day,'exposure_id':exposure_id,'source_plan_id':plan})
                instance['realized_exposures']+=1
                self.state['events'].append({'day':day,'kind':'POTENTIAL_CUSTOMER_EXPOSED','customer_id':candidate,'source_plan_id':plan,'contract_id':instance['contract_id'],'exposure_id':exposure_id,'scope':'Exposure only; qualification, voluntary decision and budget remain separate.'})
        self.state['last_day']=day
        self.state['exposures_by_day'][str(day)]={'population_sha256':population_digest,'exposures':copy.deepcopy(result),'attempted_slots':attempted_slots,'realized_exposures':len(result),'unused_slots':unused_slots}
        return result

    def export(self):
        return copy.deepcopy(self.state)
