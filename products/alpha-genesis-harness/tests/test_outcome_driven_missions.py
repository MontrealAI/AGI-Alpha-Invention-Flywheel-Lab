# SPDX-License-Identifier: Apache-2.0
"""Exact arithmetic and bounded source-capture integration regressions."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from test_universal_missions import propose, specification

from bridge.adapters import BridgeError
from bridge.instruments import evaluate
from bridge.universal_missions import UniversalMissionService
from bridge.workflow_demo import FixtureRuntime


class OutcomeDrivenTests(unittest.TestCase):
    def test_portable_exact_conversion_and_indefinite_quotient(self):
        arithmetic = {
            "inputs": ["values", "volume"], "numeric_mode": "exact-rational",
            "bindings": {"total": {"formula": "sum(values) * '1000'"}},
            "outputs": {"mg_per_liter": {"formula": "total / volume"}, "possible": {"formula": "total > '1000'"},
                        "same_ratio": {"formula": "total / volume == '16600/13'"},
                        "same_scale": {"formula": "volume == '13/10'"}, "same_text": {"formula": "'mg/L' == 'mg/L'"}},
        }
        inputs = {"values": ["0.78", "0.88"], "volume": "1.3"}
        result = evaluate(arithmetic, inputs)
        self.assertEqual(result["output"], {"mg_per_liter": "16600/13", "possible": True, "same_ratio": True,
                                            "same_scale": True, "same_text": True})
        self.assertEqual(json.loads(json.dumps(result)), result)
        for volume in (1.3, "0", "1/0", "1e-42"):
            with self.subTest(volume=volume), self.assertRaises(ValueError):
                evaluate(arithmetic, {**inputs, "volume": volume})
        with self.assertRaisesRegex(ValueError, "magnitude or precision"):
            evaluate(arithmetic, {**inputs, "values": ["9" * 40]})

    def test_scope_and_pin_for_real_offline_tool_operations(self):
        source_text = "a" * 511 + "é" + "b" * 131 + "\nDiagnostic: decisive suffix.\n"
        pin = hashlib.sha256(source_text.encode()).hexdigest()
        capture = {"url": "https://example.org/source-v2.txt", "version": "2", "sha256": pin,
                   "content_type": "text/plain", "text": source_text, "acquisition": "Controlled local test"}
        actions = [
            {"tool": "read_source_snapshot", "name": "outside.json", "source_id": "unknown"},
            {"tool": "read_source_snapshot", "name": "source.json", "source_id": "diagnostic", "offset": 0},
        ]
        with TemporaryDirectory() as directory:
            invalid_offset = {**actions[1], "offset": 512}
            second_chunk = {**actions[1], "offset": 511}
            runtime = FixtureRuntime([propose(*actions), propose(invalid_offset, second_chunk), propose(done=True)])
            service = UniversalMissionService(runtime, Path(directory))
            self.addCleanup(service.close)
            valid = specification(tools=["read_source_snapshot"], requirements={"source_snapshots": {"diagnostic": capture}})
            invalid = {**valid, "requirements": {"source_snapshots": {"diagnostic": {**capture, "text": "changed"}}}}
            with self.assertRaises(BridgeError) as failure:
                service.submit(invalid)
            self.assertEqual(failure.exception.code, "MISSION_SOURCE_PIN")
            run = service.step(service.submit(valid)["id"])
            self.assertEqual(set(run["artifacts"]), {"source.json"})
            refused = next(event for event in run["events"] if event["kind"] == "tool_refused")
            self.assertEqual(refused["detail"]["reason"], "Source ID is outside the operator-approved capture scope.")
            saved = next(event["detail"]["outcome"] for event in run["events"] if event["kind"] == "tool_completed")
            self.assertEqual(saved["source_sha256"], pin)
            self.assertEqual(saved["excerpt"]["next_byte_offset"], 511)
            self.assertEqual(saved["transport"], "OPERATOR_CAPTURE")
            self.assertFalse(saved["network_retrieved_by_executor"])
            run = service.step(run["id"])
            self.assertTrue(any("UTF-8 character boundary" in event["detail"].get("reason", "") for event in run["events"]))
            second = [event["detail"]["outcome"] for event in run["events"] if event["kind"] == "tool_completed"][-1]
            self.assertEqual((second["excerpt"]["text"], second["excerpt"]["next_byte_offset"]), (source_text[511:], None))
            service.step(run["id"])
            payload = json.loads(runtime.calls[-1]["prompt"].split("\nUNTRUSTED_MISSION_DATA\n", 1)[1])
            excerpts = [item["untrusted_source_excerpt"]["text"] for item in payload["latest_tool_results"] if "untrusted_source_excerpt" in item]
            self.assertEqual("".join(excerpts), source_text)


if __name__ == "__main__":
    unittest.main()
