"""Causal, expandable acquisition for the compatibility edition.

No balance lives here. All money is admitted and recorded by an injected native
bridge. Buyer preferences and demand are explicitly authored sensitivity worlds.
The policy receives completed observations only. Campaign sizes/cadence are
policy choices, never engine limits or evidence of real market size.
"""
from __future__ import annotations
import copy
import hashlib
import json
from fractions import Fraction
from connected_enterprise.channels import ChannelBook

MODES = ('nonentry', 'simple', 'commerce_only', 'no_inheritance', 'ordinary_reuse', 'joint')
PRICES = (14900, 29900, 59900)
PUBLIC_FIELDS = {'day', 'available_cents', 'profit_cents', 'earned_cents', 'built',
                 'enhanced', 'campaigns', 'observations', 'last_size', 'channel', 'survey',
                 'contact_cost_cents', 'channel_setup_cents', 'rival_quote_cents'}
DEFAULTS = {'horizon_days':365, 'cadence_days':28, 'initial_contacts':8,
            'risk_bps':100, 'fixed_contacts':128, 'price_cents':29900,
            'setup_cents':2500, 'enhancement_cents':1500, 'survey_cents':500,
            'hosting_cents_per_active_day':10, 'fulfillment_cents':400,
            'channel_setup_cents':500, 'contact_cents':500,
            'channel_lead_days':1, 'channel_duration_days':3,
            'settlement_days':45, 'development_seeds':[17,29],
            'confirmation_seeds':[57908161,57908162,57908163]}


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def draw(seed, *parts):
    return int(digest([seed,*parts])[:16],16) % 10000


def validate_prior(weights):
    if not isinstance(weights,dict) or not weights:
        raise ValueError('NONEMPTY_PRIOR_REQUIRED')
    try:
        vals=[Fraction(v) for v in weights.values()]
    except (ValueError,TypeError,ZeroDivisionError,OverflowError):
        raise ValueError('FINITE_RATIONAL_PROBABILITIES_REQUIRED') from None
    if any(v<0 or v>1 for v in vals) or sum(vals)!=1:
        raise ValueError('NORMALIZED_NONNEGATIVE_PROBABILITIES_REQUIRED')
    return vals


def config(**overrides):
    result={**DEFAULTS,**overrides}
    if set(result)!=set(DEFAULTS): raise ValueError('UNKNOWN_REGISTRATION_FIELD')
    for key,value in result.items():
        if key.endswith('_seeds'):
            if not isinstance(value,list) or any(type(x) is not int or x<0 for x in value):
                raise ValueError('NONNEGATIVE_SEED_LIST_REQUIRED')
        elif type(value) is not int or value<0:
            raise ValueError('NONNEGATIVE_INTEGER_CONFIG_REQUIRED')
    if not result['cadence_days'] or not result['initial_contacts'] or not result['contact_cents']:
        raise ValueError('POSITIVE_CAMPAIGN_CONFIG_REQUIRED')
    if not 0<result['risk_bps']<=10000 or result['horizon_days']<1:
        raise ValueError('FINITE_HORIZON_AND_RISK_FRACTION_REQUIRED')
    if result['price_cents'] not in PRICES: raise ValueError('REGISTERED_PRICE_REQUIRED')
    if set(result['development_seeds']) & set(result['confirmation_seeds']):
        raise ValueError('DEVELOPMENT_CONFIRMATION_SEEDS_MUST_DIFFER')
    return result


def worlds():
    """Unweighted alternative models, not frequency-calibrated scenarios."""
    base={'audience':100000, 'need_bps':3500, 'reach_bps':8000,
          'activation_bps':9700, 'budget_cents':[20000,50000,100000,250000],
          'value_cents':[60000,120000,300000], 'self_service_cents':45000,
          'rival_price_cents':39900, 'rival_effort_cents':10000,
          'own_effort_cents':12000, 'enhanced_effort_cents':4000,
          'payment_bps':9800, 'delivery_bps':9900, 'refund_bps':300,
          'imitation_day':210, 'rival_after_cents':19900,
          'collection_delay_hours':48, 'audience_overlap_bps':3500,
          'channel_cost_multiplier':1}
    return {
        'capability_gap':dict(base),
        'weak_need':{**base,'need_bps':400,'audience':10000,'self_service_cents':25000},
        'competitive_parity':{**base,'rival_price_cents':14900,'rival_effort_cents':4000,
                              'rival_after_cents':9900,'self_service_cents':18000},
        'adverse_supplier':{**base,'reach_bps':4500,'activation_bps':7000,
                            'payment_bps':8500,'delivery_bps':8500,'refund_bps':1500,
                            'collection_delay_hours':480,'channel_cost_multiplier':3}}


