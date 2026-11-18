import json
from pathlib import Path
import tempfile
import unittest

from decide import HERE, decide, strict_json, validate


def contract(**changes):
    out = dict(model="unobserved", dataset="unobserved", min_concurrency=1,
               max_ttft_p90_ms="500", min_tps_per_user="100", load_mode="reported",
               rate_metric="reported_tps_per_user", require_price=False, require_access=False,
               require_point_accuracy=False)
    return {**out, **changes}


class DecisionBoundary(unittest.TestCase):
    def test_receives_new_contract_without_interpolating_or_issuing_access(self):
        result = decide(contract())
        self.assertEqual(result["decision"], "withheld")
        self.assertFalse(result["deployment_authorized"])
        self.assertEqual(result["selected"], [])
        self.assertEqual(len(result["excluded"]), 28)
        self.assertEqual(result["next_test"]["action"], "measure_matching_workload")

    def test_distinguishes_absent_metrics_from_zero(self):
        with self.assertRaises(ValueError):
            validate(contract(min_tps_per_user=None))
        for val in ("NaN", "-1", "0", "1E999999999", True):
            with self.subTest(value=val), self.assertRaises(ValueError):
                validate(contract(min_tps_per_user=val))
        with self.assertRaises(ValueError):
            validate(contract(require_access=1))

    def test_changed_evidence_and_ambiguous_json_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            fixture = Path(folder) / "reports.json"
            state = json.loads((HERE / "reports.json").read_bytes())
            state["sources"][0]["status"] = "PUBLISHED"
            fixture.write_text(json.dumps(state))
            with self.assertRaisesRegex(ValueError, "differ"):
                decide(contract(), fixture)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            strict_json('{"x":1,"x":2}')


if __name__ == "__main__":
    unittest.main()
