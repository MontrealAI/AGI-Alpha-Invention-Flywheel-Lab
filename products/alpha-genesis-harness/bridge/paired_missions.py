# SPDX-License-Identifier: Apache-2.0
"""Native consent and durable mission staging for the paired HARNESS."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac

from .adapters import BridgeError, strict_json
from .universal_missions import PROPOSE_OUTCOME, UniversalMissionService, expires
from .workflows import DEFAULT_TOOLS, MAX_STATE, RUN, TERMINAL, _atomic, _regular, digest, encoded


DATA_SCOPE = "ambition-and-mission-generated-context"
OPERATIONS = ("model-inference", "local-bounded-tools")
STAGE_FORMAT = "frontier-paired-staging/v1"


def require(condition, code, status=403):
    if not condition:
        raise BridgeError(code, code, status)


@dataclass(frozen=True)
class _ProfileReview:
    id: str
    route: object = field(repr=False)
    identity: object = field(repr=False)
    expires_at: datetime
    turns: int
    actions: int
    output_tokens: int
    clock: object = field(repr=False)
    session_current: object = field(repr=False)

    @property
    def role(self):
        return {"provider": self.route.provider, "model": self.route.model}

    def matches(self, other):
        return (self.id == other.id and self.identity == other.identity and self.role == other.role
                and self.route.binding == other.route.binding and self.route.runtime is other.route.runtime
                and self.scope() == other.scope())

    def current(self):
        if self.clock() >= self.expires_at or not self.session_current() or not self.route.valid():
            return False
        try:
            return self.route.runtime.allow_paid and self.route.runtime.execution_identity(self.route.provider) == self.identity
        except BridgeError:
            return False

    def scope(self):
        return {"mode": self.route.category, "data": DATA_SCOPE, "operations": list(OPERATIONS),
                "expires_at": self.expires_at.isoformat(), "max_turns": self.turns, "max_actions": self.actions,
                "max_output_tokens": self.output_tokens}

    def native_profile(self):
        return {"id": self.id, "category": self.route.category, "label": self.route.label, "model": self.route.model} | {
            key: getattr(self.route, key) for key in ("project", "usage") if getattr(self.route, key, None) is not None}


@dataclass(frozen=True)
class _Permit:
    review: _ProfileReview = field(repr=False)
    spec_hash: str


class _RemoteDispatch:
    def __init__(self, review, cancelled, redact):
        self.review = review
        self.runtime = review.route.runtime
        self.cancelled = cancelled
        self.redact = redact

    def __getattr__(self, name):
        return getattr(self.runtime, name)

    def generate(self, data, on_event=None, _admission=None):
        try:
            require(not self.cancelled(), "MISSION_INTELLIGENCE_CONSENT", 409)
            require(self.redact(data["prompt"]) == data["prompt"], "MISSION_INPUT_SECRET")
        except BridgeError as error:
            error.pre_dispatch = True
            raise
        result = self.runtime.generate(data, on_event=on_event, _admission=_admission)
        require(self.runtime.execution_identity(self.review.route.provider) == self.review.identity,
                "EXECUTION_IDENTITY_CHANGED", 409)
        result["text"] = self.redact(result["text"])
        if isinstance(result.get("reported_model"), str):
            result["reported_model"] = self.redact(result["reported_model"])
        return result


class PairedMissionService(UniversalMissionService):
    """Run the existing workflow with a separate, revocable remote lease."""

    def __init__(self, runtime, private_root, *, server_source_sha256=None, provider_profiles=None,
                 profile_redact=None):
        self._permits = {}
        self.provider_profiles = provider_profiles
        self.profile_redact = profile_redact
        super().__init__(runtime, private_root, server_source_sha256=server_source_sha256, allow_remote=True)
        self.staging_path = self.root / "paired-staging.json"
        self._stage_lock = self._lock("paired-staging")

    def redact_private(self, text):
        text = self.runtime.redact(text)
        return self.profile_redact(text) if self.profile_redact else text

    def _stage_records(self):
        if not (self.staging_path.exists() or self.staging_path.is_symlink()):
            return {}
        data = strict_json(_regular(self.staging_path, MAX_STATE))
        require(isinstance(data, dict) and set(data) == {"records", "mac"} and isinstance(data["records"], dict)
                and isinstance(data["mac"], str)
                and hmac.compare_digest(data["mac"], self._stage_mac(data["records"])), "MISSION_STAGING_INTEGRITY", 409)
        return data["records"]

    def _stage_mac(self, records):
        return hmac.new(self._key, encoded([STAGE_FORMAT, records]), hashlib.sha256).hexdigest()

    def _save_stages(self, records):
        raw = encoded({"records": records, "mac": self._stage_mac(records)})
        require(len(raw) <= MAX_STATE, "MISSION_STAGING_CAPACITY", 429)
        _atomic(self.staging_path, raw)

    def stage_records(self):
        return list(self._stage_records().values())

    def stage_record(self, ident):
        return self._stage_records().get(ident)

    def has_execution(self, ident):
        require(isinstance(ident, str) and RUN.fullmatch(ident), "MISSION_INPUT", 400)
        file = self.root / ident / "state.json"
        return file.exists() or file.is_symlink()

    def stage(self, ident, body):
        require("documents" not in body, "MISSION_DOCUMENT_LOCAL_ONLY")
        with self._stage_lock:
            records = self._stage_records()
            earlier = records.get(ident)
            if earlier:
                require(earlier["body"] == body, "MISSION_COMMAND_CHANGED", 409)
                return earlier
            require(not self.has_execution(ident), "MISSION_IDENTITY_CONFLICT", 409)
            previous = body.get("previous")
            original = body.get("original_ambition", body["ambition"])
            if previous:
                require(previous != ident, "MISSION_INPUT", 400)
                old = records.get(previous)
                if old:
                    original = old["original_ambition"]
                else:
                    original = self.get(previous)["original_ambition"]
            self.check_member_text(body["ambition"], original, body.get("instruction", ""))
            row = {"id": ident, "body": body, "original_ambition": original, "status": "awaiting_consent",
                   "revision": digest([ident, body, original]), "created_at": datetime.now(timezone.utc).isoformat()}
            records[ident] = row
            self._save_stages(records)
            return row

    def supersede_stage(self, ident):
        with self._stage_lock:
            records = self._stage_records()
            row = records.get(ident)
            if not row or row["status"] != "awaiting_consent":
                return
            active = self.has_execution(ident)
            if active and self.get(ident)["status"] in TERMINAL:
                return
            row["status"] = "superseded"
            self._save_stages(records)
            if active:
                permit = self._permits.pop(ident, None)
                self._cancel_revoked_dispatch(self.cancel(ident), permit)

    def cancel_stage(self, ident):
        with self._stage_lock:
            records = self._stage_records()
            row = records.get(ident)
            has_execution = self.has_execution(ident)
            permit = self._permits.pop(ident, None)
            if has_execution and self.get(ident)["status"] in TERMINAL:
                return row
            if row and row["status"] == "awaiting_consent":
                row["status"] = "cancelled"
                self._save_stages(records)
            if has_execution:
                view = self.cancel(ident)
                self._cancel_revoked_dispatch(view, permit)
            return row

    def stage_view(self, row):
        ident, body = row["id"], row["body"]
        if self.has_execution(ident):
            view = self.get(ident)
            if row["status"] in {"superseded", "cancelled", "revoked"}:
                view.update(status=row["status"], authority=row["status"])
            elif view["status"] not in TERMINAL and not self.has_permit(ident) and not view["worker_active"]:
                view.update(status="awaiting_consent", authority="approval_required")
            return view
        return {"id": ident, "objective": body["ambition"], "original_ambition": row["original_ambition"],
                "language": body["language"], "parent_run_id": body.get("previous"), "status": row["status"],
                "instruction": body.get("instruction", ""),
                "actions": 0, "model_calls": 0, "events": [], "artifacts": {}, "worker_active": False}

    def review_profile(self, ident, profile, *, deadline, budgets, clock, session_current):
        require(isinstance(profile, str) and 0 < len(profile) <= 200, "MISSION_PROFILE", 400)
        require(self.provider_profiles is not None, "MISSION_PROFILE_NOT_READY", 409)
        route = self.provider_profiles(profile)
        require(route is not None and route.category == "api" and route.provider not in {"chatgpt", "codex"}
                and route.runtime.provider(route.provider).remote, "MISSION_PROFILE_NOT_READY", 409)
        if route.expires_at is not None:
            expiry = expires(route.expires_at) if isinstance(route.expires_at, str) else route.expires_at
            deadline = min(deadline, expiry)
        require(route.valid() and clock() < deadline, "MISSION_PROFILE_NOT_READY", 409)
        identity = route.runtime.execution_identity(route.provider)
        turns = min(budgets["max_turns"], route.max_turns)
        tokens = min(budgets["max_output_tokens"], route.max_output_tokens)
        actions = budgets["max_actions"]
        if self.has_execution(ident):
            old = self.get(ident)
            spec = old["spec"]
            require(old["status"] not in TERMINAL and not old["worker_active"], "MISSION_STATE", 409)
            require(spec["local_only"] is False and spec["roles"] == {"builder": {"provider": route.provider, "model": route.model}}
                    and spec["max_iterations"] <= turns and spec["max_output_tokens"] <= tokens
                    and spec["max_actions"] <= actions, "MISSION_FRESH_SCOPE")
            turns, actions, tokens = spec["max_iterations"], spec["max_actions"], spec["max_output_tokens"]
        return _ProfileReview(profile, route, identity, deadline, turns, actions, tokens, clock, session_current)

    def revise_from_stage(self, prior, spec, ident):
        original = {"id": prior["id"], "spec": {"mission": {"original_ambition": prior["original_ambition"]}}}
        return self._submit(self._workflow_spec(spec, prior=original), ident)

    def check_member_text(self, *values):
        require(all(self.redact_private(value) == value for value in set(values) if value), "MISSION_INPUT_SECRET")

    def authorize(self, row, review):
        with self._stage_lock:
            ident, body = row["id"], row["body"]
            require(self.stage_record(ident) == row and row["status"] == "awaiting_consent", "MISSION_STAGE_CHANGED", 409)
            require(review.current(), "MISSION_PROFILE_NOT_READY", 409)
            instruction = body.get("instruction", "")
            self.check_member_text(body["ambition"], row["original_ambition"], instruction)
            if not self.has_execution(ident):
                inputs = {"ambition": body["ambition"], "language": body["language"], **review.role,
                          "expires_at": review.expires_at.isoformat(), "max_turns": review.turns, "max_actions": review.actions,
                          "max_output_tokens": review.output_tokens, "local_only": False, "tools": DEFAULT_TOOLS,
                          "member_workspace": True, "instruction": instruction}
                predecessor = body.get("previous")
                if predecessor:
                    self.revise_from_stage({"id": predecessor, "original_ambition": row["original_ambition"]}, inputs, ident)
                else:
                    self.submit(inputs, identity=ident, original_ambition=row["original_ambition"])
            with self._lock(ident):
                state = self._load(ident)
                spec = state["spec"]
                mission = spec["mission"]
                tools = [*DEFAULT_TOOLS, PROPOSE_OUTCOME] if mission.get("member_workspace") else DEFAULT_TOOLS
                require(state["status"] not in TERMINAL and ident not in self._workers and ident not in self._inflight
                        and ident not in self._waiting, "MISSION_STATE", 409)
                require(spec["objective"] == body["ambition"] and mission["language"] == body["language"]
                        and mission["original_ambition"] == row["original_ambition"]
                        and mission.get("parent_run_id") == body.get("previous") and spec["local_only"] is False
                        and spec["roles"] == {"builder": review.role} and spec["context"] == ""
                        and mission.get("instruction", "") == instruction and not mission.get("documents")
                        and not mission.get("previous_work") and mission["requirements"] == {} and spec["tool_permissions"] == tools,
                        "MISSION_FRESH_SCOPE")
                self._event(state, "remote_mission_approved", {"profile": review.id, **review.scope()})
                self._save(state)
                self._permits[ident] = _Permit(review, state["spec_hash"])
                return self.resume(ident)

    def has_permit(self, ident):
        permit = self._permits.get(ident)
        return permit is not None and permit.review.current()

    def revoke_permit(self, ident):
        with self._stage_lock:
            records = self._stage_records()
            row = records.get(ident)
            if row["status"] != "awaiting_consent":
                return row
            active = self.has_execution(ident)
            permit = self._permits.pop(ident, None)
            if active and self.get(ident)["status"] in TERMINAL:
                return row
            row["status"] = "revoked"
            self._save_stages(records)
            if active:
                self._cancel_revoked_dispatch(self.pause(ident), permit)
            return row

    @staticmethod
    def _cancel_revoked_dispatch(view, permit):
        inflight = view.get("inflight")
        if permit and inflight:
            permit.review.route.runtime.cancel(inflight["run_id"])

    def _authority_stop(self, state):
        if state["spec"]["local_only"]:
            return super()._authority_stop(state)
        if state["status"] in TERMINAL:
            return None
        permit = self._permits.get(state["id"])
        if not permit or permit.spec_hash != state["spec_hash"] or not permit.review.current():
            return "paused"
        return None

    def _view(self, state):
        view = super()._view(state)
        permit = self._permits.get(state["id"])
        if permit and permit.review.current() and state["status"] not in TERMINAL:
            view.update(expires_at=permit.review.expires_at.isoformat(), authority="active")
        return view

    @contextmanager
    def _execution_slot(self, ident, route, cancelled):
        permit = self._permits.get(ident)
        with self._lock(ident):
            local_only = self._load(ident)["spec"]["local_only"]
        if local_only:
            with super()._execution_slot(ident, route, cancelled) as slot:
                yield slot
            return
        # A missing permit cannot fall back to the workspace runtime.
        require(permit and permit.review.role == route, "MISSION_INTELLIGENCE_CONSENT", 409)

        def interrupted():
            return self._permits.get(ident) is not permit or not permit.review.current() or cancelled()

        def redact(text):
            return self.redact_private(permit.review.route.runtime.redact(text))

        runtime = permit.review.route.runtime
        with runtime.execution_slot(route, cancelled=interrupted, expected_identity=permit.review.identity) as admission:
            yield _RemoteDispatch(permit.review, interrupted, redact), admission

    def _cancel_model(self, ident, run_id):
        permit = self._permits.get(ident)
        return permit.review.route.runtime.cancel(run_id) if permit else super()._cancel_model(ident, run_id)
