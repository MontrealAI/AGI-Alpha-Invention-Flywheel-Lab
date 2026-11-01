"""Opt-in, day-zero public complete-offer acquisition; never general seed expansion."""
from fractions import Fraction
from commercial.ledger import digest

SCHEMA = 'connected-startup-acquisition/v1'


def validate_policy(cfg):
    policy = cfg['startup_acquisition_policy']
    if not isinstance(policy, dict) or set(policy) != {'schema', 'contract_ids', 'conversion_bps', 'planning_cost_microUSD'} or policy['schema'] != SCHEMA:
        raise ValueError('EXPLICIT_STARTUP_ACQUISITION_CONTRACT_REQUIRED')
    if not all(key in cfg for key in ('complete_offer_policy', 'strategic_policy', 'strategic_allocation_policy', 'channel_menu_policy')) or 'sequence' in cfg['strategic_allocation_policy'] or 'strategic_game' in cfg['strategic_allocation_policy']:
        raise ValueError('STARTUP_COMPLETE_PUBLIC_SINGLE_OPPORTUNITY_REQUIRED')
    if cfg['strategic_policy'].get('ranking_arithmetic') != 'exact-rational-v1' or cfg['strategic_policy'].get('rival_response') != 'observed_quote':
        raise ValueError('STARTUP_EXACT_PUBLIC_QUOTE_RANKING_REQUIRED')
    ids = policy['contract_ids']
    if not isinstance(ids, list) or not ids or ids != sorted(set(ids)) or any(ident not in cfg['channel_menu_policy']['contract_ids'] for ident in ids):
        raise ValueError('STARTUP_DECLARED_PAID_CHANNELS_REQUIRED')
    if type(policy['conversion_bps']) is not int or not 0 <= policy['conversion_bps'] <= 10000 or type(policy['planning_cost_microUSD']) is not int or policy['planning_cost_microUSD'] <= 0:
        raise ValueError('STARTUP_PUBLIC_CONVERSION_AND_PREPAID_EVALUATION_REQUIRED')
    return policy


def reference(receipt):
    if receipt['funding'] == 'EARNED':
        return receipt['plan_id']
    if receipt['funding'] != 'SEED' or receipt['plan_id'] is not None:
        raise ValueError('STARTUP_SEED_CANNOT_CLAIM_EARNED_PLAN')
    return 'startup-seed-' + digest({'id': receipt['id'], 'source': receipt['source_sha256'], 'work': receipt['work_sha256']})[:32]


def validate_option(option):
    execution = option.get('execution', {})
    certificate = execution.get('startup_contract')
    if option.get('kind') != 'acquisition' or execution.get('funding') != 'SEED_OR_EARNED' or not isinstance(certificate, dict) or certificate.get('schema') != SCHEMA or certificate.get('time') != 0 or certificate.get('authority') != [] or option.get('id') != 'startup-channel-' + execution.get('contract_id', ''):
        raise ValueError('TYPED_STARTUP_ACQUISITION_ONLY')
    if certificate.get('option_inputs_sha256') != digest({k: v for k, v in execution.items() if k != 'startup_contract'}):
        raise ValueError('STARTUP_OPTION_CHANGED')
    return option


def _prepared_menu(offer_menu_fn, market):
    from .engine import _offer_menu
    if offer_menu_fn is _offer_menu:
        return lambda state, jobs, buyer, cfg: offer_menu_fn(state, jobs, buyer, cfg, _market=market)
    return offer_menu_fn


def _admission_frontier(cfg, buyers, jobs, menu_fn):
    """Conservative first-opportunity admission under initial native priority.

    Every possible standalone nonempty predecessor consumes a shortlist place,
    whether profitable, physically feasible or currently reachable. This does
    not grant unknown buyers access or assume later cooldown/priority changes.
    """
    frontier = {}
    preceding = 0
    blocked_work = frozenset()
    cap = cfg['strategic_allocation_policy']['max_customers']
    for ident in sorted(buyers, key=lambda key: (buyers[key]['next_need_time'], key)):
        if preceding >= cap:
            break
        buyer = dict(buyers[ident], id=ident)
        frontier[ident] = (preceding, blocked_work)
        # Never tentatively deduplicate blocker menus: absent earlier buyers
        # can leave work available to multiple later possible predecessors.
        if menu_fn({'used_jobs': []}, jobs, buyer, cfg):
            preceding += 1
            work = set()
            for job_id in cfg['complete_offer_policy']['requested_jobs'][ident]:
                entry = jobs.get(job_id)
                if entry is not None and entry['job']['accepted'] and entry['artifact'].get('outcome_scope') == 'complete_outcome':
                    work.update(entry['job']['work_keys'])
            blocked_work = blocked_work.union(work)
    return frontier


