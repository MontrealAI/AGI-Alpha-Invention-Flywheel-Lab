"""Authored counterexamples and development fixtures; no measured source data."""
import itertools
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from .data import InputFailure, canonical_pair, prepare_records
from .evaluate import RevealOracle, run
from .freeze import FREEZE_RELATIVE, PREREG_RELATIVE, REQUIRED_PATHS, validate_freeze
from .policy import PublicContext, allocate, hash_order, hit_threshold, probability_of_hit_scores
from .protocol import SPLIT_SALT


def fixture_rows():
    genes = ["read1", "read2", "read3", "read4"]
    interventions = [f"G{i:02d}" for i in range(8)]
    control = np.asarray([1.0, 2.0, 3.0, 4.0])
    profiles = {name: control + np.asarray([i / 7, (i % 3) / 4, (i % 2) / 2, 0.1]) for i, name in enumerate(interventions)}
    out = []
    for index, (a, b) in enumerate(itertools.combinations(interventions, 2)):
        residual = np.asarray([0.1, -0.2, 0.3, -0.4]) * (1 + index / 20)
        ab = profiles[a] + profiles[b] - control + residual
        for g, gene in enumerate(genes):
            out.append({"gene_name": gene, "pert_group": a + "+" + b, "seed": 1,
                        "AB": float(ab[g]), "A": float(profiles[a][g]), "B": float(profiles[b][g]),
                        "ctrl": float(control[g]), "error": float(residual[g])})
    return out


class SourceContractTests(unittest.TestCase):
    def test_exact_independent_residual_example(self):
        result = prepare_records(fixture_rows(), expected_readouts=4)
        self.assertEqual(len(result["pair_names"]), 28)
        self.assertAlmostEqual(result["outcomes"][0], math.sqrt((.01 + .04 + .09 + .16) / 4))

    def test_reversed_pair_preserves_features_and_truth(self):
        rows = fixture_rows()
        reverse = [dict(r, pert_group="+".join(reversed(r["pert_group"].split("+"))), A=r["B"], B=r["A"]) for r in rows]
        self.assertEqual(prepare_records(rows, 4), prepare_records(reverse, 4))

    def test_duplicate_pair_readout_rejected(self):
        rows = fixture_rows()
        with self.assertRaises(InputFailure):
            prepare_records(rows + [rows[0]], 4)

    def test_missing_readout_rejected(self):
        with self.assertRaises(InputFailure):
            prepare_records(fixture_rows()[1:], 4)

    def test_conflicting_single_profile_rejected(self):
        rows = fixture_rows()
        rows[4] = dict(rows[4], A=rows[4]["A"] + .5, error=rows[4]["error"] - .5)
        with self.assertRaises(InputFailure):
            prepare_records(rows, 4)

    def test_nonfinite_and_missing_observations_rejected(self):
        for invalid in (None, float("nan"), float("inf")):
            rows = fixture_rows()
            rows[0] = dict(rows[0], AB=invalid)
            with self.subTest(value=invalid), self.assertRaises(InputFailure):
                prepare_records(rows, 4)

    def test_published_residual_is_independently_checked(self):
        rows = fixture_rows()
        rows[0] = dict(rows[0], error=5.0)
        with self.assertRaises(InputFailure):
            prepare_records(rows, 4)


