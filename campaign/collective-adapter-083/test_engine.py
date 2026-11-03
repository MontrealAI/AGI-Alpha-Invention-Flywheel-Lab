import json
import tempfile
import unittest
from pathlib import Path
from engine import fixtures, construct, prospective_plan, run, apply_adapter
from independent import audit, ordinary_coalitions


class Tests(unittest.TestCase):
    def test_preregistered_fixed_cases(self):
        states = {k: construct(v)['economic_status'] for k, v in fixtures().items()}
        self.assertEqual(states, {'compatible_three':'CONDITIONAL_ACCEPTED_NOT_COLLECTED',
            'withdrawal':'NO_DEPLOY', 'failure_and_refund':'FAILED_ACCEPTANCE_REFUND_DUE',
            'rights_block':'NO_DEPLOY', 'adverse_cost':'NO_DEPLOY'})

    def test_ordinary_complete_baseline_ties(self):
        for case in fixtures().values():
            self.assertEqual(tuple(prospective_plan(case)['buyers']), ordinary_coalitions(case))

    def test_funding_is_only_hypothetical(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'new'
            report = run(path)
            self.assertFalse(report['target_3b_achieved'])
            self.assertIsNone(report['actual_365_day_complete_cost_profit'])
            self.assertTrue(audit(path)['accepted'])
            with self.assertRaises(FileExistsError): run(path)

    def test_artifact_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'new'; run(path)
            artifact = path/'compatible_three'/'beta.json'
            artifact.write_text(artifact.read_text().replace('count', 'value'))
            with self.assertRaisesRegex(ValueError, 'CHANGED_DELIVERABLE'): audit(path)

    def test_report_promotion_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'new'; run(path)
            result_path = path/'RESULT.json'; v = json.loads(result_path.read_text())
            v['actual_collections'] = 270; result_path.write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError, 'INVALID_REAL_COMMERCE'): audit(path)

    def test_duplicate_buyer_rejected(self):
        case = fixtures()['compatible_three']; case['buyers'][1]['id'] = 'alpha'
        with self.assertRaisesRegex(ValueError, 'DUPLICATE'): prospective_plan(case)

    def test_no_permission_refuses_and_recomputes(self):
        c = fixtures()['rights_block']
        self.assertEqual(prospective_plan(c)['status'], 'NO_FEASIBLE_VOLUNTARY_COALITION')

    def test_escrow_insufficient_is_not_seller_funding(self):
        c = fixtures()['compatible_three']; c['seller_refund_collateral'] = 0
        self.assertEqual(construct(c)['economic_status'], 'INSUFFICIENT_REFUND_COLLATERAL')

    def test_unknown_field_refused(self):
        a = construct(fixtures()['compatible_three'])['artifacts']['alpha']
        with self.assertRaisesRegex(ValueError, 'MISSING_REQUIRED'):
            apply_adapter(a, {'kind':'temp'})

    def test_one_buyer_cannot_pass_fixed_cost_to_others(self):
        c = fixtures()['compatible_three']
        c['buyers'][1]['consent'] = False; c['buyers'][2]['consent'] = False
        self.assertEqual(prospective_plan(c)['status'], 'NO_FEASIBLE_VOLUNTARY_COALITION')

    def test_zero_value_or_outside_gain_forces_no_payment(self):
        c = fixtures()['compatible_three']; c['buyers'][1]['outside'] = 120
        self.assertEqual(prospective_plan(c)['status'], 'NO_FEASIBLE_VOLUNTARY_COALITION')

    def test_unbalanced_budgets_allow_feasible_cost_shares(self):
        c = fixtures()['compatible_three']
        c['buyers'][0]['budget'] = 30; c['buyers'][1]['budget'] = 120; c['buyers'][2]['budget'] = 120
        p = prospective_plan(c)
        self.assertEqual(p['status'], 'CONDITIONALLY_FEASIBLE_PLEDGES')
        self.assertLessEqual(p['shares']['alpha'], 30)
        self.assertEqual(sum(p['shares'].values()), 270)

    def test_collateral_funds_all_refunds_at_the_right_time(self):
        c = fixtures()['compatible_three']
        r = construct(c)
        self.assertEqual(r['hypothetical_escrow_receipts'], 270)
        self.assertEqual(r['hypothetical_preconstruction_cash'], 530)
        self.assertEqual(r['hypothetical_cash_after_cost'], 270)
        self.assertEqual(r['refund_reserve_before_acceptance'], 270)
        self.assertTrue(r['refund_reserve_covered_before_acceptance'])
        failed = construct(fixtures()['failure_and_refund'])
        self.assertEqual(failed['hypothetical_cash_after_full_refund'], 0)
        self.assertEqual(failed['conditional_cost_incurred'], 260)

    def test_hypothetical_cash_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'new'; run(path)
            result_path = path/'RESULT.json'
            v = json.loads(result_path.read_text())
            v['worlds']['compatible_three']['hypothetical_cash_after_cost'] += 1
            result_path.write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError, 'BROKEN_ESCROW_COLLATERAL'):
                audit(path)



    def test_extra_adapter_after_no_rights_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'new'; run(path)
            forbidden = path/'rights_block'/'gamma.json'
            forbidden.parent.mkdir(parents=True)
            forbidden.write_text('{"schema":"forbidden"}')
            with self.assertRaisesRegex(ValueError, 'UNAUTHORIZED_ADAPTER_FOR_REFUSED'):
                audit(path)

    def test_modified_source_mapping_rejected_even_with_hash_updated(self):
        from engine import digest, wire
        import hashlib
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'new'; run(path)
            artifact_path = path/'compatible_three'/'alpha.json'
            artifact = json.loads(artifact_path.read_text())
            artifact['normalizer']['source_fields']['measurement'] = 'evil'
            artifact_path.write_bytes(wire(artifact) + b'\n')
            result_path = path/'RESULT.json'
            report = json.loads(result_path.read_text())
            report['worlds']['compatible_three']['artifact_file_sha256']['alpha'] = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
            result_path.write_text(json.dumps(report))
            with self.assertRaisesRegex(ValueError, 'SOURCE_MAPPING_CHANGED'):
                audit(path)

if __name__ == '__main__':
    unittest.main()
