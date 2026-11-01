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


def audit_channel_history(channels, contracts, seed, buyers):
    """Independently reconstruct seeded rights; producer state is only a claim."""
    if type(seed) is not int or seed < 0 or contracts is None:
        raise ValueError('FROZEN_CHANNEL_CONTRACTS_AND_SEED_REQUIRED')
    terms_by_id = validate_contracts(contracts)
    def encode(value):
        return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    def commitment(value):
        return hashlib.sha256(encode(value)).hexdigest()
    def uniform(day, identity, stage):
        raw = json.dumps(['connected014-channel', seed, day, identity, stage], separators=(',', ':')).encode()
        return int.from_bytes(hashlib.sha256(raw).digest()[:8], 'big') % 10000
    def reject():
        raise ValueError('SEEDED_CHANNEL_HISTORY_MISMATCH')
    population = sorted(row['id'] for row in buyers)
    if len(population) != len(set(population)) or channels.get('binding_sha256') != commitment({'seed': seed, 'contracts': terms_by_id}):
        reject()
    purchases = channels['purchase_receipts']; instances = {}; expected_events = {}; event_days = {}
    if set(purchases) != set(channels['instances']):reject()
    for plan, purchase in purchases.items():
        ident = purchase['contract_id']; terms = terms_by_id.get(ident); day = purchase['purchased_day']
        if terms is None or type(day) is not int or day < 0 or purchase['source_plan_id'] != plan or purchase['terms'] != terms:
            reject()
        activation = day + terms['lead_days']; expiry = activation + terms['duration_days']
        if any(purchase.get(key) != value for key, value in {'activation_day': activation, 'expiry_day': expiry,
                'invoice_microUSD': terms['price_microUSD'] + terms['support_microUSD'],
                'potential_slots': terms['slots_per_day'] * terms['duration_days']}.items()):reject()
        instance = {**copy.deepcopy(purchase), 'state': 'SCHEDULED', 'potential_slots_used': 0,
                    'realized_exposures': 0, 'unused_slots': 0, 'failure_credit_due_microUSD': 0,
                    'activation_attempts': 0, 'next_activation_day': activation}
        instances[plan] = instance
        event_days[plan] = [day]
        expected_events[plan] = [{'day': day, 'kind': 'PAID_CHANNEL_PURCHASED', 'contract_id': ident,
                                 'source_plan_id': plan, 'invoice_microUSD': purchase['invoice_microUSD']}]
    days = []
    for text in channels['exposures_by_day']:
        try:day = int(text)
        except (TypeError, ValueError):reject()
        if not isinstance(text, str) or str(day) != text or day < 0:reject()
        days.append(day)
    if type(channels.get('last_day')) is not int or channels['last_day'] != max(days, default=-1):reject()
    contacts = {}; activations = {}; attempts = 0
    for day in sorted(days):
        exposures = []; exposed = set(); attempted = 0; unused = 0
        for plan, instance in sorted(instances.items()):
            terms = instance['terms']; events = expected_events[plan]
            while day >= instance['next_activation_day'] and instance['state'] in {'SCHEDULED', 'RETRY_SCHEDULED'}:
                when = instance['next_activation_day']
                if when >= instance['expiry_day']:
                    instance['state'] = 'FAILED'; break
                attempt = instance['activation_attempts']
                active = uniform(when, plan, 'activation' if attempt == 0 else 'prepaid-activation-retry-' + str(attempt)) < terms['activation_reliability_bps']
                instance['activation_attempts'] += 1; attempts += 1
                retry_day = when + terms['retry_delay_days']
                retry = not active and attempt < terms['prepaid_retry_attempts'] and retry_day < instance['expiry_day']
                instance['state'] = 'ACTIVE' if active else 'RETRY_SCHEDULED' if retry else 'FAILED'
                if retry:instance['next_activation_day'] = retry_day
                if not active and not retry:instance['failure_credit_due_microUSD'] = terms['price_microUSD'] * terms['failure_credit_bps'] // 10000
                if active:activations[plan] = when
                events.append({'day': when, 'kind': 'CHANNEL_ACTIVATED' if active else 'CHANNEL_ACTIVATION_FAILED_RETRY_SCHEDULED' if retry else 'CHANNEL_ACTIVATION_FAILED',
                    'source_plan_id': plan, 'contract_id': instance['contract_id'], 'activation_attempt': attempt + 1,
                    'next_retry_day': retry_day if retry else None, 'failure_credit_due_microUSD': instance['failure_credit_due_microUSD'],
                    'credit_status': 'RECEIVABLE_NOT_CASH' if not active and not retry else 'NOT_APPLICABLE'})
                event_days[plan].append(day)
            if day >= instance['expiry_day'] and instance['state'] == 'ACTIVE':
                instance['state'] = 'EXPIRED'
                events.append({'day': instance['expiry_day'], 'kind': 'CHANNEL_EXPIRED', 'source_plan_id': plan,
                    'contract_id': instance['contract_id'], 'realized_exposures': instance['realized_exposures'],
                    'potential_slots_used': instance['potential_slots_used'], 'potential_slots': instance['potential_slots']})
                event_days[plan].append(day)
            if instance['state'] != 'ACTIVE' or day < instance['activation_day'] or day >= instance['expiry_day']:continue
            pool = population[terms['owned_audience_count']:]
            for slot in range(terms['slots_per_day']):
                attempted += 1; instance['potential_slots_used'] += 1; identity = str(plan) + '/' + str(slot)
                candidate = None
                if pool and uniform(day, identity, 'reach-realization') < terms['realization_bps']:
                    shared = uniform(day, identity, 'overlapping-audience') < terms['overlap_bps']
                    stage = 'shared-audience' if shared else instance['contract_id'] + '-audience'
                    ranking = sorted(pool, key=lambda customer: (uniform(day, customer, stage), customer))
                    candidate = ranking[slot % len(ranking)]
                    history = contacts.get(candidate, [])
                    if candidate in exposed or len(history) >= terms['max_contacts_per_customer'] or (history and day - history[-1]['day'] < terms['contact_cooldown_days']):candidate = None
                if candidate is None:
                    unused += 1; instance['unused_slots'] += 1; continue
                ident = 'channel-exposure-' + commitment([plan, day, slot, candidate])[:24]
                row = {'customer_id': candidate, 'source_plan_id': plan, 'contract_id': instance['contract_id'], 'exposure_id': ident}
                exposures.append(row); exposed.add(candidate); instance['realized_exposures'] += 1
                contacts.setdefault(candidate, []).append({'day': day, 'exposure_id': ident, 'source_plan_id': plan})
                events.append({'day': day, 'kind': 'POTENTIAL_CUSTOMER_EXPOSED', **row,
                    'scope': 'Exposure only; qualification, voluntary decision and budget remain separate.'})
                event_days[plan].append(day)
        expected = {'population_sha256': commitment(population), 'exposures': exposures, 'attempted_slots': attempted,
                    'realized_exposures': len(exposures), 'unused_slots': unused}
        if channels['exposures_by_day'][str(day)] != expected:reject()
    if channels['instances'] != instances or channels.get('contacts') != contacts:reject()
    actual_events = {plan: [] for plan in instances}
    for event in channels.get('events', []):
        if event.get('source_plan_id') not in actual_events:reject()
        actual_events[event['source_plan_id']].append(event)
    if actual_events != expected_events:reject()
    offsets = {plan: 0 for plan in instances}; live_states = {}; prior_day = -1
    for event in channels.get('events', []):
        plan = event['source_plan_id']; phase_day = event_days[plan][offsets[plan]]; offsets[plan] += 1
        if phase_day < prior_day:reject()
        prior_day = phase_day; kind = event['kind']
        if kind == 'PAID_CHANNEL_PURCHASED':
            current = instances[plan]
            live = sum(instances[other]['contract_id'] == current['contract_id'] and instances[other]['expiry_day'] > phase_day
                       and state not in {'FAILED', 'EXPIRED'} for other, state in live_states.items())
            if live >= current['terms']['max_active_tranches']:reject()
            live_states[plan] = 'SCHEDULED'
        elif kind == 'CHANNEL_ACTIVATED':live_states[plan] = 'ACTIVE'
        elif kind == 'CHANNEL_ACTIVATION_FAILED_RETRY_SCHEDULED':live_states[plan] = 'RETRY_SCHEDULED'
        elif kind == 'CHANNEL_ACTIVATION_FAILED':live_states[plan] = 'FAILED'
        elif kind == 'CHANNEL_EXPIRED':live_states[plan] = 'EXPIRED'
    return {'activation_by_plan': activations, 'activation_attempts_checked': attempts, 'exposure_days_checked': len(days)}
