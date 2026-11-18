"""Integration checks against an isolated hosted HTTP backend with synthetic credentials."""
import concurrent.futures
import contextlib
import http.client
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from ignition.hosted import COOKIE, HostedService, model_ready
from ignition.hosted_auth import Access, DAILY_ADMISSIONS, INVITE_TTL, SESSION_TTL
from ignition.hosted_backup import snapshot
from ignition.store import StateError, PRODUCT, Store


class HostedStudio(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.origin = "https://studio.example.test"
        self.auth = Access(self.root / "state", "staging")
        self.server = HostedService(self.auth, self.origin, 0, ready_probe=lambda: False)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_service)

    def close_service(self):
        if self.server:
            self.server.shutdown()
            self.thread.join()
            self.server.server_close()
            self.server = None

    def call(self, route, body=None, cookie="", **headers):
        defaults = {"Host": "studio.example.test", "Origin": self.origin, "Content-Type": "application/json",
                    "X-Ignition-Request": "1"}
        if cookie:
            defaults["Cookie"] = cookie
        with contextlib.closing(http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=8)) as conn:
            conn.request("GET" if body is None else "POST", route,
                         body=None if body is None else json.dumps(body).encode(), headers={**defaults, **headers})
            res = conn.getresponse()
            content = res.read()
            parsed = json.loads(content) if res.getheader("Content-Type","").startswith("application/json") else content
            return res.status, parsed, res.getheader("Set-Cookie")

    def signin(self, tenant):
        code = self.auth.issue(tenant)
        status, info, header = self.call("/api/session", {"invite": code})
        self.assertEqual((status, info["authenticated"], info["environment"]), (200, True, "staging"))
        self.assertTrue(all(s in header for s in ["HttpOnly", "Secure", "Path=/", "SameSite=Strict"]))
        self.assertEqual(self.call("/api/session", {"invite": code})[0], 401)
        return header.split(";")[0]

    def test_tenant_isolation_persistence_and_cost_ceiling(self):
        a, b = self.signin("lab-a"), self.signin("lab-b")
        body = json.loads((PRODUCT / "examples" / "migration.json").read_bytes())
        submission = {"request_id": "same-request-as-tab", "mission": body["mission"], "sources": body["sources"]}
        # This mission explicitly selects the bounded local compiler. No model is simulated.
        submission["mission"]["resources"].update(execution_strategy="direct", direct_method="specialist", max_model_calls=0)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as callers:
            responses = list(callers.map(lambda _: self.call("/api/runs", submission, a), range(3)))
        self.assertEqual({r[0] for r in responses}, {202})
        self.assertEqual(len({r[1]["id"] for r in responses}), 1)
        rid = responses[0][1]["id"]
        for route in ["", "/history", "/bundle?version=1", "/evidence?version=1", "/commercial?version=1"]:
            self.assertEqual(self.call(f"/api/runs/{rid}"+route, cookie=b)[0], 404)
        self.assertEqual(self.call("/api/runs", cookie=b)[1]["runs"], [])
        self.assertEqual(self.call("/api/runs", cookie=a)[1]["runs"][0]["id"], rid)
        submission["mission"]["resources"]["max_model_calls"] = 9
        self.assertEqual(self.call("/api/runs", submission, a)[0], 400)
        self.assertEqual(self.call("/api/logout", {}, a)[0], 200)
        self.assertEqual(self.call("/api/runs", cookie=a)[0], 401)
        new_session = self.signin("lab-a")
        self.assertEqual(self.call("/api/runs", cookie=new_session)[1]["runs"][0]["id"], rid)

    def test_authentication_boundaries_and_readiness(self):
        self.assertEqual(self.call("/api/runs")[0], 401)
        self.assertEqual(self.call("/api/status")[0], 401)
        self.assertEqual(self.call("/api/examples")[0], 401)
        self.assertEqual(self.call("/api/session")[1], {"authenticated": False,"environment":"staging"})
        self.assertEqual(self.call("/healthz")[0], 200)
        self.assertEqual(self.call("/readyz")[0], 503)
        self.assertEqual(self.call("/index.html")[0], 404)
        token = self.auth.issue("owner")
        self.assertEqual(self.call("/api/session", {"invite":token}, Origin="https://different.example.test")[0], 403)
        self.assertEqual(self.call("/api/session", {"invite":token}, Host="other.example.test")[0], 403)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as callers:
            outcomes = list(callers.map(lambda _: self.call("/api/session", {"invite":token}), range(2)))
        self.assertEqual(sorted(x[0] for x in outcomes), [200,401])
        session = next(x[2].split(";")[0] for x in outcomes if x[0] == 200)
        self.auth.revoke("owner")
        self.assertEqual(self.call("/api/session", cookie=session)[1]["authenticated"], False)

    def test_session_and_invite_expiry(self):
        with patch("ignition.hosted_auth.time.time", return_value=1000):
            code = self.auth.issue("x")
            session = self.auth.exchange(code)
            unused = self.auth.issue("x")
        with patch("ignition.hosted_auth.time.time", return_value=1000+INVITE_TTL):
            self.assertIsNone(self.auth.exchange(unused))
        with patch("ignition.hosted_auth.time.time", return_value=1000+SESSION_TTL):
            self.assertIsNone(self.auth.principal(session))
        with self.assertRaises(StateError):
            Access(self.auth.root, "production")

    def test_daily_quota_counts_committed_revisions_and_survives_cross_day_replays(self):
        cookie = self.signin("quota")
        def create(key, **extra):
            return self.call("/api/runs", {"request_id": key, "mission": {"purpose": "Scope review"}, **extra}, cookie)

        with patch("ignition.store.timestamp", return_value="2026-01-01T23:59:59.000+00:00"):
            code, old, _ = create("earlier-day")
            self.assertEqual(code, 202)
        with patch("ignition.store.timestamp", return_value="2026-01-02T12:00:00.000+00:00"):
            self.assertEqual(create("invalid-scope", sources="missing list")[0], 400)
            amend_url = "/api/runs/" + old["id"] + "/amend"
            amendment = {"request_id": "valid-amendment", "mission": {"purpose": "Revised scope"}, "version": 1}
            self.assertEqual(self.call(amend_url, {**amendment, "version": 42}, cookie)[0], 409)
            self.assertEqual(self.call(amend_url, amendment, cookie)[1]["version"], 2)
            for i in range(DAILY_ADMISSIONS - 2):
                self.assertEqual(create(f"current-{i:03}")[0], 202)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as callers:
                responses = list(callers.map(create, ["last-slot-aa", "last-slot-bb"]))
            self.assertEqual(sorted(r[0] for r in responses), [202, 400])
            refused = next(r for r in responses if r[0] == 400)
            self.assertIn("Daily workspace admission limit", refused[1]["error"])
            self.assertEqual(self.call(amend_url, amendment, cookie)[1]["version"], 2)
        with patch("ignition.store.timestamp", return_value="2026-01-03T00:00:00.000+00:00"):
            # Yesterday's accepted intent is accessible without consuming today's capacity.
            self.assertEqual(create("current-000")[0], 202)
            for i in range(DAILY_ADMISSIONS):
                self.assertEqual(create(f"tomorrow-{i:03}")[0], 202)
            self.assertEqual(create("current-000")[0], 202)
            self.assertEqual(create("day-three-overflow")[0], 400)

    def test_stopped_backup_restore_and_corruption(self):
        code = self.auth.issue("team")
        session = self.auth.exchange(code)
        old_invite = self.auth.issue("team")
        store = Store(self.auth.workspaces / "team")
        with store.connection() as db:
            db.execute("CREATE TABLE user_marker (v)")
            db.execute("INSERT INTO user_marker VALUES ('retained')")
        backup = self.root / "backups" / "point"
        with self.assertRaises(StateError):
            snapshot(self.auth.root, backup, "staging")
        self.close_service()
        snapshot(self.auth.root, backup, "staging")
        restored = self.root / "restores" / "clean"
        snapshot(backup, restored, "staging", restore=True)
        access = Access(restored, "staging")
        self.assertIsNone(access.principal(session))
        self.assertIsNone(access.exchange(old_invite))
        with Store(access.workspaces / "team").connection() as db:
            self.assertEqual(db.execute("SELECT v FROM user_marker").fetchone()[0], "retained")
        with (backup / "access.sqlite3").open("ab") as f:
            f.write(b"changed")
        with self.assertRaises((StateError, sqlite3.Error)):
            snapshot(backup, self.root / "restores" / "reject", "staging", restore=True)

    def test_no_provider_is_not_ready(self):
        with patch.dict("os.environ", {"IGNITION_MODEL_PROVIDER": "unavailable"},clear=False):
            self.assertFalse(model_ready())


    def test_usable_private_results_and_distinct_commercial_record(self):
        from test_studio_dispatch import wait_for
        first, second = self.signin("alpha"), self.signin("beta")
        example = json.loads((PRODUCT / "examples/integrity.json").read_bytes())
        submission = {"request_id": "same-intent-per-workspace", "mission": example["mission"], "sources": example["sources"]}
        submission["mission"]["beneficiary"] = "private-beneficiary-for-access-check"
        submission["mission"]["resources"]["commercial_case"] = {
            "currency": "CAD", "unit": "package", "horizon": "one replay",
            "price": {"low": "350", "high": "350", "provenance": "assumption", "source": "unit test"},
        }
        submission["mission"]["resources"].update(execution_strategy="direct", direct_method="specialist", max_model_calls=0)
        status, created, _ = self.call("/api/runs", submission, first)
        self.assertEqual(status, 202)
        run = created["id"]
        prefix = "/api/runs/" + run
        wait_for(lambda: self.server.controller_for("alpha").store.get(run)["status"] == "verified")
        for suffix in ("/bundle?version=1", "/evidence?version=1", "/commercial?version=1"):
            with self.subTest(route=suffix):
                self.assertEqual(self.call(prefix + suffix, cookie=first)[0], 200)
                self.assertEqual(self.call(prefix + suffix)[0], 401)
        import hashlib
        bundle = self.call(prefix+"/bundle?version=1", cookie=first)[1]
        for language, heading in (("en", "PRIVATE OFFER DRAFT · UNSENT"), ("fr", "PROJET D’OFFRE PRIVÉ · NON ENVOYÉ")):
            offer_url = prefix + "/offer?version=1&lang=" + language
            code, document, _ = self.call(offer_url, cookie=first)
            self.assertEqual(code, 200)
            self.assertIn(heading.encode(), document)
            self.assertIn(b"CAD 350 / package", document)
            self.assertIn(hashlib.sha256(bundle).hexdigest().encode(), document)
            self.assertEqual(self.call(offer_url, cookie=second)[0], 404)
            self.assertEqual(self.call(offer_url)[0], 401)
        self.assertEqual(self.call(prefix+"/offer?version=2", cookie=first)[0], 409)
        operation = {"version":1,"sequence":0,"operation":"stop"}
        self.assertEqual(self.call(prefix + "/operation", operation, second)[0], 404)
        self.assertEqual(self.call(prefix, cookie=first)[1]["operation"]["state"], "active")
        commerce = self.call(prefix + "/commercial?version=1", cookie=first)[1]
        self.assertEqual((commerce["commercial_state"], commerce["settlement"], commerce["collected_revenue"]),
                         ("unassessed", "unverified", None))
        for page in ("/", "/demo", "/studio"):
            code, html, _ = self.call(page)
            self.assertEqual(code, 200)
            self.assertNotIn(submission["mission"]["beneficiary"].encode(), html)
            self.assertNotIn(run.encode(), html)
        second_status, new_run, _ = self.call("/api/runs", submission, second)
        self.assertEqual(second_status, 202)
        self.assertNotEqual(new_run["id"], run)

    def test_one_authorized_model_call_stops_at_worker_boundary(self):
        from ignition.controller import Controller
        from test_controller import TestProvider
        from test_integrity_boundaries import body
        from test_studio_dispatch import wait_for
        model = TestProvider()
        self.server.factory = lambda store: Controller(store, lambda: model)
        session = self.signin("bounded")
        submission = body()
        submission["mission"]["authority"] = {"local_model": True}
        submission["mission"]["resources"]["max_model_calls"] = 1
        code, created, _ = self.call("/api/runs", submission, session)
        self.assertEqual(code, 202)
        run = created["id"]
        wait_for(lambda: self.server.controller_for("bounded").store.get(run)["status"] == "blocked")
        self.assertEqual(model.stages, ["discover"])
        receipt = self.call(f"/api/runs/{run}/evidence?version=1", cookie=session)[1]
        self.assertEqual(receipt["attempts"], 1)
        self.assertIsNone(receipt["artifact"].get("sha256"))
        self.assertEqual(self.call(f"/api/runs/{run}/offer?version=1", cookie=session)[0], 409)
        control = f"/api/runs/{run}/operation"
        for sequence, operation in enumerate(("pause", "resume")):
            code, _, _ = self.call(control, {"version": 1, "sequence": sequence, "operation": operation}, session)
            self.assertEqual(code, 200)
        store = self.server.controller_for("bounded").store
        wait_for(lambda: store.get(run)["status"] == "blocked")
        self.assertEqual(self.call(f"/api/runs/{run}/resume", {"version": 1}, session)[0], 202)
        wait_for(lambda: store.get(run)["status"] == "blocked")
        self.assertEqual(store.get(run)["attempts"], 1)
        self.assertEqual(model.stages, ["discover"])

    def test_verified_program_requalifies_on_separate_rights_cleared_successor(self):
        from test_studio_dispatch import wait_for
        owner, other = self.signin("owner"), self.signin("other")
        def mission(key, value, *, allow_reuse=False, target="serial"):
            purpose = "Normalize the serial for collection " + key
            mapping = {"columns":[{"source":"raw", "target":target, "type":"text"}], "extra_fields":"reject"}
            case = {"name":"Fresh acceptance", "input":{"rows":[{"raw": value}]},
                    "expected":{"rows":[{target: value}]}}
            return {"request_id": key, "sources": [], "mission": {
                "purpose": purpose, "authority": {"allow_program_reuse":allow_reuse},
                "resources":{"execution_strategy":"direct", "direct_method":"specialist", "max_model_calls":0, "max_repairs":0},
                "construction_spec":{"purpose":purpose, "kind":"record_migration", "definition":mapping, "cases":[case]}}}

        code, stored, _ = self.call("/api/runs", mission("parent-serial", "A1", allow_reuse=True), owner)
        self.assertEqual(code, 202)
        run = stored["id"]
        db = self.server.controller_for("owner").store
        wait_for(lambda: db.get(run)["status"] == "verified")
        url = "/api/runs/" + run + "/successor"
        self.assertTrue(self.call(url + "?version=1", cookie=owner)[1]["eligible"])
        def submit(sample, cookie=owner):
            return self.call(url, {**sample, "version":1, "rights":"Owner authorizes reuse of the recorded conversion program only."}, cookie)
        fresh = mission("second-collection", "B27")
        self.assertEqual(submit(fresh, other)[0], 404)
        self.assertEqual(submit(mission("repeated-sample", "A1"))[0], 400)
        code, created, _ = submit(fresh)
        self.assertEqual(code, 202)
        child = created["id"]
        self.assertNotEqual(run, child)
        self.assertEqual(submit(fresh)[1]["id"], child)
        wait_for(lambda: db.get(child)["status"] == "verified")
        self.assertEqual(db.get(child)["artifact"]["program"], db.get(run)["artifact"]["program"])
        self.assertEqual(db.get(child)["construction_attempts"][0]["method"], "retained_program")
        self.assertEqual(db.get(child)["inherited"]["source_id"], run)
        # A grant made by the source is not inherited by a new revision.
        child_source = "/api/runs/" + child + "/successor"
        self.assertFalse(self.call(child_source+"?version=1", cookie=owner)[1]["eligible"])
        self.assertEqual(self.call(child_source,{**mission("no-grandchild", "C14"),"version":1, "rights":"new rights"},owner)[0],400)
        code, incompatible, _ = submit(mission("incompatible-output", "D93", target="new_field"))
        self.assertEqual(code, 202)
        wait_for(lambda: db.get(incompatible["id"])["status"] == "failed")
        self.assertEqual(db.get(run)["status"], "verified")
        self.assertEqual(self.call(f'/api/runs/{incompatible["id"]}/bundle?version=1', cookie=owner)[0],409)

    def test_sourced_blank_studio_mission_waits_for_new_confirmation_before_dispatch(self):
        from ignition.controller import Controller
        from test_controller import TestProvider
        from test_integrity_boundaries import body, confirmation, spec
        from test_studio_dispatch import wait_for
        class ResearchAdapter(TestProvider):
            def propose(self, stage, packet):
                if stage == "specification":
                    self.stages.append(stage)
                    return {"spec":spec([confirmation("Draft check","demo-first","demo-second")])}
                return super().propose(stage, packet)
        adapter = ResearchAdapter()
        self.server.factory = lambda store: Controller(store, lambda: adapter)
        cookie = self.signin("research")
        submission = body(explicit=False)
        submission["mission"]["authority"] = {"local_model":True, "public_sources":False}
        submission["mission"]["resources"]["max_model_calls"] = 4
        code, created, _ = self.call("/api/runs", submission, cookie)
        self.assertEqual(code, 202)
        run = created["id"]
        db = self.server.controller_for("research").store
        wait_for(lambda: db.get(run)["status"] == "awaiting_contract")
        card = self.call("/api/runs/"+run, cookie=cookie)[1]
        self.assertIsNone(card["artifact"])
        self.assertEqual(card["routing"]["route"],"research")
        self.assertEqual(card["research"]["decision"], "build")
        self.assertTrue(card["research"]["signals"])
        fresh = confirmation("Recipient confirmation", "fresh-12", "fresh-47")
        code, _, _ = self.call("/api/runs/"+run+"/approve", {
            "version":1, "contract_sha256":card["contract_sha256"], "confirmations":[fresh]},cookie)
        self.assertEqual(code, 202)
        wait_for(lambda: db.get(run)["status"] == "verified")
        self.assertEqual(adapter.stages,["discover","challenge","specification","construct"])
        self.assertEqual(self.call("/api/runs/"+run+"/bundle?version=1",cookie=cookie)[0],200)


if __name__ == "__main__":
    unittest.main()