def _frontier_menu(menu, admission):
    return [(entry, offer, anchor) for entry, offer, anchor in menu
            if not admission[1].intersection(entry['job']['work_keys'])]


def _future_operating_counts(cfg, terms, lead, days, owned, buyers, jobs, market, menu_fn):
    """Public upper bounds, never predictions of private future activity.

    The current planning prefix is already prepaid or held by ``operating``.
    Owned buyers can remain candidates even with no requested work or purchase.
    Potential prospect activity is bounded throughout the window, including
    earlier access from another allowed channel. This grants no such access.
    Empty menus cost outreach but consume no paid evaluation or shortlist slot.
    """
    future_days = lead + days - 1
    menu_sizes = {}
    for ident, buyer in sorted(buyers.items()):
        # Day-zero tentative quotes need not execute. Their source work can
        # still be evaluated later, so do not remove it from this cost bound.
        menu = menu_fn({'used_jobs': []}, jobs, dict(buyer, id=ident), cfg)
        menu_sizes[ident] = max(len(menu), len(market.profile(ident)['services'])) if menu else 0
    cap = cfg['strategic_allocation_policy']['max_customers']
    daily = sum(sorted(menu_sizes.values(), reverse=True)[:cap])
    return {'future_planning_days': future_days, 'channel_live_days': days,
        'attempt_slots': terms['slots_per_day'] * days,
        'continuing_owned_outreach_units': future_days * len(owned),
        'continuing_prospect_outreach_units': future_days * (len(buyers) - len(owned)),
        'maximum_menu_size': max(menu_sizes.values(), default=0),
        'daily_qualification_bound': daily,
        'qualification_evaluations': future_days * daily,
        'maintenance_days': future_days}


def preflight(cfg, buyers, jobs, offer_menu_fn, used_jobs=(), *, _market=None, _frontier=None):
    """No valuation or paid reservation for an inconsistent or empty audience.

    This startup guard does not repair legacy owned-access semantics. It refuses
    to rely on them unless initialized public ownership and channel exclusion
    agree exactly. The separately owned unified-access repair remains required.
    """
    policy = validate_policy(cfg)
    known = {ident for ident, buyer in buyers.items() if buyer['known']}
    eligible = []
    slots = cfg['initial_slots']
    if cfg['supplier_outage_start_day'] <= 0 < cfg['supplier_outage_start_day'] + cfg['supplier_outage_days']:
        slots = 0
    if not slots:
        return []
    from .complete_offer_market import compile_market
    market = compile_market(cfg['complete_offer_policy']) if _market is None else _market
    menu_fn = _prepared_menu(offer_menu_fn, market)
    frontier = _frontier
    for contract_id in policy['contract_ids']:
        terms = cfg['channels'][contract_id]
        owned = set(sorted(buyers)[:terms['owned_audience_count']])
        if owned != known or owned == set(buyers) or terms['activation_reliability_bps'] == 0 or terms['realization_bps'] == 0:
            continue
        lead = terms['lead_days']
        if lead < 1:
            continue
        if min(terms['duration_days'], cfg['horizon_days'] - lead) <= 0 or lead * 24 + cfg['production_hours'] + cfg['acceptance_hours'] + cfg['clearing_hours'] >= cfg['horizon_days'] * 24:
            continue
        if frontier is None:
            frontier = _admission_frontier(cfg, buyers, jobs, menu_fn)
        for ident, buyer in sorted(buyers.items()):
            if ident in owned or buyer['onboarded'] or buyer.get('pending_commitments', {}) or ident not in frontier:
                continue
            menu = _frontier_menu(menu_fn({'used_jobs': sorted(used_jobs)}, jobs, dict(buyer, id=ident), cfg), frontier[ident])
            if any(offer['capacity_units'] <= slots for entry, offer, anchor in menu):
                eligible.append(contract_id)
                break
    return eligible


