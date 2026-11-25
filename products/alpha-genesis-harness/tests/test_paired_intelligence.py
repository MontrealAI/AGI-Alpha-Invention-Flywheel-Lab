# SPDX-License-Identifier: Apache-2.0
"""Fixture transport tests for paired mission scope and native API execution."""
import http.client
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread
from time import monotonic, sleep
import unittest
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import Runtime
from bridge.pages_missions import PAGES_ORIGIN, PREFIX
from bridge.server import HarnessServer


API = "/api/frontier-intelligence/"
AMBITION = "Build frontier AI LLM for Game Theory."
SECRET = "fixture-only-never-a-real-api-key"
MODEL = "fixture-strategic-model"
PROJECT = "proj_paired_fixture"
LOCAL_ENDPOINT = "http://127.0.0.1:47881/v1"
INSTRUMENT = {"tool": "construct_instrument", "name": "regret.json", "spec": {
    "inputs": ["deviate", "current"], "outputs": {"regret": {"op": "max", "args": [
        0, {"op": "sub", "args": [{"field": "deviate"}, {"field": "current"}]}]}}}}
COMPUTE = {"tool": "run_instrument", "name": "regret.json", "input": {"deviate": 7, "current": 4}}
PROPOSAL = {"summary": "Measure unilateral deviation regret, then record the actual result.",
            "actions": [INSTRUMENT, COMPUTE], "done": True}


class PairedIntelligenceTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.workspace = Path(folder.name) / "workspace"
        self.mission_calls = []
        self.local_calls = []
        self.probe_calls = 0
        self.mission_started = Event()
        self.block = None
        self.block_after = 0
        self.proposal = PROPOSAL
        self.local_reply = None
        self._launch()
        self.addCleanup(self._close)

    def _launch(self, *, local=False):
        self.codes = []
        self.config = {"local_only": True, "source_hosts": []}
        selection = {}
        if local:
            self.config["providers"] = {"local-fixture": {"kind": "openai", "base_url": LOCAL_ENDPOINT,
                "models": {MODEL: {"input_per_million": 0, "output_per_million": 0}}}}
            selection = {"provider": "local-fixture", "model": MODEL}
        self.server = HarnessServer(("127.0.0.1", 0), Runtime(self.config, sender=self.sender),
                                    config=self.config, workspace=self.workspace)
        self.server.enable_pages_missions(announce=self.codes.append, turns=4, output_tokens=512, **selection)
        self.worker = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01}, daemon=True)
        self.worker.start()
        self.pair()

    def _close(self):
        if self.block:
            self.block.set()
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.worker.join(3)
            self.server = None

    def sender(self, url, headers, body=None, timeout=None):
        if url == LOCAL_ENDPOINT + "/chat/completions":
            self.assertNotIn("Authorization", headers)
            self.local_calls.append(body)
            reply = self.local_reply(body) if self.local_reply else self.proposal
            return {"choices": [{"message": {"content": json.dumps(reply)}}],
                    "usage": {"prompt_tokens": 43, "completion_tokens": 24}}
        self.assertTrue(url.startswith("https://api.openai.com/v1/"))
        self.assertEqual(headers["Authorization"], "Bearer " + SECRET)
        self.assertEqual(headers["OpenAI-Project"], PROJECT)
        if url.endswith("/models"):
            return {"data": [{"id": MODEL}]}
        self.assertEqual(url, "https://api.openai.com/v1/responses")
        prompt = body["input"][0]["content"]
        self.assertNotIn(SECRET, prompt)
        self.assertIs(body["store"], False)
        if prompt.startswith("FRONTIER connection test"):
            self.probe_calls += 1
            text = prompt.split()[-1]
        else:
            self.mission_calls.append(body)
            self.mission_started.set()
            if self.block and len(self.mission_calls) > self.block_after:
                self.assertTrue(self.block.wait(4))
            text = json.dumps(self.proposal, ensure_ascii=False)
        return {"status": "completed", "model": MODEL, "usage": {"input_tokens": 43, "output_tokens": 24},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}]}

    def post(self, path, body, headers=None):
        raw = json.dumps(body, ensure_ascii=False).encode()
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=4)
        try:
            conn.request("POST", path, raw, {"Content-Type": "application/json", **(headers or {})})
            response = conn.getresponse()
            result = json.loads(response.read())
            return response.status, result
        finally:
            conn.close()

    def paired(self, operation, body=None, *, command=False, session=True):
        headers = {"Origin": PAGES_ORIGIN}
        if session:
            headers["X-Frontier-Session"] = self.session
        if command:
            identity = str(uuid4()) if command is True else command
            headers["X-Frontier-Command"] = f"{self.command_scope}.{identity}"
        return self.post(PREFIX + operation, body or {}, headers)

    def native(self, operation, body=None):
        return self.post(API + operation, body or {}, {"X-Harness-Token": self.server.token,
                                                       "Origin": self.server.origin})

    def pair(self):
        result = self.expect(self.paired("pair", {"code": self.codes[-1]}, session=False))
        self.session, self.command_scope = result["session"], result["command_scope"]
        return result

    def expect(self, response, status=200, code=None):
        self.assertEqual(response[0], status, response[1])
        if code:
            self.assertEqual(response[1]["error"]["code"], code)
        return response[1]

    def profile(self, budget="1"):
        setup = self.expect(self.native("discover", {"provider": "openai", "credential": SECRET,
                                                     "organization": "", "project": PROJECT, "consent": True}))
        profile = self.expect(self.native("verify", {"setup_id": setup["setup_id"], "model": MODEL,
            "input_rate": "1", "output_rate": "1", "budget_usd": budget, "max_output_tokens": 256,
            "max_turns": 3, "expiry_hours": 2, "consent": True}))["profile"]
        self.assertNotIn(SECRET, json.dumps(profile))
        return profile["id"]

    def prepare(self, ambition=AMBITION, language="en", previous=None, command=True):
        body = {"ambition": ambition, "language": language}
        if previous:
            body["previous"] = previous
        return self.expect(self.paired("prepare-intelligence", body, command=command))

    def checked_review(self, stage, profile):
        reply = self.expect(self.native("mission-review", {"ticket": stage["setup_ticket"], "profile": profile}))
        self.assertEqual(reply["scope"]["max_turns"], 3)
        self.assertEqual(reply["scope"]["max_output_tokens"], 256)
        self.assertEqual(reply["profile"]["model"], MODEL)
        return {"ticket": stage["setup_ticket"], "profile": profile, "revision": reply["revision"], "consent": True}

    def wait_for_stop(self, ident):
        until = monotonic() + 4
        while monotonic() < until:
            result = self.expect(self.paired("get", {"id": ident}))
            if not result["worker_active"]:
                return result
            sleep(.01)
        self.fail("The bounded fixture worker did not stop.")

    def test_exact_ambition_native_approval_real_workflow_artifact(self):
        profile = self.profile()
        body = {"ambition": AMBITION, "language": "en"}
        self.expect(self.paired("submit", {**body, "provider": profile}, command=True), 400, "MISSION_INPUT")
        self.expect(self.paired("prepare-intelligence", {**body, "profile": profile}, command=True), 400, "MISSION_INPUT")
        pending = self.prepare()
        self.assertEqual((pending["ambition"], pending["status"], pending["model_calls"]), (AMBITION, "awaiting_consent", 0))
        self.assertEqual(self.mission_calls, [])
        self.assertNotIn("setup_ticket", self.expect(self.paired("get", {"id": pending["id"]})))
        review = self.expect(self.native("mission-review", {"ticket": pending["setup_ticket"]}))
        auth = {"ticket": pending["setup_ticket"], "revision": review["revision"], "profile": profile, "consent": True}
        self.expect(self.native("mission-authorize", auth), 409, "MISSION_PROFILE_REVIEW")
        self.expect(self.post(API + "mission-authorize", auth, {"Origin": PAGES_ORIGIN,
                         "X-Frontier-Session": self.session}), 403, "ORIGIN")
        auth = self.checked_review(pending, profile)
        self.expect(self.native("mission-authorize", {**auth, "revision": "old"}), 409, "MISSION_STAGE_CHANGED")
        opened = self.expect(self.native("mission-authorize", auth))
        self.assertEqual(opened["id"], pending["id"])
        self.expect(self.native("mission-authorize", auth), 403, "MISSION_SETUP_TICKET")
        result = self.wait_for_stop(opened["id"])
        self.assertEqual((result["status"], result["model_calls"], result["ambition"]), ("needs_review", 1, AMBITION))
        self.assertFalse(result["verification"]["passed"])
        self.assertEqual(len(self.mission_calls), 1)
        self.assertIn(AMBITION, self.mission_calls[0]["input"][0]["content"])
        self.assertEqual(self.mission_calls[0]["max_output_tokens"], 256)
        computed = [event for event in result["events"] if event.get("tool") == "run_instrument"]
        self.assertEqual(json.loads(computed[0]["preview"]), {"regret": 3})
        exported = self.expect(self.paired("export", {"id": opened["id"]}))
        self.assertIn("regret.json", exported["files"])
        self.assertNotIn(SECRET, json.dumps(exported))
        self.assertTrue(self.server.runtime.base.local_only)
        self.assertFalse(self.server.runtime.base.allow_paid)

    def test_release_restart_reissue_revision_and_cancel(self):
        command = str(uuid4())
        old = self.prepare("  Explorer les incitatifs.\n", "fr", command=command)
        ticket = old["setup_ticket"]
        self.expect(self.paired("release"))
        self.expect(self.native("mission-review", {"ticket": ticket}), 403, "MISSION_INTELLIGENCE_CONSENT")
        self._close()
        self._launch()
        listed = self.expect(self.paired("list"))["missions"][-1]
        self.assertEqual(listed["id"], old["id"])
        recovered = self.prepare("  Explorer les incitatifs.\n", "fr", command=command)
        self.assertEqual(recovered["id"], old["id"])
        self.assertNotEqual(recovered["setup_ticket"], ticket)
        self.expect(self.native("mission-review", {"ticket": ticket}), 403, "MISSION_SETUP_TICKET")
        revised = self.prepare("Mesurer la regret stratégique.", "fr", previous=old["id"])
        self.assertEqual(revised["original_ambition"], old["ambition"])
        self.assertEqual(revised["parent_run_id"], old["id"])
        self.expect(self.native("mission-review", {"ticket": recovered["setup_ticket"]}), 403, "MISSION_SETUP_TICKET")
        stopped = self.expect(self.paired("cancel", {"id": revised["id"]}, command=True))
        self.assertEqual(stopped["status"], "cancelled")
        self.expect(self.native("mission-review", {"ticket": revised["setup_ticket"]}), 403, "MISSION_SETUP_TICKET")
        export = self.expect(self.paired("export", {"id": revised["id"]}))
        self.assertEqual(export["mission"]["status"], "cancelled")
        restored = self.server.pages_missions.import_local(export)
        self.assertNotEqual(restored["id"], revised["id"])
        self.assertEqual((restored["ambition"], restored["original_ambition"], restored["status"]),
                         (revised["ambition"], old["ambition"], "awaiting_consent"))
        self.assertEqual(self.mission_calls, [])

    def test_revoked_profile_and_cancelled_active_response_do_not_dispatch_tools(self):
        chosen = self.profile()
        pending = self.prepare()
        approval = self.checked_review(pending, chosen)
        self.expect(self.native("disconnect", {"profile_id": chosen, "consent": True}))
        self.expect(self.native("mission-authorize", approval), 403, "INTELLIGENCE_REVOKED")
        self.assertEqual(self.mission_calls, [])
        replacement = self.profile()
        auth = self.checked_review(pending, replacement)
        self.block = Event()
        self.expect(self.native("mission-authorize", auth))
        self.assertTrue(self.mission_started.wait(3))
        revoked = self.expect(self.native("mission-revoke", {"id": pending["id"]}))
        self.assertEqual(revoked["status"], "revoked")
        self.block.set()
        result = self.wait_for_stop(pending["id"])
        self.assertEqual(result["status"], "revoked")
        self.assertEqual(result["artifacts"], [])
        self.assertEqual(len(self.mission_calls), 1)
        self.expect(self.paired("resume", {"id": pending["id"]}, command=True), 409, "MISSION_STATE")

    def test_budget_blocks_new_request_before_provider_and_shields_credentials(self):
        profile = self.profile("0.0046")
        self.expect(self.paired("prepare-intelligence", {"ambition": SECRET, "language": "en"}, command=True),
                    403, "MISSION_INPUT_SECRET")
        pending = self.prepare(AMBITION + " " + "review context " * 650)
        self.expect(self.native("mission-authorize", self.checked_review(pending, profile)))
        result = self.wait_for_stop(pending["id"])
        self.assertEqual((result["status"], result["model_calls"]), ("paused", 0))
        self.assertEqual(self.mission_calls, [])
        self.assertTrue(any(row.get("code") == "BUDGET" for row in result["events"]))

    def test_exact_run_and_artifacts_continue_with_new_native_consent_after_restart(self):
        profile = self.profile()
        pending = self.prepare()
        self.proposal = {**PROPOSAL, "actions": [INSTRUMENT], "done": False}
        self.block = Event()
        self.block_after = 1
        self.expect(self.native("mission-authorize", self.checked_review(pending, profile)))
        until = monotonic() + 3
        while len(self.mission_calls) < 2 and monotonic() < until:
            sleep(.01)
        self.assertEqual(len(self.mission_calls), 2)
        ident = {"id": pending["id"]}
        self.expect(self.paired("pause", ident, command=True))
        self.block.set()
        paused = self.wait_for_stop(pending["id"])
        saved = next(row for row in paused["artifacts"] if row["name"] == "regret.json")
        self._close()
        self._launch()
        self.assertEqual(self.expect(self.paired("get", ident))["status"], "awaiting_consent")
        self.expect(self.paired("resume", ident, command=True), 403, "MISSION_INTELLIGENCE_CONSENT")
        recovery = self.expect(self.paired("mission-intelligence-status", ident))
        self.assertEqual(recovery["ambition"], AMBITION)
        self.assertIn(saved, recovery["artifacts"])
        self.proposal = {**PROPOSAL, "actions": [COMPUTE]}
        self.expect(self.native("mission-authorize", self.checked_review(recovery, profile)))
        result = self.wait_for_stop(pending["id"])
        self.assertEqual((result["id"], result["status"], result["model_calls"]), (pending["id"], "needs_review", 3))
        self.assertIn(saved, result["artifacts"])
        self.assertEqual(self.probe_calls, 1)

    def test_queued_permit_cannot_dispatch_after_native_profile_removal(self):
        profile = self.profile()
        route = self.server.native_intelligence.get_route(profile)
        pending = self.prepare()
        approval = self.checked_review(pending, profile)
        with route.runtime.execution_slot({"provider": route.provider, "model": route.model}):
            self.expect(self.native("mission-authorize", approval))
            marker = {"id": pending["id"]}
            until = monotonic() + 3
            while monotonic() < until:
                current = self.expect(self.paired("get", marker))
                if any(row["kind"] == "model_queued" for row in current["events"]):
                    break
                sleep(.01)
            else:
                self.fail("The mission did not queue behind its profile capacity.")
            self.expect(self.native("disconnect", {"profile_id": profile, "consent": True}))
            result = self.wait_for_stop(pending["id"])
        self.assertEqual((result["status"], result["model_calls"]), ("awaiting_consent", 0))
        self.assertEqual(self.mission_calls, [])

    def test_first_api_stage_binds_browser_revision_and_original_through_restart_and_execution(self):
        profile = self.profile()
        command = str(uuid4())
        body = {"ambition": "  Mesurer le regret stratégique.\n", "language": "fr",
                "original_ambition": "  Explorer les incitatifs et les équilibres.\n"}
        pending = self.expect(self.paired("prepare-intelligence", body, command=command))
        self.assertEqual(pending["original_ambition"], body["original_ambition"])
        self.assertIsNone(pending["parent_run_id"])
        self._close()
        self._launch()
        ident = {"id": pending["id"]}
        self.expect(self.paired("prepare-intelligence", {**body, "original_ambition": "Changed history"}, command=command),
                    409, "MISSION_COMMAND_CHANGED")
        recovered = self.expect(self.paired("mission-intelligence-status", ident))
        review = self.expect(self.native("mission-review", {"ticket": recovered["setup_ticket"], "profile": profile}))
        self.assertEqual((review["ambition"], review["original_ambition"], review["parent_run_id"]),
                         (body["ambition"], body["original_ambition"], None))
        self.expect(self.native("mission-authorize", {"ticket": recovered["setup_ticket"], "profile": profile,
                                                     "revision": review["revision"], "consent": True}))
        result = self.wait_for_stop(ident["id"])
        self.assertEqual((result["id"], result["status"], result["original_ambition"], result["parent_run_id"]),
                         (pending["id"], "needs_review", body["original_ambition"], None))
        prompt = self.mission_calls[0]["input"][0]["content"]
        mission_data = json.loads(prompt.split("\nUNTRUSTED_MISSION_DATA\n", 1)[1])
        self.assertEqual((mission_data["ambition"], mission_data["original_ambition"]),
                         (body["ambition"], body["original_ambition"]))

    def test_first_local_submit_persists_browser_original_and_trusts_native_previous(self):
        self._close()
        self._launch(local=True)
        body = {"ambition": "Measure the first concrete result.\n", "language": "en",
                "original_ambition": "  Establish a repeatable strategic experiment.\n"}
        opened = self.expect(self.paired("submit", body, command=True))
        result = self.wait_for_stop(opened["id"])
        self.assertEqual((result["status"], result["original_ambition"], result["parent_run_id"]),
                         ("needs_review", body["original_ambition"], None))
        prompt = self.local_calls[0]["messages"][0]["content"]
        mission_data = json.loads(prompt.split("\nUNTRUSTED_MISSION_DATA\n", 1)[1])
        self.assertEqual((mission_data["ambition"], mission_data["original_ambition"]),
                         (body["ambition"], body["original_ambition"]))
        self._close()
        self._launch(local=True)
        recovered = self.expect(self.paired("get", {"id": opened["id"]}))
        self.assertEqual(recovered["original_ambition"], body["original_ambition"])
        revised_body = {"ambition": "Test the alternative.", "language": "en", "previous": opened["id"]}
        self.expect(self.paired("submit", {**revised_body, "original_ambition": "Override history"}, command=True),
                    400, "MISSION_INPUT")
        successor = self.expect(self.paired("submit", revised_body, command=True))
        self.assertEqual((successor["original_ambition"], successor["parent_run_id"]),
                         (body["original_ambition"], opened["id"]))
        self.wait_for_stop(successor["id"])
        self.assertEqual(self.mission_calls, [])

    def test_document_lineage_and_follow_up_survive_restart_and_portable_import(self):
        self._close()
        self._launch(local=True)
        ambition = "  Vérifier la relève d'un instrument de terrain.\n"
        marker = "Verrou opérateur TX-731"
        original = "\ufeff" + "a" * 476 + "🌌\n" + marker + "\r\n"
        attachment = {"name": "preuve-source.txt", "text": original}
        fields = {"milestone": "Diagnostiquer la présence d'un verrou de relève", "beneficiary": "Opérateur du capteur",
                  "deliverable": "Note de relève traçable", "acceptance": "Relever le code exact du document",
                  "alternative": "Vérification manuelle du registre d'exploitation", "assumptions": "Le fichier est fourni par l’opérateur"}

        def interpret(body):
            payload = json.loads(body["messages"][0]["content"].split("\nUNTRUSTED_MISSION_DATA\n", 1)[1])
            snapshot = payload["authorized_local_documents"][0]
            self.assertNotIn(marker, snapshot["first_excerpt"]["text"])
            self.assertEqual(snapshot["first_excerpt"]["next_offset"], 479)
            if not payload["latest_tool_results"]:
                return {"summary": "Examiner la provenance, puis confirmer le code.", "done": False, "actions": [
                    {"tool": "propose_outcome", "name": "outcome.json", **fields},
                    {"tool": "read_mission_document", "name": "source.json", "document": 1, "offset": 479}]}
            excerpt = payload["latest_tool_results"][-1]["untrusted_source_excerpt"]
            self.assertEqual(excerpt["text"], "🌌\n" + marker + "\r\n")
            return {"summary": "Le registre de relève contient le code exact.", "done": True, "actions": [
                {"tool": "write_document", "name": "note.md", "content": "Source : " + excerpt["name"] + "\n" + marker}]}

        self.local_reply = interpret
        body = {"ambition": ambition, "language": "fr", "documents": [attachment]}
        opened = self.expect(self.paired("submit", body, command=True))
        result = self.wait_for_stop(opened["id"])
        self.assertEqual((result["status"], result["model_calls"], result["actions"]), ("needs_review", 2, 3))
        document = {"id": 1, "name": attachment["name"], "sha256": hashlib.sha256(original.encode()).hexdigest(),
                    "bytes": len(original.encode())}
        self.assertEqual(result["documents"], [document])
        self.assertEqual(result["proposed_contract"], fields)
        self.assertEqual(result["qualification_dimensions"], dict.fromkeys(("technical_correctness", "semantic_correctness",
                                                                             "objective_relevance", "frontier_advantage"), "NOT_TESTED"))
        self.assertEqual(result["outcome"]["independent_acceptance"], "NOT_ESTABLISHED")
        self.assertNotIn(original, json.dumps(result))
        self.assertEqual(self.server.pages_missions.service.export(result["id"])["files"]["note.md"],
                         "Source : preuve-source.txt\n" + marker)

        self._close()
        self._launch(local=True)
        receipt = self.expect(self.paired("get", {"id": result["id"]}))
        self.assertEqual(receipt["documents"], [document])
        instruction = "  Réutilisez le code dans une fiche courte.\n"

        def continue_work(body):
            payload = json.loads(body["messages"][0]["content"].split("\nUNTRUSTED_MISSION_DATA\n", 1)[1])
            self.assertEqual(payload["member_follow_up"], instruction)
            self.assertEqual(payload["authorized_local_documents"][0]["sha256"], document["sha256"])
            evidence = payload["previous_local_work"]
            self.assertEqual(evidence["status_at_continuation"], "needs_review")
            self.assertIn(marker, evidence["artifacts"][0]["excerpt"])
            return {"summary": "Fiche courte construite.", "done": True, "actions": [
                {"tool": "write_document", "name": "fiche.md", "content": marker}]}

        self.local_reply = continue_work
        next_body = {"ambition": ambition, "language": "fr", "instruction": instruction, "previous": result["id"]}
        successor = self.expect(self.paired("submit", next_body, command=True))
        receipt = self.wait_for_stop(successor["id"])
        self.assertEqual((receipt["original_ambition"], receipt["parent_run_id"], receipt["instruction"]),
                         (ambition, result["id"], instruction))
        snapshot = self.expect(self.paired("export", {"id": successor["id"]}))
        self.assertEqual(snapshot["state"]["spec"]["mission"]["documents"], [attachment])
        self.assertEqual(snapshot["files"], {"fiche.md": marker})
        restored = self.server.pages_missions.import_local(snapshot)
        self.assertEqual((restored["instruction"], restored["documents"], restored["original_ambition"]),
                         (instruction, [document], ambition))
        self.assertEqual(restored["qualification_dimensions"]["objective_relevance"], "NOT_TESTED")

    def test_provider_follow_up_needs_native_review_and_does_not_inherit_local_documents(self):
        self._close()
        self._launch(local=True)
        document = {"name": "propriete.txt", "text": "PRIVATE-ORIGINAL-ONLY"}
        body = {"ambition": AMBITION, "language": "en"}
        self.expect(self.paired("prepare-intelligence", {**body, "documents": [document]}, command=True),
                    403, "MISSION_DOCUMENT_LOCAL_ONLY")
        self.expect(self.paired("submit", {**body, "documents": [{"name": "../forbidden.txt", "text": "data"}]}, command=True),
                    400, "MISSION_DOCUMENT_INPUT")
        self.expect(self.paired("submit", {**body, "documents": [{"name": "large.txt", "text": "x" * 98305}]}, command=True),
                    400, "MISSION_DOCUMENT_LIMIT")
        first = self.expect(self.paired("submit", {**body, "documents": [document]}, command=True))
        self.assertEqual(self.wait_for_stop(first["id"])["status"], "needs_review")
        instruction = "  Check the strongest applicable alternative.\n"
        body = {**body, "instruction": instruction, "previous": first["id"]}
        staged = self.expect(self.paired("prepare-intelligence", body, command=True))
        self.assertEqual((staged["instruction"], staged["documents"], staged["model_calls"]), (instruction, [], 0))
        self.assertEqual(self.mission_calls, [])
        review = self.expect(self.native("mission-review", {"ticket": staged["setup_ticket"], "profile": self.profile()}))
        self.assertEqual(review["instruction"], instruction)
        self.expect(self.native("mission-authorize", {"ticket": staged["setup_ticket"], "revision": review["revision"],
                                                     "profile": review["profile"]["id"], "consent": True}))
        self.assertEqual(self.wait_for_stop(staged["id"])["status"], "needs_review")
        self.assertEqual(len(self.mission_calls), 1)
        prompt = self.mission_calls[0]["input"][0]["content"]
        payload = json.loads(prompt.split("\nUNTRUSTED_MISSION_DATA\n", 1)[1])
        self.assertEqual(payload["member_follow_up"], instruction)
        self.assertNotIn("previous_local_work", payload)
        self.assertNotIn("authorized_local_documents", payload)
        self.assertNotIn(document["text"], prompt)

    def test_late_local_result_cannot_modify_superseded_mission(self):
        self._close()
        self._launch(local=True)
        entered, release = Event(), Event()
        self.addCleanup(release.set)

        def delayed(body):
            if len(self.local_calls) == 1:
                entered.set()
                self.assertTrue(release.wait(4))
                return {"summary": "Old work arrived late", "done": True, "actions": [
                    {"tool": "write_document", "name": "old-work.md", "content": "Canceled result"}]}
            return {"summary": "The new route ran", "done": True, "actions": [
                {"tool": "write_document", "name": "new-work.md", "content": "Current authorized result"}]}

        self.local_reply = delayed
        body = {"ambition": AMBITION, "language": "en"}
        prior = self.expect(self.paired("submit", body, command=True))
        self.assertTrue(entered.wait(3))
        successor = self.expect(self.paired("submit", {**body, "previous": prior["id"], "instruction": "Try an independent approach."}, command=True))
        release.set()
        latest = self.wait_for_stop(successor["id"])
        old = self.wait_for_stop(prior["id"])
        self.assertEqual((old["status"], old["artifacts"], old["actions"]), ("cancelled", [], 0))
        self.assertEqual([item["name"] for item in latest["artifacts"]], ["new-work.md"])
        self.assertEqual(latest["parent_run_id"], prior["id"])

    def test_superseding_active_provider_run_does_not_reuse_its_permission(self):
        profile = self.profile()
        first = self.prepare()
        self.block = Event()
        self.expect(self.native("mission-authorize", self.checked_review(first, profile)))
        self.assertTrue(self.mission_started.wait(3))
        revised = self.expect(self.paired("prepare-intelligence", {"ambition": AMBITION, "language": "en",
            "previous": first["id"], "instruction": "Continue with the revised evidence requirement."}, command=True))
        self.assertEqual(revised["status"], "awaiting_consent")
        self.block.set()
        old = self.wait_for_stop(first["id"])
        self.assertEqual((old["status"], old["actions"], old["artifacts"]), ("superseded", 0, []))
        successor = self.expect(self.paired("get", {"id": revised["id"]}))
        self.assertEqual((successor["status"], successor["model_calls"], len(self.mission_calls)), ("awaiting_consent", 0, 1))

    def test_both_ambitions_are_independently_bounded_and_previous_cannot_be_overridden(self):
        maximal = "é" * (12 * 1024)
        body = {"ambition": maximal, "language": "fr", "original_ambition": maximal + " "}
        for operation in ("prepare-intelligence", "submit"):
            with self.subTest(operation=operation):
                self.expect(self.paired(operation, body, command=True), 400, "MISSION_AMBITION")
                self.expect(self.paired(operation, {**body, "ambition": " \n", "original_ambition": "Valid"},
                                        command=True), 400, "MISSION_AMBITION")
                self.expect(self.paired(operation, {**body, "original_ambition": " \n"}, command=True),
                            400, "MISSION_AMBITION")
                self.expect(self.paired(operation, {**body, "original_ambition": "Override", "previous": "wf_" + "a" * 24},
                                        command=True), 400, "MISSION_INPUT")
        body["original_ambition"] = "à" + maximal[1:]
        instruction = "é" * 1024
        self.expect(self.paired("prepare-intelligence", {**body, "instruction": instruction + "x"}, command=True),
                    400, "MISSION_INSTRUCTION")
        pending = self.expect(self.paired("prepare-intelligence", {**body, "instruction": instruction}, command=True))
        self.assertEqual(pending["ambition"], maximal)
        self.assertEqual(len(pending["original_ambition"].encode()), 24 * 1024)
        self.assertEqual(pending["instruction"], instruction)


if __name__ == "__main__":
    unittest.main()
