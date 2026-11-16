"""P0-189 frozen self-contained root-ticket proof transport tests.

Protocol frozen in 51277db628182c2ac30912d59a7f3c3d129b4b9d before
implementation. Synthetic tickets only; never exercises financial authority.
"""
from dataclasses import replace
import hashlib
from pathlib import Path
from types import MappingProxyType
import tempfile
import unittest

from commercial.ledger import digest
from connected_enterprise import transition_evidence as te
from connected_enterprise.history_snapshot188 import capture_historical_evidence
from tests.test_transition_store184 import HistoricalEvidenceStoreRebindingTests


class SelfContainedSnapshot189(unittest.TestCase):
    @staticmethod
    def fixture():
        wire = HistoricalEvidenceStoreRebindingTests._wire_with_blobs
        parent, a = wire("portable-parent", {"synthetic_history": "parent"})
        root, b = wire(
            "portable-root", {"source_transitions": {"parent": parent}}
        )
        unique = sorted(set(a) - set(b))
        assert unique
        return parent, root, a, b, unique[0]

    def capture(self):
        parent, root, a, b, unique = self.fixture()
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "cas"
            directory.mkdir()
            te.persist_evidence(directory, {**a, **b})
            with te.evidence_directory(directory):
                snapshot = capture_historical_evidence(root)
            # Original mutable disk store is destroyed at context exit.
        return snapshot, parent, root, unique

    def test_reopen_without_original_mutable_store_or_external_root_ticket(self):
        snapshot, parent, expected, _ = self.capture()
        original_digest = digest(expected)
        del expected
        self.assertEqual(digest(snapshot.reopen_ticket()), original_digest)
        with snapshot.evidence():
            resolved = te.ticket_body(snapshot.reopen_ticket())
            self.assertEqual(resolved["source_transitions"]["parent"], parent)
            self.assertEqual(te.ticket_body(parent)["schema"], te.V1)
        self.assertFalse(hasattr(snapshot, "authorize_upgrade"))
        self.assertFalse(hasattr(snapshot, "accepted"))
        self.assertFalse(hasattr(snapshot, "reserve_cash"))

    def test_root_mutation_truncation_noncanonical_or_duplicate_key_refused(self):
        snapshot, _, _, _ = self.capture()
        raw = snapshot.root_ticket_bytes
        variants = [
            raw[:-1],
            raw + b" ",
            b'{"body":{},' + raw[1:],
            b'{"body":null,"signature":"not a proof"}',
        ]
        for changed in variants:
            with self.subTest(changed=changed[:32]):
                with self.assertRaises((ValueError, TypeError)):
                    replace(snapshot, root_ticket_bytes=changed).reopen_ticket()
        with self.assertRaises(ValueError):
            replace(snapshot, root_ticket_digest="0" * 64).reopen_ticket()

    def test_nested_removed_wrong_bytes_foreign_blob_and_forged_metadata_refused(self):
        snapshot, _, _, unique = self.capture()
        raw = dict(snapshot.blobs)
        variants = []
        missing = dict(raw)
        del missing[unique]
        variants.append(replace(snapshot, blobs=MappingProxyType(missing)))
        wrong = dict(raw)
        wrong[unique] = b"altered"
        variants.append(replace(snapshot, blobs=MappingProxyType(wrong)))
        unrelated = te.canonical({"not_a_required_blob": True})
        extra = dict(raw)
        extra[hashlib.sha256(unrelated).hexdigest()] = unrelated
        variants.append(replace(snapshot, blobs=MappingProxyType(extra)))
        variants.append(replace(snapshot, closure_digest="f" * 64))
        variants.append(replace(snapshot, ticket_count=snapshot.ticket_count + 1))
        for changed in variants:
            with self.subTest(which=str(len(changed.blobs)) + changed.closure_digest[:5]):
                with self.assertRaises((ValueError, TypeError)):
                    changed.reopen_ticket()

    def test_canonical_bytes_and_cas_mapping_are_immutable(self):
        snapshot, _, _, unique = self.capture()
        self.assertIs(type(snapshot.root_ticket_bytes), bytes)
        with self.assertRaises(TypeError):
            snapshot.blobs[unique] = b"overwrite"
        with self.assertRaises(Exception):
            snapshot.root_ticket_bytes = b"overwrite"


if __name__ == "__main__":
    unittest.main(verbosity=2)
