"""Checkpointed research, bounded construction and evaluation for one private workspace."""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

from . import construction, evaluation, delivery, development, research, routing
from .economics import assessment
from .provider import HandoffRequired, ManualProvider, ModelProvider, ProviderUnavailable
from .store import Conflict, StateError, digest, event, runtime_source, timestamp

CONSTRUCT_INSTRUCTION = "Construct an executable program for the selected purpose. Return exactly {kind,program}. For a manifest audit use {use_frozen_manifest:true} to bind the exact trusted manifest from the contract. Never invent or retype trust anchors. For record migration, program has columns, extra_fields and optional input_fields. Each column uses source,target,type, optional split:{separator,index}, or sources,separator,target,type for a join. Produce no shell, executable Python, URLs or external actions."

FINISHED = {"verified", "failed", "deferred"}
PRIVATE_FIELDS = {"calls", "exchanges", "last_proposal"}
SPEC_FORMAT = {
    "record_migration": {"definition": {"input_fields": ["legacy_key"], "targets": [{"name": "new_key","type": "text"}],
                                       "extra_fields": "reject", "demonstrations": "separate development cases"},
                         "cases": "held-back named cases: input and expected, or error"},
    "manifest_audit": {"definition": {"manifest": {"relative/path": "operator-supplied trusted sha256"}},
                       "cases": "frozen named byte-input cases and exact expected classifications"}
}


class ModelBudgetExhausted(StateError):
    """The next uncached inference exceeds the mission authorization."""


