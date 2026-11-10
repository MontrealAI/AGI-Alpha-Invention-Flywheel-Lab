# SPDX-License-Identifier: Apache-2.0
"""Bounded, source-bound HARNESS improvement research. No credentials or network."""
from __future__ import annotations

import argparse
import copy
import hashlib
import hmac
import json
import math
from pathlib import Path
import re
import secrets
import time
from urllib.parse import urlsplit
from datetime import datetime, timezone

from . import adapters as _adapters_module, instruments as _instruments_module, workflows as _workflows_module, workflow_strategies as _strategies_module, services as _services_module
from . import workflow_schemas as _workflow_schemas_module, output_schema as _output_schema_module
from .adapters import BridgeError, strict_json
from .instruments import evaluate
from .workflows import WorkflowService, _atomic, _regular, digest, encoded, equivalent, now, require

SHA = re.compile(r"[a-f0-9]{64}\Z")
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
PRODUCT = Path(__file__).resolve().parent.parent
MAX_RECORDS = 2000  # Per-document processing envelope, not a commercial scale claim.
SCOPE = "Bounded HARNESS engineering research; no autonomous general invention, market validation, spending or deployment authority."


def _text(value, label, maximum=2000):
    require(isinstance(value, str) and 0 < len(value) <= maximum, label + " must be nonempty text within its processing envelope.", "GENESIS_INPUT")
    return value


def _ids(value, label):
    require(isinstance(value, list) and len(value) <= 100 and all(isinstance(x, str) and IDENT.fullmatch(x) for x in value), label + " must be a list of simple capability IDs.", "GENESIS_INPUT")
    return sorted(set(value))


def _number(value, label, optional=False):
    if optional and value is None:
        return None
    try:
        finite = type(value) in {int, float} and math.isfinite(value) and value >= 0
    except (OverflowError, TypeError):
        finite = False
    require(finite, label + " must be a finite nonnegative number.", "GENESIS_INPUT")
    return value


def source_identity():
    identities = {name: hashlib.sha256(_regular(PRODUCT / "bridge" / name, 1024 * 1024)).hexdigest()
                  for name in ("workflows.py", "workflow_strategies.py", "workflow_schemas.py", "output_schema.py", "services.py", "instruments.py", "adapters.py", "genesis_next.py")}
    dependencies_loaded = {"adapters.py": _adapters_module.LOADED_SOURCE_SHA256,
                           "instruments.py": _instruments_module.LOADED_SOURCE_SHA256,
                           "workflows.py": _workflows_module.LOADED_SOURCE_SHA256,
                           "workflow_strategies.py": _strategies_module.LOADED_SOURCE_SHA256,
                           "workflow_schemas.py": _workflow_schemas_module.LOADED_SOURCE_SHA256,
                           "output_schema.py": _output_schema_module.LOADED_SOURCE_SHA256,
                           "services.py": _services_module.LOADED_SOURCE_SHA256}
    require(all(identities[name] == value for name, value in dependencies_loaded.items()),
            "HARNESS dependency changed after it was loaded. Restart the connector before GENESIS initialization.",
            "GENESIS_SOURCE_DRIFT")
    loaded = globals().get("_LOADED_SOURCE_IDENTITIES")
    require(loaded is None or identities == loaded,
            "HARNESS source changed after module load. Restart the connector before verification or construction.",
            "GENESIS_SOURCE_DRIFT")
    return identities


_LOADED_SOURCE_IDENTITIES = source_identity()


def require_current_source():
    identities = source_identity()
    require(identities == _LOADED_SOURCE_IDENTITIES,
            "HARNESS source changed after module load. Restart the connector before verification or construction.",
            "GENESIS_SOURCE_DRIFT")
    return dict(identities)