def validate_world(world):
    template=worlds()['capability_gap']
    if type(world) is not dict or set(world)!=set(template):
        raise ValueError('EXACT_PRIVATE_WORLD_REQUIRED')
    for key,value in world.items():
        if isinstance(value,list):
            if not value or any(type(x) is not int or x<0 for x in value):
                raise ValueError('INDEPENDENT_NONNEGATIVE_BUYER_VALUES_REQUIRED')
        elif type(value) is not int or value<0 or (key.endswith('_bps') and value>10000):
            raise ValueError('VALID_PRIVATE_WORLD_PARAMETER_REQUIRED')
    if world['audience']<1 or world['channel_cost_multiplier']<1:
        raise ValueError('POSITIVE_DECLARED_AUDIENCE_AND_COST_REQUIRED')
    return copy.deepcopy(world)


def buyer_choice(world, seed, buyer, day, price_cents, enhanced):
    """Environment-only complete-outcome choice; no purchase wins utility ties."""
    world=validate_world(world)
    budget=world['budget_cents'][draw(seed,buyer,'budget')%len(world['budget_cents'])]
    value=world['value_cents'][draw(seed,buyer,'value')%len(world['value_cents'])]
    if draw(seed,buyer,'need')>=world['need_bps']: value=0
    effort=world['enhanced_effort_cents'] if enhanced else world['own_effort_cents']
    rival=world['rival_after_cents'] if day>=world['imitation_day'] else world['rival_price_cents']
    alternatives=[('decline',0,0),('self_service',world['self_service_cents'],0),
                  ('rival',rival,world['rival_effort_cents']),('us',price_cents,effort)]
    ranked=[]
    for name,fee,adoption in alternatives:
        utility=0 if name=='decline' else value-fee-adoption
        # Budget includes the buyer's modeled adoption/compute outlay.
        if fee+adoption<=budget: ranked.append((utility,name,fee,adoption))
    best=max(x[0] for x in ranked)
    tied=[x for x in ranked if x[0]==best]
    # Conservative complete alternatives win an exact utility tie.
    selected=next((x for x in tied if x[1]=='decline'),None) or sorted(tied,key=lambda x:x[1]=='us')[0]
    outside=max(x[0] for x in ranked if x[1]!='us')
    return {'provider':selected[1],'budget_cents':budget,'value_cents':value,
            'net_benefit_cents':selected[0],'outside_net_cents':outside,
            'incremental_net_cents':selected[0]-outside,
            'adoption_cents':selected[3],'price_cents':selected[2]}


def public_state(state, snapshot, contact_cost_cents=500, channel_setup_cents=500, rival_quote_cents=39900):
    return {'day':state['day'],'available_cents':snapshot['available_cents'],
            'profit_cents':snapshot['profit_cents'],
            'earned_cents':snapshot.get('unrestricted_earned_cents',0),
            'built':state['built'],'enhanced':state['enhanced'],
            'campaigns':len(state['campaigns']),
            'observations':[{k:x[k] for k in ('contacts','orders','declines','net_cents','size','settled','channel')} for x in state['observations']],
            'last_size':state['last_size'],'channel':state['channel'],
            'survey':copy.deepcopy(state['survey']),'contact_cost_cents':contact_cost_cents,
            'channel_setup_cents':channel_setup_cents,'rival_quote_cents':rival_quote_cents}


