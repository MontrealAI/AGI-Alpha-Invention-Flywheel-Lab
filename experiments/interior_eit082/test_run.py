"""Synthetic engineering guards; physical inference comes only from downloaded KIT4 data."""
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
import numpy as np
from scipy.io import savemat
import run

class FinitePhysicalSourceTests(unittest.TestCase):
    def setUp(self):
        self.y = ["PLASTIC"] * 3 + ["METAL"] * 7
        self.names = run.DEV
        self.X = np.zeros((10,79,16), dtype=float)
        for i in range(10):
            self.X[i,0,:] = -1 if i < 3 else 1
            self.X[i,1,:] = i / 100
    def test_protocol_is_pinned_and_not_a_financial_operator(self):
        self.assertEqual(run.MD5, "ad9f03325cafc9aae8c0149927de8e06")
        self.assertEqual(run.BUDGET, 4)
        self.assertEqual(len(run.DEV), 10)
        self.assertEqual(len(run.TEST), 6)
        self.assertEqual(set(run.DEV) & set(run.TEST), set())
        self.assertEqual(run.PROTOCOL["authority"] if "authority" in run.PROTOCOL else run.PROTOCOL["role"], "FINITE_PHYSICAL_OBSERVATION_DEPENDENCY_TEST")
    def test_no_hiding_the_frozen_test_cases(self):
        self.assertEqual(run.class_labels(run.TEST), ["PLASTIC"]*3 + ["METAL"]*3)
        self.assertEqual(len(run.LABELS), 16)
    def test_ties_abstain(self):
        X = np.zeros_like(self.X)
        decision, margin = run.centroid_predict(X, self.y, X[0], [0])
        self.assertEqual(decision, "ABSTAIN")
        self.assertEqual(margin, 0)
    def test_strong_control_is_not_dummy(self):
        scores = run.fisher_scores(self.X,self.y)
        self.assertEqual(run.rank_top(scores)[0], 0)
        selected = run.greedy_loo(self.X,self.y,scores)
        self.assertIn(0,selected)
        self.assertEqual(len(set(selected)),run.BUDGET)
    def test_candidate_receives_only_development(self):
        first = run.rank_top(run.robust_scores(self.X,self.y,self.names))
        self.assertEqual(len(first),run.BUDGET)
        self.assertEqual(first,run.rank_top(run.robust_scores(self.X.copy(),self.y,self.names.copy())))
    def test_prediction_does_not_consume_test_truth(self):
        pred, margin = run.centroid_predict(self.X,self.y,self.X[0],[0])
        self.assertEqual(pred,"PLASTIC")
        self.assertGreater(margin,0)
    def test_balanced_scoring_counts_abstentions_as_wrong(self):
        self.assertEqual(run.score_prediction(["PLASTIC","ABSTAIN","METAL","ABSTAIN"],["PLASTIC","PLASTIC","METAL","METAL"]),(2,0.5))
    def test_rank_tie_is_deterministic(self):
        self.assertEqual(run.rank_top(np.ones(79)),[0,1,2,3])
    def test_missing_and_malformed_source_refuses(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_MEMBER_COUNT"):
            run.load_physical(b"PK\x05\x06" + b"\0"*18)
    def test_nonfinite_voltage_refuses_without_touching_account(self):
        names = sorted(set(run.LABELS) | {run.PROTOCOL["cases"]["background"]})
        buf = io.BytesIO()
        with zipfile.ZipFile(buf,"w") as z:
            for i in range(38):
                name = names[i] if i < len(names) else f"datamat_8_{i}.mat"
                sample = io.BytesIO()
                v = np.zeros((16,79))
                if i == 0:
                    v[0,0] = np.nan
                savemat(sample,{"Uel":v,"CurrentPattern":np.zeros((16,79)),"MeasPattern":np.zeros((16,16))})
                z.writestr(name,sample.getvalue())
        with self.assertRaisesRegex(ValueError,"SOURCE_MATRIX_INVALID_Uel"):
            run.load_physical(buf.getvalue())
    def test_trailing_source_manifests_do_not_create_funding(self):
        self.assertIn("No native 365-day profit", run.PROTOCOL["claim_boundaries"])
        self.assertIn("No financial Account or JournalAccount opened or mutated",run.PROTOCOL["integrity"])

if __name__ == "__main__":
    unittest.main()
