"""P0-188 frozen independent CAS-snapshot experiment.

Protocol commit 9ed199b89c086c4ea1a8e2b37bc89dc83f039725.
Synthetic evidence only, no source owner or financial account mutation.
"""
import hashlib
from pathlib import Path
import tempfile
import unittest

from commercial.ledger import digest
from connected_enterprise import transition_evidence as te
from connected_enterprise.history_snapshot188 import capture_historical_evidence
from tests.test_transition_store184 import HistoricalEvidenceStoreRebindingTests


class ImmutableHistoryEvidenceSnapshot188(unittest.TestCase):
    def _fixture(self):
        wire = HistoricalEvidenceStoreRebindingTests._wire_with_blobs
        predecessor, a = wire("snapshot-predecessor", {"synthetic_history": "true"})
        outer, b = wire(
            "snapshot-outer", {"source_transitions": {"predecessor": predecessor}}
        )
        nested_only = sorted(set(a) - set(b))
        self.assertTrue(nested_only, "Need a uniquely nested referenced CAS blob")
        return predecessor, outer, a, b, nested_only[0]

    def test_closed_snapshot_survives_subsequent_live_directory_deletion(self):
        predecessor, outer, a, b, lost = self._fixture()
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "evidence"
            store.mkdir()
            te.persist_evidence(store, {**a, **b})
            with te.evidence_directory(store):
                snapshot = capture_historical_evidence(outer)
                self.assertEqual(snapshot.ticket_count, 2)
                self.assertEqual(snapshot.root_ticket_digest, digest(outer))
                self.assertEqual(set(snapshot.blobs), set(a) | set(b))
                with snapshot.evidence():
                    self.assertEqual(te.ticket_body(outer)["schema"], te.V1)
                    self.assertEqual(te.ticket_body(predecessor)["schema"], te.V1)
                # A live mutation after capture cannot change owned bytes.
                (store / lost).unlink()
                with self.assertRaisesRegex(
                    ValueError, "TRANSITION_EVIDENCE_MISSING_OR_CHANGED"
                ):
                    te.ticket_body(predecessor)
                with snapshot.evidence():
                    self.assertEqual(te.ticket_body(predecessor)["schema"], te.V1)
                    self.assertEqual(te.ticket_body(outer)["schema"], te.V1)
                expected = digest({
                    "root_ticket": digest(outer),
                    "blobs": [
                        {"sha256": sha, "bytes": len(raw)}
                        for sha, raw in sorted({**a, **b}.items())
                    ],
                })
                self.assertEqual(snapshot.closure_digest, expected)
                # This is historical proof transport, not financial authority.
                self.assertFalse(hasattr(snapshot, "accepted"))
                self.assertFalse(hasattr(snapshot, "authorize_upgrade"))
                self.assertFalse(hasattr(snapshot, "reserve_cash"))

    def test_missing_or_corrupted_nested_blob_before_capture_fails_closed(self):
        predecessor, outer, a, b, lost = self._fixture()
        for corruption in ("deleted", "wrong_contents"):
            with self.subTest(corruption=corruption):
                with tempfile.TemporaryDirectory() as tmp:
                    store = Path(tmp) / "evidence"
                    store.mkdir()
                    te.persist_evidence(store, {**a, **b})
                    if corruption == "deleted":
                        (store / lost).unlink()
                    else:
                        (store / lost).write_bytes(b'{"tampered":true}')
                    with te.evidence_directory(store):
                        with self.assertRaisesRegex(
                            ValueError, "TRANSITION_EVIDENCE_MISSING_OR_CHANGED"
                        ):
                            capture_historical_evidence(outer)

    def test_snapshot_blobs_immutable_and_unrelated_store_data_excluded(self):
        predecessor, outer, a, b, lost = self._fixture()
        extra = te.canonical({"unrelated": True})
        extra_sha = hashlib.sha256(extra).hexdigest()
        self.assertNotIn(extra_sha, {**a, **b})
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp) / "evidence"
            store.mkdir()
            te.persist_evidence(store, {**a, **b, extra_sha: extra})
            with te.evidence_directory(store):
                snapshot = capture_historical_evidence(outer)
            self.assertNotIn(extra_sha, snapshot.blobs)
            with self.assertRaises(TypeError):
                snapshot.blobs[lost] = b"altered"
            with snapshot.evidence():
                self.assertEqual(te.ticket_body(outer)["schema"], te.V1)

    def test_v1_without_cas_does_not_acquire_invented_evidence(self):
        original, _outer, a, _b, _lost = self._fixture()
        with te.evidence_scope(a):
            v1 = {"body": te.ticket_body(original), "signature": "0" * 64}
        with te.evidence_scope({}):
            snapshot = capture_historical_evidence(v1)
        self.assertEqual(snapshot.ticket_count, 1)
        self.assertEqual(len(snapshot.blobs), 0)
        with snapshot.evidence():
            self.assertEqual(te.ticket_body(v1)["schema"], te.V1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
