"""Frozen FIRSTCASH209 offline positive and adversarial test matrix."""
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "tools" / "firstcash209_decision_kit.py"
CASE = ROOT / "campaign" / "unseen-first-cash-209" / "PUBLIC_SELF_CASE.json"
spec = importlib.util.spec_from_file_location("firstcash209_kit", CODE)
kit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kit)


def sample():
    return json.loads(CASE.read_text(encoding="utf-8"))


class FirstCash209Tests(unittest.TestCase):
    def build(self, case=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        src = root / "INPUT.json"
        src.write_text(json.dumps(case or sample(), ensure_ascii=False), encoding="utf-8")
        kit.build(src, root / "bundle")
        return root / "bundle"

    def test_fixed_public_case_three_distinct_decisions(self):
        c = kit.validate(sample())
        self.assertEqual(len({o["id"] for o in c["options"]}), 3)
        self.assertEqual([o["verdict"] for o in c["options"]], ["HOLD", "HOLD", "NO_DEPLOY"])
        self.assertTrue(all(v is None for o in c["options"] for v in o["complete_costs_cad"].values()))

    def test_build_and_independent_offline_replay(self):
        root = self.build()
        self.assertEqual(kit.verify(root)["status"], "OFFLINE_PROOF_VERIFIED")
        text = (root / "DECISION.html").read_text()
        self.assertEqual(text.count('class="sheet" data-page='), 10)
        self.assertIn('lang="fr"', text)
        self.assertIn('lang="en"', text)
        self.assertNotIn("<script", text.lower())
        d = json.loads((root / "DECISION.json").read_text())
        self.assertIsNone(d["buyer_collected_cad"])
        self.assertIsNone(d["complete_cost_profit_cad"])
        self.assertFalse(d["buyer_accepted_delivery"])
        self.assertFalse(d["commercial_release_authorized"])

    def test_identical_input_deterministic_outputs(self):
        first = self.build()
        second = self.build()
        for name in (*kit.FILE_NAMES, "MANIFEST.json"):
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes(), name)

    def test_prevent_replacement_of_existing_output(self):
        root = self.build()
        with self.assertRaisesRegex(kit.Refusal, "OUTPUT_MUST_NOT_EXIST"):
            kit.build(CASE, root)

    def test_refuse_duplicate_json_keys(self):
        with self.assertRaisesRegex(kit.Refusal, "DUPLICATE_JSON_KEY"):
            kit.json_load_bytes(b'{"schema":"one","schema":"two"}')

    def test_refuse_unapproved_customer_cash_in_case(self):
        c = sample()
        c["collected_revenue"] = 10000
        with self.assertRaisesRegex(kit.Refusal, "CASE_FIELDS"):
            kit.validate(c)

    def test_refuse_unverified_deployment(self):
        c = sample()
        c["options"][0]["verdict"] = "DEPLOY"
        with self.assertRaisesRegex(kit.Refusal, "UNVERIFIED_DEPLOY"):
            kit.validate(c)

    def test_refuse_missing_complete_costs(self):
        c = sample()
        del c["options"][0]["complete_costs_cad"]["correction"]
        with self.assertRaisesRegex(kit.Refusal, "INCOMPLETE_COST"):
            kit.validate(c)

    def test_refuse_invalid_source_and_auth_fields(self):
        for url in ("http://example.com", "https://guest:secret@example.com/test",
                    "file:///etc/passwd", "https://localhost.local/test"):
            c = sample()
            c["options"][0]["sources"][0]["url"] = url
            with self.subTest(url=url), self.assertRaises(kit.Refusal):
                kit.validate(c)

    def test_refuse_claim_of_finite_source_digest_without_hex(self):
        c = sample()
        c["options"][0]["sources"][0]["sha256"] = "verified"
        with self.assertRaisesRegex(kit.Refusal, "SOURCE_HASH_INVALID"):
            kit.validate(c)

    def test_refuse_duplicate_option_or_missing_no_deploy(self):
        c = sample()
        c["options"][1]["id"] = c["options"][0]["id"]
        with self.assertRaises(kit.Refusal):
            kit.validate(c)
        c = sample()
        c["options"][2]["verdict"] = "HOLD"
        with self.assertRaisesRegex(kit.Refusal, "EXACTLY_ONE_NO_DEPLOY"):
            kit.validate(c)

    def test_html_from_untrusted_case_text_is_escaped(self):
        c = sample()
        c["beneficiary"]["en"] = "<script>alert(1)</script>"
        root = self.build(c)
        text = (root / "DECISION.html").read_text()
        self.assertIn("&lt;script&gt;", text)
        self.assertNotIn("<script>", text)
        kit.verify(root)

    def test_refuse_modified_html_even_if_manifest_rewritten(self):
        root = self.build()
        p = root / "DECISION.html"
        p.write_bytes(p.read_bytes().replace(b"NO CLIENT OR PAYMENT CLAIM", b"CLIENT HAS PAID"))
        manifest_path = root / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["DECISION.html"] = hashlib.sha256(p.read_bytes()).hexdigest()
        manifest_path.write_bytes(kit.canonical(manifest))
        with self.assertRaisesRegex(kit.Refusal, "HTML_REPLAY_MISMATCH"):
            kit.verify(root)

    def test_refuse_modified_case_even_if_manifest_rewritten(self):
        root = self.build()
        p = root / "CASE.json"
        c = json.loads(p.read_text())
        c["beneficiary"]["en"] = "MONTREAL.AI altered public research self-case"
        p.write_bytes(kit.canonical(c))
        manifest_path = root / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"]["CASE.json"] = hashlib.sha256(p.read_bytes()).hexdigest()
        manifest_path.write_bytes(kit.canonical(manifest))
        with self.assertRaisesRegex(kit.Refusal, "CASE_SOURCE_MISMATCH"):
            kit.verify(root)

    def test_refuse_source_drift_or_missing_file(self):
        root = self.build()
        p = root / "MANIFEST.json"
        manifest = json.loads(p.read_text())
        manifest["generator_source_sha256"] = "0" * 64
        p.write_bytes(kit.canonical(manifest))
        with self.assertRaisesRegex(kit.Refusal, "GENERATOR_SOURCE_CHANGED"):
            kit.verify(root)
        p.write_bytes(kit.canonical({**manifest, "generator_source_sha256": kit.digest(CODE.read_bytes())}))
        (root / "DECISION.json").unlink()
        with self.assertRaisesRegex(kit.Refusal, "UNSAFE_OR_MISSING_FILE"):
            kit.verify(root)


if __name__ == "__main__":
    unittest.main()
