"""Finite voluntary market for source-bound productive constructor bundles.

Prices pay for qualified construction/integration/operation, not exclusion from
public source. This layer creates inert offers and payoff/participation records;
only the canonical native caller may authorize work, spend or collect money.
"""
from __future__ import annotations

import copy
from decimal import Decimal, ROUND_CEILING
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path

SCHEMA = 'production060/constructor-rights-market/v1'
FAMILIES = ('license', 'transfer', 'gainshare')
COST_FIELDS = ('construction', 'integration', 'checking', 'support', 'error_loss',
               'acquisition', 'compute', 'maintenance', 'capital_use', 'residual_obligations')
OUTSIDES = ('human_build', 'ordinary_self_build', 'free_equal_content_copy', 'withdraw')
SOURCE_FILES = ('production060/dispatch.py', 'production060/acceptance.py',
                'production060/rights_market.py', 'production060/evaluation.json')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _integer(value, name, *, unknown=False):
    if unknown and value is None:return None
    if type(value) is not int or value<0:raise ValueError('EXACT_NONNEGATIVE_INTEGER_REQUIRED:'+name)
    return value


def _money(value):
    result=Decimal(str(value))*1000000
    if not result.is_finite() or result<0 or result!=result.to_integral_value():raise ValueError('EXACT_PUBLIC_COST_REQUIRED')
    return int(result)


def _cost_total(case, family):
    row=case['production_costs_microUSD'][family]
    if any(row[k] is None for k in COST_FIELDS):return None
    return sum(row.values())


