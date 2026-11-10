# SPDX-License-Identifier: Apache-2.0
"""Live-probe result classification with explicit non-network fixtures."""
import hashlib
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.adapters import BridgeError
from scripts.probe_frontier_monitor import probe, SOURCE_URL, SOURCE_HOST


class FrontierProbeTests(unittest.TestCase):
    def test_success_binds_one_fixed_source_and_reported_replay(self):
        content = b"Official source transport fixture, not a live observation"
        returned = {"url": SOURCE_URL, "sha256": hashlib.sha256(content).hexdigest(),
                    "retrieved_at": "2026-01-01T00:00:00+00:00", "text": content.decode()}
        with patch("bridge.frontier_monitor.retrieve_source", return_value=returned) as source:
            result = probe()
        self.assertEqual(source.call_count, 1)
        self.assertEqual(source.call_args.args, (SOURCE_URL, frozenset({SOURCE_HOST}), None))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["evidence_event"]["evidence_status"], "reported")
        self.assertEqual(result["opportunity_status"], "reconsider")
        self.assertIsNone(result["byte_change_observed"])
        self.assertFalse(result["publication_age_verified"])
        self.assertTrue(result["stopped"])
        self.assertTrue(result["temporary_workspace_removed"])
        self.assertFalse(result["real_credentials_used"])
        self.assertEqual(result["inference_calls"], 0)
        self.assertNotIn(content.decode(), str(result))

    def test_transport_blocks_are_not_live_passes(self):
        for code in ("SOURCE_URL", "SOURCE_CONNECTION", "SOURCE_HTTP", "SOURCE_TYPE", "SOURCE_SIZE"):
            with self.subTest(code=code), patch("bridge.frontier_monitor.retrieve_source", side_effect=BridgeError(code, "untrusted-body")) as source:
                result = probe()
            self.assertEqual(source.call_count, 1)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["error_code"], code)
            self.assertFalse(result["http_dispatch_verified"])
            self.assertNotIn("actual_source_sha256", result)
            self.assertNotIn("untrusted-body", str(result))
            self.assertTrue(result["temporary_workspace_removed"])

    def test_malformed_identity_is_an_implementation_failure(self):
        with patch("bridge.frontier_monitor.retrieve_source", return_value={"url": SOURCE_URL, "sha256": "bad"}):
            result = probe()
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["error_code"], "MONITOR_SOURCE")

    def test_replay_failure_never_becomes_a_transport_pass(self):
        returned = {"url": SOURCE_URL, "sha256": "a" * 64, "retrieved_at": "2026-01-01T00:00:00+00:00"}
        with patch("bridge.frontier_monitor.retrieve_source", return_value=returned), patch("bridge.genesis_next.GenesisNextService.replay", side_effect=ValueError("fixture")):
            result = probe()
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["error_type"], "ValueError")


if __name__ == "__main__":
    unittest.main()
