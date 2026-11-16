"""Frozen TRUST Ω reviewer tests: official FlashProve --next-token plumbing."""
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

SOURCE = Path(__file__).resolve().parents[1] / "products" / "trust-omega" / "verify.py"
spec = importlib.util.spec_from_file_location("trust_omega_reply_review_target", SOURCE)
target = importlib.util.module_from_spec(spec)
spec.loader.exec_module(target)


class CompleteReplyReview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.response = self.root / "response"
        self.response.mkdir()
        self.key_dir = self.root / "public"
        self.key_dir.mkdir()
        self.data = {
            "request": self.root / "request.req",
            "checker_source": self.root / "check_proof.py",
            "verifier_binary": self.root / "cp_verify",
            "parameter_file": self.root / "policy.txt",
            "scales_file": self.root / "KL.bin",
            "layout_file": self.root / "layout.txt",
        }
        for name, path in self.data.items():
            path.write_bytes(("controlled-" + name).encode())
        (self.response / "proof.bin").write_bytes(b"synthetic-proof-fixture")
        (self.response / "y.bin").write_bytes(b"synthetic-y")
        anchor = {
            "schema": "trust-omega-anchor-v1",
            "commitment_id": "a" * 64,
            "model_label": "fixture-only",
            "independent_source": "synthetic reviewer-controlled fixture; not model identity",
            "policy": "exact-match",
            "end_token_ids": [199],
            "allow_proof_of_work": False,
            "trusted_sha256": {
                name: hashlib.sha256(self.data[name].read_bytes()).hexdigest()
                for name in (
                    "checker_source", "verifier_binary", "parameter_file",
                    "scales_file", "layout_file"
                )
            },
        }
        self.anchor = self.root / "anchor.json"
        self.anchor.write_text(json.dumps(anchor))

    def arguments(self, next_token):
        return [
            "--anchor", str(self.anchor),
            "--checker", str(self.data["checker_source"]),
            "--verifier", str(self.data["verifier_binary"]),
            "--response", str(self.response),
            "--request", str(self.data["request"]),
            "--parameter-file", str(self.data["parameter_file"]),
            "--scales-file", str(self.data["scales_file"]),
            "--layout-file", str(self.data["layout_file"]),
            "--public-key-dir", str(self.key_dir),
            "--prompt-tokens", "61", "--reply-tokens", "4",
            "--next-token", str(next_token),
        ]

    def call(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = target.main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_client_next_token_is_forwarded_to_pinned_upstream_checker(self):
        # Fake upstream success tests *argument plumbing only*; it is not a proof.
        response = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="result: outcome=verified claim=exact-match\n"
                   "check_proof: verified: synthetic fixture",
            stderr=""
        )
        with patch.object(target.subprocess, "run", return_value=response) as run:
            code, output, _ = self.call(self.arguments(199))
        self.assertEqual(code, 0, output)
        self.assertTrue(run.called, "no pinned upstream checker invoked")
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[cmd.index("--next-token") + 1], "199")
        self.assertEqual(cmd[cmd.index("--reply") + 1], "61:4")
        self.assertEqual(cmd[cmd.index("--end-token") + 1], "199")
        self.assertIn("--no-proof-of-work", cmd)

    def test_invalid_client_next_token_fails_before_checker(self):
        for value in (-1, 2 ** 32, "abc"):
            with self.subTest(value=value):
                with patch.object(target.subprocess, "run") as run:
                    code, _, _ = self.call(self.arguments(value))
                self.assertNotEqual(code, 0)
                self.assertFalse(run.called, "invalid token reached checker")


if __name__ == "__main__":
    unittest.main()