def validate_case(case):
    required={'schema','scope','evidence','source_binding','project','available_microUSD','production_costs_microUSD',
              'buyer_handling_microUSD','outside_options','party_terms','prices_microUSD','gainshare_bps','worlds','selection'}
    if not isinstance(case,dict) or set(case)-{'settlement'}!=required or case['schema']!=SCHEMA or case['scope']!='CONDITIONAL_MODEL_NO_ACTUAL_RIGHTS_TRANSFER':raise ValueError('EXACT_CONSTRUCTOR_MARKET_CASE_REQUIRED')
    _integer(case['available_microUSD'],'available')
    settlement=case.get('settlement')
    if settlement is not None:
        if set(settlement)!={'payment_fixed_microUSD','payment_bps','positive_profit_tax_bps'}:raise ValueError('EXACT_SETTLEMENT_SCOPE_REQUIRED')
        for name,value in settlement.items():
            _integer(value,name,unknown=True)
            if value is not None and name.endswith('_bps') and value>10000:raise ValueError('SETTLEMENT_BASIS_POINTS_OUT_OF_RANGE')
    if set(case['production_costs_microUSD'])!=set(FAMILIES) or set(case['buyer_handling_microUSD'])!=set(FAMILIES):raise ValueError('ALL_PRODUCT_FAMILIES_REQUIRED')
    for family,row in case['production_costs_microUSD'].items():
        if set(row)!=set(COST_FIELDS):raise ValueError('COMPLETE_AGENT_CONSTRUCTION_COST_SCOPE_REQUIRED')
        for k,v in row.items():_integer(v,k,unknown=True)
        _integer(case['buyer_handling_microUSD'][family],family+' buyer handling',unknown=True)
    if set(case['outside_options'])!=set(OUTSIDES):raise ValueError('HUMAN_SELF_BUILD_FREE_COPY_AND_WITHDRAW_REQUIRED')
    for name,row in case['outside_options'].items():
        if set(row)!={'cost_microUSD','cash_required_microUSD','equivalent_outcome','basis'} or type(row['equivalent_outcome']) is not bool or not isinstance(row['basis'],str):raise ValueError('COMPLETE_OUTSIDE_OUTCOME_REQUIRED')
        _integer(row['cost_microUSD'],name+' cost',unknown=True);_integer(row['cash_required_microUSD'],name+' cash',unknown=True)
    if case['outside_options']['withdraw']['cost_microUSD']!=0 or case['outside_options']['withdraw']['cash_required_microUSD']!=0:raise ValueError('FREE_WITHDRAWAL_REQUIRED')
    terms=case['party_terms']
    if set(terms)!={'contributor_minimum_microUSD','capital_minimum_microUSD','contributor_share_bps','capital_share_bps'}:raise ValueError('VOLUNTARY_PARTY_TERMS_REQUIRED')
    for name,value in terms.items():_integer(value,name)
    if terms['capital_share_bps']+terms['contributor_share_bps']>10000:raise ValueError('SURPLUS_SHARES_CANNOT_EXCEED_AVAILABLE_SURPLUS')
    for values,label,cap in [(case['prices_microUSD'],'prices',None),(case['gainshare_bps'],'gainshare',10000)]:
        if not isinstance(values,list) or not values or len(values)!=len(set(values)):raise ValueError('FINITE_UNIQUE_'+label.upper()+'_REQUIRED')
        for value in values:
            _integer(value,label)
            if cap is not None and value>cap:raise ValueError('BASIS_POINTS_OUT_OF_RANGE')
    if case['selection'] not in {'maximin','declared_prior_expected_profit'}:raise ValueError('DECLARED_SELECTION_RULE_REQUIRED')
    if not isinstance(case['worlds'],list) or not case['worlds']:raise ValueError('DECLARED_WORLDS_REQUIRED')
    ids=set()
    for w in case['worlds']:
        if set(w)!={'id','weight','value_microUSD','budget_microUSD','requested','copy_after_delivery_cost_microUSD','verified_incremental_gain_microUSD','basis'} or w['id'] in ids or type(w['requested']) is not bool or not isinstance(w['basis'],str):raise ValueError('EXACT_BUYER_ENVIRONMENT_REQUIRED')
        ids.add(w['id']);_integer(w['weight'],'world weight')
        for name in ['value_microUSD','budget_microUSD','copy_after_delivery_cost_microUSD','verified_incremental_gain_microUSD']:_integer(w[name],name,unknown=True)
    if sum(w['weight'] for w in case['worlds'])<=0:raise ValueError('POSITIVE_DECLARED_WORLD_WEIGHT_REQUIRED')
    binding=case['source_binding']
    if set(binding)!={'files','sha256'} or not isinstance(binding['files'],dict) or not binding['files'] or binding['sha256']!=digest(binding['files']):raise ValueError('EXACT_CAPABILITY_SOURCE_BINDING_REQUIRED')
    if any(not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v) for v in binding['files'].values()):raise ValueError('CAPABILITY_SOURCE_HASH_REQUIRED')
    if case['project'].get('accepted') is not True or not case['project'].get('requests') or not all(isinstance(case['project'].get(k),str) and case['project'][k] for k in ['id','scope','module_entrypoint','checker_entrypoint']):raise ValueError('SOURCE_BOUND_ACCEPTED_PRODUCTIVE_MODULE_REQUIRED')
    if case['evidence'].get('actual_purchase_count')!=0:raise ValueError('OBSERVED_PURCHASES_REQUIRE_SEPARATE_PROVENANCE_NOT_MODEL_INVENTION')
    return case


