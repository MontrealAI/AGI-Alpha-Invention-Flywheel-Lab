"""Costed adaptive decisions using a closed public-information contract only."""
from __future__ import annotations
import copy
import hashlib
import json
import math
from collections import defaultdict

SCHEMA = 'agi-alpha/adaptive012-public/v1'
ARMS = {'full_adaptive', 'strategic_011_public_priors', 'strong_fixed', 'ordinary_adaptive', 'no_memory', 'no_opponent', 'no_diagnosis', 'no_instrument', 'no_capital_adaptation'}
OUTCOMES = {'NO_PURCHASE', 'ACCEPTED', 'REJECTED_QUALITY', 'SETTLED', 'REFUNDED', 'PENDING'}
OFFER_FIELDS = {'id', 'service_id', 'segment', 'scope', 'method', 'verification', 'remedy', 'channel', 'capacity_units', 'price_microUSD', 'human_anchor_microUSD', 'production_cost_microUSD', 'applicable_job_ids', 'delivery_hours', 'evidence_level', 'quote_cost_microUSD', 'onboarding_cost_microUSD', 'payment_fee_bps', 'payment_fixed_microUSD'}
FEEDBACK_FIELDS = {'event_id', 'action_id', 'offer_id', 'customer_id', 'observed_cycle', 'offered_price_microUSD', 'outcome', 'complete_cost_microUSD', 'collected_microUSD', 'delivery_hours'}
PRICE_FACTORS = (.50, .65, .80, .95, 1.10, 1.25, 1.40)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _exact(record, fields, label):
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError('EXACT_PUBLIC_' + label + '_SCHEMA_REQUIRED')


def _integer(value, *, minimum=0):
    if type(value) is not int or value < minimum or value > 10**15:
        raise ValueError('BOUNDED_PUBLIC_INTEGER_REQUIRED')


def _number(value):
    if type(value) not in {int, float} or not math.isfinite(value) or value < 0 or value > 10**15:
        raise ValueError('FINITE_NONNEGATIVE_PUBLIC_NUMBER_REQUIRED')


def _text(value):
    if not isinstance(value, str) or not value or len(value) > 10000:
        raise ValueError('BOUNDED_PUBLIC_TEXT_REQUIRED')


def _identity(value):
    if not isinstance(value, str) or len(value) != 64 or any(x not in '0123456789abcdef' for x in value):
        raise ValueError('PUBLIC_CONTENT_DIGEST_REQUIRED')


