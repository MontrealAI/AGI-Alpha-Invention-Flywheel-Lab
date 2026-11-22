"""Frozen SELECTIVE232 independent ordinary-control and adversarial suite.

All synthetic inputs; no source authority, legal decision, pricing, buyer or
native-account finance assertion. Frozen seeds: 232041, 232042.
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

from tools import selective_impact232 as target
from tools import bidirectional_impact230 as incumbent
from tools import impact_continuation229 as prior

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "selective_impact232.py"


def h(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def req(name="r", version="v1", tags=("a",), controls=("audit",)):
    return {"id": name, "version": version, "source_sha256": h(name + version),
            "applies_to": list(tags), "controls": list(controls)}


def sysrec(name="s", tags=("a",), refs=("audit",)):
    return {"id": name, "tags": list(tags),
            "evidence_refs": [{"control": c, "source_sha256": h(name + c)}
                              for c in refs]}


def payload(before_r=None, after_r=None, before_s=None, after_s=None):
    return {"schema": target.SCHEMA,
            "before": {"requirements": before_r if before_r is not None else [req()],
                       "systems": before_s if before_s is not None else [sysrec()]},
            "after": {"requirements": after_r if after_r is not None else [req()],
                      "systems": after_s if after_s is not None else [sysrec()]}}


def selected(result):
    return {(x["requirement_id"], x["system_id"]) for x in result["reviews"]}


def conservative_for(data):
    return incumbent.assess({"schema": incumbent.SCHEMA,
                             "before": data["before"], "after": data["after"]})


def independent_ordinary_oracle(data):
    """Independent direct nested-loop comparator, no target helpers or imports."""
    p0 = {r["id"]: r for r in data["before"]["requirements"]}
    p1 = {r["id"]: r for r in data["after"]["requirements"]}
    s0 = {s["id"]: s for s in data["before"]["systems"]}
    s1 = {s["id"]: s for s in data["after"]["systems"]}
    necessary = set()
    for rid in p0.keys() | p1.keys():
        ra, rb = p0.get(rid), p1.get(rid)
        for sid in s0.keys() | s1.keys():
            sa, sb = s0.get(sid), s1.get(sid)
            old_applies = bool(ra and sa and
                               ("*" in ra["applies_to"] or
                                not set(ra["applies_to"]).isdisjoint(sa["tags"])))
            new_applies = bool(rb and sb and
                               ("*" in rb["applies_to"] or
                                not set(rb["applies_to"]).isdisjoint(sb["tags"])))
            if not (old_applies or new_applies):
                continue
            old_controls = ra["controls"] if old_applies else []
            new_controls = rb["controls"] if new_applies else []
            old_evidence = {x["control"]: x["source_sha256"] for x in sa["evidence_refs"]} if sa else {}
            new_evidence = {x["control"]: x["source_sha256"] for x in sb["evidence_refs"]} if sb else {}
            old_linkage = {k: old_evidence.get(k) for k in old_controls}
            new_linkage = {k: new_evidence.get(k) for k in new_controls}
            if (ra != rb or old_applies != new_applies or
                    (sa is None) != (sb is None) or old_linkage != new_linkage):
                necessary.add((rid, sid))
    return necessary


def generated(seed):
    rng = random.Random(seed)
    tags = ["a", "b", "c", "d", "e", "f"]
    r0, r1 = [], []
    for i in range(13):
        r = req("r" + str(i), "v1", rng.sample(tags, 2), ["c" + str(i)])
        r0.append(copy.deepcopy(r))
        if i % 9 == 0:
            continue
        if i % 5 == 0:
            r = req("r" + str(i), "v2", rng.sample(tags, 2), ["c" + str(i)])
        r1.append(r)
    r1.append(req("new-r", "v1", ("c",), ("audit",)))
    s0, s1 = [], []
    for i in range(34):
        r = sysrec("s" + str(i), rng.sample(tags, 2), ["c" + str(rng.randrange(13))])
        s0.append(copy.deepcopy(r))
        if i % 13 == 0:
            continue
        if i % 4 == 0:
            r["tags"].append("irrelevant")
        elif i % 3 == 0:
            r["evidence_refs"].append({"control": "unrelated", "source_sha256": h(str(i))})
        elif i % 5 == 0:
            r["evidence_refs"] = []
        s1.append(r)
    s1.append(sysrec("new-s", ("a",)))
    return payload(r0, r1, s0, s1)


class Selective232Tests(unittest.TestCase):
    def check(self, data, expected):
        result = target.assess(data)
        self.assertEqual(selected(result), expected)
        self.assertEqual(selected(result), independent_ordinary_oracle(data))
        incumbent_pairs = {(x["requirement_id"], x["system_id"])
                           for x in conservative_for(data)["reviews"]}
        self.assertTrue(selected(result).issubset(incumbent_pairs))
        self.assertEqual(result["conservative_review_count"], len(incumbent_pairs))
        self.assertEqual(result["suppressed_count"], len(incumbent_pairs) - len(expected))
        self.assertIsNone(result["economic_savings_USD"])
        self.assertEqual(result["compliance_claim"], "NONE")
        return result

    def test_01_unchanged(self):
        self.check(payload(), set())

    def test_02_unrelated_added_tag_suppressed(self):
        before, after = sysrec(), sysrec(tags=("a", "other"))
        result = self.check(payload(before_s=[before], after_s=[after]), set())
        self.assertEqual(result["suppressed_count"], 1)

    def test_03_unrelated_removed_tag_suppressed(self):
        self.check(payload(before_s=[sysrec(tags=("a", "other"))],
                           after_s=[sysrec()]), set())

    def test_04_unrelated_new_evidence_suppressed(self):
        self.check(payload(after_s=[sysrec(refs=("audit", "new-control"))]), set())

    def test_05_unrelated_changed_evidence_suppressed(self):
        a = sysrec(refs=("audit", "unrelated"))
        b = copy.deepcopy(a)
        b["evidence_refs"][1]["source_sha256"] = h("replaced-unrelated")
        self.check(payload(before_s=[a], after_s=[b]), set())

    def test_06_required_evidence_removed(self):
        self.check(payload(after_s=[sysrec(refs=("other",))]), {("r", "s")})

    def test_07_required_evidence_added(self):
        self.check(payload(before_s=[sysrec(refs=("other",))],
                           after_s=[sysrec(refs=("audit", "other"))]), {("r", "s")})

    def test_08_required_evidence_changed_hash(self):
        b = sysrec()
        b["evidence_refs"][0]["source_sha256"] = h("changed-proof")
        self.check(payload(after_s=[b]), {("r", "s")})

    def test_09_applicability_added(self):
        self.check(payload(before_s=[sysrec(tags=("b",))]), {("r", "s")})

    def test_10_applicability_retired(self):
        self.check(payload(after_s=[sysrec(tags=("b",))]), {("r", "s")})

    def test_11_policy_revised(self):
        self.check(payload(after_r=[req(version="v2")]), {("r", "s")})

    def test_12_requirement_added_retired(self):
        self.check(payload(before_r=[req("old")], after_r=[req("new")]),
                   {("old", "s"), ("new", "s")})

    def test_13_system_added_retired(self):
        self.check(payload(before_s=[sysrec("old")], after_s=[sysrec("new")]),
                   {("r", "old"), ("r", "new")})

    def test_14_version_content_collision(self):
        r = req()
        changed = copy.deepcopy(r)
        changed["controls"] = ["other"]
        with self.assertRaisesRegex(prior.InvalidInput, "VERSION_CONTENT_COLLISION"):
            target.assess(payload(before_r=[r], after_r=[changed]))

    def test_15_duplicate_or_malformed_input_rejected(self):
        with self.assertRaises(prior.InvalidInput):
            target.assess(payload(before_s=[sysrec(), sysrec()]))
        with self.assertRaises(prior.InvalidInput):
            target.assess(payload(after_s=[sysrec(tags=())]))
        with self.assertRaises(prior.InvalidInput):
            target.assess({"schema": target.SCHEMA, "before": {}, "after": {}})

    def test_16_cli_duplicate_keys_and_create_only(self):
        with tempfile.TemporaryDirectory() as directory:
            inp = Path(directory) / "input.json"
            dest = Path(directory) / "result.json"
            inp.write_text('{"schema":"selective-impact232/v1","schema":"invalid"}')
            bad = subprocess.run([sys.executable, str(SCRIPT), str(inp)],
                                 capture_output=True, text=True)
            self.assertEqual(bad.returncode, 2)
            self.assertIn("DUPLICATE_JSON_KEY", bad.stderr)
            inp.write_text(json.dumps(payload()))
            a = subprocess.run([sys.executable, str(SCRIPT), str(inp), "--output", str(dest)],
                               capture_output=True, text=True)
            self.assertEqual(a.returncode, 0, a.stderr)
            b = subprocess.run([sys.executable, str(SCRIPT), str(inp), "--output", str(dest)],
                               capture_output=True, text=True)
            self.assertEqual(b.returncode, 2)
            self.assertIn("File exists", b.stderr)

    def test_17_frozen_seed_232041(self):
        data = generated(232041)
        self.check(data, independent_ordinary_oracle(data))

    def test_18_frozen_seed_232042(self):
        data = generated(232042)
        self.check(data, independent_ordinary_oracle(data))

    def test_19_order_invariance(self):
        data = generated(232041)
        reordered = copy.deepcopy(data)
        for t in ("before", "after"):
            reordered[t]["requirements"].reverse()
            reordered[t]["systems"].reverse()
        self.assertEqual(target.assess(data), target.assess(reordered))

    def test_20_digest_reproduction_and_no_profit_claim(self):
        data = generated(232042)
        result = target.assess(data)
        original = dict(result)
        reported = original.pop("result_sha256")
        self.assertEqual(reported, prior.sha(original))
        self.assertEqual(result, target.assess(data))
        self.assertEqual(result["source_claim"],
                         "CALLER_SUPPLIED_STRUCTURED_DATA_NOT_AUTHENTICATED")
        self.assertNotIn("profit", json.dumps(result).lower())


if __name__ == "__main__":
    unittest.main()
