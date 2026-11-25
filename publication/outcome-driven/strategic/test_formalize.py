import unittest

from cases import materialize
from formalize import COMPATIBLE, FormalizationEnvironment, compile_reviewed, numeric_missing


class FormalizationTest(unittest.TestCase):
    def setUp(self):
        self.case = {"id": "checked-1", "lang": "en", "brief": "Separately reviewed brief.",
                     "payoffs": [[5, 0], [0, 5]], "accuracy": [100, 100], "fee": 1}

    def test_frozen_game_keeps_authorized_values_and_returns_exact_certificate(self):
        result = compile_reviewed(self.case, COMPATIBLE, COMPATIBLE)
        self.assertEqual(result["exact_bounds"], {"BUY": "4", "SKIP": "5/2"})
        self.assertEqual(result["decision"], "BUY")
        self.assertEqual(result["solver_input"]["accuracy"], [100, 100])
        self.assertEqual(set(result["certificates"]), {"BUY", "SKIP"})

    def test_false_timing_and_false_units_cannot_certify(self):
        for override in ({"timing": "late"}, {"timing": "adaptive"}, {"timing": "unknown"},
                         {"units": "different"}, {"units": "unknown"}):
            with self.subTest(override=override):
                reference = COMPATIBLE | override
                result = compile_reviewed(self.case, COMPATIBLE, reference)
                self.assertEqual(result["disposition"], "interpretation_disagrees")
                self.assertNotIn("solver_input", result)
                result = compile_reviewed(self.case, reference, reference)
                self.assertEqual(result["disposition"], "withhold")
                self.assertEqual(result["issues"], override)

    def test_missing_fee_and_calibration_cannot_be_substituted(self):
        for edits, expected in (({"fee": None}, "fee"), ({"accuracy": None}, "accuracy"),
                                ({"fee": None, "accuracy": None}, "both")):
            incomplete = self.case | edits
            with self.subTest(edits=edits):
                self.assertEqual(numeric_missing(incomplete), expected)
                with self.assertRaises(ValueError):
                    compile_reviewed(incomplete, COMPATIBLE, COMPATIBLE)
                reference = COMPATIBLE | {"missing": expected}
                result = compile_reviewed(incomplete, reference, reference)
                self.assertEqual(result["disposition"], "withhold")
                self.assertEqual(result["issues"], {"missing": expected})

    def test_data_boolean_is_never_enough_to_establish_finite_game(self):
        with self.assertRaises(ValueError):
            compile_reviewed(self.case | {"fee": False}, COMPATIBLE, COMPATIBLE)

    def test_environment_hides_teacher_and_penalizes_false_admission(self):
        environment = FormalizationEnvironment(self.case, COMPATIBLE | {"units": "different"})
        self.assertEqual(set(environment.reset()), {"id", "lang", "brief"})
        observation, reward, done, result = environment.step(COMPATIBLE)
        self.assertIsNone(observation)
        self.assertTrue(done)
        self.assertEqual(reward, -2)
        self.assertEqual(result["fields"], ["units"])
        with self.assertRaises(ValueError):
            environment.step(COMPATIBLE)

    def test_fixed_generator_rectangular_coverage_and_disjoint_wordings(self):
        train, development = materialize("train"), materialize("development")
        self.assertEqual(len(train), 128)
        self.assertEqual(len(development), 32)
        self.assertFalse({row["case"]["brief"] for row in train} & {row["case"]["brief"] for row in development})
        by_language = {lang: {tuple(row["oracle"].values()) for row in train if row["case"]["lang"] == lang}
                       for lang in ("en", "fr")}
        self.assertEqual({lang: len(descriptions) for lang, descriptions in by_language.items()}, {"en": 48, "fr": 48})


if __name__ == "__main__":
    unittest.main()
