"""Independent oracle and preregistered adversarial tests for IMPACT229."""
import copy
import hashlib
import importlib.util
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "tools" / "impact_continuation229.py"
spec = importlib.util.spec_from_file_location("impact229", TOOL)
lib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lib)


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def policy(name, version, tags, controls):
    return {"id": name, "version": version, "source_sha256": digest(name + version),
            "applies_to": tags, "controls": controls}


def system(name, tags, evidence=()):
    return {"id": name, "tags": tags, "evidence_refs": [
        {"control": c, "source_sha256": digest(name + c)} for c in evidence]}


def envelope(before, after, systems):
    return {"schema": lib.SCHEMA, "before": before, "after": after, "systems": systems}


def exhaustive_changed_pairs(data):
    """Deliberately independent O(requirements*systems) oracle, no index."""
    old = {r["id"]: r for r in data["before"]}
    new = {r["id"]: r for r in data["after"]}
    pairs = set()
    for rid in old.keys() | new.keys():
        a, b = old.get(rid), new.get(rid)
        if a == b:
            continue
        for s in data["systems"]:
            applies = False
            for p in (a, b):
                if p is not None:
                    applies |= "*" in p["applies_to"] or bool(set(p["applies_to"]) & set(s["tags"]))
            if applies:
                pairs.add((s["id"], rid))
    return pairs