def validate_public(observation):
    _exact(observation, {'schema', 'cycle', 'account', 'supplier', 'offers', 'customers', 'feedback', 'competitor_ads', 'history_digest'}, 'OBSERVATION')
    if observation['schema'] != SCHEMA:
        raise ValueError('SUPPORTED_PUBLIC_OBSERVATION_REQUIRED')
    _integer(observation['cycle'])
    _identity(observation['history_digest'])
    account = observation['account']
    _exact(account, {'state_digest', 'available_microUSD', 'earned_microUSD', 'cash_microUSD', 'pending_payment_count', 'learning_budget_microUSD'}, 'ACCOUNT')
    _identity(account['state_digest'])
    for key in set(account) - {'state_digest'}:
        _integer(account[key])
    if account['earned_microUSD'] > account['available_microUSD'] or account['available_microUSD'] > account['cash_microUSD']:
        raise ValueError('PUBLIC_FINANCIAL_BALANCE_ORDER_REQUIRED')
    supplier = observation['supplier']
    _exact(supplier, {'quoted_unit_cost_microUSD', 'available_capacity_units', 'announced_latency_hours'}, 'SUPPLIER')
    _integer(supplier['quoted_unit_cost_microUSD'])
    _integer(supplier['available_capacity_units'])
    _number(supplier['announced_latency_hours'])
    schemas = {
        'offers': OFFER_FIELDS,
        'customers': {'id', 'segment', 'requested_services', 'deadline_hours', 'onboarded', 'settled_jobs', 'last_outcome'},
        'feedback': FEEDBACK_FIELDS,
        'competitor_ads': {'rival_id', 'service_id', 'advertised_price_microUSD', 'advertised_delivery_hours', 'observed_cycle', 'evidence_level'}}
    for name, fields in schemas.items():
        rows = observation[name]
        if not isinstance(rows, list) or len(rows) > 10000:
            raise ValueError('BOUNDED_PUBLIC_RECORD_LIST_REQUIRED')
        for row in rows:
            _exact(row, fields, name.upper())
    for offer in observation['offers']:
        for key in ['id', 'service_id', 'segment', 'scope', 'method', 'verification', 'remedy', 'channel', 'evidence_level']:
            _text(offer[key])
        for key in ['capacity_units', 'price_microUSD', 'human_anchor_microUSD', 'production_cost_microUSD', 'quote_cost_microUSD', 'onboarding_cost_microUSD', 'payment_fixed_microUSD', 'payment_fee_bps']:
            _integer(offer[key], minimum=1 if key in {'capacity_units', 'human_anchor_microUSD'} else 0)
        if offer['payment_fee_bps'] > 10000:
            raise ValueError('PUBLIC_PAYMENT_BASIS_POINTS_REQUIRED')
        _number(offer['delivery_hours'])
        if not isinstance(offer['applicable_job_ids'], list) or any(not isinstance(x, str) for x in offer['applicable_job_ids']) or len(offer['applicable_job_ids']) != len(set(offer['applicable_job_ids'])):
            raise ValueError('UNIQUE_PUBLIC_APPLICABLE_JOB_IDENTITIES_REQUIRED')
        for ident in offer['applicable_job_ids']:
            _text(ident)
    for customer in observation['customers']:
        for key in ['id', 'segment', 'last_outcome']:
            _text(customer[key])
        _number(customer['deadline_hours'])
        _integer(customer['settled_jobs'])
        if type(customer['onboarded']) is not bool or not isinstance(customer['requested_services'], list):
            raise ValueError('PUBLIC_CUSTOMER_CONTEXT_REQUIRED')
        for service in customer['requested_services']:
            _text(service)
    for row in observation['feedback']:
        for key in ['event_id', 'action_id', 'offer_id', 'customer_id']:
            _text(row[key])
        for key in ['observed_cycle', 'offered_price_microUSD', 'complete_cost_microUSD', 'collected_microUSD']:
            _integer(row[key])
        _number(row['delivery_hours'])
        if row['observed_cycle'] > observation['cycle'] or row['outcome'] not in OUTCOMES:
            raise ValueError('OBSERVED_FEEDBACK_ONLY_NO_FUTURE_OUTCOME_REQUIRED')
        if row['outcome'] == 'PENDING' and row['collected_microUSD'] != 0:
            raise ValueError('PENDING_IS_NOT_SETTLED_REVENUE')
    for ad in observation['competitor_ads']:
        for key in ['rival_id', 'service_id', 'evidence_level']:
            _text(ad[key])
        _integer(ad['advertised_price_microUSD'])
        _number(ad['advertised_delivery_hours'])
        _integer(ad['observed_cycle'])
        if ad['observed_cycle'] > observation['cycle']:
            raise ValueError('ONLY_ALREADY_OBSERVED_ADVERTISEMENTS_REQUIRED')
    for key in ['offers', 'customers']:
        identities = [row['id'] for row in observation[key]]
        if len(identities) != len(set(identities)):
            raise ValueError('UNIQUE_PUBLIC_IDENTITIES_REQUIRED')
    return copy.deepcopy(observation)


