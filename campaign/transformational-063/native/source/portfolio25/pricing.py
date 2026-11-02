"""Bounded strategic pricing scenarios, not calibrated demand or a Nash equilibrium.

Seller is a Stackelberg price leader; a price-setting rival best responds to its
published offer, and buyers choose among the quotes and genuine outside options.
No real quotes, customer records, tokens, payments or outreach are performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

SCHEMA = 'agi-alpha-strategic-portfolio-pricing/v1'
SCENARIOS = (
    {'id':'baseline', 'weight':0.5, 'our_quality_loss':0.035, 'rival_quality_loss':0.12,
     'our_buyer_friction':0.02, 'rival_buyer_friction':0.04, 'rival_cost_ratio':1.15,
     'self_service_cost':0.52, 'self_service_risk':0.2, 'human_price_factor':1.18,
     'no_purchase_loss':1.30, 'temperature':0.10,'accept_prob':0.97,'collect_prob':0.97,
     'cost_shock':1.0,'repeat_probability':0.55,'repeat_horizon':3},
    {'id':'ai_parity_price_war', 'weight':0.3, 'our_quality_loss':0.04, 'rival_quality_loss':0.04,
     'our_buyer_friction':0.025, 'rival_buyer_friction':0.025, 'rival_cost_ratio':0.75,
     'self_service_cost':0.22, 'self_service_risk':0.11, 'human_price_factor':1.12,
     'no_purchase_loss':1.1, 'temperature':0.085,'accept_prob':0.92,'collect_prob':0.94,
     'cost_shock':1.3,'repeat_probability':0.30,'repeat_horizon':3},
    {'id':'differentiated_verified_service', 'weight':0.2, 'our_quality_loss':0.01, 'rival_quality_loss':0.20,
     'our_buyer_friction':0.01, 'rival_buyer_friction':0.06, 'rival_cost_ratio':1.3,
     'self_service_cost':0.62, 'self_service_risk':0.26, 'human_price_factor':1.25,
     'no_purchase_loss':1.55, 'temperature':0.10,'accept_prob':0.985,'collect_prob':0.99,
     'cost_shock':1.0,'repeat_probability':0.68,'repeat_horizon':3},
)


def digest(data: Any) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                                     allow_nan=False).encode('utf-8')).hexdigest()


def finite_nonnegative(value: Any) -> float:
    if isinstance(value, bool) or type(value) not in (int, float):
        raise ValueError('Numeric parameter must be integer or float, not boolean/string')
    try:
        v = float(value)
    except (OverflowError, ValueError, TypeError) as error:
        raise ValueError('Numeric parameter exceeds finite bounds') from error
    if not math.isfinite(v) or v < 0 or v > 1e12:
        raise ValueError('Numeric parameter must be nonnegative, finite and bounded')
    return v


METADATA_FIELDS = {'schema', 'as_of', 'claim', 'primary_comparison', 'secondary_comparison',
    'onboarding_rule', 'pricing_rule', 'metric_limitations', 'wage_loading', 'wage_roles',
    'rfp_evidence', 'competing_ai_price_evidence', 'rank_formula', 'ranking_weights',
    'pricing_evidence_status', 'all_commercial_outcomes', 'onboarding_source_costs_are_not_zero',
    'portfolio_diversification', 'job_count'}
JOB_FIELDS = {'id', 'name', 'sector', 'unit_of_work', 'acceptance',
    'critical_access_or_authority_boundary', 'human_hour_scenario', 'human_role',
    'ai_complete_won_job_cost_scenario_usd', 'ai_qualification_bid_cost_scenario_usd',
    'ai_onboarding_resource_cost_scenario_usd', 'portfolio_scores_1_to_5',
    'rank_weighted_points', 'source_status', 'cost_status', 'market_status', 'rank'}
SCORE_FIELDS = {'autonomy', 'verification', 'recurrence', 'human_cost', 'distribution',
                'differentiation', 'low_liability', 'scalability'}
SCENARIO_FIELDS = set(SCENARIOS[0])


def record(value, required, optional=()):
    if type(value) is not dict or not set(required) <= set(value) or set(value)-set(required)-set(optional):
        raise ValueError('Missing, malformed or unsupported record fields')
    return value


def text(value):
    if type(value) is not str or not value.strip() or len(value) > 10000:
        raise ValueError('Bounded nonempty text required')
    return value


def usd_record(value, required, optional=(), unit=None):
    value = record(value, required, set(optional) | {'currency', 'unit'})
    if value.get('currency', 'USD') != 'USD':
        raise ValueError('Only USD supported; implicit currency conversion refused')
    if 'unit' in value and value['unit'] != unit:
        raise ValueError('Unsupported units')
    return value


def validate_metadata(data):
    record(data, {'metadata', 'jobs'})
    meta = usd_record(data['metadata'], METADATA_FIELDS, unit='USD_per_complete_job')
    if meta['schema'] != 'agi-alpha-commercial-portfolio25/v1':
        raise ValueError('Unknown portfolio version')
    if meta['claim'] != 'PRIORITIZATION_HYPOTHESIS_ONLY' or meta['all_commercial_outcomes'] != 'UNESTABLISHED':
        raise ValueError('Research scope cannot become observed commerce')
    burden = usd_record(meta['wage_loading'],
        {'total_employer_compensation_usd', 'private_industry_wage_usd', 'source', 'scope'}, unit='USD_per_hour')
    wages = finite_nonnegative(burden['private_industry_wage_usd'])
    total = finite_nonnegative(burden['total_employer_compensation_usd'])
    if not wages or not (1 <= total/wages <= 2.5):
        raise ValueError('Invalid wage burden')
    text(burden['source']); text(burden['scope'])
    roles = meta['wage_roles']
    if type(roles) is not dict or not roles:
        raise ValueError('Nonempty wage-role mapping required')
    for name, role in roles.items():
        text(name)
        usd_record(role, {'median_hourly_usd', 'source'}, unit='USD_per_hour')
        if not finite_nonnegative(role['median_hourly_usd']):
            raise ValueError('Positive wage required')
        text(role['source'])
    return meta


def validate_job(job, meta):
    usd_record(job, JOB_FIELDS, unit='USD_per_complete_job')
    for key in JOB_FIELDS - {'human_hour_scenario', 'ai_complete_won_job_cost_scenario_usd',
        'ai_qualification_bid_cost_scenario_usd', 'ai_onboarding_resource_cost_scenario_usd',
        'portfolio_scores_1_to_5', 'rank_weighted_points', 'rank'}:
        text(job[key])
    if job['human_role'] not in meta['wage_roles']:
        raise ValueError('Unknown human wage role')
    for key in ['human_hour_scenario', 'ai_complete_won_job_cost_scenario_usd',
                'ai_qualification_bid_cost_scenario_usd', 'ai_onboarding_resource_cost_scenario_usd',
                'rank_weighted_points']:
        finite_nonnegative(job[key])
    scores = record(job['portfolio_scores_1_to_5'], SCORE_FIELDS)
    if any(not 1 <= finite_nonnegative(value) <= 5 for value in scores.values()):
        raise ValueError('Scores must be within 1..5')
    if type(job['rank']) is not int or not 1 <= job['rank'] <= 25:
        raise ValueError('Portfolio rank must be within 1..25')
    if job['market_status'] != 'UNVALIDATED_COMPETITIVE_DEMAND':
        raise ValueError('Unvalidated research demand scope required')
    return job


def validate_scenario(sc):
    record(sc, SCENARIO_FIELDS)
    text(sc['id'])
    for name in SCENARIO_FIELDS - {'id', 'repeat_horizon'}:
        finite_nonnegative(sc[name])
    for name in ['weight', 'accept_prob', 'collect_prob', 'repeat_probability']:
        if not 0 <= sc[name] <= 1:
            raise ValueError('Scenario probabilities and weights must be within 0..1')
    if not sc['temperature'] or type(sc['repeat_horizon']) is not int or not 0 <= sc['repeat_horizon'] <= 12:
        raise ValueError('Positive temperature and bounded integer repeat horizon required')
    return sc


def validate_scenarios(scenarios):
    if type(scenarios) not in (list, tuple) or not 1 <= len(scenarios) <= 20:
        raise ValueError('Bounded nonempty scenario sequence required')
    for sc in scenarios: validate_scenario(sc)
    if abs(sum(sc['weight'] for sc in scenarios)-1)>1e-8:
        raise ValueError('Scenario weights must sum to 1')
    return scenarios


def positive_human(value):
    if not finite_nonnegative(value):
        raise ValueError('Positive human labor proxy required')
    return value


def _human_labor_proxy(job: dict, data: dict) -> float:
    rate = finite_nonnegative(data['metadata']['wage_roles'][job['human_role']]['median_hourly_usd'])
    burden = data['metadata']['wage_loading']
    avg = finite_nonnegative(burden['total_employer_compensation_usd'])
    wages = finite_nonnegative(burden['private_industry_wage_usd'])
    if not wages or not (1 <= avg/wages <= 2.5):
        raise ValueError('Invalid wage burden')
    return rate * finite_nonnegative(job['human_hour_scenario']) * avg / wages


def _choice_prices(price_us: float | None, price_rival: float | None,
                  human_proxy: float, sc: dict) -> tuple[float, float]:
    """Logit choice is an assumed soft best response to generalized full-service costs."""
    h = human_proxy
    opt = [('self_service', h*(sc['self_service_cost'] + sc['self_service_risk'])),
           ('human', h*sc['human_price_factor']), ('no_purchase', h*sc['no_purchase_loss'])]
    if price_us is not None:
        opt.append(('us', price_us+h*(sc['our_quality_loss']+sc['our_buyer_friction'])))
    if price_rival is not None:
        opt.append(('rival', price_rival+h*(sc['rival_quality_loss']+sc['rival_buyer_friction'])))
    anchor = min(v for _,v in opt)
    temperature = sc['temperature']*h
    if temperature <= 0:
        raise ValueError('Temperature must be positive')
    weights = [(k, math.exp(-(v-anchor)/temperature)) for k,v in opt]
    den = sum(w for _,w in weights)
    result = dict((k,w/den) for k,w in weights)
    return result.get('us',0), result.get('rival',0)


def price_candidates(lower: float, upper: float, n: int = 41) -> list[float]:
    finite_nonnegative(lower); finite_nonnegative(upper)
    if not (math.isfinite(lower) and math.isfinite(upper) and 0 <= lower <= upper):
        raise ValueError('Invalid price interval')
    if type(n) is not int or n < 2 or n > 101:
        raise ValueError('Invalid price grid length')
    return [lower + (upper-lower)*i/(n-1) for i in range(n)]


def _expected_repeat_deliveries(price: float, human_proxy: float, sc: dict,
                               recurrence_score: float = 5) -> float:
    """Bounded discounted recurrence prior; NOT actual LTV or observed retention."""
    if not 1 <= recurrence_score <= 5:
        raise ValueError('Recurrence score outside 1..5')
    horizon = sc['repeat_horizon']
    if type(horizon) is not int or horizon < 0 or horizon > 12:
        raise ValueError('Unsupported repeat horizon')
    base = sc['repeat_probability']
    if not 0 <= base <= 1:
        raise ValueError('Unsupported repeat probability')
    price_effect = max(0.50, min(1.0, 1.0 - 0.35*price/human_proxy))
    r = min(0.95,base*price_effect*(0.60 + 0.08*recurrence_score))
    return sum((0.98*r)**i for i in range(horizon+1))


def _rival_best_response(our_price: float, human_proxy: float, agent_cost: float,
                        sc: dict, recurrence_score: float = 5) -> dict:
    """Rival optimizes its own expected profit after seeing our posted price."""
    rcost = agent_cost * sc['rival_cost_ratio']
    if not sc['accept_prob']*sc['collect_prob']:
        return {'price': None, 'profit': 0.0, 'win_probability': 0.0}
    lower = max(0,rcost/(sc['accept_prob']*sc['collect_prob']))
    upper = max(lower, human_proxy*1.05)
    best = {'price':None,'profit':0.0,'win_probability':0.0}
    for p in price_candidates(lower,upper,31):
        _, pr = _choice_prices(our_price,p,human_proxy,sc)
        profit = pr*_expected_repeat_deliveries(p,human_proxy,sc,recurrence_score)*(sc['accept_prob']*sc['collect_prob']*p-rcost)
        if profit > best['profit']+1e-12:
            best={'price':p,'profit':profit,'win_probability':pr}
    return best


def _evaluate_offer(price: float, human_proxy: float, agent_cost: float, quote_cost: float,
                   sc: dict, onboarding_cost: float = 0, recurrence_score: float = 5) -> dict:
    rival = _rival_best_response(price,human_proxy,agent_cost,sc,recurrence_score)
    pw,_ = _choice_prices(price,rival['price'],human_proxy,sc)
    acc_paid=sc['accept_prob']*sc['collect_prob']
    repeats = _expected_repeat_deliveries(price,human_proxy,sc,recurrence_score)
    contribution = pw*(repeats*(acc_paid*price-agent_cost*sc['cost_shock'])-onboarding_cost)-quote_cost
    return {'price_usd':round(price,2),'buyer_win_probability':pw,
            'rival_price_best_response_usd':None if rival['price'] is None else round(rival['price'],2),
            'expected_net_contribution_per_qualified_quote_usd':contribution,
            'expected_gross_collections_per_qualified_quote_usd':pw*repeats*acc_paid*price,
            'expected_repeat_deliveries_given_win':repeats,
            'conditional_accept_collect_probability':acc_paid}


def _pick_price(job: dict, data: dict, scenarios=SCENARIOS) -> dict:
    h=_human_labor_proxy(job,data)
    positive_human(h)
    agent_cost=finite_nonnegative(job['ai_complete_won_job_cost_scenario_usd'])
    onboard=finite_nonnegative(job['ai_onboarding_resource_cost_scenario_usd'])
    bid_cost=finite_nonnegative(job['ai_qualification_bid_cost_scenario_usd'])
    if not h or not (0 < agent_cost+onboard < h*2):
        raise ValueError('Implausible unbounded human/AI comparison')
    # Agent onboarding is per won job; failed quotes have separate autonomous acquisition cost.
    cost=agent_cost+onboard
    recurrence_score=finite_nonnegative(job['portfolio_scores_1_to_5']['recurrence'])
    if not scenarios or abs(sum(finite_nonnegative(s['weight']) for s in scenarios)-1)>1e-8:
        raise ValueError('Scenario weights must sum to 1')
    lower=min(h, cost/max(min(s['accept_prob']*s['collect_prob'] for s in scenarios),1e-12))
    upper=max(lower,h*1.05)
    candidates=price_candidates(lower,upper,51)
    def eval_many(price):
        rows=[_evaluate_offer(price,h,agent_cost,bid_cost,s,onboard,recurrence_score) for s in scenarios]
        expected=sum(s['weight']*x['expected_net_contribution_per_qualified_quote_usd'] for s,x in zip(scenarios,rows))
        pwin=sum(s['weight']*x['buyer_win_probability'] for s,x in zip(scenarios,rows))
        return {'price':price,'value':expected,'pwin':pwin,'rows':rows}
    optimum={'price':None,'value':0.0,'pwin':0.0,'rows':[]}
    for price in candidates:
        outcome=eval_many(price)
        if outcome['value']>optimum['value']+1e-10:
            optimum=outcome
    anchor=eval_many(min(max(lower,h*.95),upper))
    # No qualification costs are paid if the rational choice is not to bid.
    if optimum['price'] is None:
        return {'job_id':job['id'],'rank':job['rank'],'status':'NO_BID_IN_SCENARIO','human_loaded_labor_proxy_usd':round(h,2),
                'model_win_probability':0.0,'strategy':'CONDITIONAL_STACKELBERG_SCENARIO_ONLY',
                'expected_net_per_qualified_quote_usd':0.0,'human_anchor_95pct_usd':round(anchor['price'],2),
                'human_anchor_expected_net_usd':round(anchor['value'],2)}
    risk=[{'scenario':s['id'],'assumed_weight':s['weight'],
           **{k:round(v,4) if isinstance(v,float) else v for k,v in row.items()}}
          for s,row in zip(scenarios,optimum['rows'])]
    return {'job_id':job['id'],'rank':job['rank'],'status':'SCENARIO_ONLY_NOT_AUTHORIZED_QUOTE',
            'price_usd':round(optimum['price'],2),'human_loaded_labor_proxy_usd':round(h,2),
            'discount_from_human_loaded_labor_proxy_pct':round(100*(1-optimum['price']/h),2),
            'scenario_agent_won_job_cost_usd':round(cost,2),'agent_quote_cost_usd':round(bid_cost,2),
            'model_win_probability':round(optimum['pwin'],4),
            'expected_net_per_qualified_quote_usd':round(optimum['value'],2),
            'human_anchor_95pct_usd':round(anchor['price'],2),
            'human_anchor_expected_net_usd':round(anchor['value'],2),
            'price_changed_from_human_anchor_gt_15_pct':abs(optimum['price']/(h*.95)-1)>0.15,
            'worst_scenario_expected_net_usd':round(min(row['expected_net_contribution_per_qualified_quote_usd'] for row in optimum['rows']),2),
            'scenario_results':risk,'strategy':'STACKELBERG_LEADER_VS_GRID_RIVAL_BEST_RESPONSE_LOGIT_BUYERS',
            'strategic_equilibrium_claim':'NONE','probability_calibrated':False,
            'actual_price_quoted':False,'actual_customers':0,'actual_earned_revenue_usd':0}


def human_labor_proxy(job: dict, data: dict) -> float:
    meta = validate_metadata(data); validate_job(job, meta)
    return positive_human(_human_labor_proxy(job, data))


def choice_prices(price_us, price_rival, human_proxy, sc):
    positive_human(human_proxy); validate_scenario(sc)
    for value in [price_us, price_rival]:
        if value is not None: finite_nonnegative(value)
    return _choice_prices(price_us, price_rival, human_proxy, sc)


def expected_repeat_deliveries(price, human_proxy, sc, recurrence_score=5):
    finite_nonnegative(price); positive_human(human_proxy); validate_scenario(sc)
    if not 1 <= finite_nonnegative(recurrence_score) <= 5:
        raise ValueError('Recurrence score outside 1..5')
    return _expected_repeat_deliveries(price, human_proxy, sc, recurrence_score)


def rival_best_response(our_price, human_proxy, agent_cost, sc, recurrence_score=5):
    finite_nonnegative(our_price); positive_human(human_proxy); finite_nonnegative(agent_cost)
    validate_scenario(sc)
    if not 1 <= finite_nonnegative(recurrence_score) <= 5:
        raise ValueError('Recurrence score outside 1..5')
    return _rival_best_response(our_price, human_proxy, agent_cost, sc, recurrence_score)


def evaluate_offer(price, human_proxy, agent_cost, quote_cost, sc, onboarding_cost=0, recurrence_score=5):
    for value in [price, agent_cost, quote_cost, onboarding_cost]: finite_nonnegative(value)
    positive_human(human_proxy); validate_scenario(sc)
    if not 1 <= finite_nonnegative(recurrence_score) <= 5:
        raise ValueError('Recurrence score outside 1..5')
    return _evaluate_offer(price, human_proxy, agent_cost, quote_cost, sc, onboarding_cost, recurrence_score)


def pick_price(job: dict, data: dict, scenarios=SCENARIOS) -> dict:
    meta = validate_metadata(data); validate_job(job, meta); validate_scenarios(scenarios)
    return _pick_price(job, data, scenarios)


def evaluate_portfolio(data: dict) -> dict:
    meta = validate_metadata(data)
    jobs=data['jobs']
    if type(jobs) is not list or len(jobs)!=25:
        raise ValueError('Portfolio must contain 25 distinct jobs')
    for job in jobs: validate_job(job, meta)
    if len({job['id'] for job in jobs})!=25:
        raise ValueError('Portfolio must contain 25 distinct jobs')
    validate_scenarios(SCENARIOS)
    results=[_pick_price(job,data) for job in jobs]
    return {'schema':SCHEMA,'inputs_sha256':digest(data),'scenario_assumptions':list(SCENARIOS),
            'pricing_objective':'maximize expected cash contribution per qualified quote including bounded repeat deliveries, competing rival best response, autonomous bid/onboarding costs; NO_BID allowed',
            'claim':'ILLUSTRATIVE_POLICY_ONLY','price_cap_scope':'human_loaded_labor_proxy plus 5%; not an observed human retail price',
            'buyer_choice':'assumed logit utility over rival, self service, human and no purchase; uncalibrated',
            'competitor':'follower optimizes expected contribution on finite grid; no equilibrium claim',
            'agent_onboarding':'hypothetical autonomous model/tool expense per won job, no default human labor',
            'market_win_probabilities':'UNCALIBRATED',
            'actual_sales_usd':0,'commercial_flywheel':'UNESTABLISHED',
            'jobs':results}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',default=str(Path(__file__).with_name('jobs.json')))
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        source=Path(args.input)
        if source.stat().st_size>250_000: raise ValueError('Input exceeds 250KB')
        output=Path(args.output)
        if output.exists() or output.is_symlink(): raise ValueError('Refuse overwrite of existing evidence path')
        def unique(pairs):
            result={}
            for key,value in pairs:
                if key in result: raise ValueError('Duplicate JSON field')
                result[key]=value
            return result
        data=json.loads(source.read_text(encoding='utf-8'),object_pairs_hook=unique,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON value')))
        result=evaluate_portfolio(data)
        with output.open('x',encoding='utf-8') as f:
            json.dump(result,f,indent=2,ensure_ascii=False,allow_nan=False)
            f.write('\n')
    except (ValueError, OSError, TypeError, OverflowError) as error:
        parser.exit(2,'REFUSED: '+str(error)+'\n')
    for x in result['jobs'][:5]:
        print(x['rank'],x['job_id'],x.get('price_usd'),x['status'],x.get('model_win_probability'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
