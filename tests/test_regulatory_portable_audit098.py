"""Synthetic-only independent adversarial verification of portable replay098.

No government source bytes, secrets, network access, finance or paid APIs.
"""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research import regulatory_citation097 as source
from research import regulatory_portable_audit098 as replay


TBS = (b"<html><body><h2>6.1.1</h2>"
       b"<p>Completing, approving and publishing the final results</p>"
       b"<h2>6.1.2</h2><h2>6.3.2</h2>"
       b"<p>Monitoring the outcomes of the automated decision system</p>"
       b"<h2>6.3.3</h2></body></html>")
SSC = (b"<html><body><p>Allow for authorised reviewers</p>"
       b"<p>validate reject, modify or annotate findings</p>"
       b"<p>Support the assessment and reassessment of risks</p></body></html>")


class OfflineReplayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source_dir = self.root / "source"
        self.source_dir.mkdir()
        self.blobs = {
            "tbs-directive-2025": TBS,
            "ssc-challenge-2026": SSC,
        }
        self.pins = {
            ident: {"url": source.ALLOWED[ident][0], "bytes": len(blob),
                    "sha256": hashlib.sha256(blob).hexdigest()}
            for ident, blob in self.blobs.items()
        }
        for ident, blob in self.blobs.items():
            (self.source_dir / (ident + ".html")).write_bytes(blob)
        self.docs = {
            ident: source.document(ident, source.ALLOWED[ident][0], blob)
            for ident, blob in self.blobs.items()
        }
        claims = [source.make_claim(code, self.docs[ident], anchor, stop, quote)
                  for code, ident, anchor, stop, quote in source.CLAIMS]
        self.packet = source.packet(self.docs, claims)
        self.packet_path = self.root / "packet.json"
        self.save_packet()

    def save_packet(self):
        self.packet_path.write_text(json.dumps(self.packet, sort_keys=True), encoding="utf-8")

    def run_replay(self, pins=None):
        return replay.verify_offline(self.source_dir, self.packet_path,
                                     trusted=self.pins if pins is None else pins)

    def assert_rejected(self, pins=None):
        with self.assertRaises((ValueError, TypeError, OSError)):
            self.run_replay(pins)

    def test_R0_valid_original_claims_and_external_synthetic_pins(self):
        result = self.run_replay()
        self.assertTrue(result["accepted"])
        self.assertEqual(result["accepted_claim_count"], 3)
        self.assertEqual(result["packet_sha256"], self.packet["packet_sha256"])
        self.assertFalse(result["limitations"]["real_paid_commerce"])
        self.assertNotIn("Completing, approving", json.dumps(result))

    def test_R1_missing_external_trust_rejected_even_self_consistent(self):
        self.assert_rejected({})
        self.assert_rejected({"tbs-directive-2025": self.pins["tbs-directive-2025"]})
        with self.assertRaises(ValueError):
            replay.verify_offline(self.source_dir, self.packet_path)

    def test_R2_changed_source_not_trusted_even_if_packet_regenerated(self):
        changed = TBS.replace(b"the final results", b"the other results")
        (self.source_dir / "tbs-directive-2025.html").write_bytes(changed)
        docs = dict(self.docs)
        docs["tbs-directive-2025"] = source.document("tbs-directive-2025",
                                                       source.ALLOWED["tbs-directive-2025"][0],
                                                       changed)
        claims = [source.make_claim(code, docs[ident], a, b, q)
                  for code, ident, a, b, q in source.CLAIMS]
        # Genuine expected claim now absent; malicious writer can still make a
        # self-consistent packet with a different quote, but cannot change pin.
        claims[0]["quote"] = "Completing, approving and publishing the other results"
        self.packet = source.packet(docs, claims)
        self.save_packet()
        self.assert_rejected()

    def test_R2_wrong_pin_digest_length_and_source_extra(self):
        bad = copy.deepcopy(self.pins)
        bad["tbs-directive-2025"]["sha256"] = "0" * 64
        self.assert_rejected(bad)
        bad = copy.deepcopy(self.pins)
        bad["tbs-directive-2025"]["bytes"] += 1
        self.assert_rejected(bad)
        bad = copy.deepcopy(self.pins)
        bad["tbs-directive-2025"]["sha256"] = "short"
        self.assert_rejected(bad)
        (self.source_dir / "third.html").write_text("<html/>")
        self.assert_rejected()

    def test_R2_missing_and_swapped_sources(self):
        path = self.source_dir / "tbs-directive-2025.html"
        path.unlink()
        self.assert_rejected()
        path.write_bytes(SSC)
        self.assert_rejected()

    def test_R3_packet_mutations_and_forged_checksum(self):
        self.packet["accepted_claims"][0]["status"] = "LEGAL_COMPLIANCE_APPROVED"
        self.packet["packet_sha256"] = source.sha(source.canonical(
            {k: v for k, v in self.packet.items() if k != "packet_sha256"}))
        self.save_packet()
        self.assert_rejected()

    def test_R3_stale_and_cross_document_packet(self):
        self.packet["sources"][0]["sha256"] = "0" * 64
        self.save_packet()
        self.assert_rejected()
        self.packet = source.packet(self.docs, [
            source.make_claim(code, self.docs[ident], a, b, q)
            for code, ident, a, b, q in source.CLAIMS])
        self.packet["accepted_claims"][1]["document"] = "ssc-challenge-2026"
        self.save_packet()
        self.assert_rejected()

    def test_R4_duplicate_key_and_nonfinite(self):
        self.packet_path.write_text('{"schema":"x","schema":"y"}')
        self.assert_rejected()
        self.packet_path.write_text('{"x":NaN}')
        self.assert_rejected()
        self.packet_path.write_text('{"x":Infinity}')
        self.assert_rejected()

    def test_R4_corrupted_and_oversized_packet(self):
        self.packet_path.write_bytes(b"\xff")
        self.assert_rejected()
        self.packet_path.write_bytes(b"{" + b" " * replay.PACKET_MAX_BYTES + b"}")
        self.assert_rejected()

    def test_R4_symlinks_and_nondirectory_source(self):
        first = self.source_dir / "tbs-directive-2025.html"
        first.unlink()
        first.symlink_to(self.root / "packet.json")
        self.assert_rejected()
        first.unlink()
        first.write_bytes(TBS)
        self.packet_path.unlink()
        source_packet = self.root / "actual-packet.json"
        source_packet.write_text(json.dumps(self.packet))
        self.packet_path.symlink_to(source_packet)
        self.assert_rejected()
        with self.assertRaises(ValueError):
            replay.verify_offline(self.packet_path, source_packet, trusted=self.pins)

    def test_R5_deterministic_zero_network_and_no_source_mutation(self):
        before = {p.name: p.read_bytes() for p in self.source_dir.iterdir()}
        with patch.object(source, "retrieve", side_effect=AssertionError("NETWORK_PROHIBITED")):
            first = self.run_replay()
            second = self.run_replay()
        self.assertEqual(first, second)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.source_dir.iterdir()})

    def test_R5_public_CLI_fails_synthetic_bytes_without_writing_raw_inputs(self):
        output = self.root / "RESULT.json"
        argv = ["verify", "--sources-dir", str(self.source_dir.resolve()),
                "--packet", str(self.packet_path.resolve()),
                "--output", str(output.resolve())]
        self.assertEqual(replay.main(argv), 1)
        refusal = json.loads(output.read_text())
        self.assertFalse(refusal["accepted"])
        self.assertNotIn(str(self.root), output.read_text())
        self.assertNotIn("Completing, approving", output.read_text())
        self.assertEqual(refusal["error"], "OFFLINE_REPLAY_REJECTED")
        with self.assertRaises(SystemExit):
            replay.main(argv)

    def test_R5_CLI_rejects_relative_paths(self):
        with self.assertRaises(SystemExit):
            replay.main(["verify", "--sources-dir", "relative", "--packet", "packet.json",
                         "--output", "RESULT.json"])


if __name__ == "__main__":
    unittest.main()
