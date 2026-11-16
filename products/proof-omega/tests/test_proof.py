"""PROOF Ω security and assurance regressions."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from proof import ProofError, prepare, prove, invent, read, main

def sample():
    return {"schema":1,"name":"metered charge","domain":{"hours":[0,7],"rate":[0,11],"rebate":[0,9]},
            "reference":"hours * rate - hours * rebate","candidate":"hours * (rate - rebate)",
            "preconditions":["rebate <= rate"],"invariants":["out >= 0"]}

class ProofTests(unittest.TestCase):
    def test_complete_domain_and_hash_determinism(self):
        a = prove(sample())
        self.assertEqual(a["status"], "VERIFIED_BOUNDED")
        self.assertEqual(a["states_total"], 8*12*10)
        self.assertEqual(a["states_admitted"], a["states_checked"])
        self.assertLess(a["candidate_cost_proxy"], a["reference_cost_proxy"])
        self.assertEqual(a, prove(copy.deepcopy(sample())))

    def test_wrong_replacement_yields_witness(self):
        c = sample(); c["candidate"] = "hours * rate + hours * rebate"
        self.assertEqual(prove(c)["counterexample"]["violation"], "non_equivalence")

    def test_invariant_violation_is_not_a_pass(self):
        c = sample(); c["invariants"] = ["out < 0"]
        self.assertEqual(prove(c)["counterexample"]["violation"], "invariant")

    def test_vacuous_predicate_is_hold(self):
        c = sample(); c["preconditions"] = ["hours < 0"]
        self.assertEqual(prove(c)["counterexample"]["violation"], "vacuous_preconditions")

    def test_no_sampling_large_domain(self):
        c = sample(); c["domain"]["hours"] = [0, 1_000_000]
        with self.assertRaisesRegex(ProofError, "never sample"): prepare(c)

    def test_unsafe_ast_rejected(self):
        for value in ("__import__('os').system('id')", "hours.__class__", "hours**9999", "[x for x in range(3)]", "lambda: 1"):
            c = sample(); c["candidate"] = value
            with self.subTest(expr=value), self.assertRaises(ProofError): prepare(c)

    def test_bool_and_float_are_not_int_bounds(self):
        for value in (True, 1.1, None):
            c = sample(); c["domain"]["hours"][0] = value
            with self.subTest(value=value), self.assertRaises(ProofError): prepare(c)

    def test_zero_division_is_hold(self):
        c = sample(); c["candidate"] = "hours // (rate-rate)"
        self.assertEqual(prove(c)["counterexample"]["violation"], "undefined")

    def test_duplicate_json_keys_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d)/"bad.json"; f.write_text('{"schema":1,"schema":2}')
            with self.assertRaisesRegex(ProofError, "duplicate"): read(f)

    def test_replay_rejects_tampered_report(self):
        with tempfile.TemporaryDirectory() as d:
            contract = Path(d)/"contract.json"; report = Path(d)/"report.json"
            contract.write_text(json.dumps(sample())); proof = prove(sample())
            report.write_text(json.dumps(proof))
            self.assertEqual(main(["replay", str(contract), str(report)]), 0)
            proof["states_checked"] -= 1
            report.write_text(json.dumps(proof))
            self.assertEqual(main(["replay", str(contract), str(report)]), 2)

    def test_classical_invention_runs_and_is_proved(self):
        c = sample(); c["candidate"] = c["reference"]
        proposed, report = invent(c)
        self.assertNotEqual(proposed["candidate"], c["reference"])
        self.assertEqual(report["status"], "VERIFIED_BOUNDED")
        self.assertEqual(report["admission"], "LOWER_STATIC_PROXY_ONLY_NOT_MEASURED_SPEED")

    def test_no_invention_is_not_faked(self):
        c = sample(); c["reference"] = "hours * rate"; c["candidate"] = c["reference"]
        _, report = invent(c)
        self.assertEqual(report["status"], "HOLD")

if __name__=="__main__":
    unittest.main()
