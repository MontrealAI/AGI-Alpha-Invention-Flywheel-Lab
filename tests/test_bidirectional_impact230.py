"""Frozen twelve-case independent/adversarial bidirectional qualification.

Synthetic metadata only; these are engineering correctness checks, not
governmental eligibility, legal compliance, or economic-benefit evidence.
"""
import copy
import hashlib
import json
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools import impact_continuation229 as old
from tools import bidirectional_impact230 as new

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "bidirectional_impact230.py"


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def rule(name, version="v1", tags=("decision",), controls=("audit",)):
    return {"id": name, "version": version,
            "source_sha256": digest(name + version),
            "applies_to": list(tags), "controls": list(controls)}


def system(name, tags=("decision",), evidence=("audit",)):
    return {"id": name, "tags": list(tags),
            "evidence_refs": [{"control": c, "source_sha256": digest(name + c)}
                              for c in evidence]}


def case(rb, ra, sb, sa):
    return {"schema": new.SCHEMA,
            "before": {"requirements": rb, "systems": sb},
            "after": {"requirements": ra, "systems": sa}}


def pairs(result):
    return {(x["system_id"], x["requirement_id"]) for x in result["reviews"]}


def independent_exhaustive(payload):
    """Control with no imports or shared applicability/index logic."""
    q0 = {r["id"]: r for r in payload["before"]["requirements"]}
    q1 = {r["id"]: r for r in payload["after"]["requirements"]}
    s0 = {r["id"]: r for r in payload["before"]["systems"]}
    s1 = {r["id"]: r for r in payload["after"]["systems"]}
    relevant = set()
    for rid in q0.keys() | q1.keys():
        for sid in s0.keys() | s1.keys():
            r_before, r_after = q0.get(rid), q1.get(rid)
            s_before, s_after = s0.get(sid), s1.get(sid)
            if r_before == r_after and s_before == s_after:
                continue
            old_match = (r_before is not None and s_before is not None and
                         ("*" in r_before["applies_to"] or
                          any(t in s_before["tags"] for t in r_before["applies_to"])))
            new_match = (r_after is not None and s_after is not None and
                         ("*" in r_after["applies_to"] or
                          any(t in s_after["tags"] for t in r_after["applies_to"])))
            if old_match or new_match:
                relevant.add((sid, rid))
    return relevant


def generated(seed):
    rng = random.Random(seed)
    tags = ["a", "b", "c", "d", "e"]
    q0, q1 = [], []
    for i in range(17):
        r = rule("rule-" + str(i), "v1", rng.sample(tags, 2), ["control-" + str(i)])
        q0.append(r)
        if i % 7 == 0:
            continue
        if i % 4 == 0:
            q1.append(rule(r["id"], "v2", rng.sample(tags, 2), r["controls"] + ["new-" + str(i)]))
        else:
            q1.append(copy.deepcopy(r))
    for i in range(5):
        q1.append(rule("added-" + str(i), "v1", rng.sample(tags, 2), ["added"]))
    s0, s1 = [], []
    for i in range(40):
        s = system("system-" + str(i), rng.sample(tags, 2),
                   ["control-" + str(i % 17)])
        s0.append(s)
        if i % 11 == 0:
            continue
        if i % 5 == 0:
            s["tags"] = rng.sample(tags, 3)
        elif i % 3 == 0:
            s["evidence_refs"] = []
        s1.append(copy.deepcopy(s))
    for i in range(3):
        s1.append(system("new-system-" + str(i), rng.sample(tags, 2)))
    return case(q0, q1, s0, s1)


