"""Fresh-account authored prospective terms; no history migration or real guarantee."""
import copy
POLICY_SCHEMA="agi-alpha/fresh-connected-prospective-policy/v1"

def default_policy():
    return {'schema': POLICY_SCHEMA, 'mode': 'prospective', 'protection_hours': 48,
            'residual_microUSD': 0, 'premium_microUSD': 0, 'coverage_limit_microUSD': 0,
            'deductible_microUSD': 0, 'payout_delay_hours': 0, 'exclusions': [],
            'jurisdiction': 'Authored synthetic jurisdiction; no legal finality established',
            'counterparty_obligations': 'Buyer pays modeled price; producer supplies independently accepted artifact; claims remain producer obligations'}


def validate_policy(raw, *, exact_money=False):
    if not isinstance(raw,dict) or set(raw)!=set(default_policy()):
        raise ValueError('EXACT_FRESH_PROSPECTIVE_POLICY_REQUIRED')
    p=copy.deepcopy(raw)
    if p['schema']!=POLICY_SCHEMA or p['mode']!='prospective':
        raise ValueError('EXPLICIT_FRESH_PROSPECTIVE_POLICY_REQUIRED')
    for key in ['protection_hours', 'residual_microUSD', 'premium_microUSD',
                'coverage_limit_microUSD', 'deductible_microUSD', 'payout_delay_hours']:
        if type(p[key]) is not int or (p[key] < 0 or ((not exact_money or not key.endswith('_microUSD')) and p[key] > 10**12)):
            raise ValueError('BOUNDED_OPERATING_POLICY_INTEGER_REQUIRED')
    if not 1 <= p['protection_hours'] <= 24 * 365:
        raise ValueError('FINITE_POSITIVE_OPERATING_PROTECTION_REQUIRED')
    if exact_money:
        from commercial.terms_exact_v2 import prospective_terms
    else:
        from commercial.terms import prospective_terms
    prospective_terms('policy-validation', max(1_000_000, p['residual_microUSD']),
                      1 + p['protection_hours'], 1, residual=p['residual_microUSD'],
                      premium=p['premium_microUSD'], coverage_limit=p['coverage_limit_microUSD'],
                      deductible=p['deductible_microUSD'], exclusions=p['exclusions'],
                      payout_delay_hours=p['payout_delay_hours'], jurisdiction=p['jurisdiction'],
                      counterparty_obligations=p['counterparty_obligations'])
    if p['mode'] == 'permanent' and any(p[k] for k in ['residual_microUSD', 'premium_microUSD', 'coverage_limit_microUSD', 'deductible_microUSD', 'payout_delay_hours']):
        raise ValueError('PERMANENT_CONTROL_HAS_NO_PROSPECTIVE_CHARGES_OR_COVERAGE')
    return p


def terms_for(order_id, price, collection, policy, fee, *, deadline=None, exact_money=False):
    if exact_money:
        from commercial.terms_exact_v2 import prospective_terms
    else:
        from commercial.terms import prospective_terms
    p = validate_policy(policy,exact_money=exact_money)
    if p['mode'] == 'permanent':
        return None
    return prospective_terms(order_id, price, max(collection, deadline or collection) + p['protection_hours'], collection,
                             residual=p['residual_microUSD'], premium=p['premium_microUSD'], fee=fee,
                             coverage_limit=p['coverage_limit_microUSD'], deductible=p['deductible_microUSD'],
                             exclusions=p['exclusions'], payout_delay_hours=p['payout_delay_hours'],
                             jurisdiction=p['jurisdiction'], counterparty_obligations=p['counterparty_obligations'])



def capital_metrics(result):
    """Observed native liquidity and narrow, explicitly scoped deferral diagnoses."""
    tape=result['owned_account']['ledger'];actions=tape['actions'];summaries=[a['before'] for a in actions]+[result['summary']]
    maturities=[a for a in actions if a['op']=='mature']
    individual=[];decision_local=[]
    from .strategic_commerce import select
    for wrapper in sorted(result.get('joint_actions',{}).values(),key=lambda value:value['time']):
        if 'cash_diagnostic_available' in result['config']:
            from .strategic_commerce import cash_opportunity_diagnostic
            if 'strategic_game' in wrapper['allocation']:
                # The available relaxation helper does not preserve this game's
                # objective. Report unknown, never a fake zero or a late run failure.
                diagnostic={'status':'UNAVAILABLE','reason':'STRATEGIC_GAME_CASH_DIAGNOSTIC_UNAVAILABLE'}
            elif 'category_upfront_caps' in wrapper['allocation']:
                diagnostic={'status':'UNAVAILABLE','reason':'CATEGORY_BUDGET_CASH_DIAGNOSTIC_UNAVAILABLE'}
            else:
                diagnostic=cash_opportunity_diagnostic(wrapper['allocation'],relaxed_available=max(wrapper['allocation']['observation']['summary']['available'],result['config']['cash_diagnostic_available']),declared_allocation_ceiling=result['config']['strategic_allocation_policy']['risk']['authorized_allocation'],operating_envelope=wrapper['operating_envelope'])
            decision_local.append({'time':wrapper['time'],'diagnostic':diagnostic})
        for delivery in wrapper['allocation']['deliveries']:
            selection=delivery['selection']
            if selection['decision']['selected'] is not None:continue
            p=selection['problem'];public=copy.deepcopy(p['public']);public['available']=max(public['available'],10**15)
            unlimited=select(p['policy'],p['method_policy'],p['job_id'],p['offer'],p['memory'],public,market_context=p.get('market_context'))
            if unlimited['decision']['selected'] is not None and unlimited['decision']['selected']['required_current_cash']>p['public']['available']:
                individual.append({'time':wrapper['time'],'customer_id':delivery['customer_id'],
                    'actual_available':p['public']['available'],
                    'positive_option_cash_required':unlimited['decision']['selected']['required_current_cash']})
    return {'schema':'fresh-capital-observations/v1','minimum_native_available':min(s['available'] for s in summaries),
        'minimum_native_unrestricted_earned':min(s['unrestrictedEarned'] for s in summaries),
        'maturity_events':len(maturities),'tail_release_at_maturity':sum(a['before']['tailReserve']-a['after']['tailReserve'] for a in maturities),
        'maturity_cash_change':sum(a['after']['cash']-a['before']['cash'] for a in maturities),
        'maturity_profit_change':sum(a['after']['profit']-a['before']['profit'] for a in maturities),
        'engine_reported_liquidity_declines':sum(d['kind']=='liquidity_decline' for d in result['decisions']),
        'individually_cash_infeasible_positive_quotes':individual,
        'decision_local_cash_opportunities':decision_local,
        'deferral_scope':'Joint candidates have a positive isolated quote only when cash is relaxed diagnostically; this is NOT a count or lower bound of causal deferrals because capacity and basket constraints may also bind. No hypothetical cash funds execution. Incumbent reported liquidity declines also include nonpositive-margin refusals; not all are proven cash-caused.',
        'final_protection':{k:result['summary'][k] for k in ['cash','available','unrestrictedEarned','tailReserve','custodyReserve','workingCapital','payables']}}