class Policy:
    def __init__(self, arm='full_adaptive'):
        if arm not in ARMS:
            raise ValueError('DECLARED_ADAPTIVE_CONTROL_ARM_REQUIRED')
        self.arm = arm
        self.seen_feedback = set()
        self.feedback_hashes = {}
        self.feedback_records = []
        self.actions = {}
        self.statistics = {}
        self.customer_statistics = {}
        self.advertisements = {}
        self.trace = []
        self.diagnostics = []
        self.shift_events = []
        self.diagnostic_adjudications = []
        self._experiment_events = {}
        self._resolved_experiments = set()
        self._blocked_until = {}
        self.action_count = 0
        self.pending_actions = set()
        self._last_cache = None
        self._legacy_cache = {}

    def _adaptive(self):
        return self.arm not in {'strong_fixed', 'strategic_011_public_priors'}

    def _key(self, offer_id, segment, factor):
        return offer_id + '|' + segment + '|' + format(factor, '.2f')

    def _stats(self, key):
        if key not in self.statistics:
            self.statistics[key] = {'purchase_yes': 0., 'purchase_no': 0., 'settled': 0., 'refunded': 0., 'quality_rejects': 0., 'offered': 0, 'collected_microUSD': 0, 'realized_cost_microUSD': 0}
        return self.statistics[key]

    def _ingest(self, observation):
        if self.arm == 'no_memory':
            self.statistics.clear()
        for feedback in sorted(observation['feedback'], key=lambda r: (r['observed_cycle'], r['event_id'])):
            ident = feedback['event_id']
            if ident in self.seen_feedback:
                if self.feedback_hashes[ident] != digest(feedback):
                    raise ValueError('CONFLICTING_PUBLIC_FEEDBACK_EVENT_IDENTITY')
                continue
            self.seen_feedback.add(ident)
            self.feedback_hashes[ident] = digest(feedback)
            self.feedback_records.append(copy.deepcopy(feedback))
            action = self.actions.get(feedback['action_id'])
            if action is None:
                continue
            stats = self._stats(action['statistic_key'])
            outcome = feedback['outcome']
            flags = action.setdefault('observed_flags', [])
            self._adjudicate_experiment(action, feedback)
            if outcome == 'PENDING':
                if 'collection' not in flags:
                    self.pending_actions.add(feedback['action_id'])
                continue
            if outcome == 'NO_PURCHASE' and 'purchase' not in flags:
                stats['purchase_no'] += 1
                flags.append('purchase')
            elif outcome in {'ACCEPTED', 'SETTLED', 'REFUNDED'} and 'purchase' not in flags:
                stats['purchase_yes'] += 1
                flags.append('purchase')
            if outcome == 'REJECTED_QUALITY' and 'quality' not in flags:
                stats['quality_rejects'] += 1
                flags.append('quality')
            if outcome in {'SETTLED', 'REFUNDED'} and 'collection' not in flags:
                stats['settled' if outcome == 'SETTLED' else 'refunded'] += 1
                stats['collected_microUSD'] += feedback['collected_microUSD']
                stats['realized_cost_microUSD'] += feedback['complete_cost_microUSD']
                flags.append('collection')
                self.pending_actions.discard(feedback['action_id'])
                record = self.customer_statistics.setdefault(feedback['customer_id'], {'settled': 0, 'refunded': 0})
                record['settled' if outcome == 'SETTLED' else 'refunded'] += 1
        for ad in observation['competitor_ads']:
            key = ad['rival_id'] + '|' + ad['service_id']
            bucket = self.advertisements.setdefault(key, [])
            if not any(x['observed_cycle'] == ad['observed_cycle'] and x['advertised_price_microUSD'] == ad['advertised_price_microUSD'] and x['advertised_delivery_hours'] == ad['advertised_delivery_hours'] for x in bucket):
                bucket.append(copy.deepcopy(ad))
                bucket.sort(key=lambda x: x['observed_cycle'])
                del bucket[:-12]
        self._detect_change(observation['cycle'])

    def _adjudicate_experiment(self, action, feedback):
        experiment = action['decision'].get('experiment')
        action_id = feedback['action_id']
        if experiment is None or action_id in self._resolved_experiments:
            return
        records = self._experiment_events.setdefault(action_id, [])
        records.append(copy.deepcopy(feedback))
        outcome = feedback['outcome']
        if outcome not in {'SETTLED', 'REFUNDED', 'REJECTED_QUALITY', 'NO_PURCHASE'}:
            return
        if outcome == 'REJECTED_QUALITY':
            decision = 'REQUIRE_ALTERNATIVE_EXECUTABLE_PIPELINE'
            inference = 'Observed contract failure supports an applicability or production defect for this customer/offer. It is not evidence of a buyer reservation price.'
            self._blocked_until[(action['offer_id'], action['customer_id'])] = feedback['observed_cycle'] + 2
        elif outcome == 'SETTLED':
            decision = 'RETAIN_CANDIDATE' if feedback['collected_microUSD'] > feedback['complete_cost_microUSD'] else 'STOP_LOSS_MAKING_PROBE'
            inference = 'This executed offer settled; isolated causation by price, scope, timing or opponent behavior remains unresolved without a matched experiment.'
        elif outcome == 'REFUNDED':
            decision = 'STOP_AND_DIAGNOSE_COLLECTION_OR_OBLIGATION_FAILURE'
            inference = 'A terminal refund is observed. Earlier pending status alone did not count as a default.'
        else:
            decision = 'INCONCLUSIVE_COMPARE_BOUNDED_ALTERNATIVE'
            inference = 'Binary decline is censored. Exact willingness to pay, outside-option costs and the private cause remain unknown.'
        self.diagnostic_adjudications.append({'action_id': action_id, 'observed_cycle': feedback['observed_cycle'], 'source_event_ids': [r['event_id'] for r in records], 'decision': decision, 'inference': inference, 'reported_collected_microUSD': feedback['collected_microUSD'], 'reported_complete_cost_microUSD': feedback['complete_cost_microUSD'], 'reported_realized_contribution_microUSD': feedback['collected_microUSD'] - feedback['complete_cost_microUSD'], 'expected_decision_value_upper_bound_microUSD': experiment['decision_value_upper_bound_microUSD'], 'scope': 'Evidence-grounded probe adjudication from delayed public feedback; reported per-action contribution is not whole-enterprise profit or proof of causal invention advantage.'})
        self._resolved_experiments.add(action_id)

    def _detect_change(self, cycle):
        if self.arm in {'strong_fixed', 'strategic_011_public_priors', 'ordinary_adaptive', 'no_memory'}:
            return
        terminal = [r for r in self.feedback_records if r['outcome'] in {'NO_PURCHASE', 'SETTLED', 'REFUNDED', 'REJECTED_QUALITY'}]
        if len(terminal) < 12:
            return
        earlier, recent = terminal[-12:-6], terminal[-6:]
        rate = lambda records: sum(r['outcome'] == 'SETTLED' for r in records) / len(records)
        old, new = rate(earlier), rate(recent)
        if old - new >= .34 and (not self.shift_events or cycle - self.shift_events[-1]['cycle'] >= 3):
            event = {'cycle': cycle, 'old_visible_settlement_fraction': old, 'recent_visible_settlement_fraction': new, 'source_event_ids': [r['event_id'] for r in earlier + recent], 'inference': 'Observed outcome shift; cause unresolved. Rejections remain censored, not reservation-value observations.'}
            self.shift_events.append(event)
            for stats in self.statistics.values():
                for key in ['purchase_yes', 'purchase_no', 'settled', 'refunded', 'quality_rejects']:
                    stats[key] *= .5

    def _opponent_signal(self, offer, price, observation):
        if self.arm in {'ordinary_adaptive', 'no_opponent'}:
            return {'conversion_prior': .5, 'record_ids': [], 'pattern': 'not_used_by_arm'}
        relevant = [ad for ad in observation['competitor_ads'] if ad['service_id'] == offer['service_id']]
        if not relevant:
            return {'conversion_prior': .5, 'record_ids': [], 'pattern': 'no_observed_ads'}
        ad = min(relevant, key=lambda x: x['advertised_price_microUSD'])
        predicted = ad['advertised_price_microUSD']
        pattern = 'current_public_quote'
        if self.arm not in {'strong_fixed', 'strategic_011_public_priors'}:
            history = self.advertisements.get(ad['rival_id'] + '|' + ad['service_id'], [])
            if len(history) >= 3:
                recent = history[-3:]
                change = (recent[-1]['advertised_price_microUSD'] - recent[0]['advertised_price_microUSD']) / max(1, recent[-1]['observed_cycle'] - recent[0]['observed_cycle'])
                predicted = max(ad['advertised_price_microUSD'] * .8, min(ad['advertised_price_microUSD'] * 1.2, ad['advertised_price_microUSD'] + change))
                pattern = 'bounded_delayed_observed_quote_trend'
        scale = max(1, offer['human_anchor_microUSD'] * .30)
        same_outcome_quote_gap = (price - predicted) / scale
        waiting_gap = (offer['delivery_hours'] + observation['supplier']['announced_latency_hours'] - ad['advertised_delivery_hours']) / 24
        log_odds = max(-6, min(6, same_outcome_quote_gap + waiting_gap))
        return {'conversion_prior': 1 / (1 + math.exp(log_odds)), 'record_ids': [digest(ad)], 'pattern': pattern, 'advertised_comparator_price_microUSD': ad['advertised_price_microUSD'], 'bounded_projected_quote_microUSD': int(round(predicted)), 'scope': 'Seller heuristic from observed advertisements and offered SLA; not a buyer value, competitor cost or equilibrium oracle.'}

    def _candidate(self, observation, offer, customer, factor, learning_cost, price_override=None):
        price = max(1, int(round(offer['human_anchor_microUSD'] * factor))) if price_override is None else price_override
        key = self._key(offer['id'], customer['segment'], factor)
        stats = self._stats(key)
        signal = self._opponent_signal(offer, price, observation)
        yes, no = stats['purchase_yes'], stats['purchase_no']
        prior = signal['conversion_prior']
        purchase = (2 * prior + yes) / (2 + yes + no) if self._adaptive() else prior
        collection = (3 + stats['settled']) / (4 + stats['settled'] + stats['refunded']) if self._adaptive() else .75
        variance = purchase * (1 - purchase) / (3 + yes + no)
        uncertainty = math.sqrt(max(0., variance))
        production = offer['production_cost_microUSD'] + observation['supplier']['quoted_unit_cost_microUSD'] * offer['capacity_units']
        fee = (price * offer['payment_fee_bps'] + 9999) // 10000 + offer['payment_fixed_microUSD']
        onboarding = 0 if customer['onboarded'] else offer['onboarding_cost_microUSD']
        per_opportunity = production + offer['quote_cost_microUSD'] + learning_cost
        expected = purchase * (collection * price - fee - onboarding) - per_opportunity
        exposure = per_opportunity + fee + onboarding
        return {'offer_id': offer['id'], 'customer_id': customer['id'], 'service_id': offer['service_id'], 'price_microUSD': price, 'factor': factor, 'capacity_units': offer['capacity_units'], 'channel': offer['channel'], 'expected_net_microUSD': int(math.floor(expected)), 'max_exposure_microUSD': exposure, 'learning_cost_microUSD': learning_cost, 'statistic_key': key, 'purchase_probability_estimate': purchase, 'collection_probability_estimate': collection, 'conversion_uncertainty': uncertainty, 'observed_count': yes + no, 'opponent_signal': signal, 'offer_production_contract': {k: offer[k] for k in ['scope', 'method', 'verification', 'remedy', 'delivery_hours', 'evidence_level']}}

    def _legacy_public_price(self, observation, offer, customer, learning_cost):
        from enterprise.pricing import optimize_price
        unit = 1_000_000
        relevant = [ad for ad in observation['competitor_ads'] if ad['service_id'] == offer['service_id']]
        observed_ad = min(relevant, key=lambda ad: (ad['advertised_price_microUSD'], -ad['observed_cycle'])) if relevant else None
        rival_hours = observed_ad['advertised_delivery_hours'] if observed_ad is not None else 24.
        production = offer['production_cost_microUSD'] + observation['supplier']['quoted_unit_cost_microUSD'] * offer['capacity_units'] + learning_cost
        urgency = 1. if 'premium' in customer['segment'].lower() else .45
        public_input = {'anchor_usd': offer['human_anchor_microUSD'] / unit, 'autonomous_cost_usd': production / unit, 'onboarding_cost_usd': 0. if customer['onboarded'] else offer['onboarding_cost_microUSD'] / unit, 'friction_usd': 0. if customer['onboarded'] else .5, 'trust': .95, 'rival_trust': .95, 'urgency_value_hour': urgency, 'repeat_probability': .75, 'payment_fraction': offer['payment_fee_bps'] / 10000, 'payment_fixed_usd': offer['payment_fixed_microUSD'] / unit}
        priors = {'our_hours': offer['delivery_hours'] + observation['supplier']['announced_latency_hours'], 'rival_hours': rival_hours, 'self_complete_cost_ratio': .85, 'temperature_ratio': .12, 'rival_cost_multiplier': 1., 'arrival_probability': 1., 'qualification_probability': 1., 'supplier_outage_probability': 0., 'collection_probability': .95, 'refund_probability': .03, 'quote_cost_usd': offer['quote_cost_microUSD'] / unit}
        identity = digest({'public_input': public_input, 'declared_common_priors': priors, 'choice_model': 'logit'})
        cache_hit = identity in self._legacy_cache
        if not cache_hit:
            self._legacy_cache[identity] = optimize_price(copy.deepcopy(public_input), copy.deepcopy(priors), 'logit', strategic=True, lagged=False)
        result = copy.deepcopy(self._legacy_cache[identity])
        adapter = {'schema': 'agi-alpha/adaptive012-legacy-public-pricing-adapter/v1', 'source_call_path': 'enterprise.pricing.optimize_price', 'solver_input_sha256': identity, 'cache_hit': cache_hit, 'public_input': public_input, 'declared_common_priors': priors, 'observed_comparator_ad': copy.deepcopy(observed_ad), 'assumptions': 'Symmetric0.95trust; common0.95collection/0.03refund and0.75repeat prior; one already-qualified public offer exposure; rival cost prior equals our disclosed operating-resource cost, never hidden competitor cost; standard urgency0.45USD/hour and premium1USD/hour are common declared priors. Rival advertised SLA is observed with delay, fallback24h. No evaluator regime, random seed, private buyer value or future shock enters.', 'solver_scope': result['scope']}
        search = {'offer_id': offer['id'], 'customer_id': customer['id'], 'source_call_path': adapter['source_call_path'], 'solver_input_sha256': identity, 'tested_price_range_microUSD': [int(round(x * unit)) for x in result['tested_price_range']], 'initial_boundary_triggered': result['boundary_triggered'], 'local_price_resolution_microUSD': max(1, int(round(result['resolution_usd'] * unit))), 'evaluated_prices': len(result['candidate_curve']), 'scope': 'Actual retained011 finite price optimizer applied only to current public contracts and declared common priors; not an omniscient regime policy.'}
        if result['price'] is None:
            return [], {**search, 'no_bid': True, 'adapter': adapter}
        price = max(1, int(round(result['price'] * unit)))
        factor = price / offer['human_anchor_microUSD']
        item = self._candidate(observation, offer, customer, factor, learning_cost, price_override=price)
        item['expected_net_microUSD'] = int(math.floor(result['expected_immediate_contribution_per_opportunity'] * unit))
        item['purchase_probability_estimate'] = result['win_probability']
        item['collection_probability_estimate'] = .95 * (1-.03)
        item['conversion_uncertainty'] = 0.
        item['legacy_public_adapter'] = adapter
        item['price_search'] = search
        item['opponent_signal'] = {'conversion_prior': result['win_probability'], 'record_ids': [digest(observed_ad)] if observed_ad is not None else [], 'pattern': 'retained011_optimizer_with_common_public_priors', 'scope': adapter['assumptions']}
        return ([item] if item['max_exposure_microUSD'] <= observation['account']['available_microUSD'] else []), search

    def _price_candidates(self, observation, offer, customer, learning_cost):
        if offer['service_id'] == 'operations_bundle':
            price = offer['price_microUSD']
            if price <= 0:
                return [], {'offer_id': offer['id'], 'customer_id': customer['id'], 'scope': 'No qualified joint bundle quote supplied; no component-price substitution.'}
            factor = price / offer['human_anchor_microUSD']
            item = self._candidate(observation, offer, customer, factor, learning_cost, price_override=price)
            search = {'offer_id': offer['id'], 'customer_id': customer['id'], 'source_call_path': 'adaptive_enterprise.model joint quote through enterprise.pricing.optimize_bundle', 'tested_price_range_microUSD': [price, price], 'local_price_resolution_microUSD': 0, 'initial_boundary_triggered': False, 'evaluated_prices': 1, 'scope': 'Exact public joint complete-service quote from the actual upstream retained bundle optimizer; three executed component obligations replace their individual sales, never added to them.'}
            item['price_search'] = search
            return ([item] if item['max_exposure_microUSD'] <= observation['account']['available_microUSD'] else []), search
        if self.arm == 'strategic_011_public_priors':
            return self._legacy_public_price(observation, offer, customer, learning_cost)
        factors = (.95,) if self.arm == 'strong_fixed' else PRICE_FACTORS
        curve = [self._candidate(observation, offer, customer, factor, learning_cost) for factor in factors]
        feasible = lambda rows: [row for row in rows if row['max_exposure_microUSD'] <= observation['account']['available_microUSD']]
        initial = feasible(curve)
        initial_best = max(initial, key=lambda row: (row['expected_net_microUSD'], -row['factor'])) if initial else None
        boundary = initial_best is not None and self.arm != 'strong_fixed' and initial_best['factor'] in {min(factors), max(factors)}
        tested_factors = set(factors)
        if boundary:
            extension = [round(.35 + .05 * i, 2) for i in range(27)]
            for factor in extension:
                if factor not in tested_factors:
                    curve.append(self._candidate(observation, offer, customer, factor, learning_cost))
                    tested_factors.add(factor)
        extended = feasible(curve)
        if self.arm != 'strong_fixed' and extended:
            center = max(extended, key=lambda row: (row['expected_net_microUSD'], -row['factor']))['factor']
            for offset in range(-5, 6):
                factor = round(max(.35, min(1.65, center + offset * .01)), 2)
                if factor not in tested_factors:
                    curve.append(self._candidate(observation, offer, customer, factor, learning_cost))
                    tested_factors.add(factor)
        final = feasible(curve)
        best = max(final, key=lambda row: (row['expected_net_microUSD'], -row['factor'])) if final else None
        search = {'offer_id': offer['id'], 'customer_id': customer['id'], 'declared_factor_range': [.35, 1.65], 'initial_tested_factor_range': [min(factors), max(factors)], 'tested_factor_range': [min(tested_factors), max(tested_factors)], 'tested_price_range_microUSD': [min(row['price_microUSD'] for row in curve), max(row['price_microUSD'] for row in curve)], 'initial_boundary_triggered': boundary, 'final_declared_boundary_hit': best is not None and self.arm != 'strong_fixed' and best['factor'] in {.35, 1.65}, 'local_factor_resolution': 0 if self.arm == 'strong_fixed' else .01, 'local_price_resolution_microUSD': 0 if self.arm == 'strong_fixed' else max(1, int(round(offer['human_anchor_microUSD'] * .01))), 'evaluated_prices': len(curve), 'scope': 'Best tested finite public-context prices with conditional boundary extension and local refinement. Endpoints are declared action limits, not a claim of global or equilibrium optimality.'}
        for row in final:
            row['price_search'] = search
        return final, search

    def _hypothesis(self, chosen, candidates, observation):
        matching = [r for r in self.feedback_records[-12:] if r['customer_id'] == chosen['customer_id']]
        rivals = chosen['opponent_signal']
        quality_failures = sum(r['outcome'] == 'REJECTED_QUALITY' for r in matching)
        rejected = sum(r['outcome'] == 'NO_PURCHASE' for r in matching)
        hypotheses = [
            {'id': 'price_or_outside_option', 'supporting_event_ids': [r['event_id'] for r in matching if r['outcome'] == 'NO_PURCHASE'], 'falsifier': 'A lower total-cost matched-scope offer still has no purchase; this does not reveal an exact reservation value.'},
            {'id': 'scope_or_intake_failure', 'supporting_event_ids': [r['event_id'] for r in matching if r['outcome'] == 'REJECTED_QUALITY'], 'falsifier': 'An applicable independently checked alternative pipeline produces the same rejection.'},
            {'id': 'rival_response_or_timing', 'supporting_event_ids': rivals['record_ids'], 'falsifier': 'Observed rival price/SLA remains stable across the next two visible advertisements.'},
            {'id': 'demand_or_collection_shift', 'supporting_event_ids': [r['event_id'] for r in matching if r['outcome'] in {'REFUNDED', 'PENDING'}], 'falsifier': 'Comparable customers settle on time while this segment continues rejecting.'}]
        intervention = 'execute_actual_alternative_pipeline' if quality_failures else 'bounded_price_or_complete_offer_probe' if rejected else 'costed_new_context_probe'
        alternative = max((c['expected_net_microUSD'] for c in candidates if c['offer_id'] != chosen['offer_id']), default=0)
        return {'schema': 'agi-alpha/adaptive012-diagnostic-experiment/v1', 'competing_hypotheses': hypotheses, 'intervention': intervention, 'decision_value_upper_bound_microUSD': max(0, alternative, chosen['expected_net_microUSD']) * 2, 'experiment_resource_cost_microUSD': chosen['learning_cost_microUSD'], 'maximum_exposure_microUSD': chosen['max_exposure_microUSD'], 'resolution_after_visible_feedback_events': 2, 'switch_rule': 'Retain an applicable tested complete offer only when observed accepted settlement and complete-cost posterior improve; otherwise stop this probe and retain failure evidence.', 'censoring_rule': 'Binary decline updates conversion counts only; no exact willingness-to-pay or private reason is inferred.', 'source_history_digest': observation['history_digest']}

    def act(self, observation):
        public = validate_public(observation)
        identity = digest(public)
        if self._last_cache is not None and self._last_cache[0] == identity:
            return copy.deepcopy(self._last_cache[1])
        self._ingest(public)
        learning_cost = min(public['account']['learning_budget_microUSD'], 50_000)
        if self.arm in {'strong_fixed', 'strategic_011_public_priors'}:
            learning_cost = min(learning_cost, 10_000)
        candidates, searches = [], []
        for offer in public['offers']:
            if not offer['applicable_job_ids'] or offer['capacity_units'] > public['supplier']['available_capacity_units']:
                continue
            for customer in public['customers']:
                if offer['channel'] == 'authorized_repeat' and not customer['onboarded']:
                    continue
                if public['cycle'] < self._blocked_until.get((offer['id'], customer['id']), 0):
                    continue
                if offer['service_id'] not in customer['requested_services'] or offer['segment'] not in {customer['segment'], 'all', '*'} or offer['delivery_hours'] + public['supplier']['announced_latency_hours'] > customer['deadline_hours']:
                    continue
                context_candidates, search = self._price_candidates(public, offer, customer, learning_cost)
                candidates.extend(context_candidates)
                searches.append(search)
        chosen, exploration = None, False
        if candidates:
            ordered = sorted(candidates, key=lambda c: (-c['expected_net_microUSD'], c['offer_id'], c['customer_id'], c['factor']))
            profitable = [c for c in ordered if c['expected_net_microUSD'] > 0]
            if profitable:
                chosen = profitable[0]
                can_explore = self._adaptive() and self.arm != 'no_diagnosis' and self.action_count % 4 == 1
                if can_explore:
                    bounded = [c for c in profitable if c['expected_net_microUSD'] >= max(1, chosen['expected_net_microUSD'] // 3) and c['max_exposure_microUSD'] <= min(public['account']['available_microUSD'], max(chosen['max_exposure_microUSD'], 10_000_000))]
                    if bounded:
                        chosen = max(bounded, key=lambda c: (c['conversion_uncertainty'], -c['observed_count'], -c['max_exposure_microUSD'], c['offer_id'], c['customer_id']))
                        exploration = True
        action_id = 'adaptive-' + str(public['cycle']) + '-' + str(self.action_count) + '-' + identity[:12]
        if chosen is None:
            decision = {'action_id': action_id, 'offer_id': None, 'customer_id': None, 'service_id': None, 'price_microUSD': 0, 'capacity_units': 0, 'channel': None, 'action': 'WITHDRAW', 'experiment': None, 'expected_net_microUSD': 0, 'max_exposure_microUSD': learning_cost, 'rationale': 'No available permitted complete offer has positive tested expected contribution within visible capacity, deadline and protected cash; no private demand or future shock information was supplied.', 'learning_cost_microUSD': learning_cost, 'exploration': False, 'evidence_digest': identity}
        else:
            experiment = self._hypothesis(chosen, candidates, public) if exploration and self.arm not in {'ordinary_adaptive', 'no_memory', 'no_diagnosis'} else None
            if experiment is not None:
                self.diagnostics.append(copy.deepcopy(experiment))
            decision = {key: chosen[key] for key in ['offer_id', 'customer_id', 'service_id', 'price_microUSD', 'capacity_units', 'channel', 'expected_net_microUSD', 'max_exposure_microUSD', 'learning_cost_microUSD']}
            decision.update(action_id=action_id, action='EXPERIMENT' if experiment is not None else 'OFFER', experiment=experiment, exploration=exploration, evidence_digest=identity, rationale='Public-context complete-offer decision using ' + ('retained censored conversion/collection counts and bounded opponent observations' if self._adaptive() else 'declared fixed public-information comparator') + '; no exact buyer reservation value inferred.')
            stored = copy.deepcopy(chosen)
            stored['decision'] = copy.deepcopy(decision)
            stored['observed_flags'] = []
            self.actions[action_id] = stored
            self._stats(chosen['statistic_key'])['offered'] += 1
        self.trace.append({'cycle': public['cycle'], 'observation_digest': identity, 'feedback_events_observed': sorted(self.seen_feedback), 'decision': copy.deepcopy(decision), 'best_tested_expected_net_microUSD': max((c['expected_net_microUSD'] for c in candidates), default=0), 'candidate_count': len(candidates), 'price_searches': searches, 'selected_public_estimates': copy.deepcopy(chosen), 'policy_scope': 'Finite contextual posterior/heuristic search and bounded exploration; not an equilibrium or calibrated market demand estimate.'})
        self.action_count += 1
        self._last_cache = (identity, copy.deepcopy(decision))
        return copy.deepcopy(decision)

    def export(self):
        return copy.deepcopy({'schema': 'agi-alpha/adaptive012-learning-state/v1', 'arm': self.arm, 'ablation_scope': 'Conversion-count posterior reset only; customer, opponent, diagnostic and instrument state retained' if self.arm=='no_memory' else 'As declared by arm', 'action_count': self.action_count, 'used_feedback_event_ids': sorted(self.seen_feedback), 'statistics': self.statistics, 'customer_statistics': self.customer_statistics, 'pending_action_ids': sorted(self.pending_actions), 'opponent_observation_histories': self.advertisements, 'change_events': self.shift_events, 'diagnostic_experiments': self.diagnostics, 'diagnostic_adjudications': self.diagnostic_adjudications, 'verified_failure_constraints': [{'offer_id': k[0], 'customer_id': k[1], 'blocked_until_cycle': v} for k, v in sorted(self._blocked_until.items())], 'trace': self.trace, 'scope': 'Public observations and censored outcomes only; no latent reservation values, future events, hidden competitor costs or evaluator labels.'})


AdaptivePolicy = Policy