def public_market(root, measurement_rows=None, *, scenario=None):
    root=Path(root).resolve();evaluation=json.loads((root/'production060/evaluation.json').read_text())
    if measurement_rows is None:
        path=root/'production060/evidence/ordinary/summary.json';raw=path.read_bytes();summary=json.loads(raw);measurement_rows=summary['rows'];snapshot=hashlib.sha256(raw).hexdigest()
    else:snapshot=digest(measurement_rows)
    accepted=[r for r in measurement_rows if r.get('accepted') is True]
    if not accepted:raise ValueError('NO_ACCEPTED_MODULE_MEASUREMENTS')
    cost=evaluation['costs_usd'];cpu=sum(Decimal(str(r.get('cpu_s',0))) for r in measurement_rows)
    cpu_cost=int((cpu*Decimal(str(cost['compute_per_cpu_hour']))/3600*1000000).to_integral_value(rounding=ROUND_CEILING))
    common={'construction':_money(cost['initial_construction']),'integration':_money(cost['operator_onboarding']),
        'checking':_money(cost['service_per_day'])*len(accepted),'support':_money(cost['support_per_network_month'])*12,
        'error_loss':None,'acquisition':_money(cost['acquisition_attempt']),'compute':cpu_cost,
        'maintenance':_money(cost['annual_hosting'])+_money(cost['annual_maintenance']),
        'capital_use':None,'residual_obligations':None}
    outside=lambda basis:{'cost_microUSD':None,'cash_required_microUSD':None,'equivalent_outcome':True,'basis':basis}
    sources={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in SOURCE_FILES}
    case={'schema':SCHEMA,'scope':'CONDITIONAL_MODEL_NO_ACTUAL_RIGHTS_TRANSFER',
        'evidence':{'actual_purchase_count':0,'anonymous_public_work_operators':1,'accepted_day_measurements':len(accepted),'measured_CPU_seconds':str(cpu),
            'measurement_snapshot_sha256':snapshot,'commercial_value':'UNKNOWN; actual public work requests are not software purchases',
            'cost_status':'Authored evaluation envelopes plus observed CPU at a declared modeled rate; unknown fields are not zero',
            'source_rights':'Existing licenses and publication permissions only. No exclusivity, credential transfer or access grant. Public availability does not itself prove every copyright permission.'},
        'source_binding':{'files':sources,'sha256':digest(sources)},
        'project':{'id':'source-bound-dispatch-constructor','accepted':True,'scope':'benchmark logistics only; no physical quality or legal-driver certification',
            'requests':[r['id'] for r in accepted],'module_entrypoint':'production060.dispatch.rolling_schedule','checker_entrypoint':'production060.acceptance.verify',
            'observed_operational_score_is_not_money':True,'financial_period':'declared network-year cost envelope, not a new observed year'},
        'available_microUSD':100000000000,'production_costs_microUSD':{f:copy.deepcopy(common) for f in FAMILIES},
        'buyer_handling_microUSD':{f:None for f in FAMILIES},
        'outside_options':{'human_build':outside('Complete bespoke human engineering, verification, support and error exposure; unknown'),
            'ordinary_self_build':outside('Same ordinary source, tools and information; no invention tax or forced R&D'),
            'free_equal_content_copy':outside('Equal-content source-copy stress always retained; include legitimate integration/operation only, no exclusion rent'),
            'withdraw':{'cost_microUSD':0,'cash_required_microUSD':0,'equivalent_outcome':False,'basis':'Voluntary no-purchase outside option'}},
        'party_terms':{'contributor_minimum_microUSD':0,'capital_minimum_microUSD':0,'contributor_share_bps':0,'capital_share_bps':0},
        'prices_microUSD':[_money(v) for v in evaluation['business_evaluation']['price_choices_usd_network_year']],
        'gainshare_bps':[0,1000,2500,5000],
        'worlds':[{'id':'unverified_no_adoption','weight':1,'value_microUSD':0,'budget_microUSD':0,'requested':False,
            'copy_after_delivery_cost_microUSD':0,'verified_incremental_gain_microUSD':None,'basis':'Evidence-backed current state: no observed purchase or validated incremental monetary gain'}],
        'selection':'maximin'}
    case['settlement']={'payment_fixed_microUSD':_money(cost['payment_fixed_per_invoice']),'payment_bps':int(Decimal(str(cost['payment_percent']))*10000),'positive_profit_tax_bps':int(Decimal(str(cost['tax_rate_positive_income']))*10000)}
    if scenario:
        allowed={'settlement'} | {'project','available_microUSD','production_costs_microUSD','buyer_handling_microUSD','outside_options','party_terms','prices_microUSD','gainshare_bps','worlds','selection'}
        if set(scenario)-allowed:raise ValueError('SCENARIO_CANNOT_REWRITE_MEASURED_EVIDENCE_OR_SOURCE')
        for name,value in scenario.items():case[name]=copy.deepcopy(value)
    return validate_case(case)


