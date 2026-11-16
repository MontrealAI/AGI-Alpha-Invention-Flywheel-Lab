"""Independent P0-184 adversarial test: evidence-store context must bind audit reuse.

Frozen before implementation at campaign/p0-review184/PROTOCOL.md.
No real account, signing key, recovery data or financial operation.
"""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from connected_enterprise import transition_evidence as te
from connected_enterprise import upgrades


class HistoricalEvidenceStoreRebindingTests(unittest.TestCase):
    @staticmethod
    def _wire_with_blobs(name, prior_record):
        body = {field: f"synthetic-{name}" for field in te.FIELDS}
        body.update(
            schema=te.V1,
            counter=1,
            from_source={"files": {"synthetic.py": "f" * 64}, "sha256": "a" * 64},
            to_source={"files": {"synthetic.py": "f" * 64}, "sha256": "b" * 64},
            historical_root=str(Path.cwd().absolute()),
            prior_record=prior_record,
            prior_envelope={"body": {"entries": []}},
            verifier_files={"synthetic.py": "f" * 64},
        )
        blobs = {}
        wire = te.externalize(body, blobs)
        # No signing secret: verify_historical tests independent historical
        # auditing, not owner HMAC authorization or account/ledger mutation.
        return {"body": wire, "signature": "0" * 64}, blobs

    def test_original_scope_success_must_not_authorize_missing_nested_cas_in_other_scope(self):
        nested, inner_objects = self._wire_with_blobs(
            "inner", {"synthetic_history": "inner"}
        )
        outer, outer_objects = self._wire_with_blobs(
            "outer", {"source_transitions": {"predecessor": nested}}
        )
        self.assertTrue(set(inner_objects) - set(outer_objects),
                        "The two stores must have different required CAS coverage")

        with tempfile.TemporaryDirectory() as tmp:
            historical_root = Path(tmp) / "source"
            historical_root.mkdir()
            first = Path(tmp) / "complete-store"
            second = Path(tmp) / "incomplete-store"
            first.mkdir()
            second.mkdir()
            # The two stores share the same outer CAS bytes and hence the same
            # outer signed descriptor; only the nested historical CAS differs.
            te.persist_evidence(first, {**inner_objects, **outer_objects})
            te.persist_evidence(second, outer_objects)

            with te.evidence_directory(first):
                self.assertEqual(te.ticket_body(outer)["prior_record"]
                                 ["source_transitions"]["predecessor"], nested)
                self.assertEqual(te.ticket_body(nested)["schema"], te.V1)
            with te.evidence_directory(second):
                self.assertEqual(te.ticket_body(outer)["prior_record"]
                                 ["source_transitions"]["predecessor"], nested)
                with self.assertRaisesRegex(
                    ValueError, "TRANSITION_EVIDENCE_MISSING_OR_CHANGED"
                ):
                    te.ticket_body(nested)

            calls = []

            def historical_subprocess_model(command, *, input, **kwargs):
                payload = json.loads(input)
                calls.append(payload["evidence_dir"])
                self.assertEqual(payload["evidence_dir"],
                                 te.current_store_directory())
                # An actual independent historical verifier must recursively
                # resolve the authenticated nested predecessor's CAS evidence.
                try:
                    te.ticket_body(nested)
                except ValueError:
                    return SimpleNamespace(returncode=1, stdout="",
                                           stderr="NESTED_HISTORICAL_CAS_MISSING")
                return SimpleNamespace(returncode=0,
                                       stdout='{"accepted": true}',
                                       stderr="")

            upgrades._HISTORICAL_AUDITS.clear()
            try:
                with (patch.object(upgrades, "source_inventory",
                                   return_value={"synthetic.py": "f" * 64}),
                      patch("commercial.ledger.load_jobs"),
                      patch.object(upgrades.subprocess, "run",
                                   side_effect=historical_subprocess_model)):
                    with te.evidence_directory(first):
                        accepted = upgrades.verify_historical(
                            outer, {}, root=historical_root
                        )
                        self.assertTrue(accepted["accepted"])
                        again = upgrades.verify_historical(
                            outer, {}, root=historical_root
                        )
                        self.assertTrue(again["accepted"])
                        self.assertEqual(len(calls), 1,
                                         "Within-scope reuse is permitted")
                    with te.evidence_directory(second):
                        with self.assertRaisesRegex(
                            ValueError, "PINNED_HISTORICAL_AUDIT_FAILED"
                        ):
                            upgrades.verify_historical(
                                outer, {}, root=historical_root
                            )
                        self.assertEqual(len(calls), 2,
                                         "Changed CAS scope requires re-audit")
            finally:
                upgrades._HISTORICAL_AUDITS.clear()


    def test_same_directory_evicted_nested_cas_must_not_reuse_earlier_audit(self):
        # Separately frozen in campaign/p0-review184/EXTENSION185.md at
        # commit 2095a6f121c08c5f19d70ddcc29b5142c9b9abc1.
        nested, inner_objects = self._wire_with_blobs(
            "inner", {"synthetic_history": "inner"}
        )
        outer, outer_objects = self._wire_with_blobs(
            "outer", {"source_transitions": {"predecessor": nested}}
        )
        inner_only = sorted(set(inner_objects) - set(outer_objects))
        self.assertTrue(inner_only, "Required nested-only CAS must exist")
        missing_sha = inner_only[0]

        with tempfile.TemporaryDirectory() as tmp:
            historical_root = Path(tmp) / "source"
            historical_root.mkdir()
            store = Path(tmp) / "one-ephemeral-store"
            store.mkdir()
            te.persist_evidence(store, {**inner_objects, **outer_objects})
            calls = []

            def historical_subprocess_model(command, *, input, **kwargs):
                payload = json.loads(input)
                calls.append(payload["evidence_dir"])
                self.assertEqual(payload["evidence_dir"],
                                 te.current_store_directory())
                try:
                    te.ticket_body(nested)
                except ValueError:
                    return SimpleNamespace(returncode=1, stdout="",
                                           stderr="NESTED_HISTORICAL_CAS_MISSING")
                return SimpleNamespace(returncode=0,
                                       stdout='{"accepted": true}',
                                       stderr="")

            upgrades._HISTORICAL_AUDITS.clear()
            try:
                with (patch.object(upgrades, "source_inventory",
                                   return_value={"synthetic.py": "f" * 64}),
                      patch("commercial.ledger.load_jobs"),
                      patch.object(upgrades.subprocess, "run",
                                   side_effect=historical_subprocess_model)):
                    with te.evidence_directory(store):
                        self.assertEqual(
                            te.ticket_body(outer)["prior_record"]
                            ["source_transitions"]["predecessor"], nested
                        )
                        self.assertEqual(te.ticket_body(nested)["schema"], te.V1)
                        self.assertTrue(upgrades.verify_historical(
                            outer, {}, root=historical_root
                        )["accepted"])
                        self.assertTrue(upgrades.verify_historical(
                            outer, {}, root=historical_root
                        )["accepted"])
                        self.assertEqual(len(calls), 1,
                                         "Initial identical context may be cached")

                    # Fixture-only loss occurs between independent store scopes.
                    # No real account, historical evidence, or repository file
                    # is removed. Directory pathname and verifier input do not change.
                    (store / missing_sha).unlink()
                    with te.evidence_directory(store):
                        self.assertEqual(
                            te.ticket_body(outer)["prior_record"]
                            ["source_transitions"]["predecessor"], nested
                        )
                        with self.assertRaisesRegex(
                            ValueError, "TRANSITION_EVIDENCE_MISSING_OR_CHANGED"
                        ):
                            te.ticket_body(nested)
                        with self.assertRaisesRegex(
                            ValueError, "PINNED_HISTORICAL_AUDIT_FAILED"
                        ):
                            upgrades.verify_historical(
                                outer, {}, root=historical_root
                            )
                        self.assertEqual(len(calls), 2,
                                         "Evidence loss must force re-audit")
            finally:
                upgrades._HISTORICAL_AUDITS.clear()



if __name__ == "__main__":
    unittest.main(verbosity=2)
