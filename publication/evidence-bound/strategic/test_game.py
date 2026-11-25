"""Check exact game semantics, executable episodes and solver agreement."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
import random
import unittest

from game import DECISIONS, Game, PurchaseEnvironment, check, compare, play, read_games
from generate import retained_check


SYMMETRIC = Game("symmetric", ((8, -8), (-8, 8)), (100, 100), 3)


class ExactGameTests(unittest.TestCase):
    def test_purchase_observation_excludes_case_outcome(self):
        world = PurchaseEnvironment(SYMMETRIC)
        self.assertEqual(world.reset(), {"id": "symmetric", "payoffs": [[8, -8], [-8, 8]],
                                         "accuracy": [100, 100], "fee": 3})
        self.assertEqual(world.step("SKIP"), (None, Fraction(-5), True, {"accepted": False, "secure_value": "0"}))
        with self.assertRaises(ValueError):
            world.step("BUY")
        world.reset()
        self.assertEqual(world.step("BUY"), (None, Fraction(0), True, {"accepted": True, "secure_value": "5"}))

    def test_perfectly_inverted_signal_remains_valuable(self):
        case = replace(SYMMETRIC, accuracy=(0, 0))
        decision, bounds = compare(case)
        self.assertEqual((decision, bounds["BUY"].value), ("BUY", Fraction(5)))
        self.assertEqual(play(case, decision, bounds["BUY"].policy, 27),
                         {"column": 0, "signal": 1, "row": 0, "payoff": 5})

    def test_uninformative_channel_and_break_even(self):
        for accuracy in [(50, 50), (75, 25), (2, 98)]:
            case = replace(SYMMETRIC, accuracy=accuracy, fee=0)
            decision, bounds = compare(case)
            self.assertEqual(decision, "SKIP")
            self.assertEqual(bounds["BUY"].value, bounds["SKIP"].value)
        self.assertEqual(compare(replace(SYMMETRIC, fee=8))[0], "SKIP")

    def test_structural_transformations_keep_values(self):
        case = Game("asymmetric", ((8, -5), (-6, 9), (-15, -13)), (98, 63), 4)
        result, originals = compare(case)
        for equivalent in (
            replace(case, payoffs=tuple(reversed(case.payoffs))),
            replace(case, payoffs=tuple((x1, x0) for x0, x1 in case.payoffs), accuracy=case.accuracy[::-1]),
            replace(case, payoffs=case.payoffs[:-1]),
        ):
            answer, bounds = compare(equivalent)
            self.assertEqual(result, answer)
            self.assertEqual({a: originals[a].value for a in DECISIONS}, {a: bounds[a].value for a in DECISIONS})

    def test_tampered_reference_and_training_targets_cannot_be_inputs(self):
        _, originals = compare(SYMMETRIC)
        with self.assertRaises(ValueError):
            check(SYMMETRIC, "BUY", replace(originals["BUY"], value=Fraction(7)))
        with self.assertRaises(ValueError):
            Game.from_document({**SYMMETRIC.document(), "target": "BUY"})
        with TemporaryDirectory() as work:
            file = Path(work) / "bad.jsonl"
            file.write_text('{"id":"u","id":"v","payoffs":[[1,0],[0,1]],"accuracy":[62,71],"fee":0}\n')
            with self.assertRaises(ValueError):
                read_games(file)
        for document in [{**SYMMETRIC.document(), "accuracy": [True, 20]},
                         {**SYMMETRIC.document(), "fee": -1}]:
            with self.assertRaises(ValueError):
                Game.from_document(document)

    def test_retained_verifier_agrees_on_asymmetric_multiaction_games(self):
        rng = random.Random(723886)
        for i in range(56):
            case = Game(f"test-{i}", tuple((rng.randrange(-15, 15), rng.randrange(-15, 15))
                                          for _ in range(rng.randrange(2, 6))),
                        (rng.randrange(101), rng.randrange(101)), rng.randrange(8))
            _, candidates = compare(case)
            for action in DECISIONS:
                proof = retained_check(case, action, candidates[action])
                self.assertEqual(Fraction(proof["exact_value_after_shift"]) - proof["payoff_shift"],
                                 candidates[action].value)


if __name__ == "__main__":
    unittest.main()