class Bidirectional230Tests(unittest.TestCase):
    def test_policy_unchanged_new_tag(self):
        p = rule("directive")
        x = system("x", ("prototype",))
        y = system("x", ("decision",), ())
        data = case([p], [copy.deepcopy(p)], [x], [y])
        original = old.assess({"schema": old.SCHEMA, "before": [p], "after": [p], "systems": [y]})
        self.assertEqual(original["reassessment_count"], 0)
        result = new.assess(data)
        self.assertEqual(pairs(result), {("x", "directive")})
        self.assertEqual(result["changed_requirement_count"], 0)
        self.assertEqual(result["changed_system_count"], 1)
        self.assertEqual(result["reviews"][0]["new_evidence"]["unlinked"], ["audit"])

    def test_policy_unchanged_removed_evidence(self):
        p = rule("directive")
        a = system("x", ("decision",), ("audit",))
        b = system("x", ("decision",), ())
        r = new.assess(case([p], [p], [a], [b]))
        self.assertEqual(pairs(r), {("x", "directive")})
        self.assertEqual(len(r["reviews"][0]["old_evidence"]["linked"]), 1)
        self.assertEqual(r["reviews"][0]["new_evidence"]["unlinked"], ["audit"])
        self.assertEqual(r["reviews"][0]["cause"], ["system_or_evidence_change"])

    def test_system_added_and_retired(self):
        p = rule("directive")
        r = new.assess(case([p], [p], [system("retired")], [system("added")]))
        self.assertEqual(pairs(r), {("added", "directive"), ("retired", "directive")})
        self.assertTrue(next(x for x in r["reviews"] if x["system_id"] == "retired")["system_retired"])
        self.assertFalse(next(x for x in r["reviews"] if x["system_id"] == "added")["system_retired"])

    def test_requirement_changed_bidirectional_applicability(self):
        a = rule("directive", "v1", ("old",))
        b = rule("directive", "v2", ("new",))
        data = case([a], [b], [system("a", ("old",)), system("b", ("new",))],
                    [system("a", ("old",)), system("b", ("new",))])
        self.assertEqual(pairs(new.assess(data)), {("a", "directive"), ("b", "directive")})

    def test_deduplicate_joint_changes(self):
        a = rule("r", "v1", ("old",))
        b = rule("r", "v2", ("new",))
        r = new.assess(case([a], [b], [system("s", ("old",))], [system("s", ("new",))]))
        self.assertEqual(r["review_count"], 1)
        self.assertEqual(r["reviews"][0]["cause"],
                         ["requirement_change", "system_or_evidence_change"])

    def test_unchanged_empty_and_no_compliance_verdict(self):
        p, s = rule("p"), system("s")
        a = new.assess(case([p], [copy.deepcopy(p)], [s], [copy.deepcopy(s)]))
        self.assertEqual(a["review_count"], 0)
        self.assertEqual(a["compliance_claim"], "NONE")
        self.assertNotIn("COMPLIANT", json.dumps(a))
        self.assertEqual(new.assess(case([], [], [], []))["review_count"], 0)

    def test_version_collision_and_malformed(self):
        p = rule("p")
        mutated = copy.deepcopy(p)
        mutated["controls"] = ["different"]
        with self.assertRaisesRegex(old.InvalidInput, "VERSION_CONTENT_COLLISION"):
            new.assess(case([p], [mutated], [system("s")], [system("s")]))
        for bad in (case([p, p], [p], [], []),
                    case([p], [p], [system("s"), system("s")], []),
                    case([p], [p], [system("s")], [{"id": "s", "tags": [], "evidence_refs": []}])):
            with self.subTest(bad=bad), self.assertRaises(old.InvalidInput):
                new.assess(bad)

    def test_cli_duplicate_json_and_create_only(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            source.write_text('{"schema":"bidirectional-impact230/v1","schema":"duplicate"}')
            bad = subprocess.run([sys.executable, str(TOOL), str(source)], text=True, capture_output=True)
            self.assertEqual(bad.returncode, 2)
            self.assertIn("DUPLICATE_JSON_KEY", bad.stderr)
            source.write_text(json.dumps(case([], [], [], [])))
            dest = Path(directory) / "receipt.json"
            ok = subprocess.run([sys.executable, str(TOOL), str(source), "--output", str(dest)],
                                text=True, capture_output=True)
            self.assertEqual(ok.returncode, 0, ok.stderr)
            duplicate = subprocess.run([sys.executable, str(TOOL), str(source), "--output", str(dest)],
                                       text=True, capture_output=True)
            self.assertEqual(duplicate.returncode, 2)

    def test_independent_ordinary_exhaustive_ai(self):
        p = rule("ai-policy")
        data = case([p], [p], [system("ai-one", ("prototype",)), system("ai-two")],
                    [system("ai-one"), system("ai-two", evidence=())])
        self.assertEqual(pairs(new.assess(data)), independent_exhaustive(data))
        self.assertEqual(len(pairs(new.assess(data))), 2)

    def test_distinct_supplier_quality(self):
        p = rule("lot-check", "v1", ("materials",), ("inspection",))
        data = case([p], [p],
                    [system("supplier-a", ("candidate",)), system("supplier-b", ("materials",), ("inspection",))],
                    [system("supplier-a", ("materials",)), system("supplier-b", ("materials",), ())])
        r = new.assess(data)
        self.assertEqual(pairs(r), independent_exhaustive(data))
        self.assertEqual(r["review_count"], 2)
        self.assertEqual(r["compliance_claim"], "NONE")

    def test_frozen_seed_230041(self):
        data = generated(230041)
        self.assertEqual(pairs(new.assess(data)), independent_exhaustive(data))
        self.assertEqual(new.assess(data), new.assess(data))

    def test_frozen_seed_230042(self):
        data = generated(230042)
        self.assertEqual(pairs(new.assess(data)), independent_exhaustive(data))
        reversed_data = copy.deepcopy(data)
        for edition in ("before", "after"):
            reversed_data[edition]["systems"].reverse()
            reversed_data[edition]["requirements"].reverse()
        self.assertEqual(new.assess(data), new.assess(reversed_data))


if __name__ == "__main__":
    unittest.main()
