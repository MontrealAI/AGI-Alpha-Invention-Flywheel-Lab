"""Ordinary finite repeat-contribution forecast; no account or future-draw access."""
from fractions import Fraction
from commercial.ledger import digest
from .audience055 import reachability
from .complete_offer_market import compile_market, _choices
from .recurring055 import observed_spend

SCHEMA = 'connected-recurring-acquisition/v1'


def _calendar(cfg, buyers, jobs, day, reach, slots, used_jobs, consumed_jobs):
    from .engine import _offer_menu
    first = reach['activation_day'] * 24
    horizon = cfg['horizon_days'] * 24
    unavailable = set(used_jobs) | set(consumed_jobs)
    admitted_jobs = list(used_jobs)
    targets = set(reach['potential_customer_ids'])
    capacity = min(slots, cfg['initial_slots'])
    rows = sorted((row['release_hour'], ident, row) for ident, requests in cfg['recurring_request_policy']['requests'].items() for row in requests)
    load = {}; ready = {}; result = {ident: [] for ident in buyers}
    for _, ident, row in rows:
        if row['job_id'] in unavailable or row['expiry_hour'] <= day * 24 or row['job_id'] not in jobs:
            continue
        start = max(row['release_hour'], day * 24, ready.get(ident, buyers[ident].get('next_need_time', 0)))
        if ident in targets:
            start = max(start, first, reach['earliest_contact_day'].get(ident, 0) * 24)
        when = ((start + 23) // 24) * 24
        while when < row['expiry_hour'] and when + cfg['production_hours'] + cfg['acceptance_hours'] + cfg['clearing_hours'] < horizon:
            d = when // 24
            outage = cfg['supplier_outage_start_day'] <= d < cfg['supplier_outage_start_day'] + cfg['supplier_outage_days']
            menu = _offer_menu({'used_jobs': admitted_jobs, 'queue': [{'time': when}], 'decisions': []}, jobs, dict(buyers[ident], id=ident), cfg)
            admitted = [(entry, offer) for entry, offer, _ in menu if entry['job']['id'] == row['job_id']
                and entry['job']['accepted'] and entry['artifact'].get('outcome_scope') == 'complete_outcome'
                and offer.get('scope') == 'complete_outcome' and type(offer.get('capacity_units')) is int
                and 0 < offer['capacity_units'] <= capacity and entry['job'].get('work_keys')
                and len(entry['job']['work_keys']) == len(set(entry['job']['work_keys']))]
            if not admitted:
                break
            entry, offer = admitted[0]
            if not outage and load.get(d, 0) + offer['capacity_units'] <= capacity:
                break
            when += 24
        else:
            continue
        if not admitted:
            continue
        load[when // 24] = load.get(when // 24, 0) + offer['capacity_units']
        admitted_jobs.append(row['job_id'])
        ready[ident] = when + cfg['production_hours'] + cfg['acceptance_hours'] + cfg['clearing_hours'] + 7 * 24
        result[ident].append({**row, 'quote_hour': when, 'capacity_units': offer['capacity_units'],
            'work_keys': entry['job']['work_keys'], 'accepted_offer_sha256': digest({'job': entry['job'], 'artifact': entry['artifact'], 'offer': offer}),
            'maximum_outreach_days': (row['expiry_hour'] - 1 - when) // 24 + 1})
    return result


def _buyer_forecast(cfg, profile, buyer, requests, price, collection, last_contact_hour):
    service = profile['services'][0]
    spend = observed_spend(buyer)
    atoms = [a for a in profile['atoms'] if a['budget_microUSD'] >= spend]
    weight = sum(a['weight_bps'] for a in atoms)
    if not weight or not requests or requests[0]['quote_hour'] >= last_contact_hour:
        return None
    direct = sum(cfg[k] for k in ('production_cost', 'supplier_unit_cost', 'support_cost'))
    fee = (price * cfg['payment_bps'] + 9999) // 10000 + cfg['payment_fixed']
    premium = cfg.get('prospective_policy', {}).get('premium_microUSD', 0)
    onboarding = 0 if buyer.get('onboarded', False) else cfg['onboarding_cost']
    if price <= direct + fee + premium + onboarding:
        return None
    arrival = Fraction(cfg['arrival_bps'], 10000)
    retention = Fraction(cfg['retention_bps'], 10000)
    amounts = {key: Fraction(0) for key in ('collections', 'production_supplier_support', 'payment_fee', 'onboarding', 'premium', 'tax', 'initial_qualification', 'qualification', 'outreach', 'collected_orders')}
    possible = False
    for atom in atoms:
        context = {'profile': profile, 'observed_spend': spend, 'rival_available': True}
        initial = atom['budget_microUSD'] - spend
        states = {(initial, False): Fraction(atom['weight_bps'], weight)}
        for index, row in enumerate(requests):
            next_states = {}
            def retain(key, probability):
                if probability:next_states[key] = next_states.get(key, Fraction(0)) + probability
            for (remaining, acquired), probability in states.items():
                if not acquired and index:
                    continue
                attempts = 1 if not acquired else row['maximum_outreach_days']
                if acquired:amounts['outreach'] += probability * attempts * cfg['exposure_cost']
                amounts['qualification' if acquired else 'initial_qualification'] += probability * attempts * arrival * cfg['qualification_cost']
                choices = _choices(context, atom, remaining, service, price)
                ours = sum(choice['provider'] == 'us' for choice in choices)
                if not ours:
                    # A public atom under which no sale is possible supplies no
                    # speculative revenue. Outside purchases still deplete it.
                    for choice in choices:
                        if acquired:retain((remaining - choice['spend'], True), probability * arrival / len(choices))
                    if acquired:retain((remaining, True), probability * (1 - arrival))
                    continue
                possible = True
                # Revenue credits one conservative attempt. Costs cover every
                # possible daily follow-up in the registered request window.
                if acquired:retain((remaining, True), probability * (1 - arrival))
                for choice in choices:
                    chosen = probability * arrival / len(choices)
                    if choice['provider'] != 'us':
                        if acquired:retain((remaining - choice['spend'], True), chosen)
                        continue
                    onboard = 0 if acquired or buyer.get('onboarded', False) else cfg['onboarding_cost']
                    amounts['production_supplier_support'] += chosen * direct
                    amounts['payment_fee'] += chosen * fee
                    amounts['onboarding'] += chosen * onboard
                    amounts['premium'] += chosen * premium
                    amounts['collections'] += chosen * collection * price
                    amounts['collected_orders'] += chosen * collection
                    amounts['tax'] += chosen * collection * max(0, price - direct - fee - premium - onboard) * Fraction(cfg['profit_tax_bps'], 10000)
                    # No future sale after a modeled default or churn is valued.
                    retain((remaining - price, True), chosen * collection * retention)
            states = next_states
    if not possible or amounts['collected_orders'] <= 0:
        return None
    costs = sum(value for key, value in amounts.items() if key not in {'collections', 'collected_orders'})
    return {'price_microUSD': price, 'net_fraction': str(amounts['collections'] - costs),
        'amounts_fraction': {key: str(value) for key, value in amounts.items()},
        'required_current_cash': direct + fee + premium + onboarding + price + 1000000,
        'request_count': len(requests), 'requests_sha256': digest(requests)}


def forecast(cfg, buyers, contacts, day, contract_id, slots, *, jobs=None, contact_fraction=None, used_jobs=(), consumed_jobs=()):
    if 'audience_policy' not in cfg or 'recurring_request_policy' not in cfg or cfg.get('mechanism_policy') is not None or 'refusal_recourse_policy' in cfg:
        return None
    if not isinstance(jobs, dict) or any(ident not in jobs for ident in used_jobs):
        return None
    if any(row['expiry_hour'] - row['release_hour'] > 7 * 24 for rows in cfg['recurring_request_policy']['requests'].values() for row in rows):
        raise ValueError('RECURRING_ACQUISITION_REQUIRES_AT_MOST_SEVEN_DAY_REQUEST_WINDOWS')
    terms = cfg['channels'][contract_id]
    reach = reachability(cfg, buyers, contacts, day, contract_id)
    if not slots or not reach['potential_customer_ids'] or not cfg['arrival_bps']:
        return None
    market = compile_market(cfg['complete_offer_policy'])
    collection = min(Fraction(str(row['accept_prob'])) * Fraction(str(row['collect_prob'])) for row in cfg['strategic_policy']['scenarios'])
    if collection <= 0:
        return None
    calendar = _calendar(cfg, buyers, jobs, day, reach, slots, used_jobs, consumed_jobs)
    public = []
    for ident in reach['potential_customer_ids']:
        profile = market.profile(ident)
        if len(profile['services']) != 1 or profile['services'][0] not in {'reconciliation', 'kpi_variance', 'evidence_matrix'}:
            continue
        choices = []
        for price in profile['price_grids'][profile['services'][0]]:
            row = _buyer_forecast(cfg, profile, buyers[ident], calendar[ident], price, collection, (reach['last_live_day'] + 1) * 24)
            if row is not None and Fraction(row['net_fraction']) > 0:
                choices.append(row)
        if choices:
            row = min(choices, key=lambda r: (-Fraction(r['net_fraction']), r['price_microUSD']))
            public.append({'customer_id': ident, **row})
    if not public:
        return None
    pool = len(reach['potential_customer_ids'])
    contacts_expected = min(Fraction(pool), Fraction(reach['expected_contact_bound_fraction']))
    if contact_fraction is not None:contacts_expected = min(contacts_expected, Fraction(contact_fraction))
    if contacts_expected <= 0:
        return None
    conversion = Fraction(cfg['channel_menu_policy']['conversion_bps'], 10000)
    if day == 0 and 'startup_acquisition_policy' in cfg:
        conversion = Fraction(cfg['startup_acquisition_policy']['conversion_bps'], 10000)
    if conversion <= 0:return None
    amounts = {key: Fraction(0) for key in public[0]['amounts_fraction']}
    for row in public:
        reactivate = Fraction(1) if buyers[row['customer_id']].get('active', True) else Fraction(35, 100)
        chance = contacts_expected / pool * conversion * reactivate
        for key, value in row['amounts_fraction'].items():
            if key != 'initial_qualification':amounts[key] += chance * Fraction(value)
    amounts['initial_qualification'] = contacts_expected * Fraction(cfg['arrival_bps'], 10000) * cfg['qualification_cost']
    days = max(0, reach['last_live_day'] - reach['activation_day'] + 1)
    attempts = days * terms['slots_per_day']
    maintenance_days = max(0, cfg['horizon_days'] - day - 1)
    channel_outreach = attempts * cfg['exposure_cost']
    maintenance = maintenance_days * cfg['maintenance_daily']
    variable = sum(value for key, value in amounts.items() if key not in {'collections', 'collected_orders'})
    benefit = amounts['collections'] - variable - channel_outreach - maintenance
    invoice = terms['price_microUSD'] + terms['support_microUSD']
    # Cash holds use an unconditional request-window envelope, never forecast
    # collections. Every actual native write still checks available cash.
    unavailable = set(used_jobs) | set(consumed_jobs)
    planning_days = {ident: sorted({hour // 24 for row in requests if row['job_id'] not in unavailable
        for hour in range(((max(row['release_hour'], (day + 1) * 24) + 23) // 24) * 24, row['expiry_hour'], 24)})
        for ident, requests in cfg['recurring_request_policy']['requests'].items()}
    followup_days = sum(len(days) for days in planning_days.values())
    evaluation_lock = followup_days * (cfg['exposure_cost'] + cfg['qualification_cost']) + channel_outreach + maintenance
    cash_lock = max(row['required_current_cash'] for row in public) * min(slots, cfg['initial_slots']) + evaluation_lock
    return {'schema': SCHEMA, 'day': day, 'contract_id': contract_id, 'audience': reach,
        'public_offers': public, 'fixed_capacity_units': min(slots, cfg['initial_slots']),
        'calendar_sha256': digest(calendar), 'requests_sha256': digest(cfg['recurring_request_policy']),
        'used_jobs_sha256': digest(sorted(used_jobs)), 'consumed_jobs_sha256': digest(sorted(consumed_jobs)),
        'all_buyer_future_planning_days': {ident: len(days) for ident, days in planning_days.items()},
        'contact_fraction': str(contacts_expected), 'conversion_fraction': str(conversion),
        'collection_fraction': str(collection), 'retention_fraction': str(Fraction(cfg['retention_bps'], 10000)),
        'amounts_fraction': {key: str(value) for key, value in amounts.items()},
        'channel_attempt_outreach_microUSD': channel_outreach, 'maintenance_days': maintenance_days,
        'maintenance_allocation_microUSD': maintenance, 'future_operating_cash_lock': evaluation_lock,
        'cash_lock': cash_lock, 'benefit_before_invoice_fraction': str(benefit), 'net_fraction': str(benefit - invoice),
        'invoice_microUSD': invoice,
        'scope': 'ORDINARY_PUBLIC_FINITE_REPEAT_CONTRIBUTION_HYPOTHESIS_NOT_NATIVE_INCOME',
        'assumptions': 'Uniform declared exposure allocation and conversion haircut; one conservative revenue attempt per scheduled request, all possible follow-up quote costs; public atom/tie branches conserve annual budgets including substitutes; no additional purchase after default or churn valued. Public fixed-capacity appointment calendar reserves all potentially competing requests, not future purchased capacity. Initial exposed-prospect qualification is charged independently of conversion; channel-attempt outreach and entire remaining maintenance assigned once to this mutually exclusive acquisition option. The future cash envelope covers every registered buyer unique request-planning day, including owned and concurrently active customers; these incumbent variable costs remain allocated to ordinary baseline commerce rather than claimed as marginal acquisition gain. No extra customer, budget, request, seed, or private future draw.',
        'limits': 'Not a calibrated native-controller forecast: concurrent refusal/arrival ordering can differ. Incurred native costs, collections, liquidity and full-account audit decide realized profit. Setup and sunk costs remain in the account; unknown actual billing remains unknown.'}
