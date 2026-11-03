"""Native counterpart identity, crash boundaries, public replay and funding gates."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
import unittest

from commercial.ledger import canonical, digest
from connected_enterprise.finance import JournalAccount
from omega import competitive, primary_operator as primary, successor

ROOT = Path(__file__).resolve().parents[1]


class PrimaryAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.reg = primary.registration(ROOT)
        self.plan = successor.plan(ROOT)
        self.summary = {'available': 100_000 * primary.MICRO, 'unrestrictedEarned': 70_000 * primary.MICRO,
                        'profit': 70_000 * primary.MICRO, 'investmentStopped': False}

    def test_withdrawal_and_native_tax_protected_illiquidity_compete(self):
        for value, selected in [(0, False), (primary.MICRO, False), (3 * primary.MICRO, True)]:
            reg = copy.deepcopy(self.reg); reg['successor_decision']['task_value_microUSD'] = value
            decision = primary.successor_choice(self.summary, reg, self.plan)
            self.assertIs(decision['selected'], selected)
            self.assertEqual(decision['withdrawal_net_microUSD'], 0)
        illiquid = dict(self.summary, available=100 * primary.MICRO, unrestrictedEarned=100 * primary.MICRO,
                        profit=100 * primary.MICRO)
        original = copy.deepcopy(illiquid)
        self.assertFalse(primary.successor_choice(illiquid, self.reg, self.plan)['selected'])
        self.assertEqual(illiquid, original)  # Profit is not erased by unavailable funding.
        unearned = dict(self.summary, unrestrictedEarned=0)
        self.assertFalse(primary.successor_choice(unearned, self.reg, self.plan)['selected'])

    def test_forecast_utility_is_not_ordinary_reuse_superiority(self):
        decision = primary.successor_choice(self.summary, self.reg, self.plan)
        self.assertEqual(decision['method'], 'ORDINARY_EQUIVALENT_REUSE')
        self.assertEqual(decision['complete_cost_microUSD'], 5_100_000)
        self.assertEqual(decision['reuse_expected_net_microUSD'], 3_900_000)
        self.assertEqual(decision['expected_resource_saving_microUSD'], 1_200_000)

    def test_public_observation_excludes_hidden_environment(self):
        state = {'quarter': 0, 'built': [], 'successor_status': 'NOT_FUNDED', 'signal': None, 'outcome': None}
        observation = primary.public_observation(state, self.summary, self.reg['selection'])
        self.assertEqual(set(observation), set(competitive.initial_public(primary.game_for(self.reg['selection']))))
        self.assertNotIn('world_id', observation); self.assertNotIn('reach', observation)
        changed = copy.deepcopy(self.reg['selection']); changed['reach'] = [False] * 4
        with self.assertRaisesRegex(ValueError, 'EXACT_PRIMARY'):
            primary.registration(ROOT, changed)

    def test_one_budget_for_complete_selected_package(self):
        row = {'orders': [dict(status='accepted', buyer_group_id='buyer', product=p, price_cents=price)
                          for p, price in [('self_hosted', 29900), ('group_webinar', 9900)]],
               'buyer_decisions': [{'buyer_group_id': 'buyer', 'synthetic_consent': True, 'provider': 'us',
                                    'selected_package': ['self_hosted', 'group_webinar'], 'total_price_cents': 39800,
                                    'spent_before_cents': 0, 'budget_cents': 39800}]}
        self.assertTrue(primary.check_joint_budgets(row))
        row['buyer_decisions'][0]['budget_cents'] = 29900
        with self.assertRaisesRegex(ValueError, 'WHOLE_BUYER'):
            primary.check_joint_budgets(row)

    def test_task_count_cannot_replace_individual_acceptance(self):
        ids = primary.TASK_IDS
        use = {'artifact_sha256': self.plan['artifact_sha256'], 'task_ids': ids, 'case_count': 3,
               'accepted_case_count': 3, 'task_cost_each_microUSD': 1_000_000, 'total_task_cost_microUSD': 3_000_000,
               'tasks': [{'task_id': ident, 'request_sha256': '0' * 64, 'result': {}, 'result_sha256': digest({}),
                          'acceptance': {'id': ident, 'accepted': True}} for ident in ids]}
        self.assertTrue(primary.check_successor_uses(use, self.plan, self.reg['successor_decision']))
        use['tasks'][0]['acceptance']['accepted'] = False
        with self.assertRaisesRegex(ValueError, 'SUCCESSOR_FUTURE'):
            primary.check_successor_uses(use, self.plan, self.reg['successor_decision'])


class PrimaryDurabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name) / 'registered-test-counterpart'
        cls.interrupted_fund = primary.run(cls.path, root=ROOT, interrupt_after='first-fund')
        cls.after_fund = cls.export()
        cls.interrupted_tax = primary.run(cls.path, root=ROOT, resume=True, interrupt_after='tax')
        cls.after_tax = cls.export()
        cls.result = primary.run(cls.path, root=ROOT, resume=True)
        cls.reg = primary.read(cls.path / 'registration.json')
        cls.manifest = primary.read(cls.path / 'manifest.json')
        cls.record = primary.read(cls.path / 'public-native.json')
        cls.state = primary.read(cls.path / 'public-operation.json')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def export(cls):
        reg = primary.read(cls.path / 'registration.json')
        manifest = primary.read(cls.path / 'manifest.json')
        with JournalAccount(cls.path / 'source', manifest, cls.path / 'account.sqlite',
                            opening=100_000 * primary.MICRO, working=0,
                            contract='omega-primary-counterpart:' + digest(reg)) as account:
            return account.export()

    def audit_state(self, state):
        return primary.derive_report(self.path, self.reg, self.manifest, self.record, state)

    def test_actual_postcommit_crashes_resume_once(self):
        self.assertFalse(self.interrupted_fund['complete']); self.assertFalse(self.interrupted_tax['complete'])
        fund = self.after_fund['ledger']['actions'][-1]
        self.assertEqual((fund['op'], fund['args']['action']), ('event', 'fund'))
        tax = self.after_tax['ledger']['actions'][-1]
        self.assertEqual(tax['args']['id'], 'corrected-year-tax-sensitivity')
        actions = self.record['ledger']['actions']
        self.assertEqual(sum(a['op'] == 'cost' and a['args']['id'] == 'corrected-year-tax-sensitivity' for a in actions), 1)
        self.assertEqual(canonical(actions[:-1]), canonical(self.after_tax['ledger']['actions']))
        self.assertEqual(digest(actions[:42]), primary.HISTORY_ACTIONS)
        self.assertEqual(actions[41]['after']['cash'], 75_200 * primary.MICRO)
        self.assertEqual(self.record['ledger']['config']['opening'], 100_000 * primary.MICRO)

    def test_full_365_days_and_native_earned_successor(self):
        self.assertTrue(primary.replay(self.path)['accepted'])
        self.assertFalse(self.result['original_account_recovered'])
        self.assertFalse(self.result['three_billion_objective_achieved'])
        self.assertEqual(self.result['successor_status'], 'QUALIFIED')
        intent = self.result['successor_intent']
        self.assertEqual(intent['funding_receipt']['funding'], 'EARNED')
        self.assertEqual(intent['uses']['accepted_case_count'], 3)
        self.assertEqual(self.record['ledger']['actions'][-1]['day'], 17519)
        self.assertEqual(self.result['selection']['operating_end_hour_exclusive'] - self.result['selection']['operating_start_hour'], 365 * 24)
        self.assertEqual({j['product'] for j in self.manifest['jobs']}, {'self_hosted', 'group_webinar', 'founder_private'})

    def test_repeated_resume_cannot_reseed_or_duplicate(self):
        previous = self.record['ledger']['actions_sha256']
        again = primary.run(self.path, root=ROOT, resume=True)
        self.assertEqual(again['native_actions_sha256'], previous)
        with self.assertRaisesRegex(ValueError, 'NEVER_RESEED'):
            primary.run(self.path, root=ROOT)

    def test_missing_authority_does_not_create_replacement(self):
        key = self.path / 'account.sqlite.adaptive-simulation-key'
        temporary = key.with_name(key.name + '.held-for-test')
        key.rename(temporary)
        try:
            with self.assertRaisesRegex(ValueError, 'SAME_COUNTERPART_PRIVATE_AUTHORITY_REQUIRED'):
                primary.run(self.path, root=ROOT, resume=True)
            self.assertFalse(key.exists())
        finally:
            temporary.rename(key)

    def test_missing_native_database_cannot_trigger_fresh_initialization(self):
        database = self.path / 'account.sqlite'; temporary = database.with_name('database-held-for-test.sqlite')
        database.rename(temporary)
        try:
            with self.assertRaisesRegex(ValueError, 'SAME_COUNTERPART_NATIVE_DATABASE_AND_JOURNAL_REQUIRED'):
                primary.run(self.path, root=ROOT, resume=True)
            self.assertFalse(database.exists())
        finally:
            temporary.rename(database)

    def test_forged_successor_outputs_status_and_spend_rejected(self):
        bad = copy.deepcopy(self.state); bad['successor_intent']['uses']['tasks'][0]['result']['error'] = 'FORGED'
        with self.assertRaisesRegex(ValueError, 'SUCCESSOR_STORED_EVIDENCE_CHANGED'):
            self.audit_state(bad)
        bad = copy.deepcopy(self.state); bad['successor_intent']['funding_receipt']['work_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'CANONICAL_EARNED'):
            self.audit_state(bad)
        bad = copy.deepcopy(self.state); bad['successor_intent'] = None
        with self.assertRaisesRegex(ValueError, 'SUCCESSOR_ACTION_MISSING'):
            self.audit_state(bad)

    def test_trace_and_tax_mutations_rejected(self):
        bad = copy.deepcopy(self.state); bad['trace'][-1]['id'] = 'unregistered-id'
        with self.assertRaisesRegex(ValueError, 'ACTION_DEPENDENT'):
            self.audit_state(bad)
        bad = copy.deepcopy(self.state); bad['tax']['tax_microUSD'] -= 1
        with self.assertRaisesRegex(ValueError, 'TAX_SENSITIVITY'):
            self.audit_state(bad)

    def test_registered_claim_reserve_and_catalog_cannot_change(self):
        index = primary.read(self.path / 'jobs.json'); game = primary.game_for(self.reg['selection'])
        for field, value in [('claim_window_hours', 1), ('residual_bps', 0)]:
            changed = copy.deepcopy(self.manifest); changed[field] = value
            with self.assertRaisesRegex(ValueError, 'REGISTERED_PRODUCT_TERMS_CHANGED'):
                primary.validate_manifest(self.path / 'source', game, changed, index)
        changed = copy.deepcopy(index); first = next(iter(changed)); changed[first] += 1
        with self.assertRaisesRegex(ValueError, 'REGISTERED_FIXED_PRODUCT_CATALOG_CHANGED'):
            primary.validate_manifest(self.path / 'source', game, self.manifest, changed)
        changed = copy.deepcopy(self.manifest); changed['jobs'] = changed['jobs'][::-1]
        with self.assertRaisesRegex(ValueError, 'REGISTERED_FIXED_PRODUCT_CATALOG_CHANGED'):
            primary.validate_manifest(self.path / 'source', game, changed, index)

    def test_source_and_headline_mutations_rejected(self):
        path = self.path / 'source/omega/primary_operator.py'; original = path.read_bytes()
        try:
            path.write_bytes(original + b'\n# changed\n')
            with self.assertRaisesRegex(ValueError, 'PRIMARY_SOURCE_POLICY_CHANGED'):
                primary.replay(self.path)
        finally:
            path.write_bytes(original)
        path = self.path / 'result.json'; original = path.read_bytes()
        try:
            altered = primary.read(path); altered['three_billion_objective_achieved'] = True
            primary.write(path, altered)
            with self.assertRaisesRegex(ValueError, 'PRIMARY_REPORTED_RESULT_CHANGED'):
                primary.replay(self.path)
        finally:
            path.write_bytes(original)


if __name__ == '__main__':
    unittest.main()
