"""Frozen independent adversarial review of PR #410, see review_transcript/PREREGISTRATION.md.

All programs generated here are trusted, synthetic and local. No customer executables.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import explore
from binary_contract import binary_conformance

GOOD = json.loads((ROOT / "examples" / "escrow.json").read_text())


class FrozenConformanceFalsification(unittest.TestCase):
    def test_transcript_lookup_cannot_count_as_deterministic_binary_conformance(self):
        model = copy.deepcopy(GOOD)
        certificate = explore(model)
        self.assertEqual(certificate["status"], "PASS")
        names = certificate["variables"]
        actions = sorted(action["name"] for action in model["actions"])
        graph = {
            (tuple(edge["from"]), edge["action"]): edge["to"]
            for edge in certificate["edges"]
        }
        requests = []
        expected = []
        for state in certificate["states"]:
            for action in actions:
                requests.append({"state": dict(zip(names, state)), "action": action})
                target = graph.get((tuple(state), action))
                expected.append(
                    {"state": dict(zip(names, target))}
                    if target is not None
                    else {"rejected": True}
                )

        # Deliberately defective: outputs the canonical traversal answers by position,
        # disregarding the request. An executable is supposed to be input-deterministic.
        with tempfile.TemporaryDirectory() as dirname:
            executable = Path(dirname) / "trusted_fake_oracle.py"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                f"answers = {expected!r}\n"
                "for i, request in enumerate(sys.stdin):\n"
                "    print(json.dumps(answers[i % len(answers)], sort_keys=True))\n"
            )
            executable.chmod(0o700)

            # Independently prove this executable is wrong for the same input domain
            # in another ordering, before challenging the published conformance gate.
            reversed_requests = list(reversed(requests))
            p = subprocess.run(
                [str(executable)],
                input="".join(json.dumps(request, sort_keys=True) + "\n"
                              for request in reversed_requests),
                capture_output=True, text=True, timeout=15, check=True
            )
            actual = [json.loads(line) for line in p.stdout.splitlines()]
            self.assertEqual(len(actual), len(expected))
            self.assertNotEqual(actual, list(reversed(expected)),
                                "synthetic fixture must violate the input contract")

            result = binary_conformance(model, certificate, executable, unsafe_local=True)
            self.assertEqual(
                result["status"], "FAIL_MISMATCH",
                "A traversal-dependent script must not receive a bounded "
                "deterministic executable-conformance PASS",
            )

    def test_nonboolean_guard_must_never_produce_proof_pass(self):
        model = copy.deepcopy(GOOD)
        model["actions"][0]["when"] = 1
        result = explore(model)
        self.assertNotEqual(
            result["status"], "PASS",
            "An integer guard is not a Boolean policy predicate; the independent "
            "auditor rejects such a model, so the producer must not certify PASS",
        )


if __name__ == "__main__":
    unittest.main()
