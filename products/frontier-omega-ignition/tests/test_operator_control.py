import copy
import tempfile
import unittest
from unittest.mock import patch

from ignition.controller import Controller
from ignition.store import Conflict, StateError, Store, canonical
from test_controller import TestProvider
from test_integrity_boundaries import body


class OperatorControlTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.store = Store(directory.name)
        self.provider = TestProvider()
        self.controller = Controller(self.store, lambda: self.provider)
        self.request = body()
        self.request["mission"]["authority"] = {"local_model": True, "allow_program_reuse": True}
        self.run, self.version = self.controller.create(self.request)

    def command(self, action, **kwargs):
        return self.controller.set_operation(self.run, self.version, action, **kwargs)["operation"]

    def test_auditable_pause_and_terminal_stop_across_restart(self):
        state = self.store.get(self.run)
        # Stand in for a pre-control revision with its original bytes.
        del state["operation"]
        with self.store.connection() as db:
            db.execute("UPDATE revisions SET data=? WHERE id=? AND version=?",
                       (canonical(state), self.run, self.version))
        self.assertEqual(self.controller.view(self.run)["operation"]["state"], "active")
        self.assertEqual(self.command("pause", reason="Check the source", expected_sequence=0)["sequence"], 1)
        self.assertEqual(self.command("pause")["sequence"], 1)
        self.assertEqual(list(self.store.inventory())[0]["operation_state"], "paused")
        with self.assertRaises(Conflict):
            self.command("resume", expected_sequence=0)
        with self.assertRaises(StateError):
            self.command("resume", expected_sequence=True)
        with self.assertRaises(Conflict):
            self.controller.advance(self.run, self.version)
        self.assertEqual(self.provider.stages, [])
        self.controller = Controller(Store(self.store.root), lambda: self.provider)
        self.assertEqual(self.command("resume", expected_sequence=1)["state"], "active")
        self.assertEqual(self.controller.advance(self.run, self.version)["status"], "verified")
        self.assertEqual(self.command("stop", reason="End trial")["state"], "stopped")
        amendment = copy.deepcopy(self.request)
        amendment.update(version=self.version, request_id="separate-amendment")
        successor = dict(self.request, request_id="separate-successor")
        for action in (lambda: self.controller.create(amendment, self.run),
                       lambda: self.controller.successor(self.run, self.version, successor, "test-owned"),
                       lambda: self.controller.intervene(self.run, self.version, "approve", {}),
                       lambda: self.controller.deliver(self.run, self.version),
                       lambda: self.controller.deliver(self.run, self.version, {}, trial=True),
                       lambda: self.command("resume")):
            with self.assertRaises(Conflict):
                action()
        control = self.store.history(self.run)[0]["operation"]
        self.assertEqual([row["action"] for row in control["history"]], ["pause", "resume", "stop"])
        self.assertEqual(control["history"][0]["reason"], "Check the source")
        self.assertEqual(len(list(self.store.inventory())), 1)

    def test_paused_inflight_call_is_accounted_and_reused_after_restart(self):
        def pause_during_discovery(stage, _):
            if stage == "discover":
                self.command("pause")

        self.provider.before = pause_during_discovery
        with self.assertRaises(Conflict):
            self.controller.advance(self.run, self.version)
        paused = self.store.get(self.run)
        self.assertEqual(paused["operation"]["state"], "paused")
        self.assertEqual(paused["attempts"], 1)
        self.assertEqual([v["stage"] for v in paused["calls"].values()], ["discover"])
        self.assertIsNone(paused["research"])
        self.controller = Controller(Store(self.store.root), lambda: self.provider)
        self.command("resume")
        self.assertEqual(self.controller.advance(self.run, self.version)["status"], "verified")
        self.assertEqual(self.provider.stages, ["discover", "challenge", "construct"])

    def test_pause_resume_fences_worker_and_does_not_release_racing_export(self):
        stale = self.store.get(self.run)
        self.command("pause")
        self.command("resume")
        with self.assertRaises(Conflict):
            self.store.save(stale)
        self.controller.advance(self.run, self.version)

        def finish_after_stop(*_):
            self.command("stop")
            return b"in-flight output"

        with patch("ignition.delivery.export_bundle", side_effect=finish_after_stop):
            with self.assertRaises(Conflict):
                self.controller.deliver(self.run, self.version)
        self.assertEqual(self.controller.view(self.run)["operation"]["state"], "stopped")
