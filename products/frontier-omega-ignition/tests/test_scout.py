"""Publisher fixtures exercise the ordinary research controller without external model calls."""
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ignition import scout
from ignition.controller import Controller
from ignition.provider import ModelProvider
from ignition.store import Conflict, StateError, Store


class FixtureProvider(ModelProvider):
    def __init__(self):
        super().__init__()
        self.stages = []

    def identity(self):
        return {"mode": "local", "provider": "fixture", "model": "fixture"}

    def propose(self, stage, payload):
        self.stages.append(stage)
        if stage == "discover":
            return {"candidates": [], "favourite": None}
        if stage == "challenge":
            return {"decision": "defer", "selected": None, "challenger": None, "fit": [],
                    "reason": "The publisher announcement alone does not verify the proposed advantage."}
        raise AssertionError(stage)


class ScoutTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.model = FixtureProvider()
        self.controller = Controller(Store(self.directory.name), provider_factory=lambda: self.model)
        self.brief = json.loads((Path(__file__).resolve().parents[1] / "examples" / "scout.json").read_text())
        self.now = datetime.now(timezone.utc) - timedelta(seconds=3)
        self.published = (self.now - timedelta(days=1)).isoformat()
        self.retrieved = self.now.isoformat()
        self.tag = "v1"
        self.note = "Publisher release note."
        self.downloads = 1
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        self.assertTrue(url.startswith("https://api.github.com/repos/ggml-org/llama.cpp/"))
        origin = "https://github.com/ggml-org/llama.cpp/"
        if "/releases?" in url:
            rows = [{"tag_name": self.tag, "published_at": self.published, "body": self.note,
                     "html_url": origin + "releases/tag/" + self.tag, "downloads": self.downloads}]
        else:
            sha = "a" * 40
            rows = [{"sha": sha, "html_url": origin + "commit/" + sha,
                     "commit": {"committer": {"date": (self.now - timedelta(days=36)).isoformat()},
                                "message": "Prior snapshot."}}]
        raw = json.dumps(rows)
        return {"text": raw, "retrieved_at": self.retrieved, "sha256": hashlib.sha256(raw.encode()).hexdigest()}

    def poll(self, initial=False):
        return scout.poll(self.controller, self.brief, "lab", investigate_initial=initial,
                          fetch=self.fetch, clock=lambda: self.now)

    def test_source_change_drives_research_then_obeys_budget(self):
        self.brief["max_investigations"] = 1
        self.assertEqual(self.poll()["status"], "baseline_recorded")
        self.assertFalse(self.model.stages)
        self.tag = "v2"
        result = self.poll()
        self.assertEqual((result["status"], len(result["missions"])), ("investigation_registered", 1))
        child = self.controller.store.get(result["missions"][0]["mission_id"])
        self.assertFalse(child["mission"]["authority"]["public_sources"])
        self.assertEqual(child["mission"]["purpose"], self.brief["mission"]["purpose"])
        self.assertEqual(child["sources"][0]["version"], "v2")
        self.assertEqual(child["research"]["decision"], "defer")
        self.assertEqual(result["missions"][0]["model_attempts"], 2)
        self.downloads += 1
        self.now += timedelta(seconds=1)
        self.retrieved = self.now.isoformat()
        self.assertEqual(self.poll()["status"], "observed_unchanged")
        self.tag = "v3"
        self.assertEqual(self.poll()["status"], "budget_exhausted")
        self.assertEqual(self.model.stages, ["discover", "challenge"])

    def test_recovery_replays_frozen_snapshot_without_another_model_call(self):
        with patch.object(self.controller, "create", side_effect=RuntimeError("process interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.poll(initial=True)
        self.controller = Controller(Store(self.directory.name), provider_factory=lambda: self.model)
        self.now += timedelta(seconds=1)
        result = self.poll(initial=True)
        self.assertEqual(result["status"], "observed_unchanged")
        self.assertEqual(len(result["missions"]), 1)
        self.assertEqual(result["missions"][0]["decision"], "defer")
        self.assertEqual(result["investigations_reserved"], 1)
        self.assertEqual(self.poll()["missions"], [])
        self.assertEqual(self.model.stages, ["discover", "challenge"])

    def test_failed_feed_clock_and_authority(self):
        with patch.object(self, "fetch", side_effect=OSError("offline")):
            failed = self.poll()
        self.assertEqual(len(failed["failures"]), 2)
        self.assertEqual(failed["status"], "source_unavailable")
        self.assertEqual(self.poll()["status"], "baseline_recorded")
        self.now -= timedelta(seconds=1)
        before = len(self.calls)
        with self.assertRaises(Conflict):
            self.poll()
        for invalid in (dict(self.brief, feeds=["https://127.0.0.1"]), copy.deepcopy(self.brief)):
            if invalid["feeds"] == self.brief["feeds"]:
                invalid["mission"]["authority"]["assisted_model"] = True
            with self.assertRaises(StateError):
                scout.poll(self.controller, invalid, "lab", fetch=self.fetch)
        self.brief["max_investigations"] += 1
        with self.assertRaises(Conflict):
            self.poll()
        self.assertEqual(len(self.calls), before)
