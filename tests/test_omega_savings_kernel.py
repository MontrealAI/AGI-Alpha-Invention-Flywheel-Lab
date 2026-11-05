import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from fractions import Fraction

import numpy as np

from omega_savings.kernel import (build_request, construct, digest, execute,
                                  retained_assets, solve, validate_request)
from omega_savings.verify import qualify, verify


def _manual_request(matrix, rhs, *, tolerance=1e-10):
    return {"schema": "omega-savings/linear-request/v1", "id": "adversarial-interval",
            "base_matrix": matrix, "cases": [{"matrix": matrix, "rhs": rhs, "update": None}],
            "goal": {"outcome": "solve_linear_responses", "absolute_tolerance": tolerance,
                     "relative_tolerance": tolerance, "max_condition_bound": 1e10,
                     "allow_network": False, "allow_external_actions": False}}


def _manual_result(request, solution):
    return {"schema": "omega-savings/linear-result/v1", "status": "executed",
            "request_sha256": digest(request), "solutions": [solution]}


class OptionalIntervalTests(unittest.TestCase):
    def test_directed_bounds_dominate_exact_fraction_on_adversarial_outputs(self):
        from omega_savings.interval import instrument, verify_interval
        _, metadata = instrument()
        self.assertTrue(metadata["self_test_passed"])
        for seed in (11, 12):
            rng = np.random.default_rng(seed)
            request = build_request(seed, "low_rank", n=8, cases=3)
            result = solve(request)
            for scale in (0.0, 1e-15, 1e-9, 0.1, 1e100):
                bad = copy.deepcopy(result)
                bad["solutions"] = (np.asarray(result["solutions"]) + rng.normal(size=(3, 8)) * scale).tolist()
                checked = verify_interval(request, bad, fallback=False)
                exact = verify(request, bad)
                self.assertTrue(checked["fast_path"], checked["reasons"])
                if checked["accepted"]:
                    self.assertTrue(exact["accepted"])
                for case, output, bound in zip(request["cases"], bad["solutions"], checked["case_bounds"]):
                    a = [[Fraction(v) for v in row] for row in case["matrix"]]
                    b, x = list(map(Fraction, case["rhs"])), list(map(Fraction, output))
                    norm = max(sum(map(abs, row)) for row in a)
                    alpha = min(abs(a[i][i]) - sum(abs(v) for j, v in enumerate(a[i]) if j != i) for i in range(8))
                    residual = max(abs(b[i] - sum(a[i][j] * x[j] for j in range(8))) for i in range(8))
                    self.assertLessEqual(Fraction(bound["diagonal_margin_lower_bound"]), alpha)
                    self.assertGreaterEqual(Fraction(bound["condition_bound"]), norm / alpha)
                    self.assertGreaterEqual(Fraction(bound["absolute_error_bound"]), residual / alpha)

    def test_extreme_inputs_and_illconditioning_adjudicate_exactly(self):
        from omega_savings.interval import verify_interval
        tiny = float(np.nextafter(0.0, 1.0))
        cases = [
            (_manual_request([[tiny]], [tiny]), [1.0]),
            (_manual_request([[tiny]], [0.0]), [0.5]),
            (_manual_request([[1e308, -5e307], [0.0, 1e308]], [1.5e308, 1e308]), [2.0, 1.0]),
            (_manual_request([[1e308, 8e307], [0.0, 1e308]], [0.0, 0.0]), [0.0, 0.0]),
            (_manual_request([[1.0, 0.0], [0.0, 1e-14]], [1.0, 1e-14]), [1.0, 1.0]),
            (_manual_request([[1.0, 1.0], [1.0, 1.0]], [2.0, 2.0]), [1.0, 1.0]),
            (_manual_request([[2**53 + 1]], [2**53 + 1]), [1.0]),
            (_manual_request([[1.0]], [0.0]), [0.0]),
        ]
        for request, output in cases:
            result = _manual_result(request, output)
            exact = verify(request, result)
            fast = verify_interval(request, result)
            self.assertEqual(fast["accepted"], exact["accepted"], (request, fast, exact))

    def test_immutable_prepared_boundary_does_not_authorize_changed_input(self):
        from omega_savings.interval import prepare_request, verify_interval
        request = build_request(11, "rhs", n=8, cases=2)
        result = solve(request)
        boundary = prepare_request(request)
        with self.assertRaises(ValueError):
            boundary.matrices[0].setflags(write=True)
        self.assertTrue(verify_interval(boundary, result)["accepted"])
        request["cases"][0]["rhs"][0] += 1
        self.assertFalse(verify_interval(request, result)["accepted"])
        self.assertTrue(verify_interval(boundary, result)["accepted"])

    def test_forged_nonfinite_and_missing_compiler_fail_or_fallback(self):
        from omega_savings.interval import verify_interval
        request = build_request(11, "rhs", n=8, cases=2)
        result = solve(request)
        with patch("omega_savings.interval.instrument", side_effect=OSError("compiler absent")):
            checked = verify_interval(request, result)
            self.assertTrue(checked["accepted"])
            self.assertEqual(checked["instrument"], "exact_fraction_fallback")
            self.assertFalse(verify_interval(request, result, fallback=False)["accepted"])
        for value in (float("nan"), float("inf"), 1e100):
            bad = copy.deepcopy(result)
            bad["solutions"][0][0] = value
            self.assertFalse(verify_interval(request, bad)["accepted"])

    def test_checker_restores_rounding_mode_and_default_stays_fraction(self):
        from omega_savings.interval import instrument, verify_interval
        library, _ = instrument()
        library.fegetround.restype = __import__("ctypes").c_int
        before = library.fegetround()
        request = build_request(12, "rhs", n=8, cases=2)
        result = solve(request)
        self.assertTrue(verify_interval(request, result)["accepted"])
        self.assertEqual(before, library.fegetround())
        self.assertIn("exact rational", verify(request, result)["operation_kind"])


