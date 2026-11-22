"""Source-bound adversarial checks for EIT104; honors preregistered failure."""
from hashlib import sha256
import copy
import unittest
from research.eit_calibration104.analysis import (
    ROWS, LEVELS, SOURCE_PROJECTION_SHA256, unpack, read_rows, validate_rows,
    calibrator, pairs_for, score, inner_choose, evaluate)


class PhysicalDecisionCalibration104Tests(unittest.TestCase):
    def setUp(self):
        self.rows = read_rows()

    def test_pin_raw_source_byte_identity(self):
        self.assertEqual(sha256(ROWS.encode()).hexdigest(), SOURCE_PROJECTION_SHA256)
        self.assertEqual(len(self.rows), 21)

    def test_only_valid_binary_bytes(self):
        self.assertEqual(unpack('81'),(1,0,0,0,0,0,0,1))
        for data in ('F0', 'Ff','gg','1','003',''):
            with self.subTest(data=data), self.assertRaises(ValueError):
                unpack(data)

    def test_tampered_pinned_projection_fails(self):
        with self.assertRaisesRegex(ValueError, 'SOURCE_PROJECTION_CHANGED'):
            read_rows(ROWS.replace('04 05 05 05','04 04 05 05'))

    def test_missing_specimen_fails(self):
        with self.assertRaisesRegex(ValueError,'SOURCE_EXACT_21'):
            read_rows('\n'.join(ROWS.splitlines()[1:]),pinned=False)

    def test_duplicate_specimen_fails(self):
        rows=ROWS.splitlines()
        rows[1]=rows[0]
        with self.assertRaisesRegex(ValueError,'SOURCE_DUPLICATE_SPECIMEN'):
            read_rows('\n'.join(rows),pinned=False)

    def test_foreign_physical_group_fails(self):
        rows=ROWS.replace('level1/data1.mat','level8/data1.mat')
        with self.assertRaisesRegex(ValueError,'SOURCE_EXACT_SPECIMEN'):
            read_rows(rows,pinned=False)

    def test_decision_boolean_rejected(self):
        rows=list(copy.deepcopy(self.rows))
        rows[0]=dict(rows[0], truth=(True,)+rows[0]['truth'][1:])
        with self.assertRaisesRegex(ValueError,'EXACT_EIGHT_BINARY'):
            validate_rows(rows)

    def test_invalid_position_rejected(self):
        rows=list(copy.deepcopy(self.rows))
        rows[0]=dict(rows[0], direct40=(2,)+rows[0]['direct40'][1:])
        with self.assertRaisesRegex(ValueError,'EXACT_EIGHT_BINARY'):
            evaluate(rows)

    def test_no_training_data_rejected(self):
        with self.assertRaisesRegex(ValueError,'NONEMPTY_TRAINING'):
            calibrator([], 'position')
        with self.assertRaisesRegex(ValueError,'UNREGISTERED'):
            calibrator(self.rows,'oracle')

    def test_no_training_for_candidate_fails(self):
        with self.assertRaisesRegex(ValueError,'TRAINING_SET'):
            pairs_for(self.rows,'position')

    def test_illegal_policy_fails(self):
        with self.assertRaisesRegex(ValueError,'UNREGISTERED'):
            pairs_for(self.rows,'clairvoyant')

    def test_fixed_seven_levels(self):
        self.assertEqual(LEVELS,tuple(f'level{i}' for i in range(1,8)))
        self.assertEqual([sum(x['level']==level for x in self.rows) for level in LEVELS], [3]*7)

    def test_training_cannot_use_outer_heldout_labels(self):
        train=[r for r in self.rows if r['level'] != 'level4']
        held=[r for r in self.rows if r['level'] == 'level4']
        selected, scores=inner_choose(train)
        predictions={p:calibrator(train,p) for p in ('pooled','position')}
        before={p:[f(r) for r in held] for p,f in predictions.items()}
        altered=[dict(r, truth=tuple(1-b for b in r['truth'])) for r in held]
        after={p:[f(r) for r in altered] for p,f in predictions.items()}
        self.assertEqual(before, after)
        self.assertIn(selected,('direct40','pooled','position'))
        self.assertEqual(set(scores),{'direct40','pooled','position'})

    def test_exact_beta_tie_keeps_original_binary(self):
        t=[dict(r,truth=r['direct40']) for r in self.rows[:18]]
        p=calibrator(t,'position')
        self.assertEqual(p(self.rows[19]),self.rows[19]['direct40'])

    def test_balanced_accuracy_undefined_for_single_class(self):
        s=score([(0,0),(0,1)])
        self.assertIsNone(s['balanced_accuracy'])
        self.assertEqual(s['correct'],1)

    def test_source_baselines_unchanged(self):
        r=evaluate(self.rows)
        self.assertEqual(r['policies']['full76']['correct'],147)
        self.assertEqual(r['policies']['direct40']['correct'],146)
        self.assertEqual(r['policies']['impute40']['correct'],146)
        self.assertEqual(r['policies']['absent']['correct'],112)

    def test_full_predeclared_observation_count(self):
        r=evaluate(self.rows)
        self.assertEqual(len(r['by_level']),7)
        self.assertEqual(r['physical_decisions'],168)
        self.assertEqual(r['counted_fold_predictions'],168)
        for p in r['policies']:
            self.assertEqual(r['policies'][p]['total'],168)
        self.assertEqual(sum(d['test_specimens'] for d in r['by_level']),21)
        self.assertTrue(all(d['train_specimens']==18 for d in r['by_level']))

    def test_independent_fold_error_accounting(self):
        r=evaluate(self.rows)
        for p in r['policies']:
            self.assertEqual(r['policies'][p]['correct'],sum(d['heldout'][p]['correct'] for d in r['by_level']))
            self.assertEqual(r['policies'][p]['tp']+r['policies'][p]['tn'],r['policies'][p]['correct'])
            self.assertEqual(r['by_material'][p][0]['total'],84)
            self.assertEqual(r['by_material'][p][1]['total'],84)

    def test_no_reclassification_after_frozen_gate_fails(self):
        r=evaluate(self.rows)
        self.assertFalse(r['position_challenger_technical_gate'])
        self.assertEqual(r['decision'],'REJECT_POSITION_CALIBRATION_NO_BID_NO_DEPLOY')
        self.assertLess(r['policies']['position']['balanced_accuracy'],r['policies']['nested']['balanced_accuracy'])

    def test_financial_or_physical_claims_not_invented(self):
        r=evaluate(self.rows)
        self.assertEqual(r['actual_new_physical_acquisitions'],0)
        self.assertEqual(r['actual_customer_accepted_outputs'],0)
        self.assertEqual(r['native_accounts_operated'],0)
        self.assertEqual(r['native_financial_actions'],0)
        self.assertIsNone(r['complete_cost_profit_usd'])
        self.assertFalse(r['usd_3b_trailing365_qualified'])
        self.assertEqual(r['actual_collected_revenue_usd'],0)


if __name__=='__main__':
    unittest.main()
