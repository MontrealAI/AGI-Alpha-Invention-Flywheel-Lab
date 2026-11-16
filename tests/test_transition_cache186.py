"""P0-186 prospective review-only verification of nested historical CAS cache safety.

Protocol frozen at 7b27e26244a6f4f33ef7082f00a3543a57711756.
No native account, private key, signed financial authority, paid operation or source migration.
"""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from connected_enterprise import transition_evidence as te
from connected_enterprise import upgrades
from tests.test_transition_store184 import HistoricalEvidenceStoreRebindingTests


wire = HistoricalEvidenceStoreRebindingTests._wire_with_blobs


class HistoricalCacheClosureReview186(unittest.TestCase):
    def test_third_generation_grandparent_cas_loss_rejects_cached_receipt(self):
        ancestor, a = wire("grandparent", {"synthetic_history": "grandparent"})
        parent, b = wire("parent", {"source_transitions": {"ancestor": ancestor}})
        child, c = wire("child", {"source_transitions": {"parent": parent}})
        grandparent_only = sorted(set(a) - set(b) - set(c))
        self.assertTrue(grandparent_only)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "source"
            root.mkdir()
            store = Path(tmp) / "evidence"
            store.mkdir()
            te.persist_evidence(store, {**a, **b, **c})
            calls = []

            def historical_verifier(_command, *, input, **_kwargs):
                calls.append(json.loads(input)["evidence_dir"])
                try:
                    te.ticket_body(ancestor)
                except ValueError:
                    return SimpleNamespace(returncode=1, stdout="",
                                           stderr="GRANDPARENT_CAS_MISSING")
                return SimpleNamespace(returncode=0,
                                       stdout='{"accepted": true}', stderr="")

            upgrades._HISTORICAL_AUDITS.clear()
            try:
                with (patch.object(upgrades, "source_inventory",
                                   return_value={"synthetic.py": "f"*64}),
                      patch("commercial.ledger.load_jobs"),
                      patch.object(upgrades.subprocess, "run",
                                   side_effect=historical_verifier)):
                    with te.evidence_directory(store):
                        self.assertTrue(upgrades.verify_historical(child, {}, root=root)["accepted"])
                        self.assertTrue(upgrades.verify_historical(child, {}, root=root)["accepted"])
                        self.assertEqual(len(calls), 1)
                        # Same open evidence scope: CAS may still change on disk.
                        (store / grandparent_only[0]).unlink()
                        self.assertEqual(te.ticket_body(child)["schema"], te.V1)
                        self.assertEqual(te.ticket_body(parent)["schema"], te.V1)
                        with self.assertRaisesRegex(ValueError, "PINNED_HISTORICAL_AUDIT_FAILED"):
                            upgrades.verify_historical(child, {}, root=root)
                        self.assertEqual(len(calls), 2)
            finally:
                upgrades._HISTORICAL_AUDITS.clear()

    def test_original_v1_success_reuse_is_not_unnecessarily_disabled(self):
        outer_v2, blobs = wire("old-v1", {"synthetic_history": "ordinary"})
        with te.evidence_scope(blobs):
            original_v1 = {"body": te.ticket_body(outer_v2), "signature": "0"*64}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = []
            def verifier(*_args, **_kwargs):
                calls.append(1)
                return SimpleNamespace(returncode=0, stdout='{"accepted": true}', stderr="")
            upgrades._HISTORICAL_AUDITS.clear()
            try:
                with (patch.object(upgrades, "source_inventory",
                                   return_value={"synthetic.py": "f"*64}),
                      patch("commercial.ledger.load_jobs"),
                      patch.object(upgrades.subprocess, "run", side_effect=verifier)):
                    self.assertTrue(upgrades.verify_historical(original_v1, {}, root=root)["accepted"])
                    self.assertTrue(upgrades.verify_historical(original_v1, {}, root=root)["accepted"])
                    self.assertEqual(len(calls), 1)
            finally:
                upgrades._HISTORICAL_AUDITS.clear()


if __name__ == "__main__":
    unittest.main(verbosity=2)