def enumerate_contracts(case):
    validate_case(case);out=[]
    for family,fee in itertools.product(FAMILIES,case['prices_microUSD']):
        for share in case['gainshare_bps'] if family=='gainshare' else [0]:
            out.append({'schema':'production060/productive-constructor-contract/v1','family':family,'upfront_microUSD':fee,
                'gainshare_bps':share,'source_sha256':case['source_binding']['sha256'],'project_sha256':digest(case['project']),
                'rights':{'exclusive':False,'public_source_remains_available':True,'constructor_replication':'existing license and user authority only',
                    'buyer_may_self_operate_and_compete':True,'private_account_authority_inherited':False,
                    'transfer_scope':'constructed project configuration and verified execution means; not ownership of third-party public assets'},
                'payment_rule':'accepted work plus verified incremental gain only; no forecast gain is a funding receipt',
                'origin':'developer-authored finite contract family, not new legal rights or universal mechanism optimality'})
    return out


def _checked_contract(case,contract):
    if contract not in enumerate_contracts(case):raise ValueError('CONTRACT_NOT_IN_SOURCE_BOUND_DECLARED_GAME')
    return contract


def invoice_amount(case,contract,*,verified_incremental_gain_microUSD=None,accepted=False):
    _checked_contract(case,contract)
    if type(accepted) is not bool:raise ValueError('EXPLICIT_ACCEPTANCE_REQUIRED')
    if not accepted:return 0
    if contract['family']=='gainshare':
        _integer(verified_incremental_gain_microUSD,'independently verified incremental gain')
        return contract['upfront_microUSD']+verified_incremental_gain_microUSD*contract['gainshare_bps']//10000
    return contract['upfront_microUSD']


def choose_buyer(case,contract,buyer_world):
    _checked_contract(case,contract)
    if buyer_world not in case['worlds']:raise ValueError('BUYER_WORLD_NOT_REGISTERED')
    w=buyer_world
    if not w['requested']:return {'chosen':'withdraw','buys':False,'status':'NO_QUALIFIED_REQUEST','utility_microUSD':0,'invoice_microUSD':0,'best_complete_outside_cost_microUSD':None}
    if w['value_microUSD'] is None or w['budget_microUSD'] is None:return {'chosen':'withdraw','buys':False,'status':'UNKNOWN_PRIVATE_STATE','utility_microUSD':None,'invoice_microUSD':0,'best_complete_outside_cost_microUSD':None}
    rows=[{'id':'withdraw','utility':0,'cost':0,'rank':0}];unknown=[];eligible_costs=[]
    for rank,name in enumerate(OUTSIDES[:-1],1):
        option=case['outside_options'][name]
        if not option['equivalent_outcome']:continue
        if option['cost_microUSD'] is None or option['cash_required_microUSD'] is None:unknown.append(name);continue
        if option['cash_required_microUSD']<=w['budget_microUSD']:
            rows.append({'id':name,'utility':w['value_microUSD']-option['cost_microUSD'],'cost':option['cost_microUSD'],'rank':rank});eligible_costs.append(option['cost_microUSD'])
    handling=case['buyer_handling_microUSD'][contract['family']]
    if contract['family']=='license' and w['copy_after_delivery_cost_microUSD'] is None:
        unknown.append('post_delivery_self_operation')
    gain=w['verified_incremental_gain_microUSD'];unqualified=handling is None or contract['family']=='gainshare' and gain is None
    price=None if unqualified else invoice_amount(case,contract,verified_incremental_gain_microUSD=gain,accepted=True)
    if not unknown and price is not None:
        if price+handling<=w['budget_microUSD']:rows.append({'id':'buy','utility':w['value_microUSD']-price-handling,'cost':price+handling,'rank':10})
        if contract['family']=='license' and w['copy_after_delivery_cost_microUSD'] is not None and price+min(handling,w['copy_after_delivery_cost_microUSD'])<=w['budget_microUSD']:
            # A copyable constructor cannot support fictitious mandatory renewal.
            rows.append({'id':'buy_then_self_operate','utility':w['value_microUSD']-price-min(handling,w['copy_after_delivery_cost_microUSD']),
                         'cost':price+min(handling,w['copy_after_delivery_cost_microUSD']),'rank':11})
    best=max(rows,key=lambda r:(r['utility'],-r['rank']))
    return {'chosen':best['id'],'buys':best['id'].startswith('buy'),'status':'UNKNOWN_COMPLETE_OUTSIDE_COST' if unknown else 'UNKNOWN_CHARGE_OR_HANDLING' if unqualified else 'DETERMINISTIC_BEST_RESPONSE',
        'utility_microUSD':best['utility'],'invoice_microUSD':price if best['id'].startswith('buy') else 0,
        'best_complete_outside_cost_microUSD':min(eligible_costs) if eligible_costs else None,
        'all_options':rows,'unknown_options':unknown,'tie_rule':'outside option wins; no forced purchase or preference for our firm'}


