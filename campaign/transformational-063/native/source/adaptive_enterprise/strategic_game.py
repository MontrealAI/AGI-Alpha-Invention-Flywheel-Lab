"""Exact finite reduced-form follower stress; NOT an executed rival market.

Only positive conditional net contributions are haircut. Existing signed costs,
negative contributions, liabilities and native liquidity locks never shrink.
"""
import copy
from fractions import Fraction
from commercial.ledger import digest

KINDS={'acquisition','retention','new_service','capacity','supplier_diversity','instrument','delivery','cash','interaction'}
SCHEMA='connected-finite-follower-regret/v1'

def _integer(x,minimum=0):
    if type(x) is not int or x<minimum:raise ValueError('EXACT_NONNEGATIVE_GAME_INTEGER_REQUIRED')
    return x

def validate_game(policy,scenarios):
    if not isinstance(policy,dict) or set(policy)!={'schema','public_basis','max_response_states','scenarios'} or policy['schema']!=SCHEMA:raise ValueError('EXPLICIT_FINITE_GAME_POLICY_REQUIRED')
    if not isinstance(policy['public_basis'],str) or not policy['public_basis'].strip():raise ValueError('PUBLIC_GAME_BASIS_REQUIRED')
    _integer(policy['max_response_states'],1)
    if set(policy['scenarios'])!=set(scenarios):raise ValueError('GAME_SCENARIOS_MUST_MATCH_ALLOCATION')
    for spec in policy['scenarios'].values():
        if set(spec)!={'budget','responses'}:raise ValueError('EXPLICIT_FOLLOWER_COST_BUDGET_REQUIRED')
        _integer(spec['budget']);rs=spec['responses']
        if not isinstance(rs,list) or not rs:raise ValueError('FINITE_NONEMPTY_RESPONSES_REQUIRED')
        ids=set();unchanged=False
        for r in rs:
            if set(r)!={'id','haircut_bps','capture_bps','cost'} or not isinstance(r['id'],str) or not r['id'] or len(r['id'])>160 or r['id'] in ids:raise ValueError('UNIQUE_EXPLICIT_RESPONSE_REQUIRED')
            ids.add(r['id']);_integer(r['capture_bps']);_integer(r['cost'])
            if r['capture_bps']>10000 or not isinstance(r['haircut_bps'],dict) or set(r['haircut_bps'])-KINDS:raise ValueError('NO_POSITIVE_SELLER_BONUS_ALLOWED')
            for v in r['haircut_bps'].values():
                if _integer(v)>10000:raise ValueError('NO_POSITIVE_SELLER_BONUS_ALLOWED')
            unchanged|=not any(r['haircut_bps'].values()) and r['cost']==0 and r['capture_bps']==0
        if not unchanged:raise ValueError('COSTLESS_UNCHANGED_FOLLOWER_OPTION_REQUIRED')
    return policy


