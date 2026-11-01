"""One optional public owned-audience definition and dated contact admission."""
from fractions import Fraction

SCHEMA = 'connected-audience/v1'


def validate_policy(cfg):
    policy = cfg['audience_policy']
    if not isinstance(policy, dict) or set(policy) != {'schema', 'owned_audience_count'} or policy['schema'] != SCHEMA:
        raise ValueError('EXPLICIT_UNIFIED_AUDIENCE_POLICY_REQUIRED')
    count = policy['owned_audience_count']
    if type(count) is not int or not 0 <= count <= cfg['customer_pool']:
        raise ValueError('OWNED_AUDIENCE_MUST_BE_REGISTERED_POPULATION_SUBSET')
    if any(terms.get('owned_audience_count', 4) != count for terms in cfg['channels'].values()):
        raise ValueError('CHANNEL_AND_INITIAL_OWNED_AUDIENCE_MUST_MATCH')
    return policy


def population_ids(buyers):
    ids = sorted(buyers if isinstance(buyers, dict) else (row if isinstance(row, str) else row['id'] for row in buyers))
    if len(ids) != len(set(ids)) or any(not isinstance(ident, str) or not ident for ident in ids):
        raise ValueError('UNIQUE_PUBLIC_AUDIENCE_IDENTITIES_REQUIRED')
    return ids


def owned_customer_ids(cfg, buyers):
    count = validate_policy(cfg)['owned_audience_count'] if 'audience_policy' in cfg else 4
    return set(population_ids(buyers)[:count])


def channel_population(buyers, terms):
    return population_ids(buyers)[terms.get('owned_audience_count', 4):]


def reachability(cfg, buyers, contacts, day, contract_id):
    """Admit public contact possibilities without sampling future outcomes.

    Fatigue is permanent for this finite contract. Cooldown and dated need are
    temporary; a later acquisition can be useful even when none is ready now.
    This is a reach bound, not a promise of exposure, conversion or collection.
    """
    if type(day) is not int or day < 0:
        raise ValueError('DATED_PUBLIC_AUDIENCE_REQUIRED')
    if 'audience_policy' in cfg:
        validate_policy(cfg)
    terms = cfg['channels'][contract_id]
    byid = buyers if isinstance(buyers, dict) else {row['id']: row for row in buyers}
    ids = population_ids(buyers)
    owned = set(ids[:terms.get('owned_audience_count', 4)])
    first = day + terms['lead_days']
    last = min(first + terms['duration_days'], cfg['horizon_days']) - 1
    ready = []; delayed = []; blocked = {}; earliest = {}; remaining = {}
    disabled = terms['activation_reliability_bps'] == 0 or terms['realization_bps'] == 0
    for ident in ids:
        buyer = byid[ident]
        history = contacts.get(ident, [])
        if ident in owned:
            blocked[ident] = 'OWNED'
        elif buyer.get('onboarded', False) and buyer.get('active', True):
            blocked[ident] = 'ALREADY_ACTIVE_CUSTOMER'
        elif len(history) >= terms.get('max_contacts_per_customer', 3):
            blocked[ident] = 'CONTACTS_EXHAUSTED'
        elif buyer.get('pending_commitments', {}):
            blocked[ident] = 'PENDING_ORDER'
        elif disabled:
            blocked[ident] = 'NO_CONTRACT_REALIZATION'
        else:
            need = (buyer.get('next_need_time', 0) + 23) // 24
            cooldown = max((row['day'] for row in history), default=-terms.get('contact_cooldown_days', 7)) + terms.get('contact_cooldown_days', 7)
            when = max(first, need, cooldown)
            earliest[ident] = when
            remaining[ident] = terms.get('max_contacts_per_customer', 3) - len(history)
            if first > last:
                blocked[ident] = 'NO_LIVE_WINDOW'
            elif when > last:
                blocked[ident] = 'TEMPORARILY_UNAVAILABLE_IN_WINDOW'
            elif when > first:
                delayed.append(ident)
            else:
                ready.append(ident)
    potential = sorted(ready + delayed)
    capacity = sum(min(remaining[ident], 1 + (last - earliest[ident]) // max(1, terms.get('contact_cooldown_days', 7))) for ident in potential)
    expected_slots = Fraction(terms['slots_per_day'] * max(0, last - first + 1) * terms['activation_reliability_bps'] * terms['realization_bps'] * (10000 - terms['overlap_bps']), 10000**3)
    return {'schema': SCHEMA, 'contract_id': contract_id, 'day': day,
        'owned_customer_ids': sorted(owned), 'prospect_customer_ids': [ident for ident in ids if ident not in owned],
        'activation_day': first, 'last_live_day': last,
        'ready_customer_ids': ready, 'delayed_customer_ids': delayed,
        'potential_customer_ids': potential, 'earliest_contact_day': earliest,
        'blocked': blocked, 'remaining_contact_capacity': capacity,
        'expected_contact_bound_fraction': str(min(Fraction(capacity), expected_slots)),
        'scope': 'PUBLIC_POSSIBILITY_BOUND_NOT_EXPOSURE_OR_CUSTOMER_OR_REVENUE'}
