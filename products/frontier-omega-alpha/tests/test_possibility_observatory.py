"""Adversarial, offline tests for the read-only Possibility Observatory."""
from contextlib import redirect_stderr
from copy import deepcopy
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from research.possibility_observatory import __main__ as atlas
from research.scheduled import SOURCES, SCHEMA as RELEASE_SCHEMA

T = "2026-11-23T12:00:00+00:00"
S = "a" * 64
F = "b" * 64

def observations(change=None, state="unchanged"):
    found = {}
    for key, (repo, _) in SOURCES.items():
        release = {"id": 200, "tag": "v2", "sha256": S, "published_at": T,
                   "retrieved_at": T,
                   "url": "https://api.github.com/repos/" + repo + "/releases/tags/v2"}
        rec = {"state": state if key == change else "unchanged", "observed": release}
        if rec["state"] == "published_version_changed":
            rec["preceding"] = {"id": 100, "tag": "v1", "sha256": F,
                                "published_at": T, "retrieved_at": T,
                                "url": "https://api.github.com/repos/" + repo + "/releases/tags/v1"}
        found[key] = rec
    return {"schema": RELEASE_SCHEMA, "sources": found}

def finding():
    return {"schema": atlas.FINDING_SCHEMA, "classification": "public-evidence",
            "status": "experiment-prepared", "production_authority": False,
            "finding_id": S, "profile": "lean-bitvector",
            "source_evidence": [{"url": "https://lean-lang.org/doc/reference/",
                                 "sha256": F, "version": "v4.36"}],
            "reception": {"authenticated_by": "github-rest",
                          "task_origin": "operator-declared, task authorship unverified"},
            "opportunity": {"purpose": "Check a versioned byte-order contract",
                            "existing_alternative": "Existing direct regression tests"}}

class ObservatoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.goals, _ = atlas.goals_at(atlas.HERE / "blocked-purposes.json")

    def write(self, name, data):
        p = self.root / name
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def test_registry_known_sources(self):
        self.assertEqual(len(self.goals), 5)
        self.assertEqual({g["source_keys"][0] for g in self.goals},
                         {"formal_verification", "local_models_and_quantization",
                          "serving_cost", "hardware_runtime", "scientific_computing"})

    def test_registry_rejects_unknown_key(self):
        obj = json.loads((atlas.HERE / "blocked-purposes.json").read_text())
        obj["goals"][0]["source_keys"] = ["finance"]
        with self.assertRaises(ValueError):
            atlas.goals_at(self.write("goals.json", obj))

    def test_registry_rejects_unregistered_fields(self):
        obj = json.loads((atlas.HERE / "blocked-purposes.json").read_text())
        obj["goals"][0]["auto_trade"] = True
        with self.assertRaises(ValueError):
            atlas.goals_at(self.write("goals.json", obj))

    def test_registry_rejects_duplicate_goal(self):
        obj = json.loads((atlas.HERE / "blocked-purposes.json").read_text())
        obj["goals"].append(deepcopy(obj["goals"][0]))
        with self.assertRaises(ValueError):
            atlas.goals_at(self.write("goals.json", obj))

    def test_checkpoint_accepts_release_schema(self):
        data, d = atlas.observations_at(self.write("src.json", observations()))
        self.assertEqual(len(data), 6)
        self.assertEqual(len(d), 64)

    def test_checkpoint_rejects_unexpected_source(self):
        obj = observations()
        obj["sources"]["other"] = obj["sources"].pop("serving_cost")
        with self.assertRaises(ValueError):
            atlas.observations_at(self.write("bad.json", obj))

    def test_checkpoint_rejects_mislabelled_upstream(self):
        obj = observations()
        obj["sources"]["serving_cost"]["observed"]["url"] = (
            "https://api.github.com/repos/someone-else/repo/releases/tags/v2")
        with self.assertRaises(ValueError):
            atlas.observations_at(self.write("bad.json", obj))

    def test_checkpoint_rejects_naked_claim_of_new_version(self):
        obj = observations("formal_verification", "published_version_changed")
        del obj["sources"]["formal_verification"]["preceding"]
        with self.assertRaises(ValueError):
            atlas.observations_at(self.write("bad.json", obj))

    def test_checkpoint_rejects_non_https(self):
        obj = observations()
        obj["sources"]["formal_verification"]["observed"]["url"] = "http://api.github.com/a"
        with self.assertRaises(ValueError):
            atlas.observations_at(self.write("bad.json", obj))

    def test_checkpoint_rejects_false_clock(self):
        obj = observations()
        obj["sources"]["formal_verification"]["observed"]["published_at"] = "2026-11-23T12:00:00"
        with self.assertRaises(ValueError):
            atlas.observations_at(self.write("bad.json", obj))

    def test_checkpoint_rejects_missing_release(self):
        obj = observations()
        obj["sources"]["formal_verification"]["observed"] = None
        with self.assertRaises(ValueError):
            atlas.observations_at(self.write("bad.json", obj))

    def test_changed_source_reopens_not_verifies(self):
        records, _ = atlas.observations_at(
            self.write("changed.json", observations("formal_verification", "published_version_changed")))
        result = atlas.build(records, self.goals, as_of="2026-11-23")
        entry = next(x for x in result["entries"] if x["id"] == "fixed-width-proof-maintenance")
        self.assertEqual(entry["status"], "reopen-for-review")
        self.assertEqual(entry["technical_advantage"], "unproven")
        self.assertEqual(entry["economic_advantage"], "unproven")
        self.assertIsNone(entry["missing_move_hypothesis"])
        self.assertEqual(len(result["experiment_queue"]), 1)
        self.assertFalse(result["experiment_queue"][0]["automatic_execution"])

    def test_metadata_change_is_not_new_capability(self):
        observed, _ = atlas.observations_at(
            self.write("meta.json", observations("formal_verification", "metadata_changed")))
        result = atlas.build(observed, self.goals)
        self.assertEqual(result["experiment_queue"], [])
        entry = next(e for e in result["entries"] if e["id"] == "fixed-width-proof-maintenance")
        self.assertEqual(entry["status"], "source-change-review")

    def test_first_observation_is_baseline_only(self):
        observed, _ = atlas.observations_at(
            self.write("first.json", observations("formal_verification", "first_observation")))
        result = atlas.build(observed, self.goals)
        self.assertEqual(result["experiment_queue"], [])
        self.assertTrue(any(x["status"] == "baseline-only" for x in result["entries"]))

    def test_unavailable_does_not_open_experiment(self):
        obj = observations()
        obj["sources"]["formal_verification"] = {"state": "unavailable", "observed": None}
        result = atlas.build(atlas.observations_at(self.write("missing.json", obj))[0], self.goals)
        self.assertEqual(result["experiment_queue"], [])
        self.assertTrue(any(x["status"] == "source-unavailable" for x in result["entries"]))

    def test_negative_findings_not_promoted(self):
        selected, _ = atlas.findings_at([self.write("f.json", finding())])
        result = atlas.build(observations()["sources"], self.goals, selected)
        self.assertEqual(result["reviewed_findings"][0]["status"], "experiment-prepared")
        self.assertIn("not independently established", result["reviewed_findings"][0]["economics"])

    def test_finding_rejects_non_github_provenance(self):
        f = finding()
        f["reception"]["authenticated_by"] = "local-only"
        with self.assertRaises(ValueError):
            atlas.findings_at([self.write("bad.json", f)])

    def test_finding_rejects_production_authority(self):
        f = finding()
        f["production_authority"] = True
        with self.assertRaises(ValueError):
            atlas.findings_at([self.write("bad.json", f)])

    def test_finding_rejects_private_classification(self):
        f = finding()
        f["classification"] = "internal"
        with self.assertRaises(ValueError):
            atlas.findings_at([self.write("bad.json", f)])

    def test_finding_rejects_embedded_task_identifier(self):
        f = finding()
        f["source_task_id"] = "private-task"
        with self.assertRaises(ValueError):
            atlas.findings_at([self.write("bad.json", f)])

    def test_finding_rejects_malformed_reception(self):
        f = finding()
        f["reception"] = ["not", "an", "object"]
        with self.assertRaises(ValueError):
            atlas.findings_at([self.write("bad.json", f)])

    def test_finding_rejects_malformed_opportunity(self):
        f = finding()
        f["opportunity"] = "private conversation"
        with self.assertRaises(ValueError):
            atlas.findings_at([self.write("bad.json", f)])

    def test_finding_rejects_duplicate_id(self):
        p1 = self.write("f1.json", finding())
        p2 = self.write("f2.json", finding())
        with self.assertRaises(ValueError):
            atlas.findings_at([p1, p2])

    def test_finding_rejects_symlink(self):
        real = self.write("real.json", finding())
        link = self.root / "link.json"
        link.symlink_to(real)
        with self.assertRaises(ValueError):
            atlas.findings_at([link])

    def test_audit_without_independent_set_is_unknown(self):
        result = atlas.build(observations()["sources"], self.goals)
        self.assertEqual(result["independent_coverage"]["state"], "not-assessed")
        self.assertIsNone(result["independent_coverage"]["missed"])

    def test_audit_counts_labeled_found_and_missed(self):
        events = {"schema": atlas.AUDIT_SCHEMA, "events": [
            {"id": "known-lean-release", "source_key": "formal_verification", "tag": "v2",
             "evidence_url": "https://lean-lang.org/release", "reviewer": "independent-human",
             "reviewed_at": T},
            {"id": "known-vllm-release", "source_key": "serving_cost", "tag": "v3",
             "evidence_url": "https://vllm.ai/release", "reviewer": "independent-human",
             "reviewed_at": T},
        ]}
        path = self.write("audit.json", events)
        result = atlas.build(observations("formal_verification", "published_version_changed")["sources"],
                             self.goals, audit=path)
        self.assertEqual(result["independent_coverage"]["reviewed"], 2)
        self.assertEqual(result["independent_coverage"]["found"], 1)
        self.assertEqual(result["independent_coverage"]["missed"], 1)
        self.assertEqual(result["independent_coverage"]["missed_ids"], ["known-vllm-release"])

    def test_audit_rejects_injected_source(self):
        events = {"schema": atlas.AUDIT_SCHEMA, "events": [
            {"id": "other-source", "source_key": "arbitrary-url", "tag": "v1",
             "evidence_url": "https://example.com", "reviewer": "auditor", "reviewed_at": T}]}
        with self.assertRaises(ValueError):
            atlas.reviewed_audit(self.write("audit.json", events), [])

    def test_render_bilingual_and_scope(self):
        report = atlas.build(observations()["sources"], self.goals)
        self.assertIn("Possibility Atlas", atlas.render(report, "en"))
        self.assertIn("Atlas des possibles", atlas.render(report, "fr"))
        self.assertIn("not establish economic", atlas.render(report, "en"))
        self.assertNotIn("private-task", atlas.render(report, "en"))

    def test_cli_writes_private_outputs_without_git_actions(self):
        input_path = self.write("obs.json", observations("formal_verification", "published_version_changed"))
        out = self.root / "research-result"
        with patch.object(sys, "argv", ["ob", "--observations", str(input_path), "--output", str(out),
                                        "--as-of", "2026-11-23"]):
            self.assertEqual(atlas.main(), 0)
        self.assertTrue((out / "atlas.json").exists())
        self.assertTrue((out / "atlas.en.md").exists())
        self.assertTrue((out / "atlas.fr.md").exists())
        self.assertTrue((out / "experiment-queue.json").exists())
        self.assertEqual(json.loads((out / "atlas.json").read_text())["production_authority"], False)
        self.assertEqual(atlas.build(*[observations()["sources"], self.goals])["alerts"][:13],
                         "Not generated")

    def test_cli_fails_closed_on_existing_output(self):
        input_path = self.write("obs.json", observations())
        out = self.root / "existing"
        out.mkdir()
        with patch.object(sys, "argv", ["ob", "--observations", str(input_path), "--output", str(out)]):
            with redirect_stderr(StringIO()):
                self.assertEqual(atlas.main(), 1)

if __name__ == "__main__":
    unittest.main()
