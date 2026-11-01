"""Opt-in finite public requests; no demand, funding or account mutations."""
from .complete_offer_market import request_profile, validate_policy as validate_market

SCHEMA = 'connected-recurring-requests/v1'


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(name + '_INTEGER_REQUIRED')
    return value


def validate_policy(cfg):
    policy = cfg.get('recurring_request_policy')
    fields = {'schema', 'jobs_per_service', 'chunk_size', 'requests'}
    if not isinstance(policy, dict) or set(policy) != fields or policy['schema'] != SCHEMA:
        raise ValueError('EXACT_RECURRING_REQUEST_POLICY_REQUIRED')
    _integer(policy['jobs_per_service'], 'FINITE_ADMITTED_JOBS', 32)
    _integer(policy['chunk_size'], 'FINITE_ADMISSION_CHUNK', 1)
    horizon = 24 * _integer(cfg.get('horizon_days'), 'FINITE_REQUEST_HORIZON', 1)
    population = _integer(cfg.get('customer_pool'), 'FINITE_REQUEST_POPULATION', 1)
    market = cfg.get('complete_offer_policy')
    if not isinstance(market, dict) or 'requested_jobs' not in market:
        raise ValueError('RECURRING_COMPLETE_PUBLIC_MARKET_REQUIRED')
    validate_market(market)
    if any(len(profile['services'])!=1 for profile in market['profiles']):
        raise ValueError('RECURRING_SINGLE_COMPLETE_OUTCOME_PROFILE_REQUIRED')
    requests = policy['requests']
    buyers = {f'SIM-customer-{i:03d}' for i in range(population)}
    if not isinstance(requests, dict) or set(requests) != buyers or set(market['requested_jobs']) != buyers:
        raise ValueError('RECURRING_REQUEST_CUSTOMER_POPULATION_MISMATCH')
    seen = set()
    for buyer, rows in requests.items():
        if not isinstance(rows, list):
            raise ValueError('FINITE_REQUEST_WINDOWS_REQUIRED')
        prior_expiry = -1
        admitted = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'job_id', 'release_hour', 'expiry_hour'}:
                raise ValueError('EXACT_RECURRING_REQUEST_WINDOW_REQUIRED')
            ident = row['job_id']
            if not isinstance(ident, str) or not ident or ident in seen:
                raise ValueError('UNIQUE_GLOBAL_RECURRING_JOB_REQUIRED')
            release = _integer(row['release_hour'], 'REQUEST_RELEASE')
            expiry = _integer(row['expiry_hour'], 'REQUEST_EXPIRY', 1)
            if not prior_expiry <= release < expiry <= horizon:
                raise ValueError('ORDERED_DISJOINT_IN_HORIZON_REQUEST_WINDOWS_REQUIRED')
            prior_expiry = expiry
            admitted.append(ident)
            seen.add(ident)
        if admitted != market['requested_jobs'][buyer]:
            raise ValueError('RECURRING_REQUESTS_DIFFER_FROM_COMPLETE_ADMISSION')
    return policy


def request_ids(cfg, buyer_id, when, used_jobs=(), consumed_jobs=()):
    _integer(when, 'PUBLIC_REQUEST_TIME')
    requests = cfg['recurring_request_policy']['requests']
    if buyer_id not in requests:
        raise ValueError('PUBLIC_REQUEST_BUYER_REQUIRED')
    unavailable = set(used_jobs) | set(consumed_jobs)
    return [row['job_id'] for row in requests[buyer_id]
            if row['release_hour'] <= when < row['expiry_hour'] and row['job_id'] not in unavailable]


def observed_spend(buyer):
    outside = _integer(buyer.get('outside_spend', 0), 'PUBLIC_OUTSIDE_SPEND')
    settled = _integer(buyer.get('our_settled_spend', 0), 'PUBLIC_SETTLED_SPEND')
    pending = buyer.get('pending_commitments', {})
    if not isinstance(pending, dict):
        raise ValueError('PUBLIC_PENDING_COMMITMENTS_REQUIRED')
    return outside + settled + sum(_integer(v, 'PUBLIC_COMMITMENT') for v in pending.values())


def public_candidate(cfg, buyer, when, used_jobs=(), consumed_jobs=()):
    if not request_ids(cfg, buyer['id'], when, used_jobs, consumed_jobs):
        return False
    profile = request_profile(cfg['complete_offer_policy'], buyer['id'])
    possible_budget = max(atom['budget_microUSD'] for atom in profile['atoms']) - observed_spend(buyer)
    minimum_price = min(price for grid in profile['price_grids'].values() for price in grid)
    if possible_budget < minimum_price:return False
    from .strategic_commerce import _exact_market_probability
    context={'profile':profile,'observed_spend':observed_spend(buyer),'rival_available':True}
    direct=sum(cfg.get(k,0) for k in ('production_cost','supplier_unit_cost','support_cost'))
    direct+=0 if buyer.get('onboarded',False) else cfg.get('onboarding_cost',0)
    evaluation=cfg.get('qualification_cost',0)+cfg.get('exposure_cost',0)
    for service,grid in profile['price_grids'].items():
        for price in grid:
            fee=(price*cfg.get('payment_bps',0)+9999)//10000+cfg.get('payment_fixed',0)
            if _exact_market_probability(context,service,price)*max(0,price-direct-fee)>evaluation:return True
    return False


def consumed_job_ids(cfg, decisions, *, before=None):
    if before is not None:
        _integer(before, 'PUBLIC_DECISION_CUTOFF')
    requests = cfg['recurring_request_policy']['requests']
    by_job = {row['job_id']: (buyer, row) for buyer, rows in requests.items() for row in rows}
    consumed = set()
    for decision in decisions:
        if decision.get('kind') not in {'offer', 'outside_choice'}:
            continue
        when = _integer(decision.get('time'), 'PUBLIC_DECISION_TIME')
        if before is not None and when >= before:
            continue
        ident = decision.get('request_job_id')
        if ident not in by_job:
            raise ValueError('RECURRING_DECISION_REQUEST_BINDING_REQUIRED')
        buyer, row = by_job[ident]
        if (decision.get('customer_id') != buyer
                or not row['release_hour'] <= when < row['expiry_hour']):
            raise ValueError('RECURRING_DECISION_OUTSIDE_REQUEST_WINDOW')
        if ident in consumed:
            raise ValueError('RECURRING_REQUEST_ALREADY_CONSUMED')
        if decision.get('buyer_choice') in {'us', 'human', 'rival', 'self_service'}:
            consumed.add(ident)
    return consumed
