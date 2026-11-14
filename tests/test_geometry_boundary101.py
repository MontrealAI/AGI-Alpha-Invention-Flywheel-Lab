"""Adversarial algebra/source tests for the precommitted two-family boundary101."""
import hashlib
import json
import math
from pathlib import Path
import random
import tempfile
import unittest

from research.blue_sky064.geometry_boundary101 import boundary as b


class SourceAndIntervalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = b.load_verified(b.FIXTURE, b.FIXTURE_HASH)
        cls.registration = b.load_verified(b.REGISTRATION, b.REGISTRATION_HASH)
        cls.families = b.source_families(cls.fixture, cls.registration)

    def test_literal_existing_source_hashes(self):
        self.assertEqual(hashlib.sha256(b.FIXTURE.read_bytes()).hexdigest(), b.FIXTURE_HASH)
        self.assertEqual(hashlib.sha256(b.REGISTRATION.read_bytes()).hexdigest(), b.REGISTRATION_HASH)

    def test_exact_original_fits(self):
        a = self.families["Batch1_R496"]
        self.assertAlmostEqual(a["sigma_s"]["estimate"], 0.38332182207451543, places=13)
        self.assertAlmostEqual(a["sigma_s"]["low"], 0.3422516012234852, places=13)
        self.assertAlmostEqual(a["B_d"]["estimate"], 0.8932316677044592, places=13)
        d = self.families["Batch2_R1543"]
        self.assertAlmostEqual(d["sigma_d"]["estimate"], 0.22995602406013618, places=13)
        self.assertAlmostEqual(d["B_d"]["high"], 1.0044374479214546, places=13)

    def test_nominal_and_adverse_opposite_sign(self):
        nom = b.nominal_world(self.families)
        adversary = b.endpoint_world(self.families, 1.0)
        self.assertAlmostEqual(nom["B_minus_A_gap"], .19275455808653086, places=12)
        self.assertAlmostEqual(adversary["B_minus_A_min_gap"], -.3318077268330042, places=12)
        self.assertEqual(b.prove_all_geometry(nom["B_minus_A_gap"], adversary["B_minus_A_min_gap"]),
                         "CONDITIONAL_NO_GO_ALL_FIXED_TWO_FAMILY_GEOMETRIES")

    def test_all_registered_interval_sign_states(self):
        want = {0.0: True, 0.25: True, 0.5: False, 1.0: False}
        for q, expected in want.items():
            with self.subTest(q=q):
                self.assertIs(b.endpoint_world(self.families, q)["source_model_sign_robust"], expected)

    def test_unphysical_q_zero_only_point_information(self):
        no_uncertainty = b.endpoint_world(self.families, 0.0)
        nom = b.nominal_world(self.families)
        self.assertAlmostEqual(no_uncertainty["B_minus_A_min_gap"], nom["B_minus_A_gap"], places=13)

    def test_physical_and_commerce_must_not_be_promoted(self):
        receipt = b.experiment()
        self.assertEqual(receipt["decision"], "STOP_EXACT_TWO_FAMILY_GEOMETRY_ONLY_GRAMMAR_NO_BID_NO_DEPLOY")
        self.assertEqual(receipt["experimental_physical_transfer"], "NOT_ESTABLISHED")
        self.assertEqual(receipt["actual_buyer_acceptance"], "NOT_ESTABLISHED")
        self.assertEqual(receipt["native_account_actions"], 0)
        self.assertIsNone(receipt["trailing365_complete_cost_profit_usd"])
        self.assertIs(receipt["target_3b_qualified"], False)
        self.assertIn("NOT_BLIND", receipt["prior_exposure"])

    def test_tampered_source_rejected_and_never_substituted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "source.json"
            p.write_bytes(b.FIXTURE.read_bytes() + b"\n ")
            with self.assertRaisesRegex(ValueError, "FROZEN_SOURCE_BYTES_CHANGED"):
                b.load_verified(p, b.FIXTURE_HASH)

    def test_symlink_input_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "point.json"
            p.symlink_to(b.FIXTURE)
            with self.assertRaisesRegex(ValueError, "FROZEN_SOURCE_FILE_INVALID"):
                b.load_verified(p, b.FIXTURE_HASH)

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE_SOURCE_JSON_KEY"):
            json.loads('{"a":1,"a":2}', object_pairs_hook=b._no_duplicate_keys)

    def test_malformed_immutable_registration_refused(self):
        reg = dict(self.registration)
        reg["necessary_construction_target"] = {"increase_in_static_dynamic_ratio_at_least": 0.04}
        with self.assertRaisesRegex(ValueError, "REGISTERED_TARGET_CHANGED"):
            b.source_families(self.fixture, reg)

    def test_wrong_families_not_silently_substituted(self):
        reg = dict(self.registration)
        reg["families"] = ["Batch2_R1543", "Batch1_R496"]
        with self.assertRaisesRegex(ValueError, "WRONG_FROZEN_TWO_FAMILY_REGISTRATION"):
            b.source_families(self.fixture, reg)

    def test_origin_fit_on_zero_residual(self):
        exact = [[1., 0., 3., 0.], [2., 0., 6., 0.], [3., 0., 9., 0.]]
        fit = b.ols_interval(exact)
        self.assertEqual(fit["estimate"], 3.0)
        self.assertEqual(fit["low"], 3.0)
        self.assertEqual(fit["high"], 3.0)

    def test_bad_rows_refuse_without_fallback(self):
        for rows in ([], [[1, 0, 1, 0]] * 2, [[-1, 0, 1, 0]] * 3, [[True, 0, 1, 0]] * 3):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                b.ols_interval(rows)


