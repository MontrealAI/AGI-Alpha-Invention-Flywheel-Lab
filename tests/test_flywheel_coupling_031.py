"""Declared-premise and native-context boundaries, not an economic trial."""
import copy
import unittest
from unittest import mock
from test_flywheel_wheel_030 import fixtures
from flywheel_wheel.coupling import (SCHEMA, assess, context_from_rederived, live_context,
                                     verify_proposal, BASELINE_ALLOCATOR_BLOB)
from flywheel_wheel.readout import EvidenceError, sha


def context_fixture():
    audit, report, board = fixtures()
    for b in board['businesses']:
        b['executed_hours'] = 168
        b['native_actions_sha256'] = ('c' if b['business_reference'] == 'case-0' else 'd') * 64
        b['financial_state_microUSD'].update(available=12_000_000, unrestrictedEarned=8_000_000, investmentStopped=False)
    return audit, report, board


def sample():
    ctx = context_from_rederived(*context_fixture(), 'case-0')
    universe = {'jobs': [{'id': 'reconciliation'}]}
    direct = {'id': 'direct', 'lane': 'delivery', 'catalog_id': 'reconciliation', 'cost': 3_000_000,
              'requires': [], 'exclusive_group': 'same-outcome', 'cash_returns': {'central': 6_000_000},
              'evidence': 'declared-scenario-not-market-data', 'authorized': True}
    reuse = {**direct, 'id': 'reuse', 'cost': 1_000_000}
    attachment = {'scope': 'synthetic-reconciliation', 'asset_ids': [], 'incentive_ids': [],
                  'shared_cost_ids': [], 'producer': 'producer', 'checker': 'checker',
                  'fresh_mission_check': True, 'base_excludes_declared_extras': True}
    request = {
        'schema': SCHEMA, 'expected_context_sha256': sha(ctx), 'planning_cap_microUSD': 7_000_000,
        'allocation': {'schema': 'alpha-transformational-allocation/v1', 'scope': 'SIMULATED',
            'currency': 'simulated-microUSD', 'scenarios': {'central': 10000}, 'actions': [direct, reuse],
            'synergies': [], 'max_states': 65536, 'worst_loss_limit': 0, 'downside_penalty_bps': 10000},
        'assets': [{'id': 'source-index', 'artifact_sha256': 'e'*64, 'scope': 'synthetic-reconciliation',
            'qualification': 'QUALIFIED_IN_SCOPE', 'rights': 'PERMITTED', 'expires_hour': 200,
            'evidence_ref': 'declared-asset-qualification', 'shared_cost_ids': ['index-upkeep']}],
        'incentives': [{'id': 'verification-work', 'role': 'verifier', 'payee': 'checker',
            'adjudicator': 'auditor', 'basis': 'completed_check', 'cap_microUSD': 200_000,
            'evidence_ref': 'work-contract'}],
        'shared_costs': [{'id': 'index-upkeep', 'kind': 'maintenance', 'amount_microUSD': 300_000}],
        'attachments': {'direct': copy.deepcopy(attachment), 'reuse': copy.deepcopy(attachment)},
    }
    request['attachments']['reuse'].update(asset_ids=['source-index'], incentive_ids=['verification-work'])
    return request, ctx, universe