def decide(public, mode='joint', settings=None):
    """Declared heuristic, with ordinary reuse granted identical decisions."""
    cfg=config(**(settings or {}))
    if type(public) is not dict or set(public)!=PUBLIC_FIELDS:
        raise ValueError('ONLY_DECLARED_PUBLIC_OBSERVATIONS_PERMITTED')
    if mode not in MODES: raise ValueError('REGISTERED_POLICY_REQUIRED')
    for key in ('day','available_cents','earned_cents','campaigns','last_size','channel'):
        if type(public[key]) is not int or public[key]<0: raise ValueError('PUBLIC_INTEGER_REQUIRED')
    if any(type(public[k]) is not int or public[k]<1 for k in ('contact_cost_cents','channel_setup_cents')):
        raise ValueError('POSITIVE_PUBLIC_SUPPLIER_QUOTE_REQUIRED')
    if type(public['rival_quote_cents']) is not int or public['rival_quote_cents']<0:
        raise ValueError('NONNEGATIVE_CURRENT_RIVAL_QUOTE_REQUIRED')
    if mode=='nonentry': return {'kind':'wait','reason':'nonentry_control'}
    prices=[p for p in PRICES if p<public['rival_quote_cents'] and p>cfg['fulfillment_cents']+(p*290+9999)//10000+30]
    if mode!='simple' and not prices:return {'kind':'wait','reason':'no_registered_offer_beats_current_quote_above_resource_floor'}
    if not public['built']:
        return {'kind':'build','cents':cfg['setup_cents']} if public['available_cents']>=cfg['setup_cents'] else {'kind':'wait','reason':'illiquid'}
    obs=[x for x in public['observations'] if x['settled'] and x.get('channel',0)==public['channel']]; recent=obs[-2:]
    # A completed losing campaign triggers a paid, optional channel test once.
    loss=bool(recent) and sum(x['net_cents'] for x in recent)<0
    if loss and mode in ('joint','ordinary_reuse','no_inheritance') and public['survey'] is None:
        if public['available_cents']>=cfg['survey_cents']:
            return {'kind':'survey','cents':cfg['survey_cents']}
    if loss and (mode in ('joint','ordinary_reuse','no_inheritance') or len(recent)>=2):
        if public['survey'] and public['survey']['qualified']>=6 and public['channel']==0:
            return {'kind':'pivot','channel':1}
        return {'kind':'wait','reason':'observed_unprofitable_acquisition'}
    # Current buyer qualification finds ordinary reuse ties. No paid upgrade is
    # selected or assigned invented conversion improvement by this policy.
    if public['day']+cfg['channel_lead_days']>=cfg['horizon_days']:
        return {'kind':'wait','reason':'delivery_beyond_registered_horizon'}
    if public['day']%cfg['cadence_days']:
        return {'kind':'wait','reason':'registered_campaign_cadence'}
    size=cfg['fixed_contacts'] if mode=='simple' else cfg['initial_contacts'] if not obs else public['last_size']*2
    # This policy risks a registered fraction of CURRENT unrestricted money.
    # Increasing risk_bps or operating scale is permitted, and separately compared.
    allowance=public['available_cents']*cfg['risk_bps']//10000
    affordable=max(0,(allowance-public['channel_setup_cents'])//public['contact_cost_cents'])
    size=min(size,affordable)
    if size<1: return {'kind':'wait','reason':'cash_risk_rule'}
    # A transparent ordinary competitor-response rule, not inferred elasticity.
    # Buyer effort and values still decide the actual complete-outcome choice.
    price=cfg['price_cents'] if mode=='simple' else max(prices)
    return {'kind':'campaign','size':size,'price_cents':price,'channel':public['channel']}


class MarketRunner:
    """Resumable environment/policy caller. Native bridge is the sole accountant."""
    def __init__(self, world, mode='joint', seed=17, settings=None, state=None):
        self.world=validate_world(world);self.mode=mode;self.seed=seed;self.cfg=config(**(settings or {}))
        if mode not in MODES or type(seed) is not int or seed<0: raise ValueError('REGISTERED_MODE_AND_SEED_REQUIRED')
        self.binding=digest({'world':world,'mode':mode,'seed':seed,'settings':self.cfg})
        self.state=copy.deepcopy(state) if state else {'binding':self.binding,'day':0,'built':False,'enhanced':False,
            'campaigns':[],'observations':[],'last_size':self.cfg['initial_contacts'],'channel':0,'survey':None,
            'contacted':[],'hosted_days':[],'pending':None,'completed':False,'events':[],'buyer_net_cents':0,'buyer_incremental_cents':0}
        if self.state['binding']!=self.binding: raise ValueError('REGISTERED_SOURCE_WORLD_OR_POLICY_CHANGED')

    def export(self): return copy.deepcopy(self.state)

    def _contacts(self, campaign):
        """Use native ChannelBook contact semantics on a finite sampled audience.

        Audience cardinality is a declared world parameter, not a software limit.
        A sample is a provider's possible exposure pool, not guaranteed demand.
        Global edition contacts prevent reselling overlap as fresh buyers.
        """
        n=campaign['size'];day=campaign['day'];channel=campaign['channel']
        pool=set()
        for i in range(n*2):
            # Full SHA index permits audiences larger than 10,000.
            index=int(digest([self.seed,day,i,'shared' if draw(self.seed,day,i,'shared-audience')<self.world['audience_overlap_bps'] else channel])[:16],16)%self.world['audience']
            pool.add(f'buyer-{index:012d}')
        terms={'price_microUSD':campaign['cost_cents']*10000,'support_microUSD':0,
               'slots_per_day':n,'duration_days':self.cfg['channel_duration_days'],'lead_days':self.cfg['channel_lead_days'],
               'activation_reliability_bps':self.world['activation_bps'],'realization_bps':self.world['reach_bps'],
               'overlap_bps':self.world['audience_overlap_bps'],'owned_audience_count':0,
               'max_contacts_per_customer':1,'max_active_tranches':1,'contact_cooldown_days':365}
        book=ChannelBook(self.seed,{'paid':terms})
        book.purchase('paid',day,campaign.get('opportunity_id',f'channel-{day}-{channel}'))
        rows=book.expose(day+self.cfg['channel_lead_days'],[{'id':x} for x in sorted(pool)])
        seen=set(self.state['contacted'])
        contacts=[x for x in rows if x['customer_id'] not in seen]
        return contacts,{'channel_binding':book.state['binding_sha256'],'sample_sha256':digest(sorted(pool)),
                         'attempted_slots':n,'channel_exposures':len(rows),'new_exposures':len(contacts),
                         'activation_day':day+self.cfg['channel_lead_days'],
                         'expiry_day':day+self.cfg['channel_lead_days']+self.cfg['channel_duration_days']}

    def _refresh(self, bridge):
        # Only completed native settlements are interpreted as observations.
        buyer_net=0;buyer_incremental=0
        for stats in self.state['observations']:
            stats['net_cents']=-stats['paid_cents'];stats['orders']=0;stats['settled']=True
            for row in stats['receipts']:
                receipt=bridge.order_receipt(row['order_id'])
                row['collected']=bool(receipt.get('collected',False))
                row['net_cents']=receipt.get('contribution_cents',0)
                stats['net_cents']+=row['net_cents']
                if receipt.get('status')=='accepted_uncollected':stats['settled']=False
                if row['collected']:
                    stats['orders']+=1;buyer_net+=row['buyer_net_cents']
                    buyer_incremental+=row['buyer_incremental_cents']
                elif receipt.get('status')=='refunded':
                    buyer_net-=row['failed_adoption_cents'];buyer_incremental-=row['failed_adoption_cents']
        self.state['buyer_net_cents']=buyer_net
        self.state['buyer_incremental_cents']=buyer_incremental

    def step(self, bridge, checkpoint=lambda state:None):
        s=self.state;cfg=self.cfg
        if s['completed']: return False
        if s['pending'] is None:
            if s['day']>=cfg['horizon_days']:
                bridge.advance(cfg['horizon_days']*24-1)
                self._refresh(bridge)
                s['completed']=True;checkpoint(self.export());return False
            bridge.advance(max(s['day']*24,bridge.snapshot().get('hour',0)))
            self._refresh(bridge)
            snapshot=bridge.snapshot()
            multiplier=self.world['channel_cost_multiplier']
            rival_quote=self.world['rival_after_cents'] if s['day']>=self.world['imitation_day'] else self.world['rival_price_cents']
            public=public_state(s,snapshot,cfg['contact_cents']*multiplier,cfg['channel_setup_cents']*multiplier,rival_quote)
            action=decide(public,self.mode,cfg)
            s['pending']={'action':action,'public':public,'day':s['day'],'before':snapshot,
                          'id':f"market-{self.mode}-{s['day']}-{len(s['events'])}"}
            checkpoint(self.export()) # Persist exact intent BEFORE any financial mutation.
        pending=s['pending'];a=pending['action'];day=pending['day'];eid=pending['id'];hour=day*24
        bridge.advance(max(hour,bridge.snapshot().get('hour',0)))
        event={'id':eid,'day':day,'action':a['kind'],'decision':copy.deepcopy(a),
               'public':copy.deepcopy(pending['public']),'native_before':copy.deepcopy(pending['before'])}
        if a['kind'] in ('build','enhance','survey'):
            funded=bridge.spend(eid,a['cents'],hour,a['kind'])
            event.update({'cost_cents':a['cents'] if funded else 0,'funded':bool(funded)})
            if funded:
                if a['kind']=='build': s['built']=True
                elif a['kind']=='enhance': s['enhanced']=True
                else:
                    # No hidden scenario label is delivered; paid sampled qualification only.
                    count=sum(draw(self.seed,'survey',day,i)<self.world['need_bps'] for i in range(20))
                    s['survey']={'sample_size':20,'qualified':count,'paid_day':day}
        elif a['kind']=='pivot': s['channel']=a['channel']
        elif a['kind']=='campaign':
            cost=(cfg['channel_setup_cents']+a['size']*cfg['contact_cents'])*self.world['channel_cost_multiplier']
            # Supplier quotation is available before purchase; not a hidden buyer outcome.
            funded=bridge.spend(eid,cost,hour,'acquisition')
            event.update({'cost_cents':cost if funded else 0,'funded':bool(funded)})
            if funded:
                camp={**a,'id':eid,'opportunity_id':f'channel-{day}-{a["channel"]}','day':day,'cost_cents':cost}
                contacts,proof=self._contacts(camp)
                stats={'campaign_id':eid,'contacts':len(contacts),'orders':0,'declines':0,'net_cents':-cost,
                       'paid_cents':cost,'size':a['size'],'channel':a['channel'],'receipts':[],'proof':proof,'settled':True}
                for exposed in contacts:
                    buyer=exposed['customer_id']
                    # Replays regenerate the same source-bound request; bridge must deduplicate.
                    decision=buyer_choice(self.world,self.seed,buyer,day,a['price_cents'],s['enhanced'])
                    if decision['provider']!='us': stats['declines']+=1;continue
                    paid=draw(self.seed,buyer,'payment')<self.world['payment_bps']
                    delivered=draw(self.seed,buyer,'delivery')<self.world['delivery_bps']
                    accepted=draw(self.seed,buyer,'refund')>=self.world['refund_bps']
                    order={'id':eid+'-'+buyer,'buyer':buyer,'budget_cents':decision['budget_cents'],
                           'price_cents':a['price_cents'],'hour':proof['activation_day']*24,
                           'accept':accepted,'pay':paid,'delivery_ok':delivered,
                           'collection_delay_hours':self.world['collection_delay_hours'],
                           'acquired':True,'choice':True}
                    receipt=bridge.deliver(order)
                    stats['receipts'].append({'order_id':order['id'],'collected':False,
                        'buyer_net_cents':decision['net_benefit_cents'],
                        'buyer_incremental_cents':decision['incremental_net_cents'],
                        'failed_adoption_cents':decision['adoption_cents'] if paid else 0})
                s['contacted']=sorted(set(s['contacted'])|{x['customer_id'] for x in contacts})
                s['campaigns'].append(camp);s['observations'].append(stats);s['last_size']=a['size']
                self._refresh(bridge)
        # Infrastructure cost follows an active operating day. No non-entry schedule.
        if s['built'] and day not in s['hosted_days']:
            event['hosting_funded']=bool(bridge.spend(f'hosting-day-{day}',cfg['hosting_cents_per_active_day'],max(hour,bridge.snapshot().get('hour',hour)),'hosting'))
            if event['hosting_funded']:s['hosted_days'].append(day)
        s['events'].append(event);s['pending']=None
        # Internal build/test decisions occur before the next acquisition decision.
        if a['kind'] not in ('build','enhance','survey','pivot') or not event.get('funded',True): s['day']=max(day+1,(bridge.snapshot().get('hour',hour)+23)//24)
        checkpoint(self.export());return True

    def run(self, bridge, checkpoint=lambda state:None):
        while self.step(bridge,checkpoint): pass
        return self.export()


def disclosure():
    return {'schema':'omega-expandable-market/v1','currency':'USD','amount_unit':'integer cents',
            'worlds':worlds(),'settings':config(),'modes':list(MODES),'weights':None,
            'cost_provenance':'All commercial costs/needs/budgets are explicit authored sensitivity assumptions; no measured demand.',
            'policy_scope':'Compared causal heuristics, no global optimum or calibrated expected-profit claim.',
            'rights':'Hypothetical distribution rights; repository licensing remains unresolved.',
            'buyer_compute':'Adoption outlay includes assumed local hardware/electricity/effort; no external routing or paid API calls.',
            'capacity':'No production capacity grants contact rights or demand; fulfilled order requires funded exposure and voluntary choice.',
            'limits':['Known finite deterministic compatibility scope only','No real transactions or customers','Public rival fee response is a heuristic, not elasticity or total-buyer-cost optimality',
                      'No human staffing charge; unresolved security/legal costs need sensitivity',
                      'No ongoing personal support or updates promised','Fixed cadence/risk are tested choices, not optimal business constraints']}