class EvidenceIndex:
    """Exact dependency-aware memoization; no semantic similarity or inherited truth.

    Inputs and checker identity must describe the complete deterministic check.
    Content hashes do not prove a remote source's truth or current freshness.
    Imported portable records cannot grant authority: they require revalidation.
    """
    def __init__(self, checker_id, *, ttl_seconds=3600, clock=time.time):
        _text(checker_id, "Checker identity", 300)
        _number(ttl_seconds, "Evidence lifetime")
        require(ttl_seconds > 0 and ttl_seconds <= 86400 * 365, "Evidence lifetime is outside the supported time envelope.", "GENESIS_INPUT")
        self.checker_id, self.ttl_seconds, self.clock = checker_id, ttl_seconds, clock
        self.entries = {}
        self.verification_calls = 0

    def key(self, spec, dependency_hashes):
        require(isinstance(spec, dict) and len(encoded(spec)) <= 1024 * 1024, "Evidence specification must be a bounded object.", "GENESIS_INPUT")
        require(isinstance(dependency_hashes, dict) and len(dependency_hashes) <= 200 and all(isinstance(k, str) and 0 < len(k) <= 200 and isinstance(v, str) and SHA.fullmatch(v) for k, v in dependency_hashes.items()), "Dependencies require exact SHA-256 identities.", "GENESIS_INPUT")
        return digest({"checker": self.checker_id, "spec": spec, "dependencies": dependency_hashes})

    @staticmethod
    def _cancelled(value):
        return bool(value() if callable(value) else value)

    def check(self, spec, dependency_hashes, verifier, *, cancelled=False):
        key = self.key(spec, dependency_hashes)
        if self._cancelled(cancelled):
            return {"accepted": False, "result": None, "reused": False, "key": key, "verification_calls": 0, "status": "CANCELLED"}
        entry = self.entries.get(key)
        if isinstance(entry, dict):
            payload = {k: v for k, v in entry.items() if k != "sha256"}
            valid = (isinstance(entry.get("sha256"), str) and hmac.compare_digest(entry["sha256"], digest(payload))
                     and entry.get("key") == key and entry.get("checker") == self.checker_id
                     and entry.get("dependencies") == dependency_hashes and entry.get("trusted") is True
                     and type(entry.get("created_at")) in {int, float} and type(entry.get("expires_at")) in {int, float} and entry["created_at"] <= self.clock() < entry["expires_at"]
                     and entry.get("accepted") is True)
            if valid:
                return {"accepted": True, "result": copy.deepcopy(entry["result"]), "reused": True, "key": key, "verification_calls": 0, "status": "REUSED_EXACT_CHECK"}
            self.entries.pop(key, None)
        self.verification_calls += 1
        result = verifier()
        require(self.key(spec, dependency_hashes) == key, "Verifier changed its bound specification or dependencies; evidence was not retained.", "GENESIS_MUTATION")
        require(isinstance(result, dict), "Verifier must return an evidence object.", "GENESIS_CHECKER")
        accepted = result.get("accepted", result.get("passed"))
        require(type(accepted) is bool, "Verifier must return an explicit boolean acceptance decision.", "GENESIS_CHECKER")
        require(len(encoded(result)) <= 1024 * 1024, "Verifier result exceeds the evidence envelope.", "GENESIS_CHECKER")
        if self._cancelled(cancelled):
            return {"accepted": False, "result": copy.deepcopy(result), "reused": False, "key": key, "verification_calls": 1, "status": "CANCELLED"}
        if accepted:
            # Evict expired/oldest records rather than allowing an unbounded cache.
            if len(self.entries) >= MAX_RECORDS:
                oldest = min(self.entries, key=lambda k: self.entries[k].get("created_at", 0))
                del self.entries[oldest]
            entry = {"key": key, "checker": self.checker_id, "dependencies": copy.deepcopy(dependency_hashes), "result": copy.deepcopy(result), "accepted": True,
                     "created_at": self.clock(), "expires_at": self.clock() + self.ttl_seconds, "trusted": True}
            entry["sha256"] = digest(entry)
            self.entries[key] = entry
        return {"accepted": accepted, "result": copy.deepcopy(result), "reused": False, "key": key, "verification_calls": 1, "status": "CHECKED"}

    def needs_verification(self, spec, dependency_hashes):
        key = self.key(spec, dependency_hashes)
        entry = self.entries.get(key)
        if not isinstance(entry, dict):
            return True
        payload = {k: v for k, v in entry.items() if k != "sha256"}
        return not (isinstance(entry.get("sha256"), str) and hmac.compare_digest(entry["sha256"], digest(payload))
                    and entry.get("key") == key and entry.get("checker") == self.checker_id
                    and entry.get("dependencies") == dependency_hashes and entry.get("trusted") is True
                    and type(entry.get("created_at")) in {int, float} and type(entry.get("expires_at")) in {int, float} and entry["created_at"] <= self.clock() < entry["expires_at"]
                    and entry.get("accepted") is True)

    def invalidate(self, changed_dependencies):
        require(isinstance(changed_dependencies, (list, tuple, set, dict)), "Invalidation needs dependency names.", "GENESIS_INPUT")
        names = set(changed_dependencies)
        keys = [k for k, entry in self.entries.items() if names.intersection(entry.get("dependencies", {}))]
        for key in keys:
            del self.entries[key]
        return len(keys)

    def export(self):
        value = {"schema": "genesis-evidence-index/v1", "checker": self.checker_id, "entries": copy.deepcopy(self.entries)}
        value["sha256"] = digest(value)
        return value

    def _load_archive(self, value, *, trusted):
        require(isinstance(value, dict) and value.get("schema") == "genesis-evidence-index/v1", "Unsupported evidence export.", "GENESIS_INTEGRITY")
        payload = {k: v for k, v in value.items() if k != "sha256"}
        require(isinstance(value.get("sha256"), str) and hmac.compare_digest(value["sha256"], digest(payload)), "Evidence export integrity failed.", "GENESIS_INTEGRITY")
        require(value.get("checker") == self.checker_id and isinstance(value.get("entries"), dict) and len(value["entries"]) <= MAX_RECORDS, "Evidence checker or inventory differs.", "GENESIS_INTEGRITY")
        self.entries = copy.deepcopy(value["entries"])
        for key, entry in self.entries.items():
            require(isinstance(key, str) and SHA.fullmatch(key) and isinstance(entry, dict), "Malformed evidence entry.", "GENESIS_INTEGRITY")
            if not trusted:
                entry["trusted"] = False
                entry["sha256"] = digest({k: v for k, v in entry.items() if k != "sha256"})

    def import_archive(self, value):
        self._load_archive(value, trusted=False)
        return {"imported": len(self.entries), "qualification": "REVALIDATION_REQUIRED"}