class Impact229Tests(unittest.TestCase):
    def test_governance_differential_vs_exhaustive(self):
        before = [policy("directive", "v1", ["decision"], ["aia", "audit"]),
                  policy("security", "v1", ["*"], ["residency"])]
        after = [policy("directive", "v2", ["decision"], ["aia", "review"]), before[1]]
        data = envelope(before, after, [system("ai-a", ["decision"], ["aia"]),
                                         system("ai-b", ["analytics"]),
                                         system("ai-c", ["decision", "analytics"])])
        result = lib.assess(data)
        got = {(x["system_id"], x["requirement_id"]) for x in result["reassessments"]}
        self.assertEqual(got, exhaustive_changed_pairs(data))
        self.assertEqual(got, {("ai-a", "directive"), ("ai-c", "directive")})
        self.assertEqual(result["unaffected_systems_count"], 1)
        self.assertEqual(result["compliance_claim"], "NONE")
        self.assertEqual(result["reassessments"][0]["unlinked_controls"], ["audit", "review"])

    def test_supplier_quality_transfer_independent_activity(self):
        data = envelope([policy("lotrule", "r1", ["component"], ["inspection"])],
                        [policy("lotrule", "r2", ["component", "materials"], ["inspection", "trace"])],
                        [system("supplier-x", ["component"], ["inspection"]),
                         system("supplier-y", ["materials"]), system("supplier-z", ["food"])])
        result = lib.assess(data)
        self.assertEqual({(r["system_id"], r["requirement_id"]) for r in result["reassessments"]},
                         exhaustive_changed_pairs(data))
        self.assertEqual(result["reassessment_count"], 2)
        self.assertTrue(result["reassessments"][0]["linked_evidence"])
        self.assertNotIn("COMPLIANT", json.dumps(result))

    def test_retired_requirement_preserved_and_reviewed(self):
        data = envelope([policy("retired", "v1", ["alpha"], ["old"])], [],
                        [system("one", ["alpha"]), system("two", ["beta"])])
        result = lib.assess(data)
        self.assertEqual(result["changed_requirements"][0]["kind"], "retired")
        self.assertEqual(result["reassessments"][0]["review_controls"], ["old"])
        self.assertFalse(result["reassessments"][0]["applies_after"])
        self.assertEqual(len(result["reassessments"]), 1)

    def test_changed_applicability_covers_old_and_new(self):
        data = envelope([policy("boundary", "v1", ["old"], ["a"])],
                        [policy("boundary", "v2", ["new"], ["b"])],
                        [system("first", ["old"]), system("second", ["new"]),
                         system("third", ["other"])])
        result = lib.assess(data)
        self.assertEqual({r["system_id"] for r in result["reassessments"]}, {"first", "second"})
        self.assertEqual(result["reassessments"][0]["review_controls"], ["a"])
        self.assertEqual(result["reassessments"][1]["review_controls"], ["b"])

    def test_added_universal(self):
        data = envelope([], [policy("universal", "v1", ["*"], ["check"])],
                        [system("x", ["a"]), system("y", ["b"])])
        self.assertEqual(lib.assess(data)["reassessment_count"], 2)

    def test_no_change_not_assertion_of_compliance(self):
        a = policy("original", "v1", ["a"], ["b"])
        result = lib.assess(envelope([a], [copy.deepcopy(a)], [system("x", ["a"])]))
        self.assertEqual(result["reassessment_count"], 0)
        self.assertEqual(result["compliance_claim"], "NONE")

    def test_no_version_collision_even_if_hash_or_mapping_changes(self):
        a = policy("rule", "v1", ["a"], ["x"])
        for field, value in [("source_sha256", digest("tampered")), ("applies_to", ["b"]),
                             ("controls", ["y"])]:
            b = copy.deepcopy(a)
            b[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(lib.InvalidInput, "VERSION_CONTENT_COLLISION"):
                lib.assess(envelope([a], [b], [system("x", ["a"])]))

    def test_malformed_or_duplicate_inputs_fail_closed(self):
        a = policy("rule", "v1", ["a"], ["x"])
        bad = [envelope([a, a], [], []),
               envelope([], [], [system("x", ["a"]), system("x", ["a"])]),
               envelope([{**a, "source_sha256": "malformed"}], [], []),
               envelope([{**a, "applies_to": ["a", "a"]}], [], []),
               envelope([], [], [system("x", ["a", "a"])]),
               envelope([], [], [{**system("x", ["a"]), "evidence_refs": [
                   {"control": "q", "source_sha256": digest("a")},
                   {"control": "q", "source_sha256": digest("b")}]}])]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(lib.InvalidInput):
                lib.assess(data)

    def test_fixed_seed_exhaustive_oracle_with_adverse_changes(self):
        rng = random.Random(229041)
        tags = ["alpha", "beta", "gamma", "delta", "epsilon"]
        systems = [system(f"system-{i}", rng.sample(tags, rng.randint(1, len(tags))))
                   for i in range(137)]
        old, new = [], []
        for i in range(57):
            p = policy(f"policy-{i}", "v1", rng.sample(tags, rng.randint(1, len(tags))),
                       [f"control-{i}"])
            old.append(p)
            if i % 7 == 0:
                continue
            if i % 3 == 0:
                new.append(policy(f"policy-{i}", "v2", rng.sample(tags, rng.randint(1, len(tags))),
                                  [f"control-{i}", f"review-{i}"]))
            else:
                new.append(p)
        for i in range(12):
            new.append(policy(f"addition-{i}", "v1", rng.sample(tags, 2), [f"new-{i}"]))
        data = envelope(old, new, systems)
        result = lib.assess(data)
        self.assertEqual({(r["system_id"], r["requirement_id"]) for r in result["reassessments"]},
                         exhaustive_changed_pairs(data))
        self.assertEqual(result["reassessment_count"], len(exhaustive_changed_pairs(data)))

    def test_order_and_process_determinism(self):
        a = policy("req", "v1", ["b", "a"], ["y", "x"])
        b = policy("req", "v2", ["a", "b"], ["x", "z"])
        x = envelope([a], [b], [system("m", ["a", "b"], ["x"]), system("z", ["other"])])
        y = envelope([{**a, "applies_to": list(reversed(a["applies_to"])),
                       "controls": list(reversed(a["controls"]))}],
                     [b], list(reversed(x["systems"])))
        self.assertEqual(lib.assess(x), lib.assess(y))
        with tempfile.TemporaryDirectory() as directory:
            inp = Path(directory) / "case.json"
            inp.write_text(json.dumps(x), encoding="utf-8")
            first = subprocess.run([sys.executable, str(TOOL), str(inp)], capture_output=True, text=True)
            second = subprocess.run([sys.executable, str(TOOL), str(inp)], capture_output=True, text=True)
            self.assertEqual(first.returncode, 0)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(json.loads(first.stdout), lib.assess(x))

    def test_cli_duplicate_json_keys_and_create_only_output(self):
        with tempfile.TemporaryDirectory() as directory:
            inp = Path(directory) / "case.json"
            inp.write_text('{"schema":"impact-continuation229/v1","schema":"duplicate"}', encoding="utf-8")
            bad = subprocess.run([sys.executable, str(TOOL), str(inp)], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertIn("DUPLICATE_JSON_KEY", bad.stderr)
            inp.write_text(json.dumps(envelope([], [], [])), encoding="utf-8")
            out = Path(directory) / "receipt.json"
            ok = subprocess.run([sys.executable, str(TOOL), str(inp), "--output", str(out)],
                                capture_output=True, text=True)
            self.assertEqual(ok.returncode, 0)
            again = subprocess.run([sys.executable, str(TOOL), str(inp), "--output", str(out)],
                                   capture_output=True, text=True)
            self.assertEqual(again.returncode, 2)
            self.assertIn("File exists", again.stderr)

    def test_receipt_integrity_and_explicit_uncertainty(self):
        data = envelope([], [policy("req", "v1", ["a"], ["unknown"])], [system("s", ["a"])])
        result = lib.assess(data)
        receipt_hash = result.pop("result_sha256")
        self.assertEqual(receipt_hash, lib.sha(result))
        self.assertEqual(result["reassessments"][0]["unlinked_controls"], ["unknown"])
        self.assertEqual(result["source_claim"], "STRUCTURED_INPUT_NOT_INDEPENDENTLY_AUTHENTICATED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
