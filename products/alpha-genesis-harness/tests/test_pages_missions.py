import http.client
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from threading import Event, Thread
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.pages_missions import PAGES_ORIGIN, PREFIX, PagesMissions
from bridge.server import HarnessServer


class Workflows:
    """Deterministic transport fixture. Engine and model evidence are tested separately."""

    def __init__(self):
        self.states = {}
        self.inputs = {}
        self.starts = 0

    def submit(self, spec, identity):
        self.inputs.setdefault(identity, spec)
        scope = {"local_only": True, "roles": {"builder": {key: spec[key] for key in ("provider", "model")}},
                 "tool_permissions": ["write_document"], "max_operations": 10_000,
                 "max_iterations": spec["max_turns"], "max_actions": spec["max_actions"],
                 "max_output_tokens": spec["max_output_tokens"]}
        return self.states.setdefault(identity, {"id": identity, "objective": spec["ambition"],
                                                  "language": spec["language"], "status": "ready", "events": [],
                                                  "spec": scope, "expires_at": spec["expires_at"]})

    def start(self, ident):
        self.starts += 1
        return self.change(ident, "running")

    def revise(self, prior, spec, identity):
        first = self.get(prior)
        revision = self.submit(spec, identity)
        revision.update(parent_run_id=prior, original_ambition=first.get("original_ambition", first["objective"]))
        return revision

    def get(self, ident):
        return self.states[ident]

    def list(self):
        return {"runs": list(self.states.values())}

    def pause(self, ident):
        return self.change(ident, "paused")

    def resume(self, ident):
        return self.change(ident, "running")

    def cancel(self, ident):
        return self.change(ident, "cancelled")

    def change(self, ident, status):
        view = self.get(ident)
        view["status"] = status
        return view

    def export(self, ident):
        return {"state": self.get(ident), "files": {}}

    def import_archive(self, archive, spec):
        ident = "wf_" + uuid4().hex[:24]
        self.submit(spec, ident)
        return self.change(ident, "paused")

    def close(self):
        pass


class Profiles:
    """Controlled model-selection fixture for the authentication transport tests."""

    def __init__(self):
        self.selection = None
        self.started = Event()
        self.unblock = None

    def current(self):
        return self.selection

    def status(self):
        return {"selection": self.selection}

    def discover(self, body, *, admit=lambda: None):
        admit()
        if body != {"consent": True}:
            raise ValueError("Discovery requires opt-in.")
        return {"candidates": [{"id": "approved", "model": "verified-model", "label": "Detected runtime"}]}

    def connect(self, body, *, admit):
        admit()
        self.started.set()
        if self.unblock is not None:
            self.unblock.wait(3)
        admit()
        self.selection = {"provider": "endpoint-bound-role", "model": "verified-model",
                          "ready": True, "max_output_tokens": 512}
        return self.status()