# Constructor-owned source recipe. Arbitrary or model-proposed Python is never loaded.
# The emitted source runs in an isolated experiment workspace with a fixture runtime.
CANDIDATE_SOURCE = '''# SPDX-License-Identifier: Apache-2.0
# Generated bounded HARNESS upgrade: exact deterministic evidence reuse.
class CandidateWorkflow(WorkflowService):
    def __init__(self, runtime, private_root, evidence_index, checker_dependencies):
        super().__init__(runtime, private_root)
        self.evidence_index = evidence_index
        self.checker_dependencies = checker_dependencies

    def _verify(self, state):
        dependencies = dict(self.checker_dependencies)
        checks = state["spec"]["acceptance"] + state.get("adversarial_cases", [])
        try:
            for name in {c["artifact"] for c in checks}:
                raw = self._read_artifact(state, name)
                actual = hashlib.sha256(raw).hexdigest()
                require(actual == state["artifacts"][name]["sha256"], "Artifact integrity failed.")
                dependencies["artifact:" + name] = actual
        except (BridgeError, ValueError, TypeError, KeyError, RecursionError):
            return super()._verify(state)
        spec = {"acceptance": checks, "max_operations": state["spec"]["max_operations"], "artifact_kinds": {name: state["artifacts"][name]["kind"] for name in {c["artifact"] for c in checks}}}
        def verify():
            super(CandidateWorkflow, self)._verify(state)
            return copy.deepcopy(state["verification"])
        receipt = self.evidence_index.check(spec, dependencies, verify)
        if receipt["reused"]:
            state["verification"] = copy.deepcopy(receipt["result"])
            state["verification"]["spec_hash"] = state["spec_hash"]
            state["verification"]["artifact_hashes"] = {k: v["sha256"] for k, v in state["artifacts"].items()}
            self._event(state, "verification", state["verification"])
        self._event(state, "evidence_reuse", {"reused": receipt["reused"], "key": receipt["key"], "verification_calls": receipt["verification_calls"], "scope": "Exact deterministic check only; no inherited empirical truth."})
'''


def construct_candidate(directory):
    directory = Path(directory)
    require(not directory.exists(), "Use a fresh isolated candidate directory.", "GENESIS_ISOLATION")
    directory.mkdir(mode=0o700)
    _atomic(directory / "candidate.py", CANDIDATE_SOURCE.encode())
    return {"path": directory / "candidate.py", "sha256": hashlib.sha256(CANDIDATE_SOURCE.encode()).hexdigest()}


def load_candidate(path):
    raw = _regular(Path(path), 64 * 1024)
    require(raw == CANDIDATE_SOURCE.encode(), "Candidate differs from the bounded constructor; arbitrary source is refused.", "GENESIS_SOURCE")
    namespace = {"WorkflowService": WorkflowService, "EvidenceIndex": EvidenceIndex, "hashlib": hashlib,
                 "require": require, "BridgeError": BridgeError, "copy": copy}
    exec(compile(raw, "<bounded-genesis-candidate>", "exec"), namespace)
    return namespace["CandidateWorkflow"]


