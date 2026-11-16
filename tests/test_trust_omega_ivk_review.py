"""Preregistered v2 public-key-tree binding, separate from upstream proof soundness."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / "products" / "trust-omega" / "verify.py"
spec = importlib.util.spec_from_file_location("trust_omega_ivk_review_target", PATH)
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)


def independent_tree_hash(root: Path) -> str:
    """Separate test-only serializer, not imported from implementation."""
    entries = []
    for p in sorted(root.rglob("*")):
        if p.is_file():
            entries.append([p.relative_to(root).as_posix(),
                            hashlib.sha256(p.read_bytes()).hexdigest()])
    serialized = json.dumps(entries, ensure_ascii=True, separators=(",", ":")).encode()
    return hashlib.sha256(serialized).hexdigest()


class VerificationKeyBindingReview(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ivk = self.root / "ivk"
        (self.ivk / "sub").mkdir(parents=True)
        (self.ivk / "key0.pub").write_bytes(b"pinned-key-0")
        (self.ivk / "sub" / "key1.pub").write_bytes(b"pinned-key-1")
        self.response = self.root / "response"
        self.response.mkdir()
        (self.response / "proof.bin").write_bytes(b"synthetic-proof")
        (self.response / "y.bin").write_bytes(b"synthetic-output")
        self.paths = {k: self.root / (k + ".bin") for k in (
            "request", "checker_source", "verifier_binary", "parameter_file",
            "scales_file", "layout_file"
        )}
        for k, p in self.paths.items():
            p.write_bytes(("test-" + k).encode())
        self.tree_pin = independent_tree_hash(self.ivk)
        self.anchor_data = {
            "schema": "trust-omega-anchor-v2",
            "commitment_id": "a" * 64,
            "model_label": "synthetic controlled v2 fixture",
            "independent_source": "independent test-owned source, not a model identity",
            "policy": "exact-match",
            "end_token_ids": [199],
            "allow_proof_of_work": True,
            "trusted_sha256": {
                **{k: hashlib.sha256(self.paths[k].read_bytes()).hexdigest()
                   for k in ("checker_source", "verifier_binary", "parameter_file",
                             "scales_file", "layout_file")},
                "public_key_tree": self.tree_pin,
            },
        }
        self.anchor = self.root / "anchor.json"
        self.write_anchor()

    def write_anchor(self):
        self.anchor.write_text(json.dumps(self.anchor_data), encoding="utf-8")

    def args(self):
        return [
            "--anchor", str(self.anchor),
            "--checker", str(self.paths["checker_source"]),
            "--verifier", str(self.paths["verifier_binary"]),
            "--response", str(self.response), "--request", str(self.paths["request"]),
            "--parameter-file", str(self.paths["parameter_file"]),
            "--scales-file", str(self.paths["scales_file"]),
            "--layout-file", str(self.paths["layout_file"]),
            "--public-key-dir", str(self.ivk),
            "--prompt-tokens", "61", "--reply-tokens", "4", "--next-token", "199",
        ]

    def invoke(self, allow_success=True):
        successful = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="result: outcome=verified claim=exact-match\n"
                   "check_proof: verified: synthetic mock only",
            stderr="")
        out, err = io.StringIO(), io.StringIO()
        with patch.object(target.subprocess, "run", return_value=successful) as runner:
            with redirect_stdout(out), redirect_stderr(err):
                result = target.main(self.args())
            if allow_success:
                self.assertEqual(result, 0, out.getvalue() + err.getvalue())
                self.assertTrue(runner.called)
            else:
                self.assertEqual(result, 1, out.getvalue() + err.getvalue())
                self.assertFalse(runner.called, "untrusted keys reached upstream checker")
        return json.loads(out.getvalue().splitlines()[-1])

    def test_v2_binds_every_public_key_byte_and_path_in_positive_receipt(self):
        receipt = self.invoke()
        self.assertEqual(receipt["schema"], "trust-omega-evidence-v1")
        self.assertEqual(receipt["anchor_schema"], "trust-omega-anchor-v2")
        self.assertEqual(receipt["evidence_sha256"]["public_key_tree"], self.tree_pin)

    def test_one_mutated_key_must_fail_before_upstream(self):
        (self.ivk / "sub" / "key1.pub").write_bytes(b"tampered-key-1")
        self.invoke(allow_success=False)

    def test_missing_or_extra_keys_must_fail_before_upstream(self):
        (self.ivk / "key0.pub").unlink()
        self.invoke(allow_success=False)
        (self.ivk / "key0.pub").write_bytes(b"pinned-key-0")
        (self.ivk / "extra.pub").write_bytes(b"untrusted-key")
        self.invoke(allow_success=False)

    def test_renamed_key_must_fail_before_upstream(self):
        (self.ivk / "key0.pub").rename(self.ivk / "key-0.pub")
        self.invoke(allow_success=False)

    def test_symlinks_fail_closed_even_when_pointing_inside_tree(self):
        (self.ivk / "alias.pub").symlink_to(self.ivk / "key0.pub")
        self.invoke(allow_success=False)

    def test_bad_or_missing_v2_pin_never_falls_back_to_v1(self):
        for pin in (None, "0" * 64):
            self.anchor_data["trusted_sha256"]["public_key_tree"] = pin
            self.write_anchor()
            self.invoke(allow_success=False)
        self.anchor_data["trusted_sha256"].pop("public_key_tree")
        self.write_anchor()
        self.invoke(allow_success=False)


if __name__ == "__main__":
    unittest.main()