def small_contract_frontier(case,family='transfer'):
    validate_case(case)
    if family not in FAMILIES:raise ValueError('UNKNOWN_CONSTRUCTOR_PRODUCT')
    cost=_cost_total(case,family);handling=case['buyer_handling_microUSD'][family]
    values=[o['cost_microUSD'] for k,o in case['outside_options'].items() if k!='withdraw' and o['equivalent_outcome']]
    unknown=cost is None or handling is None or any(v is None for v in values) or not values
    if unknown:return {'qualified':False,'enabled_value_interval_microUSD':None,'reason':'Missing complete agent, error/support or strongest direct-copy/ordinary cost; unknown is not zero or impossibility'}
    upper=min(values);terms=case['party_terms'];max_price=max(0,upper-handling-1)
    settlement=case.get('settlement')
    if settlement is not None and all(v is not None for v in settlement.values()):
        fee_room=case['available_microUSD']-cost-settlement['payment_fixed_microUSD']
        if fee_room<0:max_price=-1
        elif settlement['payment_bps']:
            max_price=min(max_price,((fee_room+1)*10000-1)//settlement['payment_bps'])
    def feasible(price):
        accounting=_settlement(case,price,cost)
        if accounting is None:return False
        net=accounting['net'];contrib=max(0,net)*terms['contributor_share_bps']//10000;capital=max(0,net)*terms['capital_share_bps']//10000
        return (net-contrib-capital>0 and contrib>=terms['contributor_minimum_microUSD'] and capital>=terms['capital_minimum_microUSD'] and cost+accounting['payment_fee']<=case['available_microUSD'])
    if _settlement(case,0,cost) is None:return {'qualified':False,'enabled_value_interval_microUSD':None,'reason':'Unknown settlement fees/taxes remain unknown'}
    low,high=0,max_price
    if high<0 or terms['contributor_share_bps']+terms['capital_share_bps']==10000 or not feasible(high):minimum=None
    else:
        while low<high:
            mid=(low+high)//2
            if feasible(mid):high=mid
            else:low=mid+1
        minimum=low
    interval=None if minimum is None or minimum+handling+1>=upper else [minimum+handling+1,upper-1]
    return {'qualified':True,'minimum_complete_cost_microUSD':cost+handling,'minimum_compensating_invoice_microUSD':minimum,'best_complete_ordinary_cost_microUSD':upper,
        'enabled_value_interval_microUSD':interval,'conditional_small_project_gap_microUSD':0 if interval is None else interval[1]-interval[0]+1,
        'claim':'Conditional fixed-price cost crossover with positive creator surplus, voluntary party minima, settlement and present cash. It is not historical impossibility or demand evidence; the declared discrete menu can be coarser than this interval.'}



def _settlement(case,revenue,base_cost):
    terms=case.get('settlement')
    if terms is None or base_cost is None or any(value is None for value in terms.values()):return None
    fee=terms['payment_fixed_microUSD']+revenue*terms['payment_bps']//10000
    pretax=revenue-base_cost-fee;tax=max(0,pretax)*terms['positive_profit_tax_bps']//10000
    return {'payment_fee':fee,'tax':tax,'net':pretax-tax,'total_cost':base_cost+fee+tax,'pretax':pretax}


def _funding_need(case,contract,base_cost):
    terms=case.get('settlement')
    if terms is None or base_cost is None or any(v is None for v in terms.values()):return None
    invoices=[]
    for world in case['worlds']:
        if contract['family']=='gainshare' and world['verified_incremental_gain_microUSD'] is None:
            if world['requested']:return None
            continue
        invoices.append(invoice_amount(case,contract,verified_incremental_gain_microUSD=world['verified_incremental_gain_microUSD'],accepted=True))
    maximum=max(invoices,default=contract['upfront_microUSD'])
    return base_cost+terms['payment_fixed_microUSD']+maximum*terms['payment_bps']//10000


def evaluate_contract(case,contract,buyer_world):
    choice=choose_buyer(case,contract,buyer_world);family=contract['family'];cost=_cost_total(case,family);terms=case['party_terms']
    revenue=choice['invoice_microUSD'] if choice['buys'] else 0
    accounting=_settlement(case,revenue,cost);funding_need=_funding_need(case,contract,cost)
    unknown=accounting is None or funding_need is None or choice['status'] not in {'DETERMINISTIC_BEST_RESPONSE','NO_QUALIFIED_REQUEST'}
    margin=None if accounting is None else accounting['net']
    # The family may be declined before spending. There is no parallel account.
    actual_cost=cost if choice['buys'] else 0
    surplus=None if margin is None else max(0,margin)
    contributor=0 if surplus is None else surplus*terms['contributor_share_bps']//10000
    capital=0 if surplus is None else surplus*terms['capital_share_bps']//10000
    ir=(not unknown and contributor>=terms['contributor_minimum_microUSD'] and capital>=terms['capital_minimum_microUSD'])
    funded=funding_need is not None and funding_need<=case['available_microUSD']
    executable=choice['buys'] and not unknown and funded and ir
    actual_cost=accounting['total_cost'] if executable else 0
    creator=margin-contributor-capital if executable else 0
    return {'contract_sha256':digest(contract),'world_id':buyer_world['id'],'buyer_choice':choice,'cost_microUSD':actual_cost,
        'complete_project_cost_microUSD':None if accounting is None else accounting['total_cost'],'production_base_cost_microUSD':cost,
        'payment_fee_microUSD':None if accounting is None else accounting['payment_fee'],'tax_provision_microUSD':None if accounting is None else accounting['tax'],
        'present_cash_required_microUSD':funding_need,'conditional_collection_microUSD':revenue if executable else 0,
        'conditional_creator_surplus_microUSD':creator,'contributor_surplus_microUSD':contributor if executable else 0,
        'capital_surplus_microUSD':capital if executable else 0,'present_seed_fundable':funded,'party_participation':ir,
        'execute':executable,'decline_reason':None if executable else 'UNKNOWN_OR_VOLUNTARY_OUTSIDE_CHOICE_OR_UNFUNDED',
        'hindsight_guard':'A committed qualifying gainshare delivery keeps its cost and loss even when realized verified gain is low; no private realized-gain-based cancellation.',
        'conditional_transaction_only':True,'actual_observed_purchase':False,
        'cash_conservation_microUSD':None if not executable else revenue-accounting['total_cost']-creator-contributor-capital,
        'credit_scope':'Contingent surplus shares are not current funds, native earnings, asset valuation or demand evidence'}


def solve_market(case):
    validate_case(case);candidates=[];inadmissible=[];total=sum(w['weight'] for w in case['worlds'])
    for contract in enumerate_contracts(case):
        outcomes=[evaluate_contract(case,contract,w) for w in case['worlds']]
        profits=[r['conditional_creator_surplus_microUSD'] for r in outcomes]
        expected=sum(Fraction(p*w['weight'],total) for p,w in zip(profits,case['worlds']))
        criterion=min(profits) if case['selection']=='maximin' else expected
        admissible=(_cost_total(case,contract['family']) is not None and all(row['present_seed_fundable'] for row in outcomes) and all(not row['buyer_choice']['buys'] or row['party_participation'] for row in outcomes) and all(row['buyer_choice']['status'] in {'DETERMINISTIC_BEST_RESPONSE','NO_QUALIFIED_REQUEST'} for row in outcomes))
        item={'contract':contract,'outcomes':outcomes,'criterion':criterion,'expected':expected}
        (candidates if admissible else inadmissible).append(item)
    best=max(candidates,key=lambda r:(r['criterion'],r['expected'],-r['contract']['upfront_microUSD'],-FAMILIES.index(r['contract']['family']))) if candidates else None
    selected=None if best is None or best['criterion']<=0 else best['contract']
    return {'schema':'production060/constructor-market-solution/v1','case_sha256':digest(case),'selection':case['selection'],
        'contract':selected,'action':'retain_cash' if selected is None else 'offer_source_bound_constructor',
        'objective_fraction':([best['criterion'].numerator,best['criterion'].denominator] if isinstance(best['criterion'],Fraction) else [best['criterion'],1]) if selected is not None else [0,1],
        'conditional_expected_creator_surplus_fraction':[best['expected'].numerator,best['expected'].denominator] if selected is not None else [0,1],
        'outcomes':best['outcomes'] if selected is not None else [],'best_offer_outcomes':best['outcomes'] if best else [],
        'all_contracts_evaluated':len(candidates)+len(inadmissible),'inadmissible_contract_count':len(inadmissible),'objective_gap_in_declared_qualified_family':0,
        'incomplete_information_or_costs':not candidates,
        'small_contract_frontiers':{f:small_contract_frontier(case,f) for f in FAMILIES},
        'optimality_scope':'Finite single-project Stackelberg posted-contract commitment with deterministic buyer best responses and declared conditional worlds, cost/participation constraints and current seed. No universal optimum, truthful-source guarantee, market adoption or legal rights is established.',
        'no_invention_advantage_from_ordinary_tie':True,'observed_industry_creation':False,'actual_purchase_count':0}


def compile_constructor(case,contract,request_id):
    _checked_contract(case,contract)
    if request_id not in case['project']['requests']:raise ValueError('CONSTRUCTOR_REQUEST_NOT_SOURCE_BOUND')
    outcomes=[evaluate_contract(case,contract,w) for w in case['worlds']]
    if not any(row['execute'] for row in outcomes) or any(row['buyer_choice']['buys'] and not row['execute'] for row in outcomes):raise ValueError('UNFUNDED_OR_NONPARTICIPATING_CONSTRUCTOR_CHARTER')
    return {'schema':'production060/productive-constructor-charter/v1','source_sha256':case['source_binding']['sha256'],
        'request_id':request_id,'contract_sha256':digest(contract),'family':contract['family'],'module':case['project']['module_entrypoint'],
        'checker':case['project']['checker_entrypoint'],'execution_mode':'ordinary','scope':case['project']['scope'],
        'rights':copy.deepcopy(contract['rights']),'preconditions':['current qualified source-bound request','native funding receipt before production','existing independent acceptance before collection','own authorized environment and account; no inherited credentials','surplus allocation only after actual collection and native audit of unrestricted earned funds; contingent shares are not current cash'],
        'effect':'construct a fresh productive output for the permitted released input; transfer reusable means and applicability, not inherited acceptance',
        'legal_status':'conditional contract model; no actual transfer, exclusivity, publication or delegation of operating authority'}


def audit_market(case,result):
    expected=solve_market(case)
    if result!=expected:raise ValueError('CONSTRUCTOR_MARKET_SOLUTION_NOT_REDERIVED')
    for row in result['outcomes']:
        if row['execute'] and (row['cash_conservation_microUSD']!=0 or not row['present_seed_fundable'] or not row['party_participation']):raise ValueError('UNFUNDED_OR_NONCONSERVING_CONSTRUCTOR_ARRANGEMENT')
    return {'accepted':True,'case_sha256':digest(case),'scope':'Finite declared-game arithmetic/choice rederivation, not independent empirical value, legal rights, physical production or native financial audit'}


def bind_capability(root, *, capability_id, module_paths, module_entrypoint, checker_entrypoint, request_ids, acceptance_receipt_sha256, scope):
    root=Path(root).resolve();files={}
    if not module_paths or not request_ids or not isinstance(acceptance_receipt_sha256,str) or len(acceptance_receipt_sha256)!=64:raise ValueError('EXISTING_ACCEPTANCE_RECEIPT_AND_REQUESTS_REQUIRED')
    for name in module_paths:
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('RELATIVE_CAPABILITY_SOURCE_REQUIRED')
        path=root/relative
        if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents)):raise ValueError('REGULAR_CAPABILITY_SOURCE_REQUIRED')
        files[str(relative)]=hashlib.sha256(path.read_bytes()).hexdigest()
    return {'source_binding':{'files':files,'sha256':digest(files)},
        'project':{'id':capability_id,'accepted':True,'scope':scope,'requests':list(request_ids),'module_entrypoint':module_entrypoint,'checker_entrypoint':checker_entrypoint,
            'acceptance_receipt_sha256':acceptance_receipt_sha256,'acceptance_scope':'Existing caller-qualified receipt binding only; this market does not implement or replace productive acceptance. Fresh instances require fresh checking.'},
        'evidence':{'actual_purchase_count':0,'source_rights':'Existing licenses and publication permissions only; no exclusivity or inherited account/access authority',
            'accepted_capability_kind':capability_id,'acceptance_origin':'caller supplies the independently qualified existing receipt; no expert answer or new admission checker read'}}


