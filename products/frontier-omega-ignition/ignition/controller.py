"""Checkpointed research, bounded construction and evaluation for one private workspace."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

from . import construction, evaluation, delivery, research
from .provider import HandoffRequired, ManualProvider, ModelProvider, ProviderUnavailable
from .store import Conflict, StateError, digest, event, runtime_source, timestamp

FINISHED = {"verified", "failed", "deferred"}
PRIVATE_FIELDS = {"calls", "exchanges"}
SPEC_FORMAT = {
    "record_migration": {"definition": {"input_fields": ["legacy_key"], "targets": [{"name": "new_key","type": "text"}],
                                       "extra_fields": "reject", "demonstrations": "separate development cases"},
                         "cases": "held-back named cases: input and expected, or error"},
    "manifest_audit": {"definition": {"manifest": {"relative/path": "operator-supplied trusted sha256"}},
                       "cases": "frozen named byte-input cases and exact expected classifications"}
}


class Controller:
    def __init__(self, store, provider_factory=None, assisted=None):
        self.store = store
        self.source = runtime_source()
        self.factory = provider_factory or ModelProvider.from_environment
        self.assisted = assisted

    def provider(self, exchanges=None):
        if self.assisted:
            return ManualProvider(*self.assisted, exchanges if exchanges is not None else {})
        return self.factory()

    def identity(self):
        return self.provider().identity()

    def create(self, body, run_id=None):
        return self.store.create(body, self.identity(), self.source, run_id=run_id, base=body.get("version"))

    def obsolete(self, s):
        return (runtime_source() != self.source or s["runtime"] != self.source
                or s["provider"] != self.identity())

    def view(self, run_id, version=None):
        s = self.store.get(run_id, version)
        if version is None and self.obsolete(s):
            s.update(status="stale", error="Provider or application source changed. Amend to open a fresh revision.",
                     handoff=None, artifact=None, evaluation=None)
        return self.public(s)

    @staticmethod
    def public(s):
        return {k:v for k,v in s.items() if k not in PRIVATE_FIELDS}

    def _guard(self, s):
        if self.obsolete(s):
            raise Conflict("Source or provider changed. Restart the service on current source and amend the mission")
        if s["version"] != self.store.get(s["id"])["version"]:
            raise Conflict("Mission was amended")

    def _step(self, s, stage, message, status="running"):
        event(s, stage, message, status)
        self.store.save(s)

    def intervene(self, run_id, version, operation, body):
        with self.store.work_lock(run_id):
            s = self.store.get(run_id)
            if type(version) is not int or s["version"] != version:
                raise Conflict("Stale mission version")
            self._guard(s)
            if operation == "respond":
                h = s["handoff"]
                value = body.get("response")
                if not h or s["status"] != "awaiting_model" or h["sha256"] != body.get("sha256"):
                    raise Conflict("Response does not match the pending model request")
                if not isinstance(value, dict):
                    raise StateError("The reviewed model response must be a JSON object")
                s["exchanges"][h["sha256"]] = {"response": value}
                s["handoff"] = None
                self._step(s, h["stage"], "Operator supplied a response bound to the pending request", "queued")
            elif operation == "approve":
                if (s["status"] != "awaiting_contract" or not s["proposed_contract"]
                        or body.get("contract_sha256") != s["contract_sha256"]):
                    raise Conflict("Approval does not match the proposed acceptance contract")
                s["contract"] = s["proposed_contract"]
                self._step(s, "contract", "Operator approved the proposed acceptance specification", "queued")
            else:
                raise StateError("Unknown intervention")

    def advance(self, run_id, version):
        with self.store.work_lock(run_id):
            s = self.store.get(run_id)
            if type(version) is not int or version != s["version"]:
                raise Conflict("Stale mission version")
            self._guard(s)
            if s["status"] in FINISHED | {"awaiting_model", "awaiting_contract"}:
                return self.public(s)
            s["error"] = None
            try:
                self._work(s)
            except HandoffRequired as exc:
                s["handoff"] = exc.request
                self._step(s, exc.request["stage"], "Awaiting an explicitly attributed, operator-assisted model response", "awaiting_model")
            except Conflict:
                raise
            except (StateError, ProviderUnavailable, ValueError, KeyError, TypeError) as exc:
                s["error"] = str(exc)[:1200]
                self._step(s, s["stage"], s["error"] or "Invalid stage output", "blocked")
            return self.public(s)

    def _work(self, s):
        mission = s["mission"]
        auth = mission["authority"]
        provider = self.provider(s["exchanges"])
        mode = provider.identity().get("mode")
        self._check_time(mission)
        if s["source_result"] is None:
            retrieved = {"sources": [], "failures": [], "feeds": []}
            if auth.get("public_sources") is True:
                self._step(s, "sources", "Reading the operator-permitted public release feeds")
                retrieved = research.discover_sources(mission)
            s["source_result"] = retrieved
            self._step(s, "sources", f"Recorded {len(s['sources'])} supplied and {len(retrieved['sources'])} retrieved source records")
        if mode in ("blocked", "unavailable", "unconfigured", "disabled"):
            raise StateError("No live model configured. Choose a local provider or explicitly start an assisted session")
        permission = "assisted_model" if self.assisted else "local_model"
        if auth.get(permission) is not True:
            raise StateError(f"Mission does not authorize {permission}")

        def propose(stage, payload):
            self._guard(s)
            self._check_time(mission)
            bound = dict(payload, run_id=s["id"], revision=s["version"], mission_sha256=s["input_sha256"])
            key = digest([stage, bound, s["provider"]])
            if key in s["calls"]:
                return s["calls"][key]["response"]
            limit = mission["resources"].get("max_model_calls")
            if limit is not None and (type(limit) is not int or limit < 0):
                raise StateError("max_model_calls must be a nonnegative integer")
            # Handoff preparation has no inference side effect. Count the supplied response once.
            counted = not self.assisted or provider.request(stage,bound)["sha256"] in s["exchanges"]
            if counted:
                if limit is not None and s.get("attempts", 0) >= limit:
                    raise StateError("Mission model-call budget exhausted")
                s["attempts"] = s.get("attempts", 0) + 1
            self._step(s, stage, f"Requested {stage} from the configured provider")
            start = time.monotonic()
            try:
                response = provider.propose(stage, bound)
            except HandoffRequired:
                raise
            except Exception:
                s.setdefault("unsuccessful_calls", []).append({
                    "stage":stage, "request_sha256":key, "at":timestamp(),
                    "elapsed_seconds":round(time.monotonic()-start,3), "receipts":provider.receipts[-1:]})
                self.store.save(s)
                raise
            if not isinstance(response, dict):
                raise StateError("Provider output must be a JSON object")
            s["calls"][key] = {"stage":stage, "response":response, "response_sha256":digest(response),
                               "receipt":provider.receipts[-1:] or None,
                               "elapsed_seconds":round(time.monotonic()-start,3)}
            self.store.save(s)
            return response

        spec = mission.get("construction_spec", {})
        # The research and builder prompts never receive the predeclared confirmation inputs.
        model_mission = dict(mission, construction_spec={k:v for k,v in spec.items() if k != "cases"})
        if s["research"] is None:
            sources = s["sources"] + s["source_result"]["sources"]
            s["research"] = research.investigate(model_mission, sources, propose, as_of=s["created_at"][:10])
            self._step(s, "selection", s["research"]["decision_reason"])
        result = s["research"]
        if result["decision"] != "build":
            return self._step(s, "selection", result["decision_reason"], "deferred")
        if result.get("kind") not in SPEC_FORMAT:
            raise StateError("The selected construction needs an execution capability outside the installed grammar")
        if s["contract"] is None:
            if spec:
                if spec.get("kind") != result["kind"]:
                    raise StateError("Selected construction and authorized specification differ")
                s["contract"] = construction.freeze_contract(spec)
                self._step(s, "contract", "Froze the mission-specific specification and acceptance cases")
            else:
                proposed = propose("specification", {
                    "instruction":"Suggest a testable specification addressing all original requirements. Do not invent trusted digests or private inputs. Return {spec: {purpose,kind,definition,cases}} or {obstruction: string}. The operator must review it before construction.",
                    "mission":model_mission, "selected":result["selected"], "kind":result["kind"], "format":SPEC_FORMAT[result["kind"]]})
                if "obstruction" in proposed:
                    raise StateError(str(proposed["obstruction"]))
                draft = proposed.get("spec")
                if not isinstance(draft,dict) or draft.get("purpose") != mission["purpose"] or draft.get("kind") != result["kind"]:
                    raise StateError("Proposed specification does not bind the purpose and selected capability")
                s["proposed_contract"] = construction.freeze_contract(draft)
                s["contract_sha256"] = digest(s["proposed_contract"])
                return self._step(s, "contract", "Review the proposed scope, acceptance cases and their independence before approval", "awaiting_contract")
        contract = s["contract"]
        if s["artifact"] is None:
            response = propose("construct", {
                "instruction":"Construct an executable program for the selected purpose. Return exactly {kind,program}. For a manifest audit the program is {manifest:{...}}. For record migration, program has columns, extra_fields and optional input_fields. Each column uses source,target,type, optional split:{separator,index}, or sources,separator,target,type for a join. Produce no shell, executable Python, URLs or external actions.",
                "selected":result["selected"], "purpose":mission["purpose"], "requirements":mission["requirements"],
                "kind":result["kind"], "definition":contract["spec"]["definition"]})
            s["artifact"] = construction.build(contract, response)
            self._step(s, "construction", "Compiled the proposed instructions into a portable bounded program")
        self._check_time(mission)
        self._step(s, "verification", "Executing the frozen cases, conventional comparator and negative controls")
        s["evaluation"] = evaluation.evaluate(contract, s["artifact"])
        passed = s["evaluation"]["status"] == "pass"
        self._step(s, "delivery", "Verified within the frozen contract" if passed else "Independent acceptance failed",
                   "verified" if passed else "failed")

    @staticmethod
    def _check_time(mission):
        end = mission["time"].get("deadline")
        if end:
            try:
                deadline = datetime.fromisoformat(end.replace("Z", "+00:00"))
                if deadline.tzinfo is None:
                    raise ValueError()
            except (ValueError, AttributeError) as exc:
                raise StateError("deadline must be an ISO 8601 timestamp with timezone") from exc
            if datetime.now(timezone.utc) >= deadline:
                raise StateError("Mission deadline elapsed")

    def deliver(self, run_id, version=None, payload=None, *, trial=False):
        with self.store.work_lock(run_id):
            s = self.store.get(run_id)
            self._guard(s)
            if version is not None and (type(version) is not int or version != s["version"]):
                raise Conflict("Mission has been amended")
            if s["status"] != "verified":
                raise Conflict("Current revision has no accepted artifact")
            if trial:
                return construction.execute(s["artifact"], payload)
            ctx = {"mission_id":s["id"], "version":s["version"], "mission":s["mission"], "input_sha256":s["input_sha256"],
                   "source_sha256":s["runtime"], "provider":s["provider"], "python":sys.version.split()[0],
                   "research":s["research"], "sources":s["sources"] + s["source_result"]["sources"],
                   "source_failures":s["source_result"]["failures"], "events":s["events"],
                   "model_calls":[{k:v for k,v in c.items() if k!="response"} for c in s["calls"].values()],
                   "unsuccessful_calls":s.get("unsuccessful_calls",[]),
                   "economics":{"payment_received":False,"commercial_acceptance":"unmeasured","complete_cost":"unknown"},
                   "inheritance":"Use only under separately established data and software rights. Requalify on each new mission."}
            return delivery.export_bundle(s["contract"],s["artifact"],s["evaluation"],ctx)
