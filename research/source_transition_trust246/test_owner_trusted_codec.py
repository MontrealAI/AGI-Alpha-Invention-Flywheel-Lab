"""Fixed adversarial tests for P0-247's no-authority trust-boundary reference."""
import ast
import copy
from pathlib import Path
import unittest

from owner_trusted_codec import (
    MAX_BLOB_BYTES, canonical, externalize_owner_trusted,
    recover_and_compare, strict_decode,
)


def fixture(queue):
    return {
        "schema": "agi-alpha/native-source-transition/v1",
        "id": "SYNTHETIC_NO_ACCOUNT",
        "account_path": "synthetic/not/a/real/account",
        "from_source": {"sha256": "a" * 64},
        "to_source": {"sha256": "b" * 64},
        "counter": 2,
        "expected_state_digest": "c" * 64,
        "day": 14,
        "historical_root": "synthetic/no/files",
        "verifier_files": {"connected_enterprise/finance.py": "d" * 64},
        "prior_record": {
            "ledger": {"actions": [
                {"day": 2, "event": "COLLECTED", "amount": 60},
                {"day": 3, "event": "CLAIM_RESERVED", "amount": 25},
            ]},
            "cash": 60, "unsettled_claims": 25,
            "permanent_tail": {"amount": 25, "maturity": 180},
        },
        "prior_envelope": {
            "body": {"entries": [{"status": "COMPLETE", "day": 2},
                                 {"status": "COMPLETE", "day": 3}]},
            "signature": "SYNTHETIC_NOT_A_REAL_SIGNATURE",
        },
        "operating": {
            "from_runtime": "synthetic-root",
            "prior_checkpoint": {
                "processed_events": 4, "queue": queue,
                "account_id": "SYNTHETIC_NO_ACCOUNT",
                "claims_due": [{"amount": 25, "day": 180}],
            },
        },
    }


QUEUES = (
    [{"id": "accept", "kind": "acceptance", "due": 16}],
    [{"id": "settle", "kind": "settlement", "due": 17}],
)


