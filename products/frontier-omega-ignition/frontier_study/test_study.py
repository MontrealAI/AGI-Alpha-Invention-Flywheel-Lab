"""Registered counterfactuals for the evidence-sensitive route selection."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from frontier_study import default_mission, investigate, load_atlas


def scenarios():
    mission = default_mission()
    atlas = load_atlas()
    full = investigate(mission, atlas)
    without = copy.deepcopy(atlas)
    without["resources"] = []
    removed = investigate(mission, without, previous=full)
    restored = investigate(mission, atlas, previous=removed)
    cash = dict(mission, requires=["matched-configurations", "issue-outcomes", "measured-cash-cost", "task-disjoint-audit"])
    proof = dict(mission, question="model-provenance", purpose="Authenticate a delivered inference against a committed model.",
                 requires=["published-proof-system", "verified-customer-proof"])
    return {
        "full": full, "matrix_withdrawn": removed, "reintroduced": restored,
        "unchanged": investigate(mission, atlas, previous=restored),
        "cash": investigate(cash, atlas, previous=full),
        "proof": investigate(proof, atlas, previous=full),
        "cutoff": investigate(dict(mission, as_of="2026-10-13"), atlas)
    }


class OpportunitySelection(unittest.TestCase):
    def test_registered_cases(self):
        s = scenarios()
        self.assertEqual([c["id"] for c in s["full"]["candidates"]],
                         ["headline", "specialist", "local-rerun", "failure-review", "budget-specialist"])
        self.assertEqual(s["full"]["decision"]["candidate_id"], "paired-replay")
        self.assertEqual(s["matrix_withdrawn"]["decision"]["status"], "defer")
        self.assertEqual(s["matrix_withdrawn"]["watch"], "suspended")
        self.assertEqual(s["reintroduced"]["watch"], "reopened")
        self.assertEqual(s["unchanged"]["watch"], "unchanged")
        self.assertEqual(s["proof"]["watch"], "new-mission")
        self.assertEqual([c["id"] for c in s["proof"]["candidates"]], ["verify-receipt"])
        self.assertFalse(s["proof"]["challengers"])
        for key in ("cash", "proof", "cutoff"):
            self.assertEqual(s[key]["decision"]["status"], "defer")
        self.assertNotIn("archive", s["cutoff"]["source_ids"])

    def test_cannot_select_bibliography_when_bytes_missing_or_changed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "runs.csv"
            with patch("frontier_study.MATRIX", path):
                self.assertEqual(investigate(default_mission())["decision"]["status"], "defer")
                path.write_text("unexpected contents")
                self.assertEqual(investigate(default_mission())["decision"]["status"], "defer")

    def test_matched_routes_are_explicit(self):
        mission = default_mission()
        mission["permissions"] += ["operate-model-fleet", "use-private-backlog"]
        report = investigate(mission)
        self.assertEqual(report["decision"]["status"], "compare")
        self.assertEqual(set(report["decision"]["eligible"]), {"local-rerun", "paired-replay"})

    def test_no_permissions_and_incomplete_goals(self):
        self.assertEqual(investigate(dict(default_mission(), permissions=[]))["decision"]["status"], "defer")
        for wrong in (dict(default_mission(), requires=[]), dict(default_mission(), as_of="2027-01-01"),
                      dict(default_mission(), permissions="compute-offline")):
            with self.assertRaises(ValueError):
                investigate(wrong)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["--record"]:
        results = scenarios()
        record = dict(results["full"])
        record["registered_comparisons"] = {
            key: {"decision": item["decision"], "watch": item["watch"], "evidence_sha256": item["evidence_sha256"],
                  "candidates": [o["id"] for o in item["candidates"] + item["challengers"]]}
            for key, item in results.items() if key != "full"
        }
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        unittest.main()