class Controller:
    def __init__(self, store, provider_factory=None, assisted=None):
        self.store = store
        self.source = runtime_source()
        from .pairing_specialist import identity as pairing_identity
        self.pairing_source = pairing_identity()
        self.factory = provider_factory or ModelProvider.from_environment
        self.assisted = assisted

    def provider(self, exchanges=None):
        if self.assisted:
            return ManualProvider(*self.assisted, exchanges if exchanges is not None else {})
        return self.factory()

    def identity(self):
        return self.provider().identity()

    def create(self, body, run_id=None):
        specialist = self._specialist_identity(body)
        if run_id is not None:
            with self.store.work_lock(run_id):
                return self.store.create(body, self.identity(), self.source, run_id=run_id, base=body.get("version"),
                                         specialist_source=specialist)
        return self.store.create(body, self.identity(), self.source, specialist_source=specialist)

    def _specialist_identity(self, body):
        mission = body.get("mission") if isinstance(body, dict) else None
        resources = mission.get("resources") if isinstance(mission, dict) else None
        if isinstance(resources, dict) and "endpoint_lab" in resources:
            if "pairing_lab" in resources:
                raise StateError("Select one specialist for this mission.")
            from .endpoint_specialist import identity
            return identity()
        return self.pairing_source

    def successor(self, run_id, version, body, rights):
        if not isinstance(rights,str) or not rights.strip() or len(rights)>2000:
            raise StateError("Provide the authorization basis for this specific reuse")
        with self.store.work_lock(run_id):
            s = self.store.get(run_id)
            self._guard(s)
            if type(version) is not int or s["version"] != version or s["status"] != "verified":
                raise Conflict("Source capability requires an accepted current revision")
            if s["mission"]["authority"].get("allow_program_reuse") is not True:
                raise StateError("Source mission did not grant local program reuse")
            if s["artifact"]["kind"] == "pairing_lab":
                raise StateError("Reuse the portable Pairing Lab instrument through a fresh specialist mission")
            if s["artifact"]["kind"] == "endpoint_evidence":
                raise StateError("Open a fresh endpoint study to requalify a changed operating requirement.")
            inherited = {"source_id":run_id, "source_version":version, "artifact_sha256":s["artifact"]["sha256"],
                         "rights":rights, "kind":s["artifact"]["kind"], "program":s["artifact"]["program"]}
            return self.store.create(body,self.identity(),self.source,inherited=inherited,specialist_source=self._specialist_identity(body))

    def obsolete(self, s):
        if "endpoint_lab" in s["mission"]["resources"]:
            from .endpoint_specialist import identity
            try:
                current = identity()
            except (OSError, ValueError):
                return True
            if s.get("specialist_source") != current:
                return True
        if "pairing_lab" in s["mission"]["resources"]:
            from .pairing_specialist import identity
            if s.get("specialist_source") != self.pairing_source or identity() != self.pairing_source or (s.get("contract") and s["contract"].get("specialist_sha256") != self.pairing_source):
                return True
        return (runtime_source() != self.source or s["runtime"] != self.source
                or s["provider"] != self.identity())

    def view(self, run_id, version=None):
        s = self.store.get(run_id, version)
        if version is None and self.obsolete(s):
            s.pop("endpoint_result", None)
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
        if status in FINISHED | {"blocked"}:
            s["economics"] = assessment(s["mission"],s["research"],
                                        {"completed":list(s["calls"].values()),"failed":s.get("unsuccessful_calls",[])})
        event(s, stage, message, status)
        self.store.save(s)

    def intervene(self, run_id, version, operation, body):
        with self.store.work_lock(run_id,version):
            s = self.store.get(run_id)
            if type(version) is not int or s["version"] != version:
                raise Conflict("Stale mission version")
            self._guard(s)
            if operation == "respond":
                h = s["handoff"]
                value = body.get("response")
                prior = s["exchanges"].get(body.get("sha256")) if isinstance(body.get("sha256"),str) else None
                if prior is not None and prior == {"response":value}:
                    return
                if not h or s["status"] != "awaiting_model" or h["sha256"] != body.get("sha256"):
                    raise Conflict("Response does not match the pending model request")
                if not isinstance(value, dict):
                    raise StateError("The reviewed model response must be a JSON object")
                s["exchanges"][h["sha256"]] = {"response": value}
                s["handoff"] = None
                self._step(s, h["stage"], "Operator supplied a response bound to the pending request", "queued")
            elif operation == "choose":
                menu = s.get("mapping_choice")
                if not menu or body.get("sha256") != menu["sha256"]:
                    raise Conflict("Selection does not match the current mapping choice")
                choice = body.get("choice")
                if not isinstance(choice, str) or choice not in [c["id"] for c in menu["candidates"]] + ["abstain"]:
                    raise StateError("Choose a listed hypothesis or abstain")
                resolution = {"choice": choice, "origin": "operator", "menu_sha256": menu["sha256"]}
                if s.get("mapping_resolution") == resolution:
                    return
                if s["status"] != "awaiting_choice" or s.get("mapping_resolution"):
                    raise Conflict("A mapping selection is no longer pending")
                s["mapping_resolution"] = resolution
                self._step(s, "selection", "Operator recorded a choice bound to the current mission and hypothesis set", "queued")
            elif operation == "approve":
                if s.get("approval_fingerprint") == digest(body):
                    return
                if (s["status"] != "awaiting_contract" or not s["proposed_contract"]
                        or body.get("contract_sha256") != s["contract_sha256"]):
                    raise Conflict("Approval does not match the proposed acceptance contract")
                confirmations = body.get("confirmations")
                if not isinstance(confirmations,list) or not any(isinstance(c,dict) and "expected" in c for c in confirmations):
                    raise StateError("Supply fresh confirmation cases including a positive case from an independent source")
                draft = s["proposed_contract"]["spec"]
                def input_units(data):
                    if isinstance(data,dict) and isinstance(data.get("rows"),list) and data["rows"]:
                        return {digest(row) for row in data["rows"]}
                    return {digest(data)}
                shown = set()
                for case in draft["cases"] + draft["definition"].get("demonstrations",[]):
                    shown |= input_units(case["input"])
                for case in confirmations:
                    if not isinstance(case,dict) or "input" not in case or shown & input_units(case["input"]):
                        raise StateError("A confirmation input duplicates a case already seen by the proposer")
                s["contract"] = construction.freeze_contract(dict(draft,cases=draft["cases"]+confirmations))
                s["contract_sha256"] = s["contract"]["sha256"]
                s["approval_fingerprint"] = digest(body)
                s["acceptance_origin"] = {"model_proposed_cases": len(draft["cases"]),
                                          "operator_supplemental_cases": len(confirmations),
                                          "independence":"Operator reports fresh confirmation inputs. External independence unmeasured."}
                self._step(s, "contract", "Operator approved the specification and supplied fresh confirmation cases", "queued")
            else:
                raise StateError("Unknown intervention")

    def advance(self, run_id, version):
        with self.store.work_lock(run_id,version):
            s = self.store.get(run_id)
            if type(version) is not int or version != s["version"]:
                raise Conflict("Stale mission version")
            self._guard(s)
            if s["status"] in FINISHED | {"awaiting_model", "awaiting_contract", "awaiting_choice"}:
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
            except Exception as exc:
                s["error"] = f"Unexpected {type(exc).__name__} at {s['stage']}. Inspect the private operator log."
                self._step(s, s["stage"], s["error"], "blocked")
                raise
            return self.public(s)

    def _work(self, s):
        mission = s["mission"]
        auth = mission["authority"]
        provider = self.provider(s["exchanges"])
        mode = provider.identity().get("mode")
        self._check_time(mission)
        if "endpoint_lab" in mission["resources"]:
            from .endpoint_specialist import run
            return run(self, s)
        if "pairing_lab" in mission["resources"]:
            from .pairing_specialist import run
            return run(self, s)
        if s.get("routing") is None:
            model_permission = "assisted_model" if self.assisted else "local_model"
            model_permitted = (mode in ("manual", "local") and auth.get(model_permission) is True
                               and mission["resources"].get("max_model_calls") != 0)
            s["routing"] = routing.route(mission, model_permitted=model_permitted)
            self._step(s, "routing", s["routing"]["reason"])
        choice = s["routing"]
        if choice["route"] == "clarify":
            return self._step(s, "clarification", choice["reason"], "deferred")
        if s["source_result"] is None:
            retrieved = {"sources": [], "failures": [], "feeds": []}
            if choice["route"] == "research" and auth.get("public_sources") is True:
                self._step(s, "sources", "Reading the operator-permitted public release feeds")
                retrieved = research.discover_sources(mission)
            s["source_result"] = dict(retrieved, observed_at=timestamp())
            self._step(s, "sources", f"Recorded {len(s['sources'])} supplied and {len(retrieved['sources'])} retrieved source records")

        def propose(stage, payload):
            self._guard(s)
            self._check_time(mission)
            if mode in ("blocked", "unavailable", "unconfigured", "disabled"):
                raise StateError("No live model configured. Choose a local provider or explicitly start an assisted session")
            permission = "assisted_model" if self.assisted else "local_model"
            if auth.get(permission) is not True:
                raise StateError(f"Mission does not authorize {permission}")
            bound = dict(payload, run_id=s["id"], revision=s["version"], mission_sha256=s["input_sha256"])
            key = digest([stage, bound, s["provider"]])
            if key in s["calls"]:
                return s["calls"][key]["response"]
            limit = mission["resources"].get("max_model_calls")
            if limit is not None and (type(limit) is not int or limit < 0):
                raise StateError("max_model_calls must be a nonnegative integer")
            # Handoff preparation has no inference side effect. Count the supplied response once.
            counted = not self.assisted or provider.request(stage,bound)["sha256"] in s["exchanges"]
            if limit is not None and s.get("attempts", 0) >= limit:
                raise ModelBudgetExhausted("Mission model-call budget exhausted")
            if counted:
                if stage == "choose_hypothesis":
                    if s.get("choice_call_started"):
                        raise StateError("A bounded choice call started without a reusable answer. Amend before a new attempt.")
                    s["choice_call_started"] = key
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
        model_mission["resources"] = {k:v for k,v in mission["resources"].items() if k!="commercial_case"}
        if s["research"] is None:
            if choice["route"] == "direct":
                s["research"] = routing.direct_selection(mission, choice)
            else:
                sources = s["sources"] + s["source_result"]["sources"]
                s["research"] = research.investigate(model_mission, sources, propose, as_of=s["source_result"]["observed_at"])
                prior = [record["research"] for record in self.store.history(s["id"])
                         if record["version"] < s["version"] and record["research"]]
                s["research"]["retest_leads"] = research.reopen_inventory(prior, s["research"]["signals"])
            self._step(s, "selection", s["research"]["decision_reason"])
        result = s["research"]
        if result["decision"] != "build":
            if mission["resources"].get("direct_after_research") is not True or not spec or spec.get("kind") not in SPEC_FORMAT:
                return self._step(s, "selection", result["decision_reason"], "deferred")
            if not choice.get("fallback"):
                fallback = routing.route(dict(mission, resources=dict(mission["resources"], execution_strategy="direct")))
                if fallback["route"] != "direct":
                    return self._step(s, "selection", fallback["reason"], "deferred")
                choice["fallback"] = fallback
                self._step(s, "routing", "Preserved the research verdict. The operator separately requested a direct attempt on the frozen specification.")
            choice = choice["fallback"]
            result = routing.direct_selection(mission, choice)
        if result.get("kind") not in SPEC_FORMAT:
            raise StateError("The selected construction needs an execution capability outside the installed grammar")
        if s["contract"] is None:
            if spec:
                if spec.get("kind") != result["kind"]:
                    raise StateError("Selected construction and authorized specification differ")
                s["contract"] = construction.freeze_contract(spec)
                s["contract_sha256"] = s["contract"]["sha256"]
                s["acceptance_origin"] = {"operator_supplied_cases":len(spec["cases"]),
                                          "independence":"Checker executes separately. Operator controls confirmation inputs."}
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
        payload = {"instruction": CONSTRUCT_INSTRUCTION, "purpose": mission["purpose"],
                   "requirements": mission["requirements"], "kind": result["kind"],
                   "definition": construction.build_view(contract)["definition"],
                   "retained_program": {k:v for k,v in (s.get("inherited") or {}).items() if k in {"kind","program"}} or None}
        if choice["route"] == "research":
            payload["selected"] = result["selected"]
        self._construct(s, contract, choice, payload, propose)

    def _choose_mapping(self, s, payload, method, propose):
        mission = s["mission"]
        definition = payload["definition"]
        menu = s.get("mapping_choice")
        if menu is None:
            menu, error = development.menu(definition, mission["resources"].get("choice_order", "ascending"))
            if error:
                self._step(s, "selection", error, "deferred")
                return None
            menu["sha256"] = digest([s["id"], s["version"], s["runtime"], s["input_sha256"], s["contract_sha256"], menu])
            s["mapping_choice"] = menu
            self._step(s, "selection", f"Observed {len(menu['candidates'])} complete public-example mapping hypotheses")
        if not s.get("mapping_resolution"):
            if len(menu["candidates"]) == 1:
                choice, origin = menu["candidates"][0]["id"], "unique_public_fit"
            elif method == "operator_choice":
                self._step(s, "selection", menu["question"], "awaiting_choice")
                return None
            elif not development.has_distinguishing_evidence(mission, menu):
                self._step(s, "selection", "The stated objective lacks a discriminating source or operation for this set. Clarify the purpose or request operator selection.", "deferred")
                return None
            else:
                packet = {"instruction": "Choose the one mapping identified by the original objective. If the supplied intent does not distinguish a complete mapping, answer abstain. Return only the registered choice identifier in the JSON choice field.",
                          "purpose": mission["purpose"], "requirements": mission["requirements"],
                          "fixed_operations": [op["description"] for op in menu["fixed_operations"]],
                          "candidates": [{"id": c["id"], "description": c["description"]} for c in menu["candidates"]]}
                try:
                    response = propose("choose_hypothesis", packet)
                except HandoffRequired:
                    raise
                except (StateError, ProviderUnavailable, ValueError):
                    if not s.get("choice_call_started"):
                        raise
                    self._step(s, "selection", "The single bounded choice attempt produced no usable response. No program was selected.", "deferred")
                    return None
                choice, origin = response.get("choice"), "model"
                if set(response) != {"choice"} or choice not in [c["id"] for c in menu["candidates"]] + ["abstain"]:
                    self._step(s, "selection", "Model response did not identify a registered hypothesis. No program was selected.", "deferred")
                    return None
            s["mapping_resolution"] = {"choice": choice, "origin": origin, "menu_sha256": menu["sha256"]}
            self.store.save(s)
        chosen = s["mapping_resolution"]["choice"]
        if chosen == "abstain":
            self._step(s, "selection", "No mapping was selected. Supply a discriminating example or clarify the intended operation.", "deferred")
            return None
        return {"kind": "record_migration", "program": development.program_for(definition, menu, chosen)}

    def _construct(self, s, contract, choice, payload, propose):
        mission = s["mission"]
        resources = mission["resources"]
        attempts = s.setdefault("construction_attempts", [])
        specialist = choice["method"] == "specialist"
        bounded = choice["method"] in ("operator_choice", "model_choice")
        # Attempts and model calls are separately checkpointed. Resuming a handoff reuses its
        # exact request, and a terminal rejection cannot be converted into a fresh budget.
        while True:
            self._check_time(mission)
            if attempts:
                last = attempts[-1]
                if last["status"] == "accepted":
                    return self._step(s, "delivery", "Verified within the frozen contract", "verified")
                if specialist or bounded or not last["repairable"] or len(attempts) > resources.get("max_repairs", 1):
                    return self._step(s, "delivery", "Independent acceptance failed. The rejected construction is retained for inspection.", "failed")
            if bounded:
                response = self._choose_mapping(s, payload, choice["method"], propose)
                if response is None:
                    return
            elif specialist:
                program = payload["definition"]
                self._step(s, "construction", "Running the installed local specialist on the builder-visible specification")
                if "demonstrations" in program:
                    program, obstruction = development.learn(program)
                    if obstruction:
                        s["error"] = obstruction
                        return self._step(s, "selection", obstruction, "deferred")
                response = {"kind": payload["kind"], "program": program}
            elif attempts:
                last = attempts[-1]
                try:
                    response = propose("repair", {**payload, "attempt": len(attempts) + 1,
                        "instruction": CONSTRUCT_INSTRUCTION + " Repair the previous proposal using the confirmed diagnostics. The frozen acceptance remains unchanged.",
                        "previous_proposal": s["last_proposal"], "verified_failure": last["feedback"]})
                except ModelBudgetExhausted:
                    return self._step(s, "delivery", "Independent acceptance failed and the model-call budget allows no further repair.", "failed")
            else:
                response = propose("construct", payload)
            started = time.monotonic()
            attempt = {"attempt": len(attempts) + 1, "contract_sha256": contract["sha256"],
                       "proposal_sha256": digest(response), "method": choice["method"] if bounded or specialist else "model",
                       "artifact_sha256": None, "receipt_sha256": None, "feedback": None, "repairable": True}
            try:
                artifact = construction.build(contract, response)
            except construction.ConstructionError as exc:
                s["artifact"] = None
                s["evaluation"] = None
                attempt.update(status="rejected", feedback={"compiler_code": exc.code, "detail": str(exc)})
            else:
                self._step(s, "verification", "Executing the frozen cases, conventional comparator and negative controls")
                s["artifact"] = artifact
                receipt = evaluation.evaluate(contract, artifact)
                s["evaluation"] = receipt
                accepted = receipt["status"] == "pass"
                attempt.update(status="accepted" if accepted else "rejected", artifact_sha256=artifact["sha256"],
                               receipt_sha256=receipt["receipt_sha256"], checks=len(receipt["cases"]),
                               passed_checks=sum(c["candidate_pass"] for c in receipt["cases"]),
                               comparison=receipt["comparison"]["outcome"],
                               repairable=not accepted and receipt["comparison"]["oracles_agree"],
                               feedback=None if accepted else routing.diagnostic(contract, artifact, receipt))
            if any(previous["proposal_sha256"] == attempt["proposal_sha256"] for previous in attempts):
                attempt["repairable"] = False
            attempt["elapsed_seconds"] = round(time.monotonic() - started, 6)
            s["last_proposal"] = response
            attempts.append(attempt)
            self._step(s, "assessment", f"Construction attempt {len(attempts)} {attempt['status']} under the frozen acceptance contract")

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
            if s["artifact"]["kind"] == "endpoint_evidence":
                from .endpoint_specialist import deliver
                return deliver(s, payload, trial)
            if s["artifact"]["kind"] == "pairing_lab":
                from .pairing_specialist import deliver
                return deliver(self, s, payload, trial)
            if trial:
                return construction.execute(s["artifact"], payload)
            ctx = {"mission_id":s["id"], "version":s["version"], "mission":s["mission"], "input_sha256":s["input_sha256"],
                   "source_sha256":s["runtime"], "provider":s["provider"], "python":sys.version.split()[0],
                   "research":s["research"], "routing":s.get("routing"), "construction_attempts":s.get("construction_attempts", []),
                   "mapping_choice":s.get("mapping_choice"), "mapping_resolution":s.get("mapping_resolution"),
                   "acceptance_origin":s.get("acceptance_origin"),
                   "inherited_from":{k:v for k,v in (s.get("inherited") or {}).items() if k!="program"}, "sources":s["sources"] + s["source_result"]["sources"],
                   "source_failures":s["source_result"]["failures"], "events":s["events"],
                   "model_calls":[{k:v for k,v in c.items() if k!="response"} for c in s["calls"].values()],
                   "unsuccessful_calls":s.get("unsuccessful_calls",[]),
                   "economics":s.get("economics"),
                   "inheritance":"Use only under separately established data and software rights. Requalify on each new mission."}
            return delivery.export_bundle(s["contract"],s["artifact"],s["evaluation"],ctx)