class CouplingTests(unittest.TestCase):
    def test_native_context_is_one_world_not_pooled(self):
        a, r, b = context_fixture()
        b['businesses'][1]['financial_state_microUSD']['available'] = 999_000_000
        c = context_from_rederived(a, r, b, 'case-0')
        self.assertEqual(c['available'], 12_000_000)
        self.assertFalse(c['funding_authority'])

    def test_missing_world_refused(self):
        with self.assertRaisesRegex(EvidenceError, 'ONE_EXISTING'): context_from_rederived(*context_fixture(), 'missing')

    def test_native_funding_fields_cannot_be_inferred_from_profit(self):
        a, r, b = context_fixture(); del b['businesses'][0]['financial_state_microUSD']['available']
        with self.assertRaisesRegex(EvidenceError, 'NATIVE_FUNDING'): context_from_rederived(a, r, b, 'case-0')

    def test_native_history_digest_required(self):
        a, r, b = context_fixture(); b['businesses'][0]['native_actions_sha256'] = 'fake'
        with self.assertRaisesRegex(EvidenceError, 'CONTENT_DIGEST'): context_from_rederived(a, r, b, 'case-0')

    def test_uses_existing_allocator_without_new_ledger(self):
        from portfolio_scale.transformational import choose
        r, c, u = sample()
        with mock.patch('portfolio_scale.transformational.choose', wraps=choose) as reused:
            p = assess(r, c, u)
        self.assertEqual(reused.call_count, 1)
        self.assertEqual(p['selected_actions'], ['reuse'])
        self.assertEqual(p['total_proposed_commitment_microUSD'], 1_500_000)
        self.assertEqual(p['planning_budget_microUSD'], 7_000_000)
        self.assertFalse(p['funding_authority']); self.assertFalse(p['execution_authority'])
        self.assertEqual(p['authority'], []); self.assertIsNone(p['current_proof'])

    def test_direct_method_wins_when_reuse_cost_is_higher(self):
        r, c, u = sample(); r['shared_costs'][0]['amount_microUSD'] = 4_000_000
        self.assertEqual(assess(r, c, u)['selected_actions'], ['direct'])

    def test_incentive_cap_can_change_selection(self):
        r, c, u = sample(); r['incentives'][0]['cap_microUSD'] = 4_000_000
        self.assertEqual(assess(r, c, u)['selected_actions'], ['direct'])

    def test_shared_asset_cost_and_reward_paid_once_in_plan(self):
        r, c, u = sample()
        new = copy.deepcopy(r['allocation']['actions'][1]); new['id'] = 'adjacent'
        new['exclusive_group'] = None
        r['allocation']['actions'].append(new)
        r['attachments']['adjacent'] = copy.deepcopy(r['attachments']['reuse'])
        p = assess(r, c, u)
        self.assertEqual(p['selected_actions'], ['adjacent', 'reuse'])
        self.assertEqual(p['total_proposed_commitment_microUSD'], 2_500_000)
        self.assertEqual(len(p['shared_and_incentive_provisions']), 2)

    def test_positive_profit_without_unrestricted_cash_cannot_invest(self):
        r, c, u = sample(); c['unrestrictedEarned'] = 0; r['expected_context_sha256'] = sha(c)
        p = assess(r, c, u)
        self.assertEqual(p['decision'], 'RETAIN_CASH'); self.assertEqual(p['planning_budget_microUSD'], 0)

    def test_native_stop_overrides_positive_cash(self):
        r, c, u = sample(); c['investmentStopped'] = True; r['expected_context_sha256'] = sha(c)
        self.assertEqual(assess(r, c, u)['decision'], 'RETAIN_CASH')

    def test_no_future_receipts_or_asset_value_fund_commitments(self):
        r, c, u = sample(); c['available'] = 1; r['expected_context_sha256'] = sha(c)
        r['allocation']['actions'][1]['cash_returns']['central'] = 10**15
        self.assertEqual(assess(r, c, u)['decision'], 'RETAIN_CASH')
        r['assets'][0]['market_value'] = 10**18
        with self.assertRaisesRegex(EvidenceError, 'EXACT_ASSET'): assess(r, c, u)

    def test_candidate_and_invalidated_assets_do_not_enable_reuse(self):
        for status in ('CANDIDATE', 'INVALIDATED', 'UNKNOWN'):
            with self.subTest(status=status):
                r, c, u = sample(); r['assets'][0]['qualification'] = status
                self.assertEqual(assess(r, c, u)['selected_actions'], ['direct'])

    def test_changed_scope_needs_new_qualification(self):
        r, c, u = sample(); r['attachments']['reuse']['scope'] = 'technical-writing'
        p = assess(r, c, u)
        self.assertIn('ASSET_SCOPE_CHANGED:source-index', p['blocked_actions']['reuse'])

    def test_unknown_rights_block_reuse(self):
        for status in ('UNKNOWN', 'DENIED'):
            r, c, u = sample(); r['assets'][0]['rights'] = status
            self.assertEqual(assess(r, c, u)['selected_actions'], ['direct'])

    def test_expiry_at_boundary_invalidates_asset(self):
        r, c, u = sample(); r['assets'][0]['expires_hour'] = c['observed_hour']
        self.assertEqual(assess(r, c, u)['selected_actions'], ['direct'])

    def test_favorable_verdict_reward_refused(self):
        r, c, u = sample(); r['incentives'][0]['basis'] = 'approved_candidate'
        with self.assertRaisesRegex(EvidenceError, 'INCENTIVE_MUST'): assess(r, c, u)

    def test_self_adjudication_refused(self):
        r, c, u = sample(); r['incentives'][0]['adjudicator'] = 'checker'
        with self.assertRaisesRegex(EvidenceError, 'SELF_ADJUDICATED'): assess(r, c, u)

    def test_producer_cannot_adjudicate_reward(self):
        r, c, u = sample(); r['incentives'][0]['adjudicator'] = 'producer'
        with self.assertRaisesRegex(EvidenceError, 'PRODUCER_CANNOT_ADJUDICATE'): assess(r, c, u)

    def test_producer_cannot_collect_own_review_fee(self):
        r, c, u = sample(); r['incentives'][0]['payee'] = 'producer'
        with self.assertRaisesRegex(EvidenceError, 'PRODUCER_CANNOT_REVIEW'): assess(r, c, u)

    def test_no_inherited_mission_proof(self):
        r, c, u = sample(); r['attachments']['reuse']['fresh_mission_check'] = False
        with self.assertRaisesRegex(EvidenceError, 'FRESH_MISSION_CHECK'): assess(r, c, u)

    def test_ambiguous_cost_attribution_refused(self):
        r, c, u = sample(); r['attachments']['reuse']['base_excludes_declared_extras'] = False
        with self.assertRaisesRegex(EvidenceError, 'EXPLICIT_NONOVERLAPPING'): assess(r, c, u)

    def test_duplicate_cost_id_and_duplicate_reference_refused(self):
        r, c, u = sample(); r['shared_costs'].append(copy.deepcopy(r['shared_costs'][0]))
        with self.assertRaisesRegex(EvidenceError, 'DUPLICATE_SHARED'): assess(r, c, u)
        r, c, u = sample(); r['attachments']['reuse']['asset_ids'].append('source-index')
        with self.assertRaisesRegex(EvidenceError, 'DUPLICATE_REFERENCE'): assess(r, c, u)

    def test_stale_native_state_or_other_world_refused(self):
        for key, value in [('actions_sha256', 'f'*64), ('world', 'case-1'), ('available', 4)]:
            r, c, u = sample(); c[key] = value
            with self.assertRaisesRegex(EvidenceError, 'STALE_OR_CROSS'): assess(r, c, u)

    def test_real_scope_and_authority_flags_refused(self):
        for key, value in [('scope', 'REAL'), ('funding_authority', True)]:
            r, c, u = sample(); c[key] = value; r['expected_context_sha256'] = sha(c)
            with self.assertRaises(EvidenceError): assess(r, c, u)

    def test_bool_float_negative_costs_refused(self):
        for value in (True, 0.5, -1):
            r, c, u = sample(); r['incentives'][0]['cap_microUSD'] = value
            with self.assertRaises(EvidenceError): assess(r, c, u)

    def test_unknown_returns_not_made_into_income(self):
        r, c, u = sample(); r['allocation']['actions'][1]['cash_returns'] = None
        p = assess(r, c, u)
        self.assertEqual(p['selected_actions'], ['direct'])
        self.assertIn('reuse', p['allocator']['unknown_return_actions'])

    def test_resource_limit_requires_decomposition(self):
        r, c, u = sample(); r['allocation']['max_states'] = 1
        self.assertEqual(assess(r, c, u)['decision'], 'DECOMPOSE_OR_RAISE_AUTHORIZED_PLANNING_BUDGET')

    def test_no_plan_tampering(self):
        r, c, u = sample(); p = assess(r, c, u)
        self.assertTrue(verify_proposal(p, r, c, u)['accepted'])
        p['total_proposed_commitment_microUSD'] = 0
        with self.assertRaisesRegex(EvidenceError, 'PROPOSAL_OR_NATIVE'): verify_proposal(p, r, c, u)

    def test_cost_replacement_never_edits_request(self):
        r, c, u = sample(); before = copy.deepcopy((r, c, u)); assess(r, c, u)
        self.assertEqual((r, c, u), before)

    def test_external_or_invented_effect_not_an_allocator_lane(self):
        r, c, u = sample(); r['allocation']['actions'][1]['lane'] = 'physical_control'
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_LANE'): assess(r, c, u)

    def test_invented_asset_financial_or_permission_fields_rejected(self):
        r, c, u = sample(); r['assets'][0]['authority'] = ['spend']
        with self.assertRaisesRegex(EvidenceError, 'EXACT_ASSET'): assess(r, c, u)

    def test_reward_basis_each_role_is_explicit(self):
        for role, basis in [('builder','accepted_outcome'), ('challenger','adjudicated_counterexample'),
                            ('originator','collected_incremental_surplus')]:
            r, c, u = sample(); r['incentives'][0].update(role=role, basis=basis)
            self.assertEqual(assess(r, c, u)['incentive_status'], 'CAPS_PROVISIONED_IN_PLAN_NOT_PAYABLE_OR_PAID')

    def test_reserved_and_unknown_dependencies_refused(self):
        r, c, u = sample(); r['allocation']['actions'][0]['requires'] = ['missing']
        with self.assertRaisesRegex(EvidenceError, 'ACTION_DEPENDENCIES'): assess(r, c, u)


if __name__ == '__main__': unittest.main()