class GenesisNextService:
    def __init__(self, workflows):
        self.workflows = workflows
        self.root = workflows.root / "genesis-next"
        require(not self.root.is_symlink(), "GENESIS workspace must not be a symlink.", "GENESIS_INTEGRITY")
        self.root.mkdir(exist_ok=True, mode=0o700)
        self.lock = workflows._lock("genesis-next")
        self.path = self.root / "state.json"
        with self.lock:
            if not self.path.exists():
                self._save(self._initial())

    def _initial(self):
        identities = require_current_source()
        cap = {"id": "bounded-verification", "title": "HARNESS deterministic artifact verification", "status": "implemented", "source": "bridge/workflows.py:_verify", "source_sha256": identities["workflows.py"],
               "inputs": ["operator acceptance", "artifact bytes"], "permissions": ["read own workflow artifacts"], "acceptance": "Exact bounded instrument outputs match operator cases; document checks are structural.",
               "evidence": [], "dependencies": ["bounded-instrument-runtime"], "costs": {"complete_cost_known": False, "maintenance": None}, "limitations": ["Cases do not prove external truth.", "Existing implementation repeats deterministic checks."]}
        return {"schema_version": 1, "revision": 0, "capabilities": [cap], "opportunities": [
            {"id": "verify-repeated-work", "title": "Reuse unchanged accepted HARNESS checks", "description": "WorkflowService._verify reruns all declared cases during builder review, finish and inheritance.", "required_capabilities": ["dependency-evidence-reuse"], "blocking_conditions": ["No source/dependency-aware evidence index"], "prospective_value": None, "value_basis": "Real call-path observation; economic value not measured.", "verification_probability": None, "estimated_cost": None, "status": "deferred"},
            {"id": "select-next-experiment", "title": "Spend a finite verification budget on unresolved experiments", "description": "Select fresh discriminating cases after reusing compatible intermediate evidence.", "required_capabilities": ["dependency-evidence-reuse", "experiment-selection"], "blocking_conditions": ["Must know which prior checks still apply"], "prospective_value": None, "value_basis": "Candidate successor, not earned value.", "verification_probability": None, "estimated_cost": None, "status": "deferred"}],
            "frontier_events": [], "candidates": [], "experiments": [], "lineage": [], "evidence_index": None, "scope": SCOPE}

    def _load(self):
        value = strict_json(_regular(self.path))
        require(isinstance(value, dict) and set(value) == {"state", "mac"}, "GENESIS state envelope is invalid.", "GENESIS_INTEGRITY")
        expected = hmac.new(self.workflows._key, encoded(value["state"]), hashlib.sha256).hexdigest()
        require(isinstance(value["mac"], str) and hmac.compare_digest(value["mac"], expected), "GENESIS state authentication failed.", "GENESIS_INTEGRITY")
        return value["state"]

    def _save(self, state):
        state["revision"] += 1
        require(len(encoded(state)) <= 16 * 1024 * 1024, "GENESIS state reached its processing envelope; export and archive the completed research workspace.", "GENESIS_SIZE")
        _atomic(self.path, encoded({"state": state, "mac": hmac.new(self.workflows._key, encoded(state), hashlib.sha256).hexdigest()}))

    @staticmethod
    def _public(state):
        view = copy.deepcopy(state)
        index = view.pop("evidence_index", None)
        view["retained_evidence_count"] = len(index.get("entries", {})) if index else 0
        return view

    def _observations(self):
        """Inspect authenticated traces, including isolated children, exactly once."""
        records, total_checks, repeats, failures, model_calls, unknown_costs = [], 0, 0, 0, 0, 0
        pending = list(self.workflows.list()["runs"])
        seen = set()
        while pending:
            summary = pending.pop(0)
            if summary["id"] in seen:
                continue
            seen.add(summary["id"])
            if summary["status"] == "integrity_error":
                records.append({"run_id": summary["id"], "status": "INTEGRITY_ERROR", "usable_evidence": False})
                continue
            try:
                workflow = self.workflows.get(summary["id"])
            except BridgeError as error:
                records.append({"run_id": summary["id"], "status": "UNAVAILABLE", "usable_evidence": False, "error_code": error.code})
                continue
            for branch in workflow.get("branch_runs", []):
                pending.append({"id": branch["run_id"], "status": "branch"})
            signatures, run_repeats, run_failures, run_checks, route_calls = set(), 0, 0, 0, []
            for event in workflow["events"]:
                if event["kind"] == "verification":
                    detail = event["detail"]
                    # A historical signature is investigation evidence only.
                    signature = digest({"checks": detail.get("checks"), "artifacts": detail.get("artifact_hashes"),
                                        "acceptance": workflow["spec"]["acceptance"], "max_operations": workflow["spec"]["max_operations"]})
                    run_checks += 1
                    run_repeats += signature in signatures
                    signatures.add(signature)
                    run_failures += detail.get("passed") is not True
            completions = {event["detail"].get("run_id"): event["detail"] for event in workflow["events"] if event["kind"] == "model_completed"}
            # Parent counters already aggregate children. Count actual started
            # requests from each run once, never parent aggregate counters.
            for request in self.workflows._request_costs(workflow):
                if request["workflow"] != workflow["id"]:
                    continue
                model_calls += 1
                cost = request.get("cost")
                unknown_costs += not isinstance(cost, dict) or cost.get("amount") is None
                completion = completions.get(request["run_id"], {})
                route_calls.append({"run_id": request["run_id"], "role": request.get("role"), "provider": completion.get("provider", request.get("provider")),
                                    "model": completion.get("model", request.get("model")), "requested_model": request.get("model"),
                                    "reported_model": completion.get("reported_model"), "reported_cost": cost, "event_kind": request["event_kind"],
                                    "cost_uncertain": request["cost_uncertain"]})
            total_checks += run_checks
            repeats += run_repeats
            failures += run_failures
            records.append({"run_id": workflow["id"], "parent_run": workflow.get("parent_run"), "branch_index": workflow.get("branch_index"),
                            "status": workflow["status"], "usable_evidence": True,
                            "event_chain_sha256": workflow["events"][-1]["sha256"] if workflow["events"] else None,
                            "verification_events": run_checks, "repeated_verification_signatures": run_repeats,
                            "failed_verifications": run_failures, "model_routes": route_calls})
        return {"runs": records, "verification_events": total_checks, "repeated_verification_signatures": repeats,
                "failed_verifications": failures, "model_calls": model_calls, "unknown_model_costs": unknown_costs,
                "scope": "Observed authenticated local traces including branch failures and every attempted model request. Repeated signatures are investigation evidence, not reusable current acceptance or measured economic savings."}

    def status(self):
        with self.lock:
            state = self._load()
            # Keep locally completed workflow capabilities observable, without changing
            # their existing acceptance authority or automatically upgrading their status.
            state["workflow_capabilities"] = self.workflows.capabilities()["capabilities"]
            state["observations"] = self._observations()
            return self._public(state)

    def export(self):
        value = self.status()
        value["export_notice"] = "Recorded evidence only. Imports do not inherit authority or production promotion. Review project content before sharing."
        value["sha256"] = digest(value)
        return value

    def add_opportunity(self, data):
        require(isinstance(data, dict), "Opportunity must be an object.", "GENESIS_INPUT")
        p = _number(data.get("verification_probability"), "Verification probability", True)
        require(p is None or p <= 1, "Verification probability must be at most 1.", "GENESIS_INPUT")
        blocking = data.get("blocking_conditions", [])
        require(isinstance(blocking, list) and len(blocking) <= 100, "Blocking conditions must be a bounded list.", "GENESIS_INPUT")
        item = {"id": "op_" + secrets.token_hex(8), "title": _text(data.get("title"), "Opportunity title", 300),
                "description": data.get("description", ""), "required_capabilities": _ids(data.get("required_capabilities", []), "Required capabilities"),
                "blocking_conditions": [_text(v, "Blocking condition", 500) for v in blocking], "prospective_value": _number(data.get("prospective_value"), "Prospective value", True),
                "value_basis": _text(data.get("value_basis", "Operator estimate; no earned value."), "Value basis"), "verification_probability": p,
                "estimated_cost": _number(data.get("estimated_cost"), "Estimated cost", True), "status": "deferred", "created_at": now()}
        require(isinstance(item["description"], str) and len(item["description"]) <= 10000, "Opportunity description exceeds its envelope.", "GENESIS_INPUT")
        with self.lock:
            state = self._load()
            require(len(state["opportunities"]) < MAX_RECORDS, "Opportunity inventory reached its document envelope.", "GENESIS_SIZE")
            state["opportunities"].append(item)
            self._save(state)
            return {"opportunity": item, "state": self._public(state)}

    def replay(self, data):
        require(isinstance(data, dict), "Frontier observation must be an object.", "GENESIS_INPUT")
        sha = data.get("content_sha256")
        require(isinstance(sha, str) and SHA.fullmatch(sha), "Frontier replay needs the exact observed content SHA-256.", "GENESIS_INPUT")
        url = _text(data.get("url"), "Source reference")
        parsed = urlsplit(url)
        require((parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password) or url.startswith("local:"), "Use an HTTPS source or local: evidence reference.", "GENESIS_INPUT")
        timestamp = _text(data.get("observed_at"), "Observation timestamp", 80)
        try:
            observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            require(observed.tzinfo is not None and observed <= datetime.now(timezone.utc), "Observation timestamp needs a timezone and cannot be in the future.", "GENESIS_INPUT")
        except ValueError:
            raise BridgeError("GENESIS_INPUT", "Use an ISO-8601 observation timestamp with timezone.") from None
        ids = _ids(data.get("capability_ids", []), "Relevant capabilities")
        require(data.get("evidence_status", "reported") in {"reported", "reproduced"}, "Invalid source evidence status.", "GENESIS_INPUT")
        event = {"id": "frontier_" + secrets.token_hex(8), "title": _text(data.get("title"), "Development title", 300), "url": url,
                 "observed_at": timestamp, "content_sha256": sha, "capability_ids": ids, "evidence_status": data.get("evidence_status", "reported"),
                 "qualification": "Operator-supplied observation; requires targeted independent verification before a capability is unlocked."}
        with self.lock:
            state = self._load()
            require(len(state["frontier_events"]) < MAX_RECORDS, "Frontier inventory reached its document envelope.", "GENESIS_SIZE")
            state["frontier_events"].append(event)
            reactivated = []
            for opportunity in state["opportunities"]:
                matches = sorted(set(ids).intersection(opportunity["required_capabilities"]))
                if matches:
                    opportunity["status"] = "reconsider"
                    opportunity["replay_evidence"] = event["id"]
                    reactivated.append({"id": opportunity["id"], "title": opportunity["title"], "matched_capabilities": matches,
                        "experiment": "Challenge whether the cited development removes: " + "; ".join(opportunity["blocking_conditions"]), "unlocked": False})
            self._save(state)
            return {"event": event, "reactivated": reactivated, "state": self._public(state)}

    def discover(self):
        with self.lock:
            state = self._load()
            observed = self._observations()
            state["observations"] = observed
            opportunities = {item["id"]: item for item in state["opportunities"]}
            for ident, title, capability, metric in [
                    ("observed-reverification", "Avoid observed repeated unchanged checks", "dependency-evidence-reuse", "repeated_verification_signatures"),
                    ("observed-verification-failures", "Resolve observed acceptance failures", "adversarial-test-design", "failed_verifications")]:
                if observed[metric]:
                    opportunities[ident] = {"id": ident, "title": title, "description": "Derived from current authenticated WorkflowService traces.",
                        "required_capabilities": [capability], "blocking_conditions": ["Observed local evidence needs a discriminating upgrade comparison"],
                        "prospective_value": None, "value_basis": "Observed event counts; time and economic value remain unknown.", "verification_probability": None,
                        "estimated_cost": None, "status": "investigate", "observed_evidence": {"metric": metric, "count": observed[metric],
                            "runs": [{"run_id": row["run_id"], "event_chain_sha256": row.get("event_chain_sha256")} for row in observed["runs"] if row.get("usable_evidence")]}}
            state["opportunities"] = list(opportunities.values())
            verified = {c["id"] for c in state["capabilities"] if c["status"] == "independently_verified"}
            groups = {}
            for opportunity in state["opportunities"]:
                for missing in set(opportunity["required_capabilities"]) - verified:
                    groups.setdefault(missing, []).append(opportunity)
            candidates = []
            for capability, items in groups.items():
                known = all(x["prospective_value"] is not None and x["estimated_cost"] is not None and x["verification_probability"] is not None for x in items)
                # Overlapping successor outcomes are not assumed additive; conservative
                # max value reports an upper-priority signal, never realized income.
                expected = max(x["prospective_value"] * x["verification_probability"] for x in items) if known else None
                cost = max(x["estimated_cost"] for x in items) if known else None
                candidates.append({"id": capability, "title": "Construct " + capability.replace("-", " "), "required_by": [x["id"] for x in items],
                    "shared_opportunities": len(items), "count": len(items), "observed_evidence": [x["observed_evidence"] for x in items if "observed_evidence" in x], "expected_value": expected, "estimated_cost": cost, "score": expected - cost if known else None,
                    "basis": "Conditional operator estimates; largest overlapping expected outcome, not sum. Unknown value/cost leaves score unranked. Shared count is a structural search priority only.",
                    "comparison_options": ["Solve opportunities individually", "Integrate an existing capability", "Construct reusable capability", "Reorganize voluntary participation or verification", "Defer / no build"]})
            candidates.sort(key=lambda x: (x["score"] is None, -(x["score"] or 0), -x["count"], x["id"]))
            state["candidates"] = candidates
            self._save(state)
            return {"candidates": candidates, "state": self._public(state)}

    def _index(self, state):
        identities = require_current_source()
        index = EvidenceIndex(digest(identities))
        old = state.get("evidence_index")
        if old and old.get("checker") == index.checker_id:
            index._load_archive(old, trusted=True)  # Authenticated by this workspace's existing HMAC key.
        return index, identities

    def verify_instrument(self, data):
        require(isinstance(data, dict), "Verification request must be an object.", "GENESIS_INPUT")
        spec = {"instrument": data.get("instrument"), "inputs": data.get("inputs"), "expected": data.get("expected"), "max_operations": data.get("max_operations", 10000)}
        require(type(spec["max_operations"]) is int and 1 <= spec["max_operations"] <= 1000000, "Invalid finite operation envelope.", "GENESIS_INPUT")
        deps = data.get("dependencies", {})
        with self.lock:
            state = self._load()
            index, sources = self._index(state)
            index.key(spec, deps)  # Validate before merging trusted source identities.
            dependencies = {**{"external:" + k: v for k, v in deps.items()}, **{"checker:" + k: v for k, v in sources.items()}}
            def check():
                result = evaluate(spec["instrument"], spec["inputs"], spec["max_operations"])
                return {"accepted": equivalent(result["output"], spec["expected"]), "actual": result["output"], "expected": spec["expected"], "operations": result["operations"]}
            try:
                receipt = index.check(spec, dependencies, check)
                require_current_source()
            except (ValueError, TypeError, KeyError, RecursionError):
                raise BridgeError("GENESIS_INSTRUMENT", "Instrument or inputs failed the bounded evaluator contract.") from None
            state["evidence_index"] = index.export()
            self._save(state)
            receipt["scope"] = "Exact deterministic acceptance reuse; external truth and current applicability require separate evidence."
            return {"verification": receipt, "state": self._public(state)}

    def run_demo(self, data):
        require(isinstance(data, dict) and data.get("authorize") is True, "Authorize this bounded local source-construction experiment explicitly.", "GENESIS_AUTHORIZATION")
        with self.lock:
            state = self._load()
            require(len(state["experiments"]) < MAX_RECORDS, "Experiment inventory reached its document envelope.", "GENESIS_SIZE")
            ident = "omega_" + secrets.token_hex(8)
            result = demonstrate(self.root / ident)
            result["id"] = ident
            state["experiments"].append(result)
            if result["qualification"]["correctness"] == "PASS":
                existing = {c["id"]: c for c in state["capabilities"]}
                existing["dependency-evidence-reuse"] = {"id": "dependency-evidence-reuse", "title": "Dependency-aware deterministic evidence reuse", "status": "tested",
                    "source": "bridge/genesis_next.py:EvidenceIndex", "source_sha256": source_identity()["genesis_next.py"], "acceptance": "Fixed protocol correctness and invalidation cases pass; external independent review remains separate.",
                    "evidence": [ident], "dependencies": ["bounded-verification"], "costs": result["costs"], "limitations": result["limitations"], "callable": "/api/genesis-next/verify"}
                state["capabilities"] = list(existing.values())
                state["lineage"].append({"parent": "dependency-evidence-reuse", "child": "experiment-selection", "relation": "used_by", "evidence": ident,
                    "benefit": result["successor"]["verdict"], "scope": "Authored distinct scheduling task; competent ordinary reuse is an equal-content control."})
            self._save(state)
            return {"experiment": result, "state": self._public(state)}


