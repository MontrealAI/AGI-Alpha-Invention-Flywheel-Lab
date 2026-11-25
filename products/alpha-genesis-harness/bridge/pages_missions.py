# SPDX-License-Identifier: Apache-2.0
"""Opt-in, scoped browser access to the owner's existing local HARNESS."""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets
import threading
from urllib.parse import urlsplit

from .adapters import BridgeError
from .workflows import RUN, digest, encoded


PREFIX = "/api/frontier-missions/"
PAGES_ORIGIN = "https://montrealai.github.io"
INTELLIGENCE = frozenset({"intelligence-status", "intelligence-discover", "intelligence-connect", "intelligence-reconnect"})
PREPARE = "prepare-intelligence"
SETUP_STATUS = "mission-intelligence-status"
OPERATIONS = INTELLIGENCE | {"pair", "submit", "get", "list", "pause", "resume", "cancel", "export", "disconnect", "release",
                             PREPARE, SETUP_STATUS}
COMMANDS = frozenset({"submit", "pause", "resume", "cancel", "disconnect", PREPARE})
COMMAND_ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
ALLOWED_HEADERS = frozenset({"content-type", "x-frontier-session", "x-frontier-command"})
DRAFT_FORMAT = "frontier-paired-mission-draft/v1"


def check(condition, code, status=400):
    if not condition:
        raise BridgeError(code, code, status)


def valid_origin(origin):
    if origin == PAGES_ORIGIN:
        return True
    if not isinstance(origin, str):
        return False
    try:
        value = urlsplit(origin)
        return bool(value.port) and origin == f"http://127.0.0.1:{value.port}"
    except ValueError:
        return False