class SavingsKernelTests(unittest.TestCase):
    """Development seeds only. Registered confirmation is run separately."""

    def test_repeated_rhs_reuses_factorization_and_accepts_real_output(self):
        request = build_request(11, "rhs")
        result = solve(request)
        self.assertEqual(result["plan"]["method"], "reuse")
        self.assertTrue(verify(request, result)["accepted"])
        self.assertTrue(qualify(request, result)["accepted"])
        self.assertGreater(result["count_model"]["saved_proxy_units"], 0)

    def test_low_rank_constructs_and_executes_woodbury(self):
        request = build_request(12, "low_rank", n=32)
        result = solve(request)
        self.assertEqual(result["plan"]["method"], "woodbury")
        self.assertTrue(qualify(request, result)["accepted"])
        direct = solve(request, "direct")
        self.assertTrue(np.allclose(result["solutions"], direct["solutions"], rtol=1e-10, atol=1e-10))

    def test_strong_conventional_and_equal_content_ordinary_reuse_tie(self):
        for family in ("rhs", "low_rank", "successor_rhs", "successor_low_rank"):
            request = build_request(13, family)
            results = [solve(request, policy, retained_assets()) for policy in ("adaptive", "conventional", "ordinary_reuse")]
            self.assertEqual(len({r["plan"]["method"] for r in results}), 1)
            self.assertEqual(len({digest(r["solutions"]) for r in results}), 1)
            self.assertEqual(len({digest(r["count_model"]) for r in results}), 1)
            self.assertTrue(all(verify(request, r)["accepted"] for r in results))

    def test_neither_hypothesis_and_noisy_update_select_direct(self):
        for family in ("dense_change", "noisy_update"):
            request = build_request(11, family)
            result = solve(request)
            self.assertTrue(result["plan"]["hypotheses"]["neither_reuse_hypothesis"])
            self.assertEqual(result["plan"]["method"], "direct")
            self.assertTrue(verify(request, result)["accepted"])
            self.assertLess(result["count_model"]["saved_proxy_units"], 0)

    def test_invalid_weak_analogy_is_not_accepted(self):
        request = build_request(12, "low_rank")
        weak = solve(request, "weak_analogy")
        self.assertEqual(weak["status"], "declined")
        self.assertIn("SELECTED_METHOD_INAPPLICABLE", weak["reasons"])
        self.assertFalse(verify(request, weak)["accepted"])
        self.assertEqual(solve(request, "random_analogy")["solutions"], solve(request, "random_analogy")["solutions"])

    def test_old_new_capability_crossed_with_policy_on_fresh_successors(self):
        for family in ("successor_rhs", "successor_low_rank"):
            request = build_request(12, family)
            for methods in (("direct",), ("direct", "reuse", "woodbury")):
                for policy in ("no_learning", "adaptive"):
                    result = solve(request, policy, retained_assets(methods))
                    self.assertTrue(verify(request, result)["accepted"])
                    if methods == ("direct",) or policy == "no_learning":
                        self.assertEqual(result["plan"]["method"], "direct")

    def test_condition_and_singular_cases_decline_without_false_completion(self):
        for family in ("ill_conditioned", "singular"):
            request = build_request(11, family)
            result = solve(request)
            self.assertEqual(result["status"], "declined")
            self.assertFalse(verify(request, result)["accepted"])

    def test_forged_solution_binding_and_nonfinite_output_fail(self):
        request = build_request(11, "rhs", n=8, cases=2)
        result = solve(request)
        for change in ("solution", "binding", "nonfinite", "missing"):
            bad = copy.deepcopy(result)
            if change == "solution":
                bad["solutions"][0][0] += 0.1
            elif change == "binding":
                bad["request_sha256"] = "0" * 64
            elif change == "nonfinite":
                bad["solutions"][0][0] = float("nan")
            else:
                bad["solutions"].pop()
            self.assertFalse(verify(request, bad)["accepted"], change)

    def test_verifier_does_not_execute_producer_or_trust_method(self):
        request = build_request(11, "rhs", n=8, cases=2)
        result = solve(request)
        result["plan"]["method"] = "seller_says_magic"
        with patch("omega_savings.kernel.solve", side_effect=AssertionError("producer called")):
            checked = verify(request, result)
        self.assertTrue(checked["accepted"])
        self.assertIsNone(checked["max_oracle_relative_error"])
        self.assertEqual(checked["verification_ops"], result["count_model"]["production_verify_rational_ops"])

    def test_generated_program_runs_without_repository_or_network(self):
        request = build_request(12, "low_rank", n=12, cases=3)
        plan = construct(request)
        expected = execute(request, plan)
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / "plan.py").write_text(plan["program"])
            (directory / "request.json").write_text(json.dumps(request))
            process = subprocess.run([sys.executable, "plan.py", "request.json"], cwd=directory,
                                     check=True, capture_output=True, text=True)
            observed = json.loads(process.stdout)
        self.assertEqual(observed["solutions"], expected["solutions"])
        self.assertEqual(observed["request_sha256"], digest(request))

    def test_changed_request_and_unreviewed_program_are_rejected(self):
        request = build_request(11, "rhs", n=8, cases=2)
        plan = construct(request)
        changed = copy.deepcopy(request)
        changed["cases"][0]["rhs"][0] += 1
        with self.assertRaisesRegex(ValueError, "PLAN_REQUEST_BINDING"):
            execute(changed, plan)
        plan["program"] += "\nprint('unreviewed')\n"
        with self.assertRaisesRegex(ValueError, "UNREVIEWED_PROGRAM"):
            execute(request, plan)

    def test_unknown_goal_malformed_numbers_and_hidden_labels_rejected(self):
        request = build_request(13, "rhs", n=8, cases=2)
        self.assertNotIn("seed", request)
        self.assertNotIn("family", request)
        for key, value in (("seed", 13), ("family", "rhs")):
            bad = copy.deepcopy(request)
            bad[key] = value
            with self.assertRaises(ValueError):
                validate_request(bad)
        bad = copy.deepcopy(request)
        bad["base_matrix"][0][0] = True
        with self.assertRaises(ValueError):
            solve(bad)
        with self.assertRaises(ValueError):
            construct(request, "omniscient")
        with self.assertRaises(ValueError):
            build_request(11, "unknown_physics")

    def test_confirmation_protocol_cannot_be_relabeled_as_development(self):
        from omega_savings.experiment import cell_specs, protocol
        with self.assertRaisesRegex(ValueError, "CONFIRMATION_SEED_CANNOT_BE_DEVELOPMENT"):
            protocol([701], "development")
        with self.assertRaisesRegex(ValueError, "EXACT_REGISTERED_CONFIRMATION_SEEDS_REQUIRED"):
            protocol([701], "confirmation")
        spec = protocol([701, 702, 703], "confirmation")
        cells = list(cell_specs(spec))
        self.assertEqual(len(cells), 180)
        self.assertEqual(sum(c["kind"] == "main" for c in cells), 144)
        self.assertEqual(sum(c["kind"] == "successor_cross" for c in cells), 36)
        repeated = protocol([701, 702, 703], "reproduction")
        self.assertEqual(repeated["role"], "reproduction")
        self.assertIn("not fresh independent confirmation", repeated["role_scope"])
        self.assertEqual(list(cell_specs(repeated)), cells)
        with self.assertRaisesRegex(ValueError, "ROLE_MUST_BE"):
            protocol([11], "invented_role")
        # This constructs only protocol metadata, never held-out requests.


if __name__ == "__main__":
    unittest.main()