class RevealContractTests(unittest.TestCase):
    def test_hit_threshold_and_objective_differ_from_ucb(self):
        self.assertEqual(hit_threshold([4, 1, 3, 2]), 3)
        # UCB chooses the highly uncertain low-mean candidate (11 > 2.1).
        # Threshold exceedance prefers the candidate already above threshold.
        means, deviations = np.array([2., 1.]), np.array([.1, 10.])
        z, probabilities = probability_of_hit_scores(means, deviations, 1.5)
        self.assertGreater(z[0], z[1])
        self.assertGreater(probabilities[0], probabilities[1])
        self.assertLess((means + deviations)[0], (means + deviations)[1])
        # Zero deviation uses the registered numerical floor, with finite ranks.
        zero_z, zero_p = probability_of_hit_scores(np.array([0., 1., 2.]), np.zeros(3), 1.)
        self.assertTrue(np.isfinite(zero_z).all())
        self.assertEqual(zero_p.tolist(), [0., .5, 1.])

    def test_changed_frozen_source_rejected_before_measurements(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hashes = {}
            for relative in REQUIRED_PATHS:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("prospective synthetic fixture\n")
                hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
            (root / FREEZE_RELATIVE).write_text(json.dumps({
                "schema": 1, "experiment_id": "NEXT072-20261102", "files": hashes,
                "prereg_sha256": hashes[PREREG_RELATIVE],
            }))
            self.assertEqual(validate_freeze(root)["actual_code_and_contract_hashes"], hashes)
            (root / "next072/policy.py").write_text("changed after freezing\n")
            with self.assertRaisesRegex(ValueError, "Frozen source mismatch"):
                validate_freeze(root)

    def test_unknown_reference_and_duplicate_reveal_rejected(self):
        oracle = RevealOracle({"A": 1., "B": 2., "C": 3.}, {"A"}, 2)
        for bad in ("A", "UNKNOWN"):
            with self.assertRaises(ValueError):
                oracle.reveal(bad)
        self.assertEqual(oracle.reveal("B"), 2.0)
        with self.assertRaises(ValueError):
            oracle.reveal("B")
        self.assertEqual(len(oracle.receipt), 1)

    def test_budget_overrun_fails_before_reveal(self):
        oracle = RevealOracle({"A": 1., "B": 2.}, set(), 1)
        oracle.reveal("A")
        with self.assertRaises(ValueError):
            oracle.reveal("B")
        self.assertEqual(len(oracle.receipt), 1)

    def test_first_batch_invariant_to_hidden_outcome_changes(self):
        prepared = prepare_records(fixture_rows(), 4)
        names = prepared["pair_names"]
        references = hash_order(names, SPLIT_SALT)[:7]
        all_y = dict(zip(names, prepared["outcomes"]))
        context = PublicContext(tuple(names), tuple(map(tuple, prepared["features"])), tuple(references), tuple(all_y[n] for n in references), 6)
        first = RevealOracle(all_y, set(references), 6)
        changed = {n: (v if n in references else 100 - v) for n, v in all_y.items()}
        second = RevealOracle(changed, set(references), 6)
        r1 = allocate(context, first.reveal, "probability_of_hit")
        r2 = allocate(context, second.reveal, "probability_of_hit")
        self.assertEqual([r["pair"] for r in r1[:4]], [r["pair"] for r in r2[:4]])
        self.assertEqual([r["acquisition_index"] for r in r1[:4]], [r["acquisition_index"] for r in r2[:4]])
        self.assertEqual({r["hit_threshold_from_initial_references"] for r in r1}, {hit_threshold(context.reference_values)})
        self.assertEqual({r["hit_threshold_from_initial_references"] for r in r2}, {hit_threshold(context.reference_values)})

    def test_full_fixture_denominators_and_equal_content_tie(self):
        prepared = prepare_records(fixture_rows(), 4)
        result = run(prepared)
        self.assertEqual(result["input_denominator"]["pairs"], 28)
        self.assertEqual(result["reference_pairs"], 7)
        self.assertEqual(result["confirmation_pairs"], 21)
        self.assertEqual(result["query_budget"], 5)
        self.assertTrue(result["equal_content_ordinary_reuse_exact_tie"])
        self.assertEqual(len(result["policy_results"]), 42)
        self.assertEqual(result["primary_policy"], "probability_of_hit")
        for name, metrics in result["policy_results"].items():
            self.assertEqual(metrics["queries"], 5, name)
            self.assertEqual(metrics["discoveries"] + metrics["missed_targets"], 6, name)
            self.assertEqual(metrics["discoveries"] + metrics["non_target_queries"], 5, name)


if __name__ == "__main__":
    unittest.main()
