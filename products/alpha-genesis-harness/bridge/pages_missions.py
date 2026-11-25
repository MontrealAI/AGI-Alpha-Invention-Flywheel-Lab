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
OPERATIONS = frozenset({"pair", "submit", "get", "list", "pause", "resume", "cancel", "export", "disconnect", "release"})
COMMANDS = frozenset({"submit", "pause", "resume", "cancel", "disconnect"})
COMMAND_ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
ALLOWED_HEADERS = frozenset({"content-type", "x-frontier-session", "x-frontier-command"})


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

    def __init__(self, service, *, role, origin=PAGES_ORIGIN, lease_minutes=60, turns=8,
                 actions=24, output_tokens=1024, announce, clock=None):
        check(valid_origin(origin), "MISSION_ORIGIN")
        check(type(lease_minutes) is int and 1 <= lease_minutes <= 1440, "MISSION_LEASE")
        check(type(turns) is int and 1 <= turns <= 100, "MISSION_TURNS")
        check(type(actions) is int and 1 <= actions <= 1000, "MISSION_ACTIONS")
        check(type(output_tokens) is int and 64 <= output_tokens <= 32768, "MISSION_OUTPUT_TOKENS")
        check(isinstance(role, dict) and set(role) == {"provider", "model"}
              and all(isinstance(v, str) and 0 < len(v) <= 200 for v in role.values()), "MISSION_PROVIDER")
        self.service = service
        self.origin = origin
        self.scope = {**role, "max_turns": turns, "max_actions": actions, "max_output_tokens": output_tokens}
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.expires = self.clock() + timedelta(minutes=lease_minutes)
        self.announce = announce
        self._lock = threading.RLock()
        self._session = None
        self._command_scope = None
        self._code = None
        self._commands = {}
        self._rotate_code()

    def _rotate_code(self):
        code = secrets.token_urlsafe(32)
        self._code = hashlib.sha256(code.encode()).digest()
        self.announce(code)

    def _verify(self, provided, expected, reason):
        check(isinstance(provided, str) and TOKEN.fullmatch(provided) and expected is not None
              and hmac.compare_digest(hashlib.sha256(provided.encode()).digest(), expected), reason, 403)

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
                for key in ("name", "artifact", "disposition", "status", "sha256", "reason"):
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
                "actions": state.get("actions", 0), "model_calls": state.get("model_calls", 0), "proposal": proposal,
                "events": events, "artifacts": artifacts}

    def _submit(self, body, command):
        check(set(body) in ({"ambition", "language"}, {"ambition", "language", "previous"}), "MISSION_INPUT")
        ambition = body["ambition"]
        check(isinstance(ambition, str) and ambition.strip() and len(ambition.encode()) <= 24 * 1024,
              "MISSION_AMBITION")
        check(body["language"] in ("en", "fr"), "MISSION_LANGUAGE")
        ident = "wf_" + hashlib.sha256(("frontier-pages-mission-v1:" + command).encode()).hexdigest()[:24]
        spec = {"ambition": ambition, "language": body["language"], **self.scope, "expires_at": self.expires.isoformat()}
        if "previous" in body:
            previous = body["previous"]
            check(isinstance(previous, str) and RUN.fullmatch(previous) and previous != ident, "MISSION_INPUT")
            view = self.service.revise(previous, spec, identity=ident)
        else:
            view = self.service.submit(spec, identity=ident)
        if view["status"] == "ready" and view.get("model_calls", 0) == 0 and not view.get("worker_active"):
            view = self.service.start(view["id"])
        return self._summary(view)

    def _resume(self, ident):
        view = self.service.get(ident)
        spec = view["spec"]
        role = {key: self.scope[key] for key in ("provider", "model")}
        check(spec["local_only"] is True and spec["roles"] == {"builder": role}
              and "retrieve_source" not in spec["tool_permissions"] and spec["max_operations"] <= 10_000
              and spec["max_iterations"] <= self.scope["max_turns"]
              and spec["max_actions"] <= self.scope["max_actions"]
              and spec["max_output_tokens"] <= self.scope["max_output_tokens"]
              and datetime.fromisoformat(view["expires_at"]) <= self.expires, "MISSION_FRESH_SCOPE", 403)
        return self.service.resume(ident)

    def import_local(self, archive):
        """Restore historical work from an owner-supplied file, paused under this policy."""
        check(isinstance(archive, dict) and isinstance(archive.get("state"), dict), "MISSION_INPUT")
        old = archive["state"].get("spec")
        check(isinstance(old, dict) and isinstance(old.get("mission"), dict), "MISSION_INPUT")
        spec = {"ambition": old.get("objective"), "language": old["mission"].get("language"),
                **self.scope, "expires_at": self.expires.isoformat()}
        return self._summary(self.service.import_archive(archive, spec))

    def dispatch(self, operation, body, *, session=None, command=None):
        with self._lock:
            check(self.clock() < self.expires, "MISSION_LEASE_EXPIRED", 403)
            if operation == "pair":
                check(set(body) == {"code"}, "MISSION_INPUT")
                self._verify(body["code"], self._code, "MISSION_PAIRING")
                token = secrets.token_urlsafe(32)
                self._session = hashlib.sha256(token.encode()).digest()
                self._command_scope = secrets.token_hex(12)
                self._commands.clear()
                self._rotate_code()
                return {"session": token, "command_scope": self._command_scope,
                        "expires_at": self.expires.isoformat(), "scope": self.scope}
            self._verify(session, self._session, "MISSION_SESSION")
            if operation == "release":
                check(not body, "MISSION_INPUT")
                self._session = self._command_scope = None
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
                    return self._summary(self.service.get(ident)) if ident else {"disconnected": True}
                check(len(self._commands) < 4096, "MISSION_COMMAND_CAPACITY", 429)
            if operation == "submit":
                result = self._submit(body, command)
            elif operation == "list":
                check(not body, "MISSION_INPUT")
                return {"missions": [{"id": row["id"], "ambition": row.get("objective", ""), "status": row["status"]}
                                     for row in self.service.list()["runs"][-40:]]}
            elif operation == "disconnect":
                check(not body, "MISSION_INPUT")
                for row in self.service.list()["runs"]:
                    if row["status"] == "running" or row.get("worker_active"):
                        self.service.pause(row["id"])
                self._session = self._command_scope = None
                result = {"disconnected": True}
            else:
                check(operation in {"get", "pause", "resume", "cancel", "export"}
                      and set(body) == {"id"} and isinstance(body["id"], str) and RUN.fullmatch(body["id"]), "MISSION_INPUT")
                action = self._resume if operation == "resume" else getattr(self.service, operation)
                view = action(body["id"])
                result = view if operation == "export" else self._summary(view)
            if operation in COMMANDS:
                # Submission identities are derived from the command UUID and are also durable in HARNESS.
                self._commands[command] = (signature, result.get("id"))
            return result
