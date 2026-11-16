import importlib.util
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "products" / "trust-omega" / "verify.py"
spec = importlib.util.spec_from_file_location("trust_omega_verify", PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class EvidenceTest(unittest.TestCase):
    def test_never_accept_exit_code_alone(self):
        for text in ("", "YES", "result: outcome=verified claim=exact-match\ncheck_proof: rejected: false"):
            status, _ = mod.parse_checker_output(0, text)
            self.assertNotEqual(status, "UPSTREAM_EXACT_ACCEPTED")

    def test_strict_exit_and_terminal_lines(self):
        ok = "result: outcome=verified claim=exact-match\ncheck_proof: verified: test statement"
        self.assertEqual(mod.parse_checker_output(0, ok)[0], "UPSTREAM_EXACT_ACCEPTED")
        self.assertEqual(mod.parse_checker_output(1, ok)[0], "NO_VERDICT")
        self.assertEqual(
            mod.parse_checker_output(0, ok.replace("claim=exact-match", "claim=next-token"))[0],
            "NO_VERDICT",
        )
        self.assertEqual(mod.parse_checker_output(0, ok + "\nWARNING")[0], "NO_VERDICT")

    def test_weaker_claim_not_full_proof(self):
        weak = "result: outcome=within-limits\ncheck_proof: within limits: weaker result"
        self.assertEqual(mod.parse_checker_output(0, weak)[0], "POLICY_ONLY")

    def test_denies_bad_trust_anchors(self):
        import json
        base = {
            "schema": "trust-omega-anchor-v1",
            "model_label": "Llama exact integer",
            "independent_source": "independently reviewed registry",
            "commitment_id": "a" * 64,
            "end_token_ids": [2],
            "policy": "exact-match",
            "allow_proof_of_work": False,
            "trusted_sha256": {
                k: "b" * 64 for k in (
                    "checker_source", "verifier_binary", "parameter_file",
                    "scales_file", "layout_file"
                )
            },
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "anchor.json"
            for key, value in (
                ("commitment_id", "fake"),
                ("end_token_ids", []),
                ("policy", "clipped-gap"),
                ("allow_proof_of_work", None),
                ("independent_source", ""),
                ("trusted_sha256", {}),
            ):
                variant = {**base, key: value}
                path.write_text(json.dumps(variant))
                with self.assertRaises(ValueError, msg=key):
                    mod.read_anchor(path)
            path.write_text(json.dumps(base))
            self.assertEqual(mod.read_anchor(path), base)

    def test_rejected_and_inconclusive(self):
        self.assertEqual(
            mod.parse_checker_output(
                1, "result: outcome=rejected\ncheck_proof: rejected: proof invalid"
            )[0], "REJECTED",
        )
        self.assertEqual(
            mod.parse_checker_output(
                14, "result: outcome=not-a-verification\ncheck_proof: not a verification: failed"
            )[0], "NOT_A_VERIFICATION",
        )
        self.assertEqual(mod.parse_checker_output(5, "NOT CHECKED")[0], "NO_VERDICT")


if __name__ == "__main__":
    unittest.main()