def select_game(baskets,policy,risk,state_digest,mandatory_ids=()):
    """Rank complete native-feasible basket receipts; no authority returned."""
    validate_game(policy,risk['scenarios'])
    if not isinstance(mandatory_ids,(tuple,list)) or any(not isinstance(x,str) for x in mandatory_ids) or len(set(mandatory_ids))!=len(mandatory_ids):raise ValueError('UNIQUE_GAME_COMMITMENTS_REQUIRED')
    mandatory=set(mandatory_ids)
    if any(not mandatory<=set(b['selected']) for b in baskets):raise ValueError('GAME_COMMITMENTS_REMOVED')
    count=len(baskets)*sum(len(x['responses']) for x in policy['scenarios'].values())
    if count>policy['max_response_states']:
        return {'status':'UNRESOLVED_RESPONSE_BOUND','selected_index':None,'response_states_required':count,'authorized_digest':None,'policy_sha256':digest(policy)}
    rows=[]
    for index,b in enumerate(baskets):
        scenario_rows={};nets={};option_nets={o['id']:{} for o in b['options']}
        for sid,spec in policy['scenarios'].items():
            baseline=Fraction(b['net'][sid]);positive={k:Fraction(v) for k,v in b['positive_by_kind'][sid].items()}
            responses=[]
            for r in spec['responses']:
                loss=sum((v*Fraction(r['haircut_bps'].get(k,0),10000) for k,v in positive.items()),Fraction(0))
                follower=loss*Fraction(r['capture_bps'],10000)-r['cost']
                responses.append({'id':r['id'],'affordable':r['cost']<=spec['budget'],'cost':r['cost'],'captured_contribution':str(loss*Fraction(r['capture_bps'],10000)),'follower_net':str(follower),'seller_net':str(baseline-loss)})
            affordable=[r for r in responses if r['affordable']]
            maximum=max(Fraction(r['follower_net']) for r in affordable)
            ties=[r for r in affordable if Fraction(r['follower_net'])==maximum]
            chosen=min(ties,key=lambda r:(Fraction(r['seller_net']),r['id']))
            nets[sid]=Fraction(chosen['seller_net'])
            response=next(x for x in spec['responses'] if x['id']==chosen['id'])
            for o in b['options']:
                value=Fraction(o['net'][sid]);option_nets[o['id']][sid]=value-max(Fraction(0),value)*Fraction(response['haircut_bps'].get(o['kind'],0),10000)
            scenario_rows[sid]={'baseline_net':str(baseline),'responses':responses,'best_response_ties':sorted(r['id'] for r in ties),'selected_response':chosen['id'],'seller_net':str(nets[sid])}
        expected=sum((Fraction(risk['scenarios'][s],10000)*n for s,n in nets.items()),Fraction(0));downside=max(Fraction(0),-min(nets.values()))
        option_expected={o['id']:sum((Fraction(risk['scenarios'][sid],10000)*value for sid,value in option_nets[o['id']].items()),Fraction(0)) for o in b['options']}
        earned_positive=all(option_expected[o['id']]>=1 for o in b['options'] if o['funding']=='EARNED')
        eligible=set(b['selected'])==mandatory or expected>=1 and downside<=risk['worst_loss_limit'] and earned_positive
        rows.append({'index':index,'selected':b['selected'],'reserve_amount':b['reserve_amount'],'scenario_responses':scenario_rows,'expected_net':str(expected),'downside':str(downside),'risk_adjusted':str(expected-Fraction(risk['downside_penalty_bps'],10000)*downside),'eligible_after_response':eligible,'option_expected_net_fraction':{k:str(v) for k,v in option_expected.items()}})
    eligible=[r for r in rows if r['eligible_after_response']]
    if not eligible or not any(set(r['selected'])==mandatory for r in eligible):raise ValueError('COMPLETE_FEASIBLE_HOLD_REQUIRED')
    best={s:max(Fraction(r['scenario_responses'][s]['seller_net']) for r in eligible) for s in risk['scenarios']}
    for r in rows:
        regrets={s:best[s]-Fraction(r['scenario_responses'][s]['seller_net']) for s in best}
        r['regret_by_scenario']={s:str(v) for s,v in regrets.items()};r['worst_regret']=str(max(regrets.values()))
    winner=min(eligible,key=lambda r:(Fraction(r['worst_regret']),-Fraction(r['risk_adjusted']),-Fraction(r['expected_net']),r['reserve_amount'],r['selected']))
    inputs={**({'mandatory_ids':sorted(mandatory)} if mandatory else {}),'baskets':copy.deepcopy(baskets),'policy':copy.deepcopy(policy),'risk':copy.deepcopy(risk),'native_state_digest':state_digest}
    return {'schema':SCHEMA,'status':'EXACT_COMPLETE_DECLARED_FEASIBLE_SET','selected_index':winner['index'],'selected_option_expected_net_fraction':winner['option_expected_net_fraction'],'inputs':inputs,'inputs_sha256':digest(inputs),'alternatives':rows,'scenario_best_feasible':{s:str(v) for s,v in best.items()},'response_states_evaluated':count,'authorized_digest':None,'scope':'Current-basket reduced-form positive-net-contribution stress and exact follower best response/minimax regret. Public hypothetical capture/cost/budget, not actual rival behavior or calibrated demand. Costs, negative contributions and native cash locks unchanged. Capacity recourse remains its frozen forecast model; no full-game/horizon equilibrium claim.'}


def rederive(record):
    i=record['inputs'];expected=select_game(i['baskets'],i['policy'],i['risk'],i['native_state_digest'],i.get('mandatory_ids',()))
    if expected!=record:raise ValueError('FINITE_GAME_CERTIFICATE_CHANGED')
    return expected


def compact_certificate(full):
    """Bounded authority-plan reference; complete table is rederived, not copied."""
    row=full['alternatives'][full['selected_index']]
    return {'schema':SCHEMA+'/compact','policy_sha256':digest(full['inputs']['policy']),
        'inputs_sha256':full['inputs_sha256'],'complete_enumeration_sha256':digest(full),
        'feasible_basket_count':len(full['alternatives']),
        'response_states_evaluated':full['response_states_evaluated'],
        'selected':row['selected'],'selected_option_expected_net_fraction':full['selected_option_expected_net_fraction'],
        'selected_responses':{sid:{k:value[k] for k in ('selected_response','seller_net')} for sid,value in row['scenario_responses'].items()},
        'expected_net_fraction':row['expected_net'],'worst_regret':row['worst_regret'],
        'validation':'Requires canonical allocator/rederive_actions reconstruction of complete enumeration from source-bound native options and public policy. Hashes alone are not proof.'}


def investment_expected_net(decision, option_id):
    """Accessor only. Auditor MUST first canonical-rederive the whole decision.

    The executing allocator just computed this certificate; caller-supplied
    compact certificates cannot authenticate their own declared financial value.
    """
    c=decision['strategic_game_certificate']
    if c.get('schema')!=SCHEMA+'/compact' or c['selected']!=decision['selected'] or set(c['selected_option_expected_net_fraction'])!=set(c['selected']):raise ValueError('SOURCE_REDERIVED_COMPACT_GAME_CERTIFICATE_REQUIRED')
    for name in ('policy_sha256','inputs_sha256','complete_enumeration_sha256'):
        h=c[name]
        if not isinstance(h,str) or len(h)!=64 or any(x not in '0123456789abcdef' for x in h):raise ValueError('COMPLETE_GAME_ENUMERATION_HASH_REQUIRED')
    text=c['selected_option_expected_net_fraction'][option_id];value=Fraction(text)
    if not isinstance(text,str) or str(value)!=text:raise ValueError('CANONICAL_EXACT_GAME_RETURN_REQUIRED')
    return value.numerator//value.denominator
