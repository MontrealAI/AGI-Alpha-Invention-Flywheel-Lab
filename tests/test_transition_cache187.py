"""P0-187: frozen synthetic revocation between verified CAS closure and cache return.

PROTOCOL frozen at commit 8280d3f2c940575372d4390d533b12e68882c61a.
Review-only and test-only. Never touches live financial accounts or keys.
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


class HistoricalCacheAcceptanceRaceReview187(unittest.TestCase):
    def test_cached_acceptance_must_refuse_evidence_revoked_after_closure(self):
        wire = HistoricalEvidenceStoreRebindingTests._wire_with_blobs
        predecessor, predecessor_objects = wire(
            "race-predecessor", {"synthetic_history": "original"}
        )
        outer, outer_objects = wire(
            "race-outer", {"source_transitions": {"predecessor": predecessor}}
        )
        nested_only = sorted(set(predecessor_objects) - set(outer_objects))
        self.assertTrue(nested_only, "Need a uniquely nested object to revoke")
        selected_blob = nested_only[0]

        with tempfile.TemporaryDirectory() as tmp:
            historical_root = Path(tmp) / "historical-source"
            historical_root.mkdir()
            store = Path(tmp) / "evidence"
            store.mkdir()
            te.persist_evidence(store, {**predecessor_objects, **outer_objects})
            verifier_calls = []
            closure_results = []

            def modeled_historical_verifier(_command, *, input, **_kwargs):
                verifier_calls.append(json.loads(input)["evidence_dir"])
                try:
                    te.ticket_body(predecessor)
                except ValueError:
                    return SimpleNamespace(returncode=1, stdout="",
                                           stderr="NESTED_CAS_REVOKED")
                return SimpleNamespace(returncode=0,
                                       stdout='{"accepted": true}', stderr="")

            real_closure = upgrades._cached_history_evidence_available

            def fixed_interleaving(ticket):
                # Execute the real candidate's closure scan unmodified first.
                available = real_closure(ticket)
                closure_results.append(available)
                # This deterministic seam models revocation after a completed
                # scan, before verify_historical has returned cached approval.
                if len(closure_results) == 2 and available:
                    (store / selected_blob).unlink()
                return available

            upgrades._HISTORICAL_AUDITS.clear()
            try:
                with (patch.object(upgrades, "source_inventory",
                                   return_value={"synthetic.py": "f" * 64}),
                      patch("commercial.ledger.load_jobs"),
                      patch.object(upgrades.subprocess, "run",
                                   side_effect=modeled_historical_verifier),
                      patch.object(upgrades, "_cached_history_evidence_available",
                                   side_effect=fixed_interleaving)):
                    with te.evidence_directory(store):
                        self.assertTrue(upgrades.verify_historical(
                            outer, {}, root=historical_root)["accepted"])
                        self.assertEqual(len(verifier_calls), 1)
                        self.assertEqual(closure_results, [True])

                        caught = None
                        returned = None
                        try:
                            returned = upgrades.verify_historical(
                                outer, {}, root=historical_root)
                        except ValueError as exc:
                            caught = exc

                        # Prove the exact selected interleaving actually ran.
                        self.assertEqual(closure_results[:2], [True, True])
                        self.assertFalse((store / selected_blob).exists())
                        self.assertEqual(
                            te.ticket_body(outer)["source_transitions"]
                            if "source_transitions" in te.ticket_body(outer)
                            else te.ticket_body(outer)["prior_record"]
                            ["source_transitions"]["predecessor"],
                            predecessor,
                        )
                        with self.assertRaisesRegex(
                            ValueError, "TRANSITION_EVIDENCE_MISSING_OR_CHANGED"
                        ):
                            te.ticket_body(predecessor)

                        # A stale in-process receipt is not independent current
                        # financial proof after its required CAS has vanished.
                        self.assertIsNotNone(
                            caught,
                            "P0_187_CACHE_APPROVED_AFTER_CAS_REVOKED: "
                            f"accepted={returned!r}, verifier_calls={len(verifier_calls)}"
                        )
            finally:
                upgrades._HISTORICAL_AUDITS.clear()


if __name__ == "__main__":
    unittest.main(verbosity=2)