def options(cfg, arm, moment, snapshot, operating, jobs, used_jobs, buyers, scenarios, offer_menu_fn, *, prior_orders=False, prior_investments=False):
    policy = validate_policy(cfg)
    if moment != 0 or arm == 'baseline' or prior_orders or prior_investments:
        return []
    available = max(0, snapshot['summary']['available'] - operating)
    slots = cfg['initial_slots']
    if cfg['supplier_outage_start_day'] <= 0 < cfg['supplier_outage_start_day'] + cfg['supplier_outage_days']:
        slots = 0
    if not slots or not available or snapshot['summary'].get('investmentStopped'):
        return []
    from .complete_offer_market import compile_market
    from .strategic_commerce import select
    from .joint_planning import investment_option
    market = compile_market(cfg['complete_offer_policy'])
    menu_fn = _prepared_menu(offer_menu_fn, market)
    frontier = _admission_frontier(cfg, buyers, jobs, menu_fn)
    result = []
    for contract_id in preflight(cfg, buyers, jobs, menu_fn, used_jobs, _market=market, _frontier=frontier):
        terms = cfg['channels'][contract_id]
        lead = terms['lead_days']
        days = min(terms['duration_days'], cfg['horizon_days'] - lead)
        if days <= 0 or lead * 24 + cfg['production_hours'] + cfg['acceptance_hours'] + cfg['clearing_hours'] >= cfg['horizon_days'] * 24:
            continue
        owned = set(sorted(buyers)[:terms['owned_audience_count']])
        public = []
        used = set(used_jobs)
        for ident, buyer in sorted(buyers.items()):
            if ident in owned or buyer['known'] or buyer['onboarded'] or buyer.get('pending_commitments',{}) or ident not in frontier:
                continue
            tentative = {'used_jobs': sorted(used)}
            choices = []
            menu = _frontier_menu(menu_fn(tentative, jobs, dict(buyer,id=ident), cfg), frontier[ident])
            for entry, offer, anchor in menu:
                units = offer['capacity_units']
                if units > slots:
                    continue
                facts = {'anchor': anchor, 'public_rival_price': int(anchor * cfg['price_pressure_bps'] / 10000),
                         'base_cost': units * (cfg['production_cost'] + cfg['supplier_unit_cost'] + cfg['support_cost']) + cfg['onboarding_cost'] + cfg.get('prospective_policy', {}).get('premium_microUSD', 0),
                         'payment_bps': cfg['payment_bps'], 'payment_fixed': cfg['payment_fixed'],
                         'available': available, 'reserve_buffer': 1000000, 'quote_cost': 0,
                         'native_state_digest': snapshot['state_digest'], 'profit_tax_bps': cfg['profit_tax_bps']}
                selected = select(cfg['strategic_policy'], cfg.get('mechanism_policy'), entry['job']['id'], offer, None, facts,
                                  market_context=market.context(ident, 0))
                for row in selected['candidates']:
                    conservative = min(Fraction(f['net_after_modeled_tax_fraction']) for f in row['forecasts'])
                    if conservative > 0:
                        choices.append((conservative, entry['job']['id'], units, row['required_current_cash'], digest(selected)))
            if not choices:
                continue
            best = sorted(choices, key=lambda x: (-x[0], x[1], x[2], x[3], x[4]))[0]
            public.append({'customer_id': ident, 'job_id': best[1], 'capacity_units': best[2],
                           'conservative_net_fraction': str(best[0]), 'current_cash_lock': best[3], 'selection_sha256': best[4],
                           'preceding_possible_menus': frontier[ident][0], 'higher_priority_requested_work_sha256': digest(sorted(frontier[ident][1]))})
            used.add(best[1])
        if not public:
            continue
        # One declared request per unique prospect; no free repeats or invented
        # conversion. Worst public modeled collection belief is already charged.
        pool = len(set(buyers) - owned)
        contacts = min(Fraction(pool), Fraction(terms['slots_per_day'] * days * terms['activation_reliability_bps'] * terms['realization_bps'] * (10000 - terms['overlap_bps']), 10000**3))
        qualified_contacts = contacts * Fraction(len(public), pool)
        outage_start = cfg['supplier_outage_start_day']
        outage_end = outage_start + cfg['supplier_outage_days']
        usable_days = days - max(0, min(lead + days, outage_end) - max(lead, outage_start))
        prospects = min(qualified_contacts * Fraction(policy['conversion_bps'] * cfg['arrival_bps'], 10000**2), Fraction(slots * usable_days, max(p['capacity_units'] for p in public)))
        margin = min(Fraction(p['conservative_net_fraction']) for p in public)
        future_costs = _future_operating_counts(cfg, terms, lead, days, owned, buyers, jobs, market, menu_fn)
        outreach_units = sum(future_costs[k] for k in ('attempt_slots', 'continuing_owned_outreach_units', 'continuing_prospect_outreach_units'))
        future_costs.update(outreach_microUSD=outreach_units * cfg['exposure_cost'],
            qualification_microUSD=future_costs['qualification_evaluations'] * cfg['qualification_cost'],
            maintenance_microUSD=future_costs['maintenance_days'] * cfg['maintenance_daily'])
        if 'refusal_recourse_policy' in cfg:
            from .refusal_recourse import validate_policy as validate_recourse, SELECTIVE_SCHEMA
            recourse = validate_recourse(cfg['refusal_recourse_policy'])
            future_days = future_costs['future_planning_days']
            daily_evaluation = recourse['daily_evaluation_cost'] if recourse['schema'] == SELECTIVE_SCHEMA else 0
            daily_allowance = recourse['daily_planning_cost']
            future_costs.update(recourse_policy_sha256=digest(recourse), recourse_planning_days=future_days,
                recourse_daily_evaluation_microUSD=daily_evaluation, recourse_daily_allowance_microUSD=daily_allowance,
                recourse_evaluation_microUSD=future_days*daily_evaluation,
                recourse_allowance_microUSD=future_days*daily_allowance)
        evaluation = sum(future_costs.get(k, 0) for k in ('outreach_microUSD', 'qualification_microUSD', 'maintenance_microUSD',
            'recourse_evaluation_microUSD', 'recourse_allowance_microUSD'))
        benefit = prospects * margin - evaluation
        invoice = terms['price_microUSD'] + terms['support_microUSD']
        net = benefit.numerator // benefit.denominator - invoice
        cash_lock = max(p['current_cash_lock'] for p in public) * slots + evaluation
        if net <= 0 or invoice + cash_lock > available:
            continue
        option = investment_option('startup-channel-' + contract_id, 'acquisition', invoice, net, scenarios, 0, terms)
        option['execution'].update(funding='SEED_OR_EARNED', contract_id=contract_id,
                                   cash_lock=cash_lock,
                                   forecast_scope='DAY_ZERO_PUBLIC_COMPLETE_OFFERS; worst declared collection belief, explicit conversion haircut and conservative future full-menu evaluation/maintenance/recourse costs, no hidden future draws; not demand, income or spendable cash.')
        execution = option['execution']
        execution['startup_contract'] = {'schema': SCHEMA, 'time': 0, 'policy_sha256': digest(policy),
            'native_state_digest': snapshot['state_digest'], 'observed_available': snapshot['summary']['available'],
            'operating_commitment': operating, 'current_slots': slots, 'qualified_public_offers': public,
            'future_cost_envelope': future_costs, 'future_operating_cash_lock': evaluation,
            'admission_scope': 'First opportunity under initial native priority; every possible earlier nonempty menu competes for the existing shortlist, and all its admitted requested complete work is excluded. No later priority improvement or free access assumed.',
            'contact_fraction': str(contacts), 'qualified_contact_fraction': str(qualified_contacts), 'prospect_fraction': str(prospects), 'net_fraction': str(benefit - invoice),
            'option_inputs_sha256': digest(execution), 'authority': []}
        validate_option(option)
        result.append(option)
    return result