class PagesMissionTests(unittest.TestCase):
    def setUp(self):
        self.service = Workflows()
        self.server = HarnessServer(("127.0.0.1", 0))
        self.now = datetime(2026, 11, 24, 21, tzinfo=timezone.utc)
        self.codes = []
        self.server.pages_missions = PagesMissions(
            self.service, role={"provider": "local", "model": "author-fixture"}, lease_minutes=3,
            clock=lambda: self.now, announce=self.codes.append,
        )
        self.thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def send(self, operation, body=None, *, token=None, origin=PAGES_ORIGIN, command=None, verb="POST", other=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        headers = {"Content-Type": "application/json"}
        if origin is not None:
            headers["Origin"] = origin
        if token is not None:
            headers["X-Frontier-Session"] = token
        if command is not None:
            headers["X-Frontier-Command"] = command if "." in command else self.command_scope + "." + command
        if other:
            headers.update(other)
        path = operation if operation.startswith("/") else PREFIX + operation
        connection.request(verb, path, None if verb == "OPTIONS" else json.dumps(body or {}), headers=headers)
        response = connection.getresponse()
        raw = response.read()
        outcome = (response.status, dict(response.getheaders()), json.loads(raw) if raw else None)
        connection.close()
        return outcome

    def pair(self):
        status, _, result = self.send("pair", {"code": self.codes[-1]})
        self.assertEqual(status, 200)
        self.command_scope = result["command_scope"]
        return result["session"]

    def test_native_pairing_needs_private_consent_and_redeems_only_for_its_tab(self):
        path = "/api/frontier-intelligence/pair-approve"
        proof = "1" * 64
        body = {"proof_sha256": hashlib.sha256(proof.encode()).hexdigest(), "consent": True}
        native = {"X-Harness-Token": self.server.token}
        self.assertEqual(self.send(path, body, origin=None)[0], 403)
        self.assertEqual(self.send(path, body, other=native)[0], 403)
        self.assertEqual(self.send("pair-approve", body)[0], 403)
        self.assertEqual(self.send(path, {**body, "consent": False}, origin=None, other=native)[0], 403)
        old_manual = self.codes[-1]
        approved = self.send(path, body, origin=None, other=native)
        self.assertEqual(approved[0], 200)
        grant = approved[2]["approval"]
        self.assertNotEqual(grant, old_manual)
        self.assertEqual(self.send("pair", {"approval": grant, "proof": "2" * 64})[0], 403)
        self.assertEqual(self.send("pair", {"approval": grant, "proof": proof}, origin="https://unrelated.example")[0], 403)
        self.assertEqual(self.send("list")[0], 403)
        paired = self.send("pair", {"approval": grant, "proof": proof})
        self.assertEqual(paired[0], 200)
        self.assertEqual(self.service.starts, 0)
        self.assertEqual(self.send("pair", {"approval": grant, "proof": proof})[0], 403)
        self.assertEqual(self.send("pair", {"code": old_manual})[0], 403)
        token = self.pair()
        self.assertEqual(self.send("list", token=paired[2]["session"])[0], 403)
        self.assertEqual(self.send("list", token=token)[0], 200)

    def test_native_pairing_grant_expires_and_release_revokes_it(self):
        token = self.pair()
        path = "/api/frontier-intelligence/pair-approve"
        proof = "3" * 64
        body = {"proof_sha256": hashlib.sha256(proof.encode()).hexdigest(), "consent": True}
        native = {"X-Harness-Token": self.server.token}
        approved = self.send(path, body, origin=None, other=native)[2]["approval"]
        self.now += timedelta(minutes=1)
        self.assertEqual(self.send("pair", {"approval": approved, "proof": proof})[0], 403)
        approved = self.send(path, body, origin=None, other=native)[2]["approval"]
        self.assertEqual(self.send("release", token=token)[0], 200)
        self.assertEqual(self.send("pair", {"approval": approved, "proof": proof})[0], 403)

    def test_connection_page_allows_only_exact_top_level_navigation_from_pages(self):
        navigation = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document"}
        for path, headers, expected in (
            ("/frontier-connect?lang=fr", navigation, 200),
            ("/frontier-connect?lang=fr", {**navigation, "Sec-Fetch-Dest": "iframe"}, 403),
            ("/frontier-connect?lang=fr", {**navigation, "Origin": PAGES_ORIGIN}, 403),
            ("/frontier-connect?lang=fr&approval=extra", navigation, 403),
        ):
            with self.subTest(path=path, headers=headers):
                connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
                try:
                    connection.request("GET", path, headers=headers)
                    response = connection.getresponse()
                    self.assertEqual(response.status, expected)
                    if expected == 200:
                        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
                        self.assertIn('Jumeler le compagnon FRONTIER Ω', response.read().decode())
                        self.assertNotIn('Access-Control-Allow-Origin', response.headers)
                finally:
                    connection.close()

    def enable_discovery(self, *, evidence_input=None):
        profiles = Profiles()
        self.server.pages_missions = PagesMissions(
            self.service, intelligence=profiles, evidence_input=evidence_input,
            lease_minutes=3, clock=lambda: self.now, announce=self.codes.append,
        )
        return profiles

    def test_discovery_starts_only_the_exact_paired_operator_mission(self):
        goal = {"ambition": "  Exploiter ces données.\n", "language": "fr"}
        bound = {"approved_tables": {"data": {"entries": [{"n": 42}]}}}
        self.enable_discovery(evidence_input={
            "schema": "frontier/local-mission-input-v1", **goal, "requirements": bound,
        })
        self.assertEqual(self.send("intelligence-discover", {"consent": True})[0], 403)
        token = self.pair()
        status, _, error = self.send("submit", goal, token=token, command=str(uuid4()))
        self.assertEqual((status, error["error"]["code"]), (409, "MISSION_INTELLIGENCE_REQUIRED"))
        self.assertEqual(self.service.starts, 0)
        found = self.send("intelligence-discover", {"consent": True}, token=token)[2]
        self.assertEqual(found["candidates"][0]["model"], "verified-model")
        selection = self.send("intelligence-connect", {"id": "approved", "consent": True}, token=token)[2]
        self.assertEqual(selection["scope"]["max_output_tokens"], 512)
        status, _, run = self.send("submit", goal, token=token, command=str(uuid4()))
        self.assertEqual((status, run["ambition"]), (200, goal["ambition"]))
        self.assertEqual(self.service.inputs[run["id"]]["requirements"], bound)
        self.assertEqual(self.send("intelligence-connect", {"id": "approved", "consent": True}, token=token)[2]["error"]["code"],
                         "MISSION_ACTIVE")
        self.assertEqual(self.send("submit", {**goal, "requirements": bound}, token=token, command=str(uuid4()))[0], 400)
        _, _, changed = self.send("submit", {**goal, "ambition": goal["ambition"].strip()}, token=token, command=str(uuid4()))
        self.assertNotIn("requirements", self.service.inputs[changed["id"]])

    def test_new_pairing_revokes_an_inflight_selection(self):
        profiles = self.enable_discovery()
        profiles.unblock = Event()
        token = self.pair()
        results = []
        worker = Thread(target=lambda: results.append(self.send("intelligence-connect", {"id": "approved"}, token=token)))
        worker.start()
        try:
            self.assertTrue(profiles.started.wait(2))
            new_token = self.pair()
        finally:
            profiles.unblock.set()
            worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0][0], 403)
        self.assertIsNone(self.send("intelligence-status", token=new_token)[2]["selection"])

    def test_import_rebinds_only_the_exact_operator_manifest(self):
        goal = {"ambition": "Exploiter les données approuvées.", "language": "fr"}
        trusted = {"approved_tables": {"current": {"entries": [{"n": 42}]}}}
        pages = PagesMissions(self.service, role={"provider": "local", "model": "author-fixture"},
                              evidence_input={"schema": "frontier/local-mission-input-v1", **goal,
                                              "requirements": trusted, "tools": ["run_table"]},
                              clock=lambda: self.now, announce=self.codes.append)
        archive = {"state": {"spec": {"objective": goal["ambition"], "mission": {
            "language": "fr", "requirements": {"approved_tables": {"obsolete": {"entries": [{"n": 1}]}}},
        }}}}
        matching = pages.import_local(archive)
        self.assertEqual(matching["status"], "paused")
        self.assertEqual(self.service.inputs[matching["id"]]["requirements"], trusted)
        self.assertEqual(self.service.inputs[matching["id"]]["tools"], ["run_table"])
        archive["state"]["spec"]["mission"]["language"] = "en"
        other = pages.import_local(archive)
        self.assertNotIn("requirements", self.service.inputs[other["id"]])
        self.assertNotIn("tools", self.service.inputs[other["id"]])

    def test_local_pairing_guide_is_single_use_and_cross_origin_denied(self):
        url = self.server.create_pairing_guide(self.codes[-1])
        path = url.removeprefix(self.server.origin)

        def visit(headers):
            connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
            try:
                connection.request("GET", path, headers=headers)
                response = connection.getresponse()
                return response.status, response.getheader("Referrer-Policy"), response.read()
            finally:
                connection.close()

        self.assertEqual(visit({"Origin": "https://example.org"})[0], 403)
        status, policy, raw = visit({})
        self.assertEqual((status, policy), (200, "no-referrer"))
        self.assertIn(self.codes[-1].encode(), raw)
        self.assertEqual(visit({})[0], 404)

    def test_exact_origin_preflight_does_not_open_native_routes(self):
        headers = {"Access-Control-Request-Method": "POST",
                   "Access-Control-Request-Headers": "content-type,x-frontier-session,x-frontier-command"}
        status, returned, _ = self.send("submit", verb="OPTIONS", other=headers)
        self.assertEqual(status, 204)
        self.assertEqual(returned["Access-Control-Allow-Origin"], PAGES_ORIGIN)
        self.assertNotIn("Access-Control-Allow-Credentials", returned)
        for origin in (None, "null", "https://example.org", PAGES_ORIGIN + ".example.org"):
            with self.subTest(origin=origin):
                status, returned, _ = self.send("submit", origin=origin, verb="OPTIONS", other=headers)
                self.assertEqual(status, 403)
                self.assertNotIn("Access-Control-Allow-Origin", returned)
        self.assertEqual(self.send("submit", verb="OPTIONS", other={**headers, "Host": "localhost"})[0], 403)
        self.assertEqual(self.send("submit", verb="OPTIONS", other={**headers,
            "Access-Control-Request-Headers": "x-harness-token"})[0], 403)
        self.assertEqual(self.send("/api/generate", verb="OPTIONS", other=headers)[0], 403)

    def test_credentials_and_command_ids_cannot_be_replayed_to_create_extra_work(self):
        code = self.codes[-1]
        token = self.pair()
        self.assertEqual(self.send("pair", {"code": code})[0], 403)
        self.assertEqual(self.send("list")[0], 403)
        goal = {"ambition": "  Vérifier exactement l’entrée.\n", "language": "fr"}
        command = str(uuid4())
        status, _, first = self.send("submit", goal, token=token, command=command)
        self.assertEqual(status, 200)
        self.assertEqual(first["ambition"], goal["ambition"])
        self.assertEqual(self.send("submit", goal, token=token, command=command)[2]["id"], first["id"])
        self.assertEqual(self.service.starts, 1)
        self.assertEqual(self.send("submit", {**goal, "ambition": "Changed"}, token=token, command=command)[0], 409)
        self.assertEqual(self.send("submit", {**goal, "provider": "other"}, token=token, command=str(uuid4()))[0], 400)
        self.assertNotIn("scope", self.send("get", {"id": first["id"]}, token=token)[2])
        changed = {**goal, "ambition": "Réviser le calcul.", "previous": first["id"]}
        _, _, revision = self.send("submit", changed, token=token, command=str(uuid4()))
        self.assertEqual(revision["ambition"], changed["ambition"])
        self.assertEqual(revision["original_ambition"], goal["ambition"])
        self.assertEqual(revision["parent_run_id"], first["id"])

    def test_session_rotation_recovery_cancel_and_expiry(self):
        token = self.pair()
        old_scope = self.command_scope
        _, _, run = self.send("submit", {"ambition": "Exact task", "language": "en"}, token=token, command=str(uuid4()))
        current = self.pair()
        self.assertEqual(self.send("list", token=token)[0], 403)
        self.assertEqual(self.send("list", token=current)[2]["missions"][0]["id"], run["id"])
        ident = {"id": run["id"]}
        self.assertEqual(self.send("pause", ident, token=current, command=str(uuid4()))[2]["status"], "paused")
        self.assertEqual(self.send("resume", ident, token=current, command=str(uuid4()))[2]["status"], "running")
        self.assertEqual(self.send("disconnect", token=current, command=str(uuid4()))[0], 200)
        self.assertEqual(self.service.get(run["id"])["status"], "paused")
        self.assertEqual(self.send("get", ident, token=current)[0], 403)
        current = self.pair()
        self.assertEqual(self.send("resume", ident, token=current, command=old_scope + "." + str(uuid4()))[0], 403)
        self.assertEqual(self.send("release", token=current)[0], 200)
        self.assertEqual(self.service.get(run["id"])["status"], "paused")
        self.assertEqual(self.send("get", ident, token=current)[0], 403)
        current = self.pair()
        self.assertEqual(self.send("cancel", ident, token=current, command=str(uuid4()))[2]["status"], "cancelled")
        self.now += timedelta(minutes=4)
        self.assertEqual(self.send("list", token=current)[2]["error"]["code"], "MISSION_LEASE_EXPIRED")

    def test_recovery_requires_current_model_tool_budget_and_lifetime_scope(self):
        token = self.pair()
        _, _, earlier = self.send("submit", {"ambition": "Prior work", "language": "en"},
                                  token=token, command=str(uuid4()))
        ident = {"id": earlier["id"]}
        stored = self.service.get(earlier["id"])
        stored["status"] = "paused"
        mismatches = {"local_only": False, "roles": {"builder": {"provider": "old", "model": "old"}},
                      "tool_permissions": ["retrieve_source"], "max_iterations": 100,
                      "max_actions": 50, "max_output_tokens": 16384, "max_operations": 100_000}
        for key, broadened in mismatches.items():
            with self.subTest(checked=key):
                original = stored["spec"].copy()
                stored["spec"].update({key: broadened})
                self.assertEqual(self.send("resume", ident, token=token, command=str(uuid4()))[2]["error"]["code"],
                                 "MISSION_FRESH_SCOPE")
                stored["spec"] = original
        stored["expires_at"] = (self.now + timedelta(minutes=4)).isoformat()
        self.assertEqual(self.send("resume", ident, token=token, command=str(uuid4()))[0], 403)
        self.assertEqual(stored["status"], "paused")
        self.assertEqual(self.send("get", ident, token=token)[2]["ambition"], "Prior work")
        fresh = {"ambition": "Prior work", "language": "en", "previous": earlier["id"]}
        _, _, revision = self.send("submit", fresh, token=token, command=str(uuid4()))
        self.assertNotEqual(revision["id"], earlier["id"])
        self.assertEqual(revision["status"], "running")
        self.assertEqual(revision["parent_run_id"], earlier["id"])


if __name__ == "__main__":
    unittest.main()