def market_for_capability(capability, scenario):
    if set(capability)!={'source_binding','project','evidence'}:raise ValueError('EXACT_GENERIC_CAPABILITY_BINDING_REQUIRED')
    needed={'available_microUSD','production_costs_microUSD','buyer_handling_microUSD','outside_options','party_terms','prices_microUSD','gainshare_bps','worlds','selection'}
    if set(scenario)-{'settlement'}!=needed:raise ValueError('COMPLETE_DECLARED_SMALL_PROJECT_SCENARIO_REQUIRED')
    return validate_case({'schema':SCHEMA,'scope':'CONDITIONAL_MODEL_NO_ACTUAL_RIGHTS_TRANSFER',**copy.deepcopy(capability),**copy.deepcopy(scenario)})


def required_profitable_projects(target_profit_microUSD, net_profit_per_project_microUSD, *, shared_cost_microUSD=0, evidenced_collected_projects=0):
    for name,value in [('target',target_profit_microUSD),('profit',net_profit_per_project_microUSD),('shared cost',shared_cost_microUSD),('evidenced projects',evidenced_collected_projects)]:_integer(value,name)
    required=None if net_profit_per_project_microUSD<=0 else (target_profit_microUSD+shared_cost_microUSD+net_profit_per_project_microUSD-1)//net_profit_per_project_microUSD
    return {'required_profitable_projects':required,'evidenced_collected_projects':evidenced_collected_projects,
        'remaining_project_count':None if required is None else max(0,required-evidenced_collected_projects),
        'status':'CONDITIONAL_CONSTANT_UNIT_PROFIT_BOUND_NOT_DEMAND_OR_NATIVE_ATTAINMENT',
        'assumptions':'Each counted project must independently qualify complete outcome, all marginal/failed-construction/support/error costs, collection, capacity and native funding. Shared costs are separate. No TAM, dataset day, task scenario, valuation or aggregate engagement amount is counted as a buyer or profit.'}