class AlgebraTests(unittest.TestCase):
    def test_closed_form_identity_frozen_weights_random_sources(self):
        # Numerical regression; universal claim is algebraic, not Monte Carlo.
        r = random.Random(101)
        for _ in range(256):
            a = (0.1 + 4*r.random(), 0.1 + 4*r.random())
            bcoef = (0.1 + 4*r.random(), 0.1 + 4*r.random())
            w0 = (r.random()*50, r.random()*50)
            w1 = (r.random()*50, r.random()*50)
            direct, identity, _ = b.delta_and_identity(w0, w1, a, bcoef)
            self.assertAlmostEqual(direct, identity, places=12)

    def test_two_worlds_disallow_positive_target_for_any_tested_geometry(self):
        f = b.source_families(b.load_verified(b.FIXTURE, b.FIXTURE_HASH),
                              b.load_verified(b.REGISTRATION, b.REGISTRATION_HASH))
        n = b.nominal_world(f)["shared_world_coefficients"]
        a = b.endpoint_world(f, 1.)["shared_world_coefficients"]
        def pair(c):
            return (c["sigma_s"]*c["B_s"], c["sigma_d"]*c["B_d"])
        wp, wm = (pair(n["A"]),pair(n["B"])), (pair(a["A"]),pair(a["B"]))
        r = random.Random(202)
        weights = [((1, 0), (1, 0)), ((1, 0), (0, 1)),
                   ((0, 1), (1, 0)), ((1, 5), (2, 3))]
        weights += [((r.random()*40,r.random()*40),
                     (r.random()*40,r.random()*40)) for _ in range(128)]
        for first, second in weights:
            p = b.delta_and_identity(first, second, *wp)[0]
            m = b.delta_and_identity(first, second, *wm)[0]
            self.assertLessEqual(min(p,m), 1e-12)

    def test_equal_mix_ratio_returns_zero_both_worlds(self):
        for coefficients in (((2.,3.), (5.,7.)), ((.6,.3), (.2,.15))):
            d, identity, diff = b.delta_and_identity((1,2),(3,6),*coefficients)
            self.assertAlmostEqual(d, 0., places=13)
            self.assertAlmostEqual(identity, 0., places=13)
            self.assertAlmostEqual(diff, 0., places=13)

    def test_sign_witness_not_invented_from_one_side(self):
        for n,a in ((.1,.2),(-.1,-.2),(0,-.1),(0,.1)):
            self.assertEqual(b.prove_all_geometry(n,a), "NO_OPPOSITE_SIGN_WITNESS_ESTABLISHED")
        self.assertEqual(b.prove_all_geometry(-.1,.2), "CONDITIONAL_NO_GO_ALL_FIXED_TWO_FAMILY_GEOMETRIES")

    def test_invalid_geometry_and_coefficient_refusals(self):
        for w in ((0,0),(-1,2),(math.nan,3),(True,1),[1]):
            with self.subTest(w=w), self.assertRaises(ValueError):
                b.weight_response(w,(2,3),(5,7))
        with self.assertRaises(ValueError):
            b.weight_response((1,2),(0,3),(5,7))
        with self.assertRaises(ValueError):
            b.prove_all_geometry(float("nan"),-.1)

    def test_out_of_contract_interval_fraction_rejected(self):
        for q in (-1,.0+1.01,math.nan,True):
            with self.subTest(q=q), self.assertRaises(ValueError):
                b.interval_coefficient({"low":1., "estimate":2., "high":3.}, "low", q)


if __name__ == "__main__":
    unittest.main()
