"""Native cash/acceptance/recovery regressions for numerical savings delivery."""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from commercial.ledger import canonical, digest
from connected_enterprise.finance import JournalAccount, audit_journal, source_paths_for_manifest
from experiments.commerce006 import PINS
from omega_savings import service

ROOT = Path(__file__).resolve().parents[1]
USD = 1_000_000


def copy_sources(target):
    for name in sorted(set(source_paths_for_manifest({'schema': service.SCHEMA})) | set(PINS)):
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)


class SavingsNative(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from omega_savings.kernel import build_request, solve
        cls.fixture = tempfile.TemporaryDirectory(prefix='omega-savings-native-source-')
        cls.root = Path(cls.fixture.name)
        copy_sources(cls.root)
        cls.request = build_request(7001, 'low_rank', n=32, cases=8, rank=2)
        cls.result = solve(cls.request, method='adaptive')

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='savings-case-', dir=self.root)
        self.path = Path(self.directory.name)
        self.accounts = []

    def tearDown(self):
        for account in self.accounts:
            account.close()
        self.directory.cleanup()

    def contract(self, ident='job', **changes):
        c = {'id': ident, 'request': copy.deepcopy(self.request), 'price_microUSD': 100 * USD,
             # Explicit assumption independent of the proposed price.
             'budget_microUSD': 250 * USD, 'costs_microUSD': {'production': 8 * USD,
             'verification': USD, 'storage_support': USD}, 'claim_window_hours': 4,
             'deadline_hours': 2, 'residual_bps': 0}
        c.update(changes)
        return c

    def manifest(self, *contracts, name='jobs'):
        return service.prepare_manifest(self.root, str(self.path.relative_to(self.root) / name), list(contracts))

    def account(self, manifest, *, name='account', opening=1000 * USD):
        a = JournalAccount(self.root, manifest, self.path / name, opening=opening, working=0,
                           contract='savings-native-test-' + name)
        self.accounts.append(a)
        return a

    def fulfill(self, account, manifest, *, ident='order', job='job', buyer=None, hour=0):
        return service.fulfill(account, self.root, manifest, job, order_id=ident,
                               buyer=buyer or ident, hour=hour, result=copy.deepcopy(self.result))

    def test_actual_delivery_budget_costs_and_independent_native_replay(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        r = self.fulfill(a, m)
        self.assertEqual(r['status'], 'released')
        s = a.snapshot()['summary']
        self.assertEqual(s['collections'], 100 * USD)
        self.assertEqual(s['expenses'], 10 * USD)
        self.assertEqual(s['profit'], 90 * USD)
        self.assertEqual(s['cash'], 1090 * USD)
        self.assertTrue(a.audit()['accepted'])
        record = a.export()
        self.assertEqual(next(x for x in record['ledger']['actions'] if x['op'] == 'wallet')['args']['amount'], 250 * USD)
        self.assertTrue(audit_journal(record, root=self.root, manifest=m)['accepted'])
        self.assertNotIn('key', record['connected_journal'])

    def test_cash_shortage_defers_investment_without_erasing_profit(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        self.fulfill(a, m)
        before = a.export()
        self.assertGreater(before['ledger']['summary']['profit'], 0)
        proposed = before['ledger']['summary']['available'] + 1
        self.assertIsNone(a.spend('unaffordable', 'capacity', proposed, 1, {'units': 2}, proposed * 2, allow_seed=True))
        self.assertEqual(a.export(), before)

    def test_future_income_cannot_finance_present_commitment(self):
        m = self.manifest(self.contract())
        a = self.account(m, opening=5 * USD)
        before = a.export()
        self.assertIsNone(a.spend('future', 'capacity', 10 * USD, 0, {'expected_future_sales': 1000}, 1000 * USD, allow_seed=True))
        self.assertEqual(self.fulfill(a, m)['status'], 'deferred_liquidity')
        self.assertEqual(a.export(), before)

    def test_unspent_seed_remains_available_when_earnings_exist(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        self.fulfill(a, m)
        s = a.snapshot()['summary']
        self.assertGreater(s['unrestrictedEarned'], 0)
        amount = s['unrestrictedEarned'] + USD
        self.assertLess(amount, s['available'])
        receipt = a.spend('seed-plus-earnings', 'capacity', amount, 1, {'units': 1}, amount * 2, allow_seed=True)
        self.assertEqual(receipt['funding'], 'SEED')
        self.assertTrue(a.audit()['accepted'])

    def test_complete_invoice_matches_itemized_funded_costs_exactly(self):
        m = self.manifest(self.contract())
        grouped = self.account(m, name='grouped-cost')
        itemized = self.account(m, name='itemized-cost')
        job, contract = service.contract_for(self.root, m, 'job')
        total = sum(contract['costs_microUSD'].values())
        self.assertGreaterEqual(grouped.snapshot()['summary']['available'], total)
        self.assertGreaterEqual(itemized.snapshot()['summary']['available'], total)
        for ident, value in service.cost_rows(job, 'invoice', contract):
            grouped.cost(ident, value, 0)
        for name, value in contract['costs_microUSD'].items():
            itemized.cost('independent-itemized-' + name, value, 0)
        self.assertEqual(grouped.snapshot()['summary'], itemized.snapshot()['summary'])
        self.assertEqual(grouped.snapshot()['summary']['expenses'], total)
        self.assertTrue(grouped.audit()['accepted']); self.assertTrue(itemized.audit()['accepted'])

    def test_sequential_feasible_orders_are_not_a_cohort_prefunding_limit(self):
        single = self.manifest(self.contract(), name='single')
        aggregate = self.manifest(self.contract(units=3), name='aggregate')
        seed = 111 * USD
        grouped = self.account(aggregate, name='aggregate-account', opening=seed)
        self.assertEqual(self.fulfill(grouped, aggregate)['status'], 'deferred_liquidity')
        individual = self.account(single, name='individual-account', opening=seed)
        for i in range(3):
            result = self.fulfill(individual, single, ident='order-' + str(i), hour=i * 5)
            self.assertEqual(result['status'], 'released')
            individual.advance_financial((i + 1) * 5)
        self.assertEqual(individual.snapshot()['summary']['collections'], 300 * USD)
        self.assertTrue(individual.audit()['accepted'])

    def test_aggregate_and_individual_finance_conserve_contingent_exposure_and_residuals(self):
        single = self.manifest(self.contract(residual_bps=137), name='single')
        aggregate = self.manifest(self.contract(units=3, residual_bps=137), name='aggregate')
        individual = self.account(single, name='individual-account')
        grouped = self.account(aggregate, name='aggregate-account')
        for i in range(3):
            self.assertEqual(self.fulfill(individual, single, ident='order-' + str(i))['status'], 'released')
        self.assertEqual(self.fulfill(grouped, aggregate)['status'], 'released')
        self.assertEqual(individual.snapshot()['summary'], grouped.snapshot()['summary'])
        individual.advance_financial(5); grouped.advance_financial(5)
        self.assertEqual(individual.snapshot()['summary'], grouped.snapshot()['summary'])
        self.assertEqual(grouped.snapshot()['summary']['tailReserve'], 3 * 137 * 100 * USD // 10000)
        self.assertTrue(individual.audit()['accepted']); self.assertTrue(grouped.audit()['accepted'])

    def test_maturity_is_not_revenue_and_residual_survives(self):
        m = self.manifest(self.contract(residual_bps=100))
        a = self.account(m)
        self.fulfill(a, m)
        prior = a.snapshot()['summary']
        a.advance_financial(4)
        self.assertEqual(a.snapshot()['summary'], prior)  # inclusive claim boundary
        a.advance_financial(5)
        after = a.snapshot()['summary']
        self.assertEqual(after['cash'], prior['cash'])
        self.assertEqual(after['revenue'], prior['revenue'])
        self.assertEqual(after['profit'], prior['profit'])
        self.assertEqual(after['tailReserve'], USD)
        self.assertGreater(after['available'], prior['available'])

    def test_immediate_tax_expense_payment_and_reserve_are_not_double_counted(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        self.fulfill(a, m)
        before = a.snapshot()['summary']
        assessment = before['profit'] * 2500 // 10000
        a.cost('tax-assessment-order', assessment, 1)
        after = a.snapshot()['summary']
        self.assertEqual(after['profit'], before['profit'] - assessment)
        self.assertEqual(after['expenses'] - before['expenses'], assessment)
        self.assertEqual(after['expensePaid'] - before['expensePaid'], assessment)
        self.assertEqual(after['cash'], before['cash'] - assessment)
        self.assertEqual(after['payables'], 0)  # declared immediate schedule; no deferred tax
        record = a.export()
        a.cost('tax-assessment-order', assessment, 1)
        self.assertEqual(a.export(), record)

    def test_earned_spend_preserves_mixed_live_and_matured_order_protection(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        self.fulfill(a, m, ident='matured-order', hour=0)
        a.advance_financial(5)
        self.fulfill(a, m, ident='live-order', hour=6)
        job, c = service.contract_for(self.root, m, 'job')
        for ident, value in service.cost_rows(job, 'pending-order', c):
            a.cost(ident, value, 6)
        a.execute('wallet', {'buyer': 'pending-buyer', 'amount': c['budget_microUSD']}, 6)
        a.execute('register_terms', {'id': 'pending-order:terms',
            'terms': service.terms_for(m, 'pending-order', c, 6)}, 6)
        a.execute('offer', {'id': 'pending-order', 'buyer': 'pending-buyer',
            'price': c['price_microUSD'], 'job_id': 'job', 'deadline': 8,
            'terms_id': 'pending-order:terms'}, 6)
        for action in ('consent', 'fund'):
            a.execute('event', {'id': 'pending-order', 'action': action,
                'event_id': 'pending-order:' + action}, 6)
        artifact = service.produce(self.root, m, 'job')
        a.execute('event', {'id': 'pending-order', 'action': 'prepare',
            'event_id': 'pending-order:prepare', 'artifact_sha256': digest(artifact)}, 6)
        before = a.snapshot()['summary']
        self.assertEqual(before['payables'], 0)
        self.assertGreater(before['custodyReserve'], 0)
        self.assertGreater(before['tailReserve'], 0)
        receipt = a.spend('mixed-protection-resource', 'capacity', 20 * USD, 7,
                          {'installed_known_method': True}, 50 * USD, allow_seed=True)
        self.assertEqual(receipt['funding'], 'EARNED')
        after = a.snapshot()['summary']
        for key in ('custodyReserve', 'tailReserve', 'collections', 'revenue'):
            self.assertEqual(after[key], before[key])
        self.assertEqual(after['expenses'] - before['expenses'], 20 * USD)
        self.assertEqual(after['expensePaid'] - before['expensePaid'], 20 * USD)
        self.assertTrue(a.audit()['accepted'])

    def test_pending_claim_is_paid_before_earned_spend_without_lost_protection(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        self.fulfill(a, m)
        claim = {'id': 'order', 'claim_id': 'order:dispute',
                 'amount': 10 * USD, 'kind': 'disputed'}
        a.execute('claim', claim, 1)
        pending = a.snapshot()['summary']
        self.assertEqual(pending['payables'], 10 * USD)
        self.assertGreater(pending['unrestrictedEarned'], 20 * USD)
        # Native resource completion requires no outstanding invoice. The
        # scheduler must execute the already-due payment before new spending;
        # positive current cash does not erase this distinct native precondition.
        resolution = {'id': 'order', 'claim_id': 'order:dispute',
                      'settlement_id': 'order:dispute:paid', 'resolution': 'pay'}
        a.execute('resolve_claim', resolution, 3)
        resolved = a.snapshot()['summary']
        self.assertEqual(resolved['payables'], 0)
        self.assertEqual(resolved['expenses'], pending['expenses'])
        self.assertEqual(resolved['tailReserve'], pending['tailReserve'])
        self.assertEqual(resolved['cash'], pending['cash'] - 10 * USD)
        self.assertEqual(resolved['available'], pending['available'])
        prior = a.export()
        a.execute('resolve_claim', resolution, 3)
        self.assertEqual(a.export(), prior)
        receipt = a.spend('after-claim-payment', 'capacity', 20 * USD, 3,
                          {'installed_known_method': True}, 50 * USD, allow_seed=True)
        self.assertEqual(receipt['funding'], 'EARNED')
        self.assertTrue(a.audit()['accepted'])

    def test_recovery_after_native_funding_does_not_duplicate_cost_payment_or_order(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        original = a._account.execute
        def interrupt(op, args, day):
            result = original(op, args, day)
            if op == 'event' and args.get('action') == 'fund':
                raise InterruptedError('after durable buyer funding')
            return result
        with patch.object(a._account, 'execute', interrupt), self.assertRaises(InterruptedError):
            self.fulfill(a, m)
        a.close()
        recovered = self.account(m)
        self.assertEqual(self.fulfill(recovered, m)['status'], 'released')
        before = recovered.export()
        self.assertEqual(self.fulfill(recovered, m)['status'], 'released')
        self.assertEqual(recovered.export(), before)
        for action in ('fund', 'release'):
            self.assertEqual(sum(x['op'] == 'event' and x['args']['action'] == action for x in before['ledger']['actions']), 1)
        self.assertTrue(recovered.audit()['accepted'])

    def test_actual_artifact_tampering_rejects_independent_replay(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        self.fulfill(a, m)
        record = a.export(); a.close()
        path = self.root / m['jobs'][0]['output']
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b'"units":1', b'"units":2'))
        with self.assertRaises(ValueError):
            audit_journal(record, root=self.root, manifest=m)
        path.write_bytes(raw)
        self.assertTrue(audit_journal(record, root=self.root, manifest=m)['accepted'])

    def test_native_prefix_reuse_rebinds_delivery_before_new_spending(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        self.fulfill(a, m)
        self.assertIsNotNone(a._native_prefix)
        a.cost('after-delivery', USD, 1)
        before = a.export()
        path = self.root / m['jobs'][0]['output']
        raw = path.read_bytes()
        try:
            path.write_bytes(raw.replace(b'"units":1', b'"units":2'))
            with self.assertRaises(ValueError):
                a.cost('must-rebind-first', USD, 2)
            self.assertEqual(a.export(), before)
        finally:
            path.write_bytes(raw)
        a.cost('must-rebind-first', USD, 2)
        self.assertEqual(a.snapshot()['summary']['expenses'], 12 * USD)
        self.assertTrue(a.audit()['accepted'])

    def test_evicted_semantic_cache_does_not_force_old_prefix_reproof(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        self.fulfill(a, m)
        a.cost('qualify-prefix-through-release', 0, 1)
        # Fill the bounded semantic cache with 129 distinct rejected receipts.
        # These are engineering cache inputs, not simulated sales or accounts.
        changed = copy.deepcopy(self.result)
        changed['count_model']['candidate_complete_proxy_units'] = 1
        for index in range(129):
            self.assertFalse(service._accepted_semantics(str(index), canonical(self.request),
                canonical(changed), 'adaptive', 0))
        self.assertEqual(service._accepted_semantics.cache_info().currsize, 128)
        with patch.object(service, '_accepted_semantics', side_effect=AssertionError('old prefix reproof')):
            a.cost('after-cache-eviction', USD, 2)
        # Public audit does not accept the private prefix as portable authority.
        with patch.object(service, '_accepted_semantics', wraps=service._accepted_semantics) as checked:
            self.assertTrue(a.audit()['accepted'])
            self.assertGreater(checked.call_count, 0)

    def test_raw_prefix_binding_rejects_even_equivalent_json_byte_changes(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        self.fulfill(a, m)
        a.cost('qualify-raw-prefix', 0, 1)
        self.assertTrue(a._native_prefix._omega_byte_bindings)
        before = a.export()
        path = self.root / m['jobs'][0]['output']
        raw = path.read_bytes()
        try:
            path.write_bytes(raw + b'\n')
            # The canonical native artifact is unchanged, but the private raw
            # binding correctly refuses bytes changed since qualification.
            with self.assertRaisesRegex(ValueError, 'PREPARED_BYTES'):
                a.cost('must-rebind-raw-bytes', 0, 2)
            self.assertEqual(a.export(), before)
            self.assertEqual(a._native_prefix._omega_byte_bindings, {})
        finally:
            path.write_bytes(raw)
        a.cost('must-rebind-raw-bytes', 0, 2)
        self.assertTrue(a.audit()['accepted'])

    def test_raw_prefix_reads_both_files_but_public_replay_requalifies_json(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        self.fulfill(a, m)
        a.cost('prime-raw-read-test', 0, 1)
        input_path = self.root / m['jobs'][0]['input']
        output_path = self.root / m['jobs'][0]['output']
        observed = set()
        original_read = Path.read_bytes
        def read(path):
            if path in (input_path, output_path):
                observed.add(path)
            return original_read(path)
        with patch.object(Path, 'read_bytes', read), patch.object(service, 'strict_json',
                side_effect=AssertionError('historical output reparsed')):
            a.cost('actual-raw-read', 0, 2)
        self.assertEqual(observed, {input_path, output_path})
        with patch.object(service, 'strict_json', side_effect=AssertionError('public replay parses')):
            with self.assertRaisesRegex(AssertionError, 'public replay parses'):
                a.audit()
        self.assertEqual(a._native_prefix._omega_byte_bindings, {})
        self.assertTrue(a.audit()['accepted'])

    def test_raw_prefix_cache_cannot_authorize_changed_historical_actions(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        self.fulfill(a, m)
        a.cost('prime-action-prefix', 0, 1)
        actions = a._account._owner._exchange.actions
        original = copy.deepcopy(actions[0])
        try:
            actions[0]['args']['amount'] += USD
            with self.assertRaises(ValueError):
                a.cost('must-replay-changed-prefix', 0, 2)
            self.assertEqual(a._native_prefix._omega_byte_bindings, {})
        finally:
            actions[0] = original
        self.assertTrue(a.audit()['accepted'])

    def test_unpaid_costs_and_changed_buyer_budget_cannot_release(self):
        m = self.manifest(self.contract())
        a = self.account(m)
        job, c = service.contract_for(self.root, m, 'job')
        a.execute('wallet', {'buyer': 'buyer', 'amount': 100 * USD}, 0)
        a.execute('register_terms', {'id': 'order:terms', 'terms': service.terms_for(m, 'order', c, 0)}, 0)
        a.execute('offer', {'id': 'order', 'buyer': 'buyer', 'price': 100 * USD,
                           'job_id': 'job', 'deadline': 2, 'terms_id': 'order:terms'}, 0)
        for action in ('consent', 'fund'):
            a.execute('event', {'id': 'order', 'action': action, 'event_id': action}, 0)
        artifact = service.produce(self.root, m, 'job', copy.deepcopy(self.result))
        with self.assertRaisesRegex(ValueError, 'FULLY_PAID_COSTS'):
            a.execute('event', {'id': 'order', 'action': 'prepare', 'event_id': 'prepare-unpaid', 'artifact_sha256': digest(artifact)}, 0)
        for ident, value in service.cost_rows(job, 'order', c):
            a.cost(ident, value, 0)
        with self.assertRaisesRegex(ValueError, 'BUYER_BUDGET'):
            a.execute('event', {'id': 'order', 'action': 'prepare', 'event_id': 'prepare-wrong-budget', 'artifact_sha256': digest(artifact)}, 0)
        self.assertEqual(a.snapshot()['summary']['collections'], 0)

    def test_budget_below_price_declines_without_cost_or_forced_purchase(self):
        m = self.manifest(self.contract(budget_microUSD=25 * USD))
        a = self.account(m)
        before = a.export()
        self.assertEqual(self.fulfill(a, m)['status'], 'declined')
        self.assertEqual(a.export(), before)

    def test_mathematically_valid_output_must_meet_registered_work_proxy_promise(self):
        m = self.manifest(self.contract(minimum_saved_bps=10000))
        a = self.account(m)
        # Correct output still cannot deliver a promised 100% work reduction.
        result = self.fulfill(a, m)
        self.assertEqual(result['status'], 'refunded')
        summary = a.snapshot()['summary']
        self.assertEqual(summary['collections'], 0)
        self.assertEqual(summary['revenue'], 0)
        self.assertEqual(summary['expenses'], 10 * USD)
        self.assertEqual(summary['profit'], -10 * USD)
        self.assertTrue(a.audit()['accepted'])

    def test_semantic_cache_cannot_hide_changed_recipe_count_or_source(self):
        m = self.manifest(self.contract())
        artifact = service.produce(self.root, m, 'job', copy.deepcopy(self.result))
        self.assertTrue(service.check_delivery(self.root, m, 'job', artifact)['accepted'])
        cache = service._accepted_semantics.cache_info()
        self.assertTrue(service.check_delivery(self.root, m, 'job', artifact)['accepted'])
        self.assertGreater(service._accepted_semantics.cache_info().hits, cache.hits)
        path = self.root / m['jobs'][0]['output']
        original = path.read_bytes()
        for field in ('count', 'program'):
            changed = copy.deepcopy(artifact)
            if field == 'count':
                changed['result']['count_model']['candidate_complete_proxy_units'] = 1
            else:
                changed['result']['program_sha256'] = '0' * 64
            path.write_bytes(canonical(changed) + b'\n')
            self.assertFalse(service.check_delivery(self.root, m, 'job', changed)['accepted'])
        path.write_bytes(original)
        source = self.root / 'omega_savings/verify.py'
        prior = source.read_bytes()
        try:
            source.write_bytes(prior + b'\n# changed checker\n')
            with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
                service.check_delivery(self.root, m, 'job', artifact)
        finally:
            source.write_bytes(prior)
        self.assertTrue(service.check_delivery(self.root, m, 'job', artifact)['accepted'])

    def test_procedural_generation_has_no_initial_catalogue_ceiling(self):
        from omega_savings.world import make_rule
        rule = make_rule(101, 'positive')
        relative = str(self.path.relative_to(self.root) / 'procedural')
        m = service.prepare_manifest(self.root, relative, rule=rule)
        # Large indices exercise generation, not a projection of market demand.
        ident = 'c100000000000000000000t0p0a0u1l99999999999'
        first = service.load_contracts(self.root, m)
        second = service.load_contracts(self.root, m)
        self.assertEqual(first, second)
        self.assertIn(ident, first)
        job, contract = service.contract_for(self.root, m, ident)
        self.assertFalse((self.root / job['input']).exists())
        self.assertEqual(contract['budget_microUSD'], 500 * USD)
        self.assertEqual(contract['price_microUSD'], 299 * USD)
        a = self.account(m)
        result = service.fulfill(a, self.root, m, ident, order_id='procedural-order',
                                buyer='procedural-buyer', hour=0)
        self.assertEqual(result['status'], 'released')
        self.assertTrue((self.root / job['input']).exists())
        self.assertTrue(a.audit()['accepted'])
        self.assertTrue(audit_journal(a.export(), root=self.root, manifest=m)['accepted'])
        self.assertNotIn('capped_customers', m)
        request_path = self.root / job['input']
        request_bytes = request_path.read_bytes()
        try:
            request_path.write_bytes(request_bytes + b'\n')
            with self.assertRaisesRegex(ValueError, 'INPUT_CHANGED'):
                service.contract_for(self.root, m, ident)
        finally:
            request_path.write_bytes(request_bytes)

    def test_invalid_costs_units_terms_and_nonfinite_requests_fail_before_account(self):
        for change in ({'units': True}, {'units': 0}, {'budget_microUSD': -1},
                       {'price_microUSD': 0}, {'residual_bps': 10001}, {'minimum_saved_bps':10001},
                       {'collection_delay_hours': 5}, {'request': {'x': float('nan')}},
                       {'costs_microUSD': {'production': -1}}):
            with self.subTest(change=change), self.assertRaises((ValueError, TypeError)):
                service.validate_contract(self.contract(**change))


if __name__ == '__main__':
    unittest.main()
