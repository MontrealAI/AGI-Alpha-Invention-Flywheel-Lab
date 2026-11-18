"""Frozen adversarial coverage for independent governance reviewer provenance176."""
import base64
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from products.governance_impact140.engine import assess, canonical
from research.governance_review176 import (
    SCHEMA, BUNDLE_SCHEMA, TRUST_SCHEMA, evaluate, sha, _strict_object,
)

NOW = "2026-11-18T15:00:00Z"


def specimen():
    return {
        "systems": [
            {"id": "S1", "tags": ["finance"]},
            {"id": "S2", "tags": ["health"]},
        ],
        "requirements_before": [
            {"id": "R1", "version": "1", "control": "trace decisions",
             "applies_to": ["finance", "health"]},
        ],
        "requirements_after": [
            {"id": "R1", "version": "1", "control": "trace decisions",
             "applies_to": ["finance", "health"]},
        ],
        "evidence": [
            {"id": "E1", "system_id": "S1", "requirement_id": "R1",
             "version": "1", "claimed_status": "met", "review_claim": "approved"},
            {"id": "E2", "system_id": "S2", "requirement_id": "R1",
             "version": "1", "claimed_status": "partial"},
        ],
    }


class Reviewer176Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="review176-test-secret-")
        cls.root = Path(cls.tmp.name)
        for name in ("one", "two", "rsa"):
            key = cls.root / (name + ".private")
            pub = cls.root / (name + ".public")
            if name == "rsa":
                cmd = ["openssl", "genpkey", "-algorithm", "RSA",
                       "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(key)]
            else:
                cmd = ["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(key)]
            subprocess.run(cmd, capture_output=True, timeout=20, check=True)
            subprocess.run(["openssl", "pkey", "-in", str(key), "-pubout",
                            "-out", str(pub)], capture_output=True,
                           timeout=10, check=True)
            key.chmod(0o600)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def sign(self, statement, name="one"):
        msg = self.root / (name + ".msg")
        sig = self.root / (name + ".sig")
        msg.write_bytes(canonical(statement))
        subprocess.run(["openssl", "pkeyutl", "-sign",
                        "-inkey", str(self.root / (name + ".private")),
                        "-rawin", "-in", str(msg), "-out", str(sig)],
                       check=True, capture_output=True, timeout=10)
        return base64.b64encode(sig.read_bytes()).decode("ascii")

    def setup_data(self):
        receipt = assess(specimen())
        self.assertEqual([x["status"] for x in receipt["findings"]],
                         ["pending_review", "pending_review"])
        trust = {
            "schema": TRUST_SCHEMA, "organization_id": "tenant-1",
            "reviewers": [
                {"reviewer_id": "r1", "role": "independent_reviewer",
                 "systems": ["S1"], "requirements": ["R1"],
                 "public_key_pem": (self.root / "one.public").read_text(),
                 "revoked": False, "valid_from_utc": "2026-11-01T00:00:00Z",
                 "valid_until_utc": "2026-12-31T23:59:59Z"},
                {"reviewer_id": "r2", "role": "independent_reviewer",
                 "systems": ["S2"], "requirements": ["R1"],
                 "public_key_pem": (self.root / "two.public").read_text(),
                 "revoked": False, "valid_from_utc": "2026-11-01T00:00:00Z",
                 "valid_until_utc": "2026-12-31T23:59:59Z"},
            ],
        }
        statement = {
            "schema": SCHEMA, "decision_id": "D1",
            "organization_id": "tenant-1", "system_id": "S1",
            "requirement_id": "R1", "requirement_version": "1",
            "evidence_id": "E1",
            "source_receipt_sha256": receipt["receipt_sha256"],
            "source_input_sha256": receipt["source_input_sha256"],
            "decision": "validate", "issued_at_utc": "2026-11-18T14:00:00Z",
            "expires_at_utc": "2026-11-19T00:00:00Z",
            "note": "Review action, not compliance",
        }
        bundle = {"schema": BUNDLE_SCHEMA, "source_receipt": receipt,
                  "decisions": [{"reviewer_id": "r1", "statement": statement,
                                 "signature_b64": self.sign(statement)}]}
        return bundle, trust

    def run_case(self, bundle, trust, *, anchor_trust=None, anchor_receipt=None,
                 anchor_input=None, at=NOW):
        return evaluate(bundle, trust,
                        expected_trust_sha256=anchor_trust or sha(trust),
                        expected_receipt_sha256=anchor_receipt or bundle["source_receipt"]["receipt_sha256"],
                        expected_input_sha256=anchor_input or bundle["source_receipt"]["source_input_sha256"],
                        as_of_utc=at)

    def test_t01_real_crypto_verification_no_automatic_compliance(self):
        b, t = self.setup_data()
        before = copy.deepcopy(b["source_receipt"])
        out = self.run_case(b, t)
        self.assertEqual(out["review_actions"][0]["decision"], "validate")
        self.assertFalse(out["compliance_authorized"])
        self.assertTrue(out["underlying_governance_findings_unchanged"])
        self.assertEqual(b["source_receipt"], before)
        self.assertTrue(b["source_receipt"]["findings"][0]["reported_approval_ignored"])
        self.assertEqual(out["receipt_sha256"], sha({k: v for k, v in out.items() if k != "receipt_sha256"}))

    def test_t02_signed_tampering_and_independent_anchors(self):
        b, t = self.setup_data()
        b["decisions"][0]["statement"]["decision"] = "reject"
        with self.assertRaises(ValueError):
            self.run_case(b, t)
        b, t = self.setup_data()
        b["decisions"][0]["signature_b64"] = base64.b64encode(b"!" * 64).decode()
        with self.assertRaisesRegex(ValueError, "SIGNED_REVIEW_ACTION_INVALID"):
            self.run_case(b, t)
        b, t = self.setup_data()
        b["source_receipt"]["findings"][0]["status"] = "met"
        with self.assertRaises(ValueError):
            self.run_case(b, t)
        b, t = self.setup_data()
        with self.assertRaisesRegex(ValueError, "TRUST_ANCHOR"):
            self.run_case(b, t, anchor_trust="0" * 64)
        with self.assertRaises(ValueError):
            self.run_case(b, t, anchor_receipt="0" * 64)

    def test_t03_scope_identity_cannot_be_rewritten_by_valid_signer(self):
        for field, value in [
            ("organization_id", "other-tenant"),
            ("system_id", "S2"),
            ("requirement_id", "R2"),
            ("requirement_version", "2"),
            ("evidence_id", "E2"),
        ]:
            b, t = self.setup_data()
            b["decisions"][0]["statement"][field] = value
            b["decisions"][0]["signature_b64"] = self.sign(b["decisions"][0]["statement"])
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.run_case(b, t)

    def test_t04_revocation_unknown_reviewer_and_key_substitution(self):
        b, t = self.setup_data()
        t["reviewers"][0]["revoked"] = True
        with self.assertRaisesRegex(ValueError, "REVOKED"):
            self.run_case(b, t)
        b, t = self.setup_data()
        b["decisions"][0]["reviewer_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "UNKNOWN_AUTHORIZED_REVIEWER"):
            self.run_case(b, t)
        b, t = self.setup_data()
        t["reviewers"][0]["public_key_pem"] = (self.root / "two.public").read_text()
        with self.assertRaisesRegex(ValueError, "SIGNED_REVIEW_ACTION_INVALID"):
            self.run_case(b, t)
        b, t = self.setup_data()
        t["reviewers"][0]["role"] = "operator"
        with self.assertRaisesRegex(ValueError, "INDEPENDENT_REVIEW_ROLE"):
            self.run_case(b, t)

    def test_t05_expired_future_and_reversed_clock(self):
        b, t = self.setup_data()
        for instant in ("2026-11-18T13:59:59Z", "2026-11-19T00:00:01Z",
                        "2026-11-18T15:00:00+00:00"):
            with self.subTest(instant=instant), self.assertRaises(ValueError):
                self.run_case(b, t, at=instant)
        b, t = self.setup_data()
        s = b["decisions"][0]["statement"]
        s["issued_at_utc"], s["expires_at_utc"] = s["expires_at_utc"], s["issued_at_utc"]
        b["decisions"][0]["signature_b64"] = self.sign(s)
        with self.assertRaises(ValueError):
            self.run_case(b, t)

    def test_t06_duplicate_decisions_and_target_in_one_batch(self):
        b, t = self.setup_data()
        b["decisions"].append(copy.deepcopy(b["decisions"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE_REVIEW_ACTION_OR_TARGET"):
            self.run_case(b, t)
        b, t = self.setup_data()
        other = copy.deepcopy(b["decisions"][0])
        other["statement"]["decision_id"] = "D2"
        other["signature_b64"] = self.sign(other["statement"])
        b["decisions"].append(other)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_REVIEW_ACTION_OR_TARGET"):
            self.run_case(b, t)

    def test_t07_prior_version_and_changed_requirement_refuse(self):
        b, t = self.setup_data()
        raw = specimen()
        raw["requirements_after"][0]["version"] = "2"
        b["source_receipt"] = assess(raw)
        s = b["decisions"][0]["statement"]
        s["source_receipt_sha256"] = b["source_receipt"]["receipt_sha256"]
        s["source_input_sha256"] = b["source_receipt"]["source_input_sha256"]
        b["decisions"][0]["signature_b64"] = self.sign(s)
        with self.assertRaisesRegex(ValueError, "CURRENT_EVIDENCE"):
            self.run_case(b, t)
        b, t = self.setup_data()
        s = b["decisions"][0]["statement"]
        s["evidence_id"] = "nonexistent"
        b["decisions"][0]["signature_b64"] = self.sign(s)
        with self.assertRaises(ValueError):
            self.run_case(b, t)

    def test_t08_invalid_schemas_and_key_algorithm_and_json(self):
        b, t = self.setup_data()
        b["decisions"][0]["signature_b64"] = "###"
        with self.assertRaisesRegex(ValueError, "INVALID_ED25519_SIGNATURE"):
            self.run_case(b, t)
        b, t = self.setup_data()
        t["reviewers"][0]["public_key_pem"] = (self.root / "rsa.public").read_text()
        with self.assertRaisesRegex(ValueError, "ONLY_ED25519_PUBLIC_KEYS"):
            self.run_case(b, t)
        b, t = self.setup_data()
        b["decisions"][0]["statement"]["decision"] = "issue_compliance_certificate"
        b["decisions"][0]["signature_b64"] = self.sign(b["decisions"][0]["statement"])
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_SIGNED_REVIEW_ACTION"):
            self.run_case(b, t)
        with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_FIELD"):
            json.loads('{"schema":1,"schema":2}', object_pairs_hook=_strict_object)

    def test_t09_second_reviewer_scope_is_disjoint(self):
        b, t = self.setup_data()
        s = b["decisions"][0]["statement"]
        s.update(decision_id="D2", system_id="S2", evidence_id="E2")
        b["decisions"][0]["reviewer_id"] = "r2"
        b["decisions"][0]["signature_b64"] = self.sign(s, "two")
        self.assertEqual(self.run_case(b, t)["review_actions"][0]["reviewer_id"], "r2")
        b["decisions"][0]["reviewer_id"] = "r1"
        with self.assertRaises(ValueError):
            self.run_case(b, t)

    def test_t10_negative_reviewer_action_is_not_compliance(self):
        b, t = self.setup_data()
        s = b["decisions"][0]["statement"]
        s["decision"] = "reject"
        b["decisions"][0]["signature_b64"] = self.sign(s)
        out = self.run_case(b, t)
        self.assertEqual(out["review_actions"][0]["decision"], "reject")
        self.assertFalse(out["compliance_authorized"])

    def test_t11_determinism_no_secret_export(self):
        b, t = self.setup_data()
        a, c = self.run_case(b, t), self.run_case(b, t)
        self.assertEqual(a, c)
        self.assertNotIn("PRIVATE KEY", json.dumps(a))
        self.assertNotIn("public_key_pem", json.dumps(a))
        self.assertNotIn("signature_b64", json.dumps(a))
        self.assertTrue(a["no_automated_native_action"])

    def test_t12_unsigned_claim_or_unauthenticated_finding_refused(self):
        b, t = self.setup_data()
        b["decisions"][0]["signature_b64"] = ""
        with self.assertRaises(ValueError):
            self.run_case(b, t)
        b, t = self.setup_data()
        b["decisions"] = []
        with self.assertRaisesRegex(ValueError, "NONEMPTY_REVIEW_ACTIONS"):
            self.run_case(b, t)


    def test_t13_actual_cli_with_separately_supplied_anchors(self):
        from research.governance_review176 import main
        b, t = self.setup_data()
        with tempfile.TemporaryDirectory(prefix="review176-cli-public-") as td:
            root = Path(td)
            (root / "bundle.json").write_text(json.dumps(b), encoding="utf-8")
            (root / "trust.json").write_text(json.dumps(t), encoding="utf-8")
            command = [
                "--bundle", str(root / "bundle.json"),
                "--trust", str(root / "trust.json"),
                "--expected-trust-sha256", sha(t),
                "--expected-input-sha256", b["source_receipt"]["source_input_sha256"],
                "--expected-receipt-sha256", b["source_receipt"]["receipt_sha256"],
                "--at-utc", NOW, "--output", str(root / "result.json"),
            ]
            main(command)
            result = json.loads((root / "result.json").read_text())
            self.assertFalse(result["compliance_authorized"])
            self.assertEqual(len(result["review_actions"]), 1)
            with self.assertRaises(FileExistsError):
                main(command)


    def test_r177_a_claimed_issuance_before_reviewer_authority_is_rejected(self):
        """An action claimed before the authorized role began cannot be accepted."""
        b, t = self.setup_data()
        statement = b["decisions"][0]["statement"]
        statement["issued_at_utc"] = "2026-10-31T14:00:00Z"
        b["decisions"][0]["signature_b64"] = self.sign(statement)
        with self.assertRaisesRegex(ValueError, "AUTHORIZ"):
            self.run_case(b, t)

    def test_r177_b_two_attributed_identities_cannot_share_one_anchored_key(self):
        """Anchored malformed identity registry must not ambiguously attribute a signer."""
        b, t = self.setup_data()
        t["reviewers"][1]["public_key_pem"] = t["reviewers"][0]["public_key_pem"]
        with self.assertRaisesRegex(ValueError, "UNIQUE.*KEY"):
            self.run_case(b, t)


if __name__ == "__main__":
    unittest.main()