class PagesMissions:
    """One opt-in browser session for one private, owner-selected workspace."""

    def __init__(self, service, *, role=None, origin=PAGES_ORIGIN, lease_minutes=60, turns=8,
                 actions=24, output_tokens=1024, announce, clock=None, intelligence=None, evidence_input=None, remote=False):
        check(valid_origin(origin), "MISSION_ORIGIN")
        check(type(lease_minutes) is int and 1 <= lease_minutes <= 1440, "MISSION_LEASE")
        check(type(turns) is int and 1 <= turns <= 100, "MISSION_TURNS")
        check(type(actions) is int and 1 <= actions <= 1000, "MISSION_ACTIONS")
        check(type(output_tokens) is int and 64 <= output_tokens <= 32768, "MISSION_OUTPUT_TOKENS")
        check(role is None or (isinstance(role, dict) and set(role) == {"provider", "model"}
              and all(isinstance(v, str) and 0 < len(v) <= 200 for v in role.values())), "MISSION_PROVIDER")
        if evidence_input is not None:
            required = {"schema", "ambition", "language", "requirements"}
            check(isinstance(evidence_input, dict) and required <= set(evidence_input) <= required | {"context", "tools"}
                  and evidence_input["schema"] == "frontier/local-mission-input-v1"
                  and isinstance(evidence_input["ambition"], str) and evidence_input["language"] in {"en", "fr"}
                  and isinstance(evidence_input["requirements"], dict)
                  and isinstance(evidence_input.get("context", ""), str), "MISSION_EVIDENCE_INPUT")
        self.service = service
        self.intelligence = intelligence
        self.remote = remote is True
        self.evidence_input = evidence_input
        self.origin = origin
        self.role = role
        self.budgets = {"max_turns": turns, "max_actions": actions, "max_output_tokens": output_tokens}
        self._selection = None
        self._selecting = False
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.expires = self.clock() + timedelta(minutes=lease_minutes)
        self.announce = announce
        self._lock = threading.RLock()
        self._session = None
        self._command_scope = None
        self._code = None
        self._commands = {}
        self._setup_tickets = {}
        self._mission_tickets = {}
        self._rotate_code()

    def _rotate_code(self):
        code = secrets.token_urlsafe(32)
        self._code = hashlib.sha256(code.encode()).digest()
        self.announce(code)

    def _verify(self, provided, expected, reason):
        check(isinstance(provided, str) and TOKEN.fullmatch(provided) and expected is not None
              and hmac.compare_digest(hashlib.sha256(provided.encode()).digest(), expected), reason, 403)

    def _admit_session(self, session):
        check(self.clock() < self.expires, "MISSION_LEASE_EXPIRED", 403)
        self._verify(session, self._session, "MISSION_SESSION")

    def _clear_tickets(self):
        self._setup_tickets.clear()
        self._mission_tickets.clear()

    def _remove_ticket(self, ident):
        old = self._mission_tickets.pop(ident, None)
        if old is not None:
            self._setup_tickets.pop(old, None)

    def _stage_response(self, row, issue=False):
        result = self._summary(self.service.stage_view(row))
        if issue and result["status"] == "awaiting_consent":
            self._remove_ticket(row["id"])
            ticket = secrets.token_urlsafe(32)
            hashed = hashlib.sha256(ticket.encode()).digest()
            self._setup_tickets[hashed] = {"id": row["id"], "revision": row["revision"], "scope": self._command_scope}
            self._mission_tickets[row["id"]] = hashed
            result["setup_ticket"] = ticket
        return result

    def _pending_review(self, ticket):
        check(self.remote and self._session is not None and self.clock() < self.expires,
              "MISSION_INTELLIGENCE_CONSENT", 403)
        check(isinstance(ticket, str) and TOKEN.fullmatch(ticket), "MISSION_SETUP_TICKET", 403)
        entry = self._setup_tickets.get(hashlib.sha256(ticket.encode()).digest())
        check(entry and entry["scope"] == self._command_scope, "MISSION_SETUP_TICKET", 403)
        row = self.service.stage_record(entry["id"])
        check(row and row["revision"] == entry["revision"]
              and self.service.stage_view(row)["status"] == "awaiting_consent", "MISSION_STAGE_CHANGED", 409)
        return entry, row

    def _profile_review(self, entry, profile):
        scope = entry["scope"]
        return self.service.review_profile(entry["id"], profile, deadline=self.expires, budgets=self.budgets,
                                           clock=self.clock, session_current=lambda: scope == self._command_scope)

    def review(self, ticket, profile=None):
        """Native-only review, behind the local companion's own authentication."""
        from .paired_missions import DATA_SCOPE, OPERATIONS
        with self._lock:
            entry, row = self._pending_review(ticket)
            reviewed = self._profile_review(entry, profile) if profile is not None else None
            if reviewed:
                entry["review"] = reviewed
            else:
                entry.pop("review", None)
            return {**self._stage_response(row), "revision": row["revision"],
                    "profile": reviewed.native_profile() if reviewed else None,
                    "scope": reviewed.scope() if reviewed else {**self.budgets, "data": DATA_SCOPE,
                        "operations": list(OPERATIONS), "expires_at": self.expires.isoformat()}}

    def approve(self, body):
        """Consume an explicitly reviewed, native-only approval once."""
        with self._lock:
            check(isinstance(body, dict) and set(body) == {"ticket", "revision", "profile", "consent"}
                  and body["consent"] is True, "MISSION_INTELLIGENCE_CONSENT", 403)
            entry, row = self._pending_review(body["ticket"])
            check(body["revision"] == row["revision"], "MISSION_STAGE_CHANGED", 409)
            old = entry.get("review")
            check(old and body["profile"] == old.id, "MISSION_PROFILE_REVIEW", 409)
            current = self._profile_review(entry, body["profile"])
            check(old.matches(current), "MISSION_PROFILE_CHANGED", 409)
            self._remove_ticket(row["id"])
            return self._summary(self.service.authorize(row, current))

    def revoke(self, ident):
        """Native-only revocation of a staged or actively authorized mission."""
        with self._lock:
            check(self.remote and isinstance(ident, str) and RUN.fullmatch(ident), "MISSION_INPUT")
            row = self.service.stage_record(ident)
            check(row, "MISSION_NOT_FOUND", 404)
            self._remove_ticket(ident)
            return self._stage_response(self.service.revoke_permit(ident))

    def _scope(self, *, require_ready=False):
        budgets = self.budgets.copy()
        role = self.role
        if self._selection is not None:
            current = self.intelligence.current()
            if current and all(current.get(key) == value for key, value in self._selection.items()):
                role = self._selection
                budgets["max_output_tokens"] = min(budgets["max_output_tokens"], current["max_output_tokens"])
            else:
                role = None
        if require_ready:
            check(not self._selecting, "MISSION_INTELLIGENCE_BUSY", 409)
            check(role is not None, "MISSION_INTELLIGENCE_REQUIRED", 409)
        return {**budgets, **(role or {})}

    def _intelligence_action(self, operation, body, session):
        action = operation.removeprefix("intelligence-")
        with self._lock:
            self._admit_session(session)
            check(self.intelligence is not None, "MISSION_INTELLIGENCE_UNAVAILABLE", 404)
            if action == "status":
                check(not body, "MISSION_INPUT")
                return {**self.intelligence.status(), "scope": self._scope(), "native_api_setup": self.remote}
            check(not self._selecting, "MISSION_INTELLIGENCE_BUSY", 409)
            selecting = action in {"connect", "reconnect"}
            if selecting:
                check(not any(row["status"] == "running" or row.get("worker_active")
                              for row in self.service.list()["runs"]), "MISSION_ACTIVE", 409)
            self._selecting = True

        def admit():
            with self._lock:
                self._admit_session(session)

        try:
            if selecting:
                result = getattr(self.intelligence, action)(body, admit=admit)
            else:
                result = self.intelligence.discover(body, admit=admit)
            with self._lock:
                self._admit_session(session)
                if selecting:
                    selection = result["selection"]
                    self._selection = {key: selection[key] for key in ("provider", "model")}
                return {**result, "scope": self._scope()}
        finally:
            with self._lock:
                self._selecting = False

    def admit(self, *, host, expected_host, origin, operation, preflight=False, method=None, headers=None):
        check(host == [expected_host], "MISSION_HOST", 403)
        check(origin == [self.origin] and operation in OPERATIONS, "MISSION_ORIGIN", 403)
        if preflight:
            check(method == ["POST"], "MISSION_METHOD", 403)
            check(len(headers) <= 1 and set((headers[0].lower().replace(" ", "").split(",") if headers else ()))
                  <= ALLOWED_HEADERS, "MISSION_HEADERS", 403)

    @staticmethod
    def _summary(state):
        events = []
        journal = state.get("events", [])
        for item in journal[-18:]:
            detail = item.get("detail", {})
            event = {key: item[key] for key in ("index", "at", "kind")}
            for key in ("tool", "reason", "code", "usage", "provider", "model", "qualification"):
                value = detail.get(key)
                if value is not None:
                    event[key] = value[:300] if isinstance(value, str) else value
            if item["kind"] == "tool_completed" and isinstance(detail.get("outcome"), dict):
                outcome = detail["outcome"]
                event["operation_executed"] = outcome.get("operation_executed", True)
                for key in ("name", "artifact", "disposition", "status", "sha256", "reason", "input_origin"):
                    if isinstance(outcome.get(key), str):
                        event[key] = outcome[key][:300]
                for key in ("output", "result", "rows"):
                    if key in outcome:
                        event["preview"] = encoded(outcome[key])[:2048].decode("utf-8", errors="ignore")
                        break
            events.append(event)
        artifacts = [{"name": name, "sha256": row.get("sha256"), "kind": row.get("kind")}
                     for name, row in list(state.get("artifacts", {}).items())[-24:]]
        verification = state.get("verification", {})
        proposal = next((item["detail"].get("summary", "")[:1500] for item in reversed(journal)
                         if item["kind"] == "route_proposed"), "")
        return {"id": state["id"], "ambition": state["objective"], "language": state.get("language", "en"),
                "original_ambition": state.get("original_ambition", state["objective"]),
                "parent_run_id": state.get("parent_run_id"),
                "status": state["status"], "phase": state.get("phase"), "worker_active": state.get("worker_active", False),
                "expires_at": state.get("expires_at"), "qualification": state.get("qualification"),
                "verification": {"passed": verification.get("passed", False), "scope": verification.get("scope")},
                "evidence": state.get("evidence"), "outcome": state.get("outcome"),
                "actions": state.get("actions", 0), "model_calls": state.get("model_calls", 0), "proposal": proposal,
                "events": events, "artifacts": artifacts}

    def _mission_spec(self, ambition, language):
        spec = {"ambition": ambition, "language": language, **self._scope(require_ready=True),
                "expires_at": self.expires.isoformat()}
        manifest = self.evidence_input
        if manifest and manifest["ambition"] == ambition and manifest["language"] == language:
            spec.update({key: manifest[key] for key in ("requirements", "context", "tools") if key in manifest})
        selection = self.intelligence.current() if self._selection else None
        if selection and selection.get("mode") == "hybrid":
            preference = ("The operator prefers scoped, verified tools when they satisfy the actual mission. "
                          "Use the local model for interpretation, missing work and repair. "
                          "Check inputs and applicability before using an existing result.")
            spec["context"] = "\n".join(part for part in (preference, spec.get("context", "")) if part)
        return spec

    def _ambition(self, body, command):
        check(set(body) in ({"ambition", "language"}, {"ambition", "language", "previous"}), "MISSION_INPUT")
        ambition = body["ambition"]
        check(isinstance(ambition, str) and ambition.strip() and len(ambition.encode()) <= 24 * 1024,
              "MISSION_AMBITION")
        check(body["language"] in ("en", "fr"), "MISSION_LANGUAGE")
        ident = "wf_" + hashlib.sha256(("frontier-pages-mission-v1:" + command).encode()).hexdigest()[:24]
        if "previous" in body:
            previous = body["previous"]
            check(isinstance(previous, str) and RUN.fullmatch(previous) and previous != ident, "MISSION_INPUT")
        return ident

    def _submit(self, body, command):
        ident = self._ambition(body, command)
        check(not self.remote or not self.service.stage_record(ident), "MISSION_IDENTITY_CONFLICT", 409)
        spec = self._mission_spec(body["ambition"], body["language"])
        previous = body.get("previous")
        if previous:
            staging = self.service.stage_record(previous) if self.remote else None
            if staging:
                view = self.service.revise_from_stage(staging, spec, ident)
                self.service.supersede_stage(previous)
                self._remove_ticket(previous)
            else:
                view = self.service.revise(previous, spec, identity=ident)
        else:
            view = self.service.submit(spec, identity=ident)
        if view["status"] == "ready" and view.get("model_calls", 0) == 0 and not view.get("worker_active"):
            view = self.service.start(view["id"])
        return self._summary(view)

    def _prepare(self, body, command):
        check(self.remote, "MISSION_INTELLIGENCE_UNAVAILABLE", 404)
        ident = self._ambition(body, command)
        row = self.service.stage(ident, body)
        if body.get("previous"):
            self._remove_ticket(body["previous"])
        return self._stage_response(row, issue=True)

    def _get(self, ident, issue=False):
        row = self.service.stage_record(ident) if self.remote else None
        if issue:
            check(row, "MISSION_NOT_FOUND", 404)
        return self._stage_response(row, issue=issue) if row else self._summary(self.service.get(ident))

    def _list(self):
        runs = self.service.list()["runs"]
        if self.remote:
            by_id = {row["id"]: row for row in runs}
            for staged in self.service.stage_records():
                current = by_id.get(staged["id"])
                if current:
                    if staged["status"] in {"superseded", "cancelled", "revoked"}:
                        current["status"] = staged["status"]
                    elif current["status"] in {"ready", "paused", "interrupted"} and not current["worker_active"] and not self.service.has_permit(current["id"]):
                        current["status"] = "awaiting_consent"
                else:
                    by_id[staged["id"]] = {"id": staged["id"], "objective": staged["body"]["ambition"],
                                           "status": staged["status"], "updated_at": staged["created_at"]}
            runs = sorted(by_id.values(), key=lambda row: row.get("updated_at", ""))
        return {"missions": [{"id": row["id"], "ambition": row.get("objective", ""), "status": row["status"]}
                             for row in runs[-40:]]}

    def _resume(self, ident):
        view = self.service.get(ident)
        spec = view["spec"]
        if self.remote and self.service.stage_record(ident):
            check(spec["local_only"] is False and self.service.has_permit(ident), "MISSION_INTELLIGENCE_CONSENT", 403)
            return self.service.resume(ident)
        scope = self._scope(require_ready=True)
        role = {key: scope[key] for key in ("provider", "model")}
        check(spec["local_only"] is True and spec["roles"] == {"builder": role}
              and "retrieve_source" not in spec["tool_permissions"] and spec["max_operations"] <= 10_000
              and spec["max_iterations"] <= scope["max_turns"]
              and spec["max_actions"] <= scope["max_actions"]
              and spec["max_output_tokens"] <= scope["max_output_tokens"]
              and datetime.fromisoformat(view["expires_at"]) <= self.expires, "MISSION_FRESH_SCOPE", 403)
        return self.service.resume(ident)

    def import_local(self, archive):
        """Restore historical work from an owner-supplied file, paused under this policy."""
        if self.remote and isinstance(archive, dict) and archive.get("schema") == DRAFT_FORMAT:
            draft = archive.get("mission")
            check(isinstance(draft, dict) and {"ambition", "language", "original_ambition"} <= set(draft), "MISSION_INPUT")
            body = {key: draft[key] for key in ("ambition", "language")}
            ident = self._ambition(body, secrets.token_hex(16))
            original = draft["original_ambition"]
            check(isinstance(original, str) and original.strip() and len(original.encode()) <= 24 * 1024, "MISSION_INPUT")
            return self._stage_response(self.service.stage(ident, body, imported_original=original))
        check(isinstance(archive, dict) and isinstance(archive.get("state"), dict), "MISSION_INPUT")
        old = archive["state"].get("spec")
        check(isinstance(old, dict) and isinstance(old.get("mission"), dict), "MISSION_INPUT")
        spec = self._mission_spec(old.get("objective"), old["mission"].get("language"))
        return self._summary(self.service.import_archive(archive, spec))

    def dispatch(self, operation, body, *, session=None, command=None):
        if operation in INTELLIGENCE:
            return self._intelligence_action(operation, body, session)
        with self._lock:
            check(self.clock() < self.expires, "MISSION_LEASE_EXPIRED", 403)
            if operation == "pair":
                check(set(body) == {"code"}, "MISSION_INPUT")
                self._verify(body["code"], self._code, "MISSION_PAIRING")
                token = secrets.token_urlsafe(32)
                self._session = hashlib.sha256(token.encode()).digest()
                self._command_scope = secrets.token_hex(12)
                self._commands.clear()
                self._clear_tickets()
                self._rotate_code()
                return {"session": token, "command_scope": self._command_scope,
                        "expires_at": self.expires.isoformat(), "scope": self._scope(),
                        "intelligence": self.intelligence.status() if self.intelligence is not None else None}
            self._verify(session, self._session, "MISSION_SESSION")
            if operation == "release":
                check(not body, "MISSION_INPUT")
                self._session = self._command_scope = None
                self._clear_tickets()
                return {"released": True}
            if operation in COMMANDS:
                check(isinstance(command, str) and command.startswith(self._command_scope + "."),
                      "MISSION_COMMAND_SCOPE", 403)
                command = command.split(".", 1)[1]
                check(COMMAND_ID.fullmatch(command), "MISSION_COMMAND")
                signature = digest({"operation": operation, "body": body})
                previous = self._commands.get(command)
                if previous:
                    check(previous[0] == signature, "MISSION_COMMAND_CHANGED", 409)
                    ident = previous[1]
                    return self._get(ident, issue=operation == PREPARE) if ident else {"disconnected": True}
                check(len(self._commands) < 4096, "MISSION_COMMAND_CAPACITY", 429)
            if operation == "submit":
                result = self._submit(body, command)
            elif operation == PREPARE:
                result = self._prepare(body, command)
            elif operation == "list":
                check(not body, "MISSION_INPUT")
                return self._list()
            elif operation == "disconnect":
                check(not body, "MISSION_INPUT")
                self._session = self._command_scope = None
                self._clear_tickets()
                for row in self.service.list()["runs"]:
                    if row["status"] == "running" or row.get("worker_active"):
                        self.service.pause(row["id"])
                result = {"disconnected": True}
            else:
                check(operation in {"get", "pause", "resume", "cancel", "export", SETUP_STATUS}
                      and set(body) == {"id"} and isinstance(body["id"], str) and RUN.fullmatch(body["id"]), "MISSION_INPUT")
                ident = body["id"]
                staged = self.service.stage_record(ident) if self.remote else None
                if operation in {"get", SETUP_STATUS}:
                    result = self._get(ident, issue=operation == SETUP_STATUS)
                elif staged and operation == "cancel":
                    self._remove_ticket(ident)
                    result = self._stage_response(self.service.cancel_stage(ident))
                elif staged and operation in {"pause", "resume"}:
                    stage = self.service.stage_view(staged)["status"]
                    check(stage not in {"superseded", "cancelled", "revoked"}, "MISSION_STATE", 409)
                    check(stage != "awaiting_consent", "MISSION_INTELLIGENCE_CONSENT", 403)
                    action = self._resume if operation == "resume" else self.service.pause
                    result = self._summary(action(ident))
                elif staged and operation == "export" and not self.service.has_execution(ident):
                    result = {"schema": DRAFT_FORMAT, "mission": self._stage_response(staged)}
                else:
                    action = self._resume if operation == "resume" else getattr(self.service, operation)
                    view = action(ident)
                    result = view if operation == "export" else self._summary(view)
            if operation in COMMANDS:
                # Submission identities are derived from the command UUID and are also durable in HARNESS.
                self._commands[command] = (signature, result.get("id"))
            return result
