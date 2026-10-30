import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from experiments.consequential009_commerce import ROOT, canonical, conditional_frontier, load_authority, run, validate_policy


class Commerce009Tests(unittest.TestCase):
    def policy(self):
        return json.loads((ROOT / 'campaign/consequential-009/COMMERCIAL_POLICY.json').read_bytes())

    def frame(self, directory):
        paths = {key: directory / (key + '.json') for key in ['artifact', 'receipt', 'protocol', 'candidate', 'verifier']}
        for key in ['artifact', 'protocol', 'candidate', 'verifier']:
            paths[key].write_bytes(canonical({'engineering_test_only': key}))
        expected = {key: hashlib.sha256(paths[key].read_bytes()).hexdigest() for key in ['artifact', 'protocol', 'candidate', 'verifier']}
        receipt = {key + '_sha256': value for key, value in expected.items()}
        receipt['accepted'] = True
        paths['receipt'].write_bytes(canonical(receipt))
        expected['receipt'] = hashlib.sha256(paths['receipt'].read_bytes()).hexdigest()
        return paths, expected

    def test_policy_carries_complete_costs_stresses_and_sourced_fee(self):
        policy = self.policy()
        validate_policy(policy)
        bad = copy.deepcopy(policy)
        del bad['modeled_costs_microUSD']['inference']
        with self.assertRaisesRegex(ValueError, 'ALL_COMPLETE_COST'):
            validate_policy(bad)
        bad = copy.deepcopy(policy)
        bad['route']['processing_fixed_microUSD'] = 0
        with self.assertRaisesRegex(ValueError, 'FROZEN_ROUTE'):
            validate_policy(bad)

    def test_artifact_receipt_and_source_frames_are_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, expected = self.frame(Path(directory))
            load_authority(paths, expected)
            paths['artifact'].write_bytes(canonical({'engineering_test_only': 'changed'}))
            with self.assertRaisesRegex(ValueError, 'SOURCE_OR_ARTIFACT_CHANGED'):
                load_authority(paths, expected)

    def test_false_acceptance_and_receipt_source_substitution_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, expected = self.frame(Path(directory))
            receipt = json.loads(paths['receipt'].read_bytes())
            receipt['accepted'] = False
            paths['receipt'].write_bytes(canonical(receipt))
            expected['receipt'] = hashlib.sha256(paths['receipt'].read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'NOT_INDEPENDENTLY_ACCEPTED'):
                load_authority(paths, expected)
            receipt['accepted'] = True
            receipt['verifier_sha256'] = '0' * 64
            paths['receipt'].write_bytes(canonical(receipt))
            expected['receipt'] = hashlib.sha256(paths['receipt'].read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'SOURCE_FRAME_MISMATCH'):
                load_authority(paths, expected)

    def test_economic_parity_does_not_veto_conditional_human_service_margin(self):
        out = conditional_frontier(self.policy(), 50_000_000, 1_750_000)
        self.assertEqual(out['AI_conditional_profit_microUSD'], 12_250_000)
        self.assertEqual(out['AI_actual_profit_interval_microUSD'], [None, None])
        self.assertIn('does not veto', out['technical_parity_policy'])
        self.assertLess(out['human_conditional_grid'][3]['profit_upper_microUSD_before_unknown_setup_tools_service_overhead'], 0)
        self.assertIn('UNESTABLISHED', out['human_to_AI_crossing'])

    def test_actual_exchange_retains_unsold_costs_reversals_and_conditional_reserve(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            paths, expected = self.frame(directory)
            policy_path = ROOT / 'campaign/consequential-009/COMMERCIAL_POLICY.json'
            result = run(paths, expected, policy_path, hashlib.sha256(policy_path.read_bytes()).hexdigest(), directory / 'worlds')
            worlds = {world['id']: world for world in result['worlds']}
            nominal = worlds['conditional_participation']
            self.assertEqual(nominal['economics']['AI_conditional_profit_microUSD'], 12_250_000)
            self.assertIsNotNone(nominal['conditional_investment_reservation'])
            self.assertEqual(nominal['construction_spend'], 0)
            self.assertEqual(nominal['snapshots']['after_prespecified_conditional_reservation']['reservedInvestment'], 10_000_000)
            for name in ['zero_demand', 'equal_ai_native_outside_option', 'strategic_nonpayment']:
                self.assertEqual(worlds[name]['economics']['AI_conditional_profit_microUSD'], -36_000_000)
            adverse = worlds['correlated_benefit_warranty_reversals']
            self.assertEqual(adverse['economics']['AI_conditional_profit_microUSD'], -87_750_000)
            self.assertEqual(adverse['snapshots']['after_prespecified_conditional_reservation']['unrestrictedEarned'], 0)
            self.assertEqual(adverse['net_collections_microUSD'], 0)
            self.assertLess(adverse['realized_utility_microUSD'], 0)
            self.assertEqual(worlds['outage_delay']['net_collections_microUSD'], 0)
            self.assertEqual(worlds['rejected_delivery']['net_collections_microUSD'], 0)
            self.assertEqual(result['evidence_grounded_decision']['qualified_unrestricted_simulated_earned_funds_microUSD'], 0)
            self.assertEqual(result['evidence_grounded_decision']['real_orders'], 0)
            self.assertEqual(len(result['worlds']), 8)
            self.assertTrue(all(item['passed'] for item in result['checks']))


if __name__ == '__main__':
    unittest.main()
