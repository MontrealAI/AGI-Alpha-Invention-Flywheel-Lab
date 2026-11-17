"""Exercise the complete checkpoint boundary with a deliberately synthetic local adapter."""
import copy
import tempfile
import threading
import unittest
from unittest.mock import patch

from ignition.controller import Controller
from ignition.provider import ProviderUnavailable
from ignition.store import Conflict, StateError, Store, strict_json

from test_integrity_boundaries import body, proposal, DISCOVERY, CHALLENGE


class TestProvider:
    def __init__(self):
        self.name = "deterministic-test-fixture"
        self.receipts = []
        self.stages = []
        self.fail_once = None
        self.before = None

    def identity(self):
        return {"mode":"local","provider":"synthetic unit test","model":self.name}

    def propose(self, stage, packet):
        self.stages.append(stage)
        if self.before:
            self.before(stage,packet)
        if stage == self.fail_once:
            self.fail_once = None
            raise ProviderUnavailable("Synthetic interrupted generation")
        self.receipts.append({"stage":stage,"application_model_calls":0})
        return {"discover":DISCOVERY,"challenge":CHALLENGE,"construct":proposal()}[stage]


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(self.directory.name)
        self.model = TestProvider()
        self.ctrl = Controller(self.store,lambda:self.model)
        self.body = body()
        self.body["mission"]["authority"] = {"local_model":True}

    def test_recover_missing_stage_and_deduplicate_create_and_resume(self):
        self.model.fail_once = "challenge"
        rid,ver = self.ctrl.create(self.body)
        self.assertEqual(self.ctrl.create(self.body),(rid,ver))
        self.assertEqual(self.ctrl.advance(rid,ver)["status"],"blocked")
        restarted = Controller(Store(self.directory.name),lambda:self.model)
        self.assertEqual(restarted.advance(rid,ver)["status"],"verified")
        restarted.advance(rid,ver)
        self.assertEqual(self.model.stages,["discover","challenge","challenge","construct"])
        state = self.store.get(rid)
        self.assertEqual(state["attempts"],4)
        self.assertEqual(len(state["unsuccessful_calls"]),1)
        changed = copy.deepcopy(self.body)
        changed["mission"]["beneficiary"]="new recipient"
        with self.assertRaises(Conflict):
            self.ctrl.create(changed)
        with patch("ignition.controller.runtime_source",return_value="different"):
            self.assertEqual(self.ctrl.view(rid)["status"],"stale")
            with self.assertRaises(Conflict):
                self.ctrl.deliver(rid,ver)
        self.model.name = "other-model"
        with self.assertRaises(Conflict):
            self.ctrl.advance(rid,ver)

    def test_invalid_authority_no_model_effects_and_deadline(self):
        invalid = copy.deepcopy(self.body)
        invalid["mission"]["authority"]={"deploy":True}
        with self.assertRaises(StateError):
            self.ctrl.create(invalid)
        self.body["mission"]["time"]={"deadline":"2001-01-01T00:00:00Z"}
        rid,ver = self.ctrl.create(self.body)
        self.assertEqual(self.ctrl.advance(rid,ver)["status"],"blocked")
        self.assertEqual(self.model.stages,[])
        with self.assertRaises(StateError):
            strict_json('{"x":1,"x":2}')
        with self.assertRaises(StateError):
            strict_json('{"x":NaN}')

    def test_resource_budget_and_fresh_source_bindings(self):
        self.body["mission"]["resources"] = {"max_model_calls":1}
        rid,ver = self.ctrl.create(self.body)
        first = self.ctrl.advance(rid,ver)
        self.assertEqual(first["status"],"blocked")
        self.assertEqual(self.model.stages,["discover"])
        revised = copy.deepcopy(self.body)
        revised.update(version=1,request_id="amend-the-source")
        revised["sources"][0]["text"] += " Revised publisher statement."
        revised["mission"]["resources"] = {"max_model_calls":3}
        self.ctrl.create(revised,rid)
        with self.assertRaises(Conflict):
            self.ctrl.deliver(rid,1)
        self.assertEqual(self.ctrl.advance(rid,2)["status"],"verified")
        self.assertNotEqual(first["input_sha256"],self.store.get(rid)["input_sha256"])
        self.assertEqual([s["version"] for s in self.store.history(rid)],[1,2])

    def test_amendment_during_inference_and_prevention_of_stale_commit(self):
        rid,ver = self.ctrl.create(self.body)
        active,release = threading.Event(),threading.Event()
        errors = []
        def pause(stage,_):
            if stage == "discover":
                active.set()
                release.wait(4)
        self.model.before = pause
        def run():
            try:
                self.ctrl.advance(rid,ver)
            except Conflict as exc:
                errors.append(str(exc))
        worker = threading.Thread(target=run)
        worker.start()
        try:
            self.assertTrue(active.wait(3))
            with self.assertRaises(Conflict):
                self.ctrl.advance(rid,ver)
            new = copy.deepcopy(self.body)
            new.update(version=1,request_id="amended-while-running")
            new["mission"]["authority"]={}
            self.ctrl.create(new,rid)
            self.assertEqual(self.ctrl.advance(rid,2)["status"],"blocked")
        finally:
            release.set()
            worker.join(4)
        self.assertTrue(errors)
        self.assertIsNone(self.store.get(rid)["artifact"])

    def test_qualified_reuse_needs_rights_and_new_acceptance(self):
        self.body["mission"]["authority"]["allow_program_reuse"]=True
        rid,ver = self.ctrl.create(self.body)
        self.ctrl.advance(rid,ver)
        successor = copy.deepcopy(self.body)
        successor["request_id"]="fresh-successor"
        successor["mission"]["authority"]={}
        successor["mission"]["beneficiary"]="Second editorial team"
        nr,nv = self.ctrl.successor(rid,ver,successor,"Operator owns the migration mapping")
        new = self.store.get(nr)
        self.assertIsNotNone(new["inherited"]["program"])
        self.assertIsNone(new["contract"])
        self.assertIsNone(new["evaluation"])
        self.assertEqual(new["mission"]["authority"],{})
        self.assertEqual(self.ctrl.advance(nr,nv)["status"],"blocked")
        self.assertEqual(len(list(self.store.inventory())),2)
        self.body["request_id"]="reuse-forbidden"
        self.body["mission"]["authority"].pop("allow_program_reuse")
        source,ver = self.ctrl.create(self.body)
        self.ctrl.advance(source,ver)
        with self.assertRaises(StateError):
            self.ctrl.successor(source,ver,successor,"Attempt to reuse without original permission")
