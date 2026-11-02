"""Scale invariants, not evidence of demand or an achieved profit milestone."""
import copy
import importlib.util
from fractions import Fraction
from pathlib import Path
import shutil
import tempfile
import unittest

from adaptive_enterprise.instruments import SOURCE_PATHS as SERVICE_SOURCES, prepare_services
from commercial.ledger import digest
from connected_enterprise.channels import ChannelBook, audit_channel_history, default_contracts, validate_contracts
from connected_enterprise.complete_offer_market import actual_choice, compile_market
from connected_enterprise.engine import default_config, validate_config
from connected_enterprise.finance import JournalAccount, SOURCE_PATHS
from connected_enterprise.pricing import price
from connected_enterprise.strategic_commerce import select, rederive, validate_policy, allocate_actions, rederive_actions
from experiments.commerce006 import PINS

ROOT = Path(__file__).resolve().parents[1]


def fixture_module(name):
    spec = importlib.util.spec_from_file_location('open_scale064_'+name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OpenScale064(unittest.TestCase):
    def test_explicit_finite_capacity_and_horizon_have_no_universal_magnitude_ceiling(self):
        cfg = default_config()
        cfg.update(customer_pool=10**9, initial_slots=10_001, maximum_slots=10**8,
                   horizon_days=10_001, capacity_duration_hours=10**9)
        self.assertEqual(validate_config(cfg), cfg)
        for key, value in [('maximum_slots', True), ('horizon_days', 0), ('arrival_bps', 10001)]:
            invalid = copy.deepcopy(cfg); invalid[key] = value
            with self.assertRaises(ValueError): validate_config(invalid)
        invalid = copy.deepcopy(cfg); invalid['initial_slots'] = invalid['maximum_slots']+1
        with self.assertRaises(ValueError): validate_config(invalid)

    def test_public_fee_floor_conserves_large_exact_money_and_full_history(self):
        quote = price(4*10**20, 3*10**20, 2*10**20, 10**20, 290, 10**16, [False]*1001)
        fee = (quote['price']*290+9999)//10000+10**16
        self.assertEqual(quote['forecast_payment_fee_microUSD'], fee)
        self.assertEqual(quote['forecast_direct_contribution_microUSD'], quote['price']-10**20-fee)
        self.assertEqual(quote['past_own_offer_count'], 1001)
        self.assertGreaterEqual(quote['price'], quote['floor'])
        self.assertIsNone(price(10**20, 10**20, 10**20, 1, 10000, 0, []))

    def test_declared_supplier_capacity_and_zero_reach_are_aggregated_and_audited(self):
        contracts = default_contracts()
        contracts['pilot'].update(price_microUSD=10**20, slots_per_day=10**12,
            duration_days=10_001, lead_days=10_001, max_active_tranches=1001,
            max_contacts_per_customer=1001, activation_reliability_bps=10000, realization_bps=0)
        terms = validate_contracts(contracts)['pilot']
        book = ChannelBook(19, contracts)
        purchase = book.purchase('pilot', 0, 'engineering-funded-plan')
        self.assertEqual(purchase['invoice_microUSD'], terms['price_microUSD']+terms['support_microUSD'])
        buyers = [{'id': 'customer-'+str(i)} for i in range(1005)]
        self.assertEqual(book.expose(10_001, buyers), [])
        day = book.export()['exposures_by_day']['10001']
        self.assertEqual(day['attempted_slots'], 10**12)
        self.assertEqual(day['unused_slots']+day['realized_exposures'], day['attempted_slots'])
        self.assertEqual(audit_channel_history(book.export(), contracts, 19, buyers)['exposure_days_checked'], 1)

    def test_more_than_thousand_voluntary_contacts_preserve_replay_and_deduplication(self):
        contracts = default_contracts()
        contracts['pilot'].update(slots_per_day=1024, owned_audience_count=0,
            activation_reliability_bps=10000, realization_bps=10000, overlap_bps=0,
            max_contacts_per_customer=1)
        buyers = [{'id': 'engineering-customer-'+str(i)} for i in range(1024)]
        book = ChannelBook(73, contracts); book.purchase('pilot', 0, 'paid-contract')
        exposed = book.expose(2, buyers)
        self.assertEqual(len(exposed), 1024)
        self.assertEqual(len({r['customer_id'] for r in exposed}), 1024)
        self.assertEqual(book.expose(3, buyers), [])
        state = book.export()
        self.assertEqual(sum(i['potential_slots_used'] for i in state['instances'].values()), 2048)
        self.assertEqual(sum(i['realized_exposures']+i['unused_slots'] for i in state['instances'].values()), 2048)
        self.assertEqual(audit_channel_history(state, contracts, 73, buyers)['exposure_days_checked'], 2)
        tampered = copy.deepcopy(state); tampered['exposures_by_day']['2']['attempted_slots'] += 1
        with self.assertRaises(ValueError): audit_channel_history(tampered, contracts, 73, buyers)

    def test_exhausted_audience_batches_trillion_slot_unused_tail(self):
        contracts = default_contracts()
        contracts['pilot'].update(slots_per_day=10**12, owned_audience_count=0,
            activation_reliability_bps=10000, realization_bps=10000, overlap_bps=0)
        buyers = [{'id': 'single-voluntary-prospect'}]
        book = ChannelBook(81, contracts); book.purchase('pilot', 0, 'paid-contract')
        self.assertEqual(len(book.expose(2, buyers)), 1)
        state = book.export()
        self.assertEqual(state['exposures_by_day']['2']['unused_slots'], 10**12-1)
        self.assertEqual(audit_channel_history(state, contracts, 81, buyers)['exposure_days_checked'], 1)

    def test_zero_probability_retry_runs_batch_and_resume_without_creating_cash(self):
        import json
        contracts = default_contracts()
        contracts['pilot'].update(activation_reliability_bps=0, prepaid_retry_attempts=10**12,
            retry_delay_days=1, duration_days=10**12+10, failure_credit_bps=5000)
        book = ChannelBook(29, contracts); book.purchase('pilot', 0, 'prepaid-retry-contract')
        self.assertEqual(book.expose(10**12, []), [])
        paused = book.export()
        self.assertEqual(paused['instances']['prepaid-retry-contract']['activation_attempts'], 10**12-1)
        self.assertEqual(paused['instances']['prepaid-retry-contract']['state'], 'RETRY_SCHEDULED')
        resumed = ChannelBook(29, contracts, json.loads(json.dumps(paused)))
        self.assertEqual(resumed.expose(10**12+2, []), [])
        state = resumed.export()
        self.assertEqual(state['instances']['prepaid-retry-contract']['activation_attempts'], 10**12+1)
        self.assertEqual(state['instances']['prepaid-retry-contract']['state'], 'FAILED')
        self.assertEqual(len(state['events']), 4)
        self.assertEqual(state['events'][-1]['kind'], 'CHANNEL_ACTIVATION_FAILED')
        self.assertEqual(audit_channel_history(state, contracts, 29, [])['activation_attempts_checked'], 10**12+1)
        self.assertNotIn('cash', state)
        tampered = copy.deepcopy(state); tampered['events'][1]['activation_attempts'] += 1
        with self.assertRaises(ValueError): audit_channel_history(tampered, contracts, 29, [])

    def test_complete_market_has_no_price_budget_or_profile_catalogue_ceiling(self):
        profile = {'id': 'request', 'services': ['engineering'], 'price_grids': {'engineering': list(range(1, 11))},
            'atoms': [{'weight_bps': 10000, 'budget_microUSD': 10**22, 'values': {'engineering': 10**22}}],
            'outside_options': [{'name': 'outside-'+str(i), 'provider': 'self_service', 'service_id': 'engineering',
                                 'price': 10**21+i, 'quality_bps': 10000, 'delay_cost': 0} for i in range(13)]}
        profile['services'] += ['engineering-'+str(i) for i in range(4)]
        profile['price_grids'] = {name: list(range(1, 11)) for name in profile['services']}
        profile['atoms'] = [{'weight_bps': 300 if i < 32 else 400, 'budget_microUSD': 10**22,
                             'values': dict.fromkeys(profile['services'], 10**22)} for i in range(33)]
        profiles = [{**copy.deepcopy(profile), 'id': 'profile-'+str(i)} for i in range(17)]
        market = compile_market({'schema': 'connected-complete-offer-market/v1', 'selection': 'menu', 'profiles': profiles})
        choice = actual_choice(market.context('buyer', 0), 0, 10**22, 'engineering', 10**20, 0)
        self.assertEqual(choice['name'], 'us')
        self.assertEqual(choice['spend'], 10**20)
        self.assertEqual(choice['utility'], 10**22-10**20)

    def test_declared_price_menu_and_cost_ratios_are_not_probability_caps(self):
        fixture = fixture_module('test_strategic024').StrategicChoice(); fixture.setUp()
        fixture.policy.update(price_bps=list(range(1, 103)), rival_price_bps=[40_000], rival_cost_bps=40_000)
        self.assertEqual(validate_policy(fixture.policy), fixture.policy)
        malformed = copy.deepcopy(fixture.policy)
        malformed['connected_beliefs']['baseline']['rival_available_bps'] = 10001
        with self.assertRaises(ValueError): validate_policy(malformed)

    def test_exact_conditional_best_response_is_scale_equivariant_and_cash_constrained(self):
        fixture = fixture_module('test_strategic024').StrategicChoice(); fixture.setUp()
        fixture.policy['ranking_arithmetic'] = 'exact-rational-v1'
        fixture.public['payment_bps'] = 0
        original = select(fixture.policy, fixture.methods, 'j', fixture.offer, None, fixture.public)
        multiplier = 10**15
        policy, methods, public = copy.deepcopy(fixture.policy), copy.deepcopy(fixture.methods), copy.deepcopy(fixture.public)
        for key in ('anchor', 'public_rival_price', 'base_cost', 'payment_fixed', 'available', 'reserve_buffer', 'quote_cost'):
            public[key] *= multiplier
        for belief in policy['connected_beliefs'].values():
            belief['min_budget_microUSD'] *= multiplier; belief['max_budget_microUSD'] *= multiplier
        for row in methods['costs'].values():
            for key in row: row[key] *= multiplier
        scaled = select(policy, methods, 'j', fixture.offer, None, public)
        rederive(scaled)
        self.assertEqual(scaled['decision']['selected']['mode'], original['decision']['selected']['mode'])
        self.assertEqual(scaled['offer']['price_microUSD'], original['offer']['price_microUSD']*multiplier)
        self.assertEqual(Fraction(scaled['decision']['selected']['expected_net_fraction']),
                         Fraction(original['decision']['selected']['expected_net_fraction'])*multiplier)
        self.assertLessEqual(scaled['decision']['selected']['required_current_cash'], public['available'])
        self.assertIsNone(select(policy, methods, 'j', fixture.offer, None, {**public, 'available': 0})['offer'])

        huge = 10**400
        for key in ('anchor', 'public_rival_price', 'base_cost', 'payment_fixed', 'available', 'reserve_buffer', 'quote_cost'):
            public[key] *= huge
        for belief in policy['connected_beliefs'].values():
            belief['min_budget_microUSD'] *= huge; belief['max_budget_microUSD'] *= huge
        for row in methods['costs'].values():
            for key in row: row[key] *= huge
        exact = select(policy, methods, 'j', fixture.offer, None, public)
        rederive(exact)
        self.assertEqual(exact['offer']['price_microUSD'], scaled['offer']['price_microUSD']*huge)
        self.assertEqual(Fraction(exact['decision']['selected']['expected_net_fraction']),
                         Fraction(scaled['decision']['selected']['expected_net_fraction'])*huge)
        self.assertIsNone(exact['decision']['selected']['expected_net'])

        legacy_policy = copy.deepcopy(policy); legacy_policy.pop('ranking_arithmetic')
        promoted = select(legacy_policy, methods, 'j', fixture.offer, None, public)
        rederive(promoted)
        self.assertEqual(promoted['problem']['policy'], legacy_policy)
        self.assertEqual(promoted['offer']['price_microUSD'], exact['offer']['price_microUSD'])
        self.assertEqual(promoted['decision']['selected']['expected_net_fraction'], exact['decision']['selected']['expected_net_fraction'])
        self.assertEqual(promoted['decision']['arithmetic_promotion'], 'FLOAT_RANGE_EXCEEDED_RATIONAL_COMPATIBLE_PUBLIC_MODEL')
        observation = {'scope': 'SIMULATED', 'state_digest': 'a'*64,
                       'summary': {'available': public['available'], 'unrestrictedEarned': 0}}
        risk = copy.deepcopy(fixture.risk)
        risk['authorized_allocation'] = public['available']
        risk['worst_loss_limit'] *= multiplier*huge
        delivery = {'id': 'large-offer', 'customer_id': 'buyer', 'onboarding': 0,
                    'exclusive_group': 'buyer', 'selection': promoted, 'requires': []}
        allocation = allocate_actions(observation, [delivery], [], risk)
        self.assertTrue(allocation['decision']['selected'])
        rederive_actions(allocation)
        self.assertLessEqual(allocation['decision']['reserve_amount'], public['available'])


class OpenScale064NativeMoney(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='open-scale064-engineering-source-')
        cls.root = Path(cls.tmp.name)/'source'
        for name in set(SOURCE_PATHS)|set(SERVICE_SOURCES)|set(PINS):
            destination = cls.root/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT/name, destination)
        cls.manifest = prepare_services(cls.root, 'services', cohort_seed=64001)
        cls.manifest['native_engine'] = 'exact-permanent-v2'

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_large_engineering_invoice_collection_and_earned_spend_conserve_native_money(self):
        opening, quoted, construction, expansion = 5*10**22, 4*10**20, 10**20, 10**20
        with JournalAccount(self.root, self.manifest, Path(self.tmp.name)/'fresh-engineering-account',
                            opening=opening, working=0, contract='ENGINEERING_STRESS_NOT_PRIMARY_100K_CHALLENGE') as account:
            job = next(j for j in self.manifest['jobs'] if j['service_id'] == 'reconciliation' and j['accepted'])
            account.cost('construction', construction, 0)
            account.execute('wallet', {'buyer': 'synthetic-engineering-buyer', 'amount': quoted}, 0)
            account.execute('offer', {'id': 'engineering-order', 'buyer': 'synthetic-engineering-buyer',
                'price': quoted, 'job_id': job['id'], 'deadline': 10}, 0)
            for action in ('consent', 'fund', 'prepare', 'release'):
                account.execute('event', {'id': 'engineering-order', 'action': action, 'event_id': action}, 0)
            receipt = account.spend('earned-capacity-contract', 'engineering_capacity', expansion, 1,
                {'scope': 'exact-money engineering conservation only'}, expected_net=1)
            self.assertEqual(receipt['funding'], 'EARNED')
            state = account.snapshot()['summary']
            self.assertEqual(state['revenue'], quoted)
            self.assertEqual(state['expenses'], construction+expansion)
            self.assertEqual(state['profit'], quoted-construction-expansion)
            self.assertEqual(state['cash'], opening+state['collections']-state['expensePaid'])
            self.assertEqual(state['available'], state['cash']-state['tailReserve'])
            self.assertEqual(state['payables'], 0)
            self.assertTrue(account.audit()['accepted'])

    def source(self):
        import hashlib
        files = {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.root.rglob('*.py') if 'services' not in p.relative_to(self.root).parts}
        return {'files': files, 'sha256': digest(files)}

    def test_trillion_day_horizon_is_lazy_and_authentically_resumable(self):
        import json
        from connected_enterprise.engine import run_world
        cfg = default_config()
        cfg.update(horizon_days=10**12, customer_pool=4, buyer_budget_multiplier_bps=0,
                   monetary_policy='exact-integer-v2')
        output = Path(self.tmp.name)/'trillion-day-checkpoint'
        first = run_world(self.root, self.manifest, cfg, 64, 'baseline', output,
                          source=self.source(), stop_after_events=2)
        self.assertFalse(first['complete'])
        self.assertEqual(first['processed_events'], 2)
        state = json.loads((output/'STATE.json').read_text())['body']['state']
        self.assertEqual(state['queue'], [{'id': 'plan-0001', 'time': 24, 'kind': 'plan'}])
        second = run_world(self.root, self.manifest, cfg, 64, 'baseline', output,
                           source=self.source(), stop_after_events=1)
        self.assertFalse(second['complete'])
        self.assertEqual(second['processed_events'], 3)
        self.assertEqual(second['summary']['expenses'], sum(c['amount'] for c in second['costs']))
        self.assertEqual(sum(c['amount'] for c in second['costs'] if c['category']=='maintenance'), 2*cfg['maintenance_daily'])
        self.assertTrue(all(c['time'] in (0,24) for c in second['costs']))
        self.assertEqual(second['summary']['profit'], -second['summary']['expenses'])
        state = json.loads((output/'STATE.json').read_text())['body']['state']
        self.assertEqual(state['queue'], [{'id': 'plan-0002', 'time': 48, 'kind': 'plan'}])
        self.assertEqual(state['last_time'], 24)

    def test_lazy_plan_order_matches_original_eager_short_trace(self):
        from unittest.mock import patch
        from connected_enterprise.engine import _initial, run_world
        stable = fixture_module('test_connected_engine').stable
        cfg = default_config()
        cfg.update(horizon_days=3, customer_pool=4, monetary_policy='exact-integer-v2')
        original = _initial
        def eager(*args):
            state = original(*args)
            state['queue'] = [{'id': '000-startup', 'time': 0, 'kind': 'startup'}]+[
                {'id': f'plan-{day:04d}', 'time': day*24, 'kind': 'plan'} for day in range(cfg['horizon_days'])]
            return state
        lazy = run_world(self.root, self.manifest, cfg, 65, 'baseline', Path(self.tmp.name)/'lazy-short', source=self.source())
        # Suppress duplicate insertion only for the explicit eager comparison.
        from connected_enterprise.engine import _schedule
        def eager_schedule(state, when, kind, ident, **fields):
            if kind == 'plan' and any(e['id'] == ident for e in state['queue']): return
            _schedule(state, when, kind, ident, **fields)
        with patch('connected_enterprise.engine._initial', side_effect=eager), patch('connected_enterprise.engine._schedule', side_effect=eager_schedule):
            eager_result = run_world(self.root, self.manifest, cfg, 65, 'baseline', Path(self.tmp.name)/'eager-short', source=self.source())
        self.assertEqual(stable(lazy), stable(eager_result))