def select_experiments(index, experiments, budget, verifier):
    """Select highest-priority unresolved deterministic checks under a call budget.

    Priorities are operator estimates, not earnings or information-theoretic proof.
    The supplied verifier receives each complete experiment specification.
    """
    require(type(budget) is int and 0 <= budget <= 10000, "Use a finite nonnegative verification call budget.", "GENESIS_INPUT")
    require(isinstance(experiments, list) and len(experiments) <= MAX_RECORDS, "Experiment list exceeds its envelope.", "GENESIS_INPUT")
    require(all(isinstance(e, dict) and isinstance(e.get("id"), str) for e in experiments), "Experiments need IDs.", "GENESIS_INPUT")
    require(len({e["id"] for e in experiments}) == len(experiments), "Experiment IDs must be unique.", "GENESIS_INPUT")
    for item in experiments:
        _number(item.get("priority"), "Experiment priority")
        index.key(item.get("spec"), item.get("dependencies"))
    ordered = sorted(experiments, key=lambda e: (-e["priority"], e["id"]))
    outcomes, spent, unresolved = [], 0, []
    for item in ordered:
        needed = index.needs_verification(item["spec"], item["dependencies"])
        if needed and spent >= budget:
            unresolved.append(item["id"])
            continue
        result = index.check(item["spec"], item["dependencies"], lambda item=item: verifier(item["spec"]))
        spent += result["verification_calls"]
        outcomes.append({"id": item["id"], **result})
    return {"outcomes": outcomes, "unresolved": unresolved, "verification_calls": spent, "budget": budget,
            "scope": "Operator-priority selection with exact reusable evidence; no claim of optimal scientific information gain."}