class TrustedCodecTest(unittest.TestCase):
    def assert_rejected(self, original, proposal, blobs):
        with self.assertRaises(ValueError):
            recover_and_compare(original, proposal, blobs)

    def test_acceptance_and_settlement_nonempty_queues(self):
        for queue in QUEUES:
            with self.subTest(queue=queue[0]["kind"]):
                body = fixture(queue)
                snapshot = copy.deepcopy(body)
                proposal, blobs = externalize_owner_trusted(body)
                receipt = recover_and_compare(body, proposal, blobs)
                self.assertEqual(receipt, canonical(proposal))
                self.assertEqual(body, snapshot)
                self.assertNotIn("prior_record", blobs)
                self.assertEqual(len(blobs), 2)
                self.assertEqual(snapshot["operating"]["prior_checkpoint"]["queue"], queue)
                self.assertEqual(snapshot["prior_record"]["unsettled_claims"], 25)

    def test_all_nonexternalized_history_and_authority_fields_are_conserved(self):
        old = fixture(QUEUES[0]); p, b = externalize_owner_trusted(old)
        for field, changed in [
            ("counter", 3), ("day", 15), ("to_source", {"sha256": "f" * 64}),
            ("expected_state_digest", "0" * 64),
            ("operating", {"prior_checkpoint": {"queue": []}}),
            ("account_path", "synthetic/alternate-account"),
        ]:
            with self.subTest(field=field):
                altered = copy.deepcopy(p); altered[field] = changed
                self.assert_rejected(old, altered, b)

    def test_mutated_money_claim_or_signed_envelope_is_rejected(self):
        old = fixture(QUEUES[1]); p, b = externalize_owner_trusted(old)
        for field, changes in [
            ("prior_record", {"cash": 10}),
            ("prior_record", {"unsettled_claims": 0}),
            ("prior_record", {"permanent_tail": {}}),
            ("prior_envelope", {"signature": "ALTERED"}),
        ]:
            with self.subTest(field=field, changes=changes):
                mutated = copy.deepcopy(old); mutated[field].update(changes)
                self.assert_rejected(mutated, p, b)

    def test_changed_blob_content(self):
        old = fixture(QUEUES[0]); p, b = externalize_owner_trusted(old)
        wrong = dict(b); sha = p["prior_record"]["sha256"]
        wrong[sha] = wrong[sha].replace(b'"cash":60', b'"cash":90')
        self.assert_rejected(old, p, wrong)

    def test_missing_extra_and_swapped_blob(self):
        old = fixture(QUEUES[0]); p, b = externalize_owner_trusted(old)
        missing = dict(b); missing.pop(p["prior_record"]["sha256"])
        self.assert_rejected(old, p, missing)
        extra = dict(b); extra["e" * 64] = b"{}"
        self.assert_rejected(old, p, extra)
        swapped = copy.deepcopy(p)
        swapped["prior_record"], swapped["prior_envelope"] = (
            swapped["prior_envelope"], swapped["prior_record"])
        self.assert_rejected(old, swapped, b)

    def test_reference_size_digest_and_structure_tamper(self):
        old = fixture(QUEUES[0]); p, b = externalize_owner_trusted(old)
        for field, value in [
            ("bytes", p["prior_record"]["bytes"] + 1),
            ("sha256", "e" * 64), ("field", "prior_envelope"),
            ("blob_domain", "target-controlled/v1"),
        ]:
            with self.subTest(field=field):
                t = copy.deepcopy(p); t["prior_record"][field] = value
                self.assert_rejected(old, t, b)
        t = copy.deepcopy(p); t["prior_record"]["unrecognized"] = 1
        self.assert_rejected(old, t, b)

    def test_duplicate_noncanonical_nonfinite_and_malformed_json(self):
        for raw in [b'{"a":1,"a":2}', b'{"a": NaN}', b'{"a": Infinity}',
                    b'{ "a":1}', b'{"z":1,"a":2}', b'\xff']:
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    strict_decode(raw)

    def test_missing_body_fields_and_nonjson_objects(self):
        for x in ({}, {"prior_record": {}}, {"prior_envelope": {}},
                  {"prior_record": b"bytes", "prior_envelope": {}},
                  {"prior_record": {"bad": {1: "not-string"}}, "prior_envelope": {}}):
            with self.subTest(candidate=str(x)[:40]):
                with self.assertRaises(ValueError):
                    externalize_owner_trusted(x)
        class Untrusted:
            def __str__(self):
                raise AssertionError("Must not run custom behavior")
        with self.assertRaises(ValueError):
            externalize_owner_trusted({"prior_record": Untrusted(),
                                       "prior_envelope": {}})

    def test_data_that_looks_like_code_never_executes(self):
        old = fixture(QUEUES[0])
        old["prior_record"]["untrusted_text"] = (
            "__import__('os').environ['SYNTHETIC_NO_KEY']"
        )
        p, b = externalize_owner_trusted(old)
        self.assertEqual(recover_and_compare(old, p, b), canonical(p))

    def test_cannot_increase_existing_resource_bounds(self):
        old = fixture(QUEUES[0])
        old["prior_record"]["oversize"] = "X" * (MAX_BLOB_BYTES + 1)
        with self.assertRaises(ValueError):
            externalize_owner_trusted(old)
        with self.assertRaises(ValueError):
            strict_decode(b" " * (MAX_BLOB_BYTES + 1))

    def test_reference_code_cannot_execute_target_code_or_touch_accounts(self):
        module = Path(__file__).with_name("owner_trusted_codec.py").read_text()
        tree = ast.parse(module)
        prohibited_imports = {"os", "subprocess", "importlib", "pathlib"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = ([alias.name.split(".")[0] for alias in node.names]
                         if isinstance(node, ast.Import) else
                         [node.module.split(".")[0] if node.module else ""])
                self.assertFalse(set(names) & prohibited_imports)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, {"exec", "eval", "__import__", "open"})
        self.assertNotIn("JournalAccount", module)
        self.assertNotIn("_account._key", module)


if __name__ == "__main__":
    unittest.main()