def demonstrate(directory):
    """Run the constructor on actual WorkflowService and a distinct selection task.

    All cases here are visible authored examples. Independent fresh-instance
    confirmation belongs to the separately frozen reviewer-owned protocol.
    """
    from .workflow_demo import FixtureRuntime, instrument, specification
    directory = Path(directory)
    require(not directory.exists(), "Use a new experiment directory.", "GENESIS_ISOLATION")
    directory.mkdir(mode=0o700)
    started = time.perf_counter()
    source_before = require_current_source()
    protocol_path = PRODUCT / "evidence" / "OMEGA-PROTOCOL.md"
    protocol_sha = hashlib.sha256(_regular(protocol_path, 1024 * 1024)).hexdigest()
    candidate = construct_candidate(directory / "foundry")
    Candidate = load_candidate(candidate["path"])
    dependencies = {"checker:" + k: v for k, v in source_before.items()}
    checker_id = digest(dependencies)
    # Baseline and competent ordinary control retain all permissions and exact content.
    arms = {}
    for arm in ("baseline", "candidate", "ordinary"):
        start = time.perf_counter()
        index = EvidenceIndex(checker_id)
        runtime = FixtureRuntime([])
        service = Candidate(runtime, directory / arm, index, dependencies) if arm == "candidate" else WorkflowService(runtime, directory / arm)
        ordinary = {}
        verification_calls, outcomes = 0, []
        try:
            cases = ["original", "unchanged", "changed-source", "changed-input", "changed-acceptance", "missing-artifact", "unchanged-again"]
            for case in cases:
                spec = specification("HARNESS self-qualification: " + case)
                spec["roles"] = {"builder": {"provider": "fixture", "model": "no-inference"}}
                if case == "changed-input":
                    spec["acceptance"][0]["input"]["x"] = 7
                    spec["acceptance"][0]["expected"]["result"] = 25
                if case == "changed-acceptance":
                    spec["acceptance"][0]["expected"]["result"] = -1
                created = service.create(spec)
                state = service._load(created["id"])
                if case != "missing-artifact":
                    service._write(state, "affine.json", json.dumps(instrument(case != "changed-source")), "instrument")
                # Count only this protocol's explicit qualification calls. Creation
                # does not perform checks for a non-inherited workflow.
                if arm == "ordinary" and case != "missing-artifact":
                    raw = service._read_artifact(state, "affine.json")
                    payload = {"acceptance": state["spec"]["acceptance"], "max_operations": state["spec"]["max_operations"], "artifact": hashlib.sha256(raw).hexdigest(), "checkers": dependencies}
                    key = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                    if key in ordinary:
                        state["verification"] = copy.deepcopy(ordinary[key])
                    else:
                        service._verify(state)
                        verification_calls += 1
                        if state["verification"]["passed"]:
                            ordinary[key] = copy.deepcopy(state["verification"])
                else:
                    before = index.verification_calls
                    service._verify(state)
                    verification_calls += index.verification_calls - before if arm == "candidate" else 1
                    # Missing/corrupt artifact takes the existing fail-closed baseline
                    # directly and is still a performed check, not free work.
                    if arm == "candidate" and case == "missing-artifact":
                        verification_calls += 1
                outcomes.append({"case": case, "accepted": state["verification"]["passed"], "checks": state["verification"]["checks"]})
            arms[arm] = {"verification_calls": verification_calls, "cases": len(cases), "accepted": sum(x["accepted"] for x in outcomes), "outcomes": outcomes,
                         "wall_seconds": time.perf_counter() - start, "model_calls": 0}
        finally:
            service.close()
    expected = [True, True, False, True, False, False, True]
    correctness = all([x["accepted"] for x in arm["outcomes"]] == expected for arm in arms.values())
    # Different task: select unresolved experiments rather than verify one workflow.
    # The candidate inherits the verified exact-evidence mechanism, not a result on
    # the new cases. Conventional memoization receives identical evidence.
    prior = {"instrument": instrument(), "inputs": {"x": 2, "gain": 3, "offset": 4}, "expected": {"result": 10}}
    def verify(spec):
        result = evaluate(spec["instrument"], spec["inputs"])
        return {"accepted": equivalent(result["output"], spec["expected"]), "actual": result["output"], "operations": result["operations"]}
    tasks = [{"id": "known-high-priority", "priority": 10, "spec": prior, "dependencies": dependencies},
             {"id": "known-second-use", "priority": 9, "spec": copy.deepcopy(prior), "dependencies": dependencies},
             {"id": "new-discriminator", "priority": 8, "spec": {"instrument": instrument(), "inputs": {"x": 17, "gain": 5, "offset": 9}, "expected": {"result": 94}}, "dependencies": dependencies},
             {"id": "new-negative-control", "priority": 7, "spec": {"instrument": instrument(), "inputs": {"x": 23, "gain": 7, "offset": 11}, "expected": {"result": 173}}, "dependencies": dependencies}]
    index = EvidenceIndex(checker_id)
    index.check(prior, dependencies, lambda: verify(prior))
    inherited = select_experiments(index, tasks, 2, verify)
    # Independent plain-dictionary control; no use of EvidenceIndex key/selection.
    def ordinary_key(item):
        return json.dumps({"spec": item["spec"], "dependencies": item["dependencies"], "checker": checker_id}, sort_keys=True, separators=(",", ":"))
    memo = {ordinary_key(tasks[0]): verify(prior)}
    ordinary_outcomes, ordinary_calls = [], 0
    for task in sorted(tasks, key=lambda t: (-t["priority"], t["id"])):
        key = ordinary_key(task)
        if key in memo:
            result = memo[key]
        elif ordinary_calls < 2:
            result = verify(task["spec"])
            ordinary_calls += 1
            if result["accepted"]:
                memo[key] = result
        else:
            continue
        ordinary_outcomes.append({"id": task["id"], "accepted": result["accepted"]})
    inherited_decisions = [{"id": x["id"], "accepted": x["accepted"]} for x in inherited["outcomes"]]
    ordinary_tie = inherited_decisions == ordinary_outcomes and inherited["verification_calls"] == ordinary_calls
    source_unchanged = source_identity() == source_before
    correctness = correctness and source_unchanged and ordinary_tie
    total = time.perf_counter() - started
    costs = {"complete_cost_known": False, "wall_seconds": total, "model_calls": 0, "candidate_source_bytes": len(CANDIDATE_SOURCE.encode()),
             "construction_and_transfer": "Included measured demo wall time only; prior engineering and review are not priced.", "engineering": None, "maintenance": None, "compute_bill": None,
             "unknown_costs": ["prior design and implementation", "independent review", "ongoing maintenance", "hardware and electricity", "complete economic cost"]}
    result = {"schema": "genesis-next-experiment/v1", "title": "The HARNESS retains exact evidence and selects unresolved successor experiments", "status": "complete", "created_at": now(),
              "limitation": "WorkflowService._verify repeats unchanged deterministic acceptance checks.", "construction": "Constructor-owned source recipe adds exact dependency-aware reuse to an isolated WorkflowService subclass.",
              "source": {"baseline_sha256": source_before["workflows.py"], "candidate_sha256": candidate["sha256"], "protocol_sha256": protocol_sha, "checker_sha256": source_before["instruments.py"], "dependency_sha256": source_before, "evaluation_sources_unchanged": source_unchanged},
              "qualification": {"correctness": "PASS" if correctness else "FAIL", "decision": "RETAIN_BOUNDED_RESEARCH_CAPABILITY" if correctness else "REJECT", "production_promotion": False,
                                "scientific_verdict": "NO_SUPERIORITY_ESTABLISHED: competent content-addressed ordinary reuse ties; complete costs remain unknown.", "independence": "Evaluator and frozen protocol outside candidate edit boundary; this built-in authored demonstration is separate from independent reviewer tests."},
              "arms": arms, "successor": {"task": "Prioritize unresolved experiments with two new verification calls", "candidate": inherited, "ordinary": {"outcomes": ordinary_outcomes, "verification_calls": ordinary_calls},
                      "verdict": "TIE_WITH_STRONG_ORDINARY_REUSE" if ordinary_tie else "REQUIRES_INVESTIGATION", "freshness": "Distinct task with visible authored cases; not a blinded external holdout.", "inherited_mechanism": "dependency-evidence-reuse"},
              "costs": costs, "limitations": ["Developer-authored bounded construction recipe, not autonomous discovery of arbitrary source modifications.", "No general scientific or market truth is cached.", "Ordinary reuse ties; compounding advantage is not established.", "No production code or evaluation rule is replaced.", "All built-in cases are public authored examples; independent fresh-instance tests are separate."],
              "artifacts": {"candidate.py": CANDIDATE_SOURCE, "candidate_sha256": candidate["sha256"]}}
    _atomic(directory / "result.json", encoded(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "discover", "demo", "export"])
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--authorize", action="store_true")
    args = parser.parse_args()
    from .workflow_demo import FixtureRuntime
    workflows = WorkflowService(FixtureRuntime([]), args.workspace)
    try:
        service = GenesisNextService(workflows)
        result = service.run_demo({"authorize": args.authorize}) if args.action == "demo" else getattr(service, args.action)()
        if args.output:
            require(not args.output.exists(), "Output exists; use a new evidence receipt path.", "GENESIS_OUTPUT")
            _atomic(args.output, encoded(result))
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
        if args.action == "demo" and result["experiment"]["qualification"]["correctness"] != "PASS":
            raise SystemExit(1)
    finally:
        workflows.close()


if __name__ == "__main__":
    main()
