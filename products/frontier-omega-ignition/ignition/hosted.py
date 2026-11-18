"""Invitation-only studio served behind a dedicated operator-controlled TLS proxy."""
import argparse
import contextlib
import http.client
from http.server import ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sqlite3
import signal
import threading
import time
from urllib.parse import urlsplit

from .controller import Controller
from .dispatcher import Dispatcher
from .hosted_auth import Access, DAILY_ADMISSIONS, SESSION_TTL, private_dir, workspace_name
from .hosted_backup import exclusive, snapshot
from .server import Handler
from .store import PRODUCT, StateError, Store

COOKIE = "__Host-ignition_session"
MAX_MODEL_CALLS = 8
ALLOWED_RESOURCES = {
    "assets", "budget", "execution_strategy", "direct_method", "direct_after_research",
    "max_model_calls", "max_repairs", "max_initial_candidates", "research_economics", "choice_order", "commercial_case",
}
PUBLIC_FILES = {"/": "welcome.html", "/welcome": "welcome.html", "/studio": "studio.html",
                "/demo": "demo.html", "/studio.js": "studio.js", "/studio.css": "studio.css"}


def validate_origin(raw):
    parsed = urlsplit(raw)
    if (parsed.scheme != "https" or not re.fullmatch(r"[a-z0-9.-]+(?::[0-9]+)?", parsed.netloc)
            or not parsed.hostname or parsed.path or parsed.query or parsed.fragment
            or (parsed.port is not None and parsed.port < 1)):
        raise StateError("Set one exact HTTPS origin without a path or credentials")
    return raw


def checked_scope(body):
    mission = body.get("mission")
    if not isinstance(mission, dict):
        raise StateError("Supply a mission")
    resources = mission.setdefault("resources", {})
    if not isinstance(resources, dict) or set(resources) - ALLOWED_RESOURCES:
        raise StateError("The hosted service accepts only the approved data-only mission resources")
    calls = resources.setdefault("max_model_calls", MAX_MODEL_CALLS)
    repairs = resources.setdefault("max_repairs", 1)
    if type(calls) is not int or not 0 <= calls <= MAX_MODEL_CALLS or type(repairs) is not int or not 0 <= repairs <= 1:
        raise StateError("The hosted scope allows up to eight local model calls and one repair")
    # The provider is selected by the operator and cannot grant manual or paid model work.
    # Only audited built-in public monitors or explicitly supplied snapshots can be read.
    if "authority" in mission and not isinstance(mission["authority"], dict):
        raise StateError("Supply a permission object")


def model_ready():
    from .provider import ModelProvider
    identity = ModelProvider.from_environment().identity()
    if identity.get("mode") != "local" or not identity.get("declared_model_sha256"):
        return False
    kind = identity["provider"]
    address = urlsplit(identity["endpoint"])
    with contextlib.closing(http.client.HTTPConnection("127.0.0.1", address.port, timeout=2)) as conn:
        conn.request("GET", "/api/tags" if kind == "ollama" else "/v1/models")
        response = conn.getresponse()
        if response.status != 200:
            return False
        payload = response.read(256 * 1024 + 1)
        if len(payload) > 256 * 1024:
            return False
        data = json.loads(payload)
        if kind == "ollama":
            return any(isinstance(m, dict) and identity["model"] in (m.get("name"), m.get("model"))
                       and m.get("digest") == identity["declared_model_sha256"] for m in data.get("models", []))
        return any(isinstance(m, dict) and identity["model"] == m.get("id") for m in data.get("data", []))


def release_revision():
    repo = PRODUCT.parents[1]
    try:
        result = subprocess.run(["git", "-c", f"safe.directory={repo}", "-C", str(repo), "rev-parse", "HEAD"],
                                check=True, capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if re.fullmatch(r"[a-f0-9]{40}", value) else None


class HostedService(ThreadingHTTPServer):
    # Drain finite-timeout HTTP requests before releasing the backup exclusion lock.
    daemon_threads = False

    def __init__(self, access, origin, port=8784, *, controller_factory=Controller, workers=2, ready_probe=model_ready):
        self.access = access
        self.origin = validate_origin(origin)
        self.authority = urlsplit(self.origin).netloc
        with access.connection() as db:
            self.environment = db.execute("SELECT env FROM setting WHERE id=1").fetchone()[0]
        self.factory = controller_factory
        self.ready_probe = ready_probe
        self.controllers = {}
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(16)
        self.login_count = self.login_minute = 0
        self.service_lock = contextlib.ExitStack()
        self.service_lock.enter_context(exclusive(access.root, shared=True))
        try:
            self.service_lock.enter_context(exclusive(access.root, lockfile=".instance.lock"))
        except BaseException:
            self.service_lock.close()
            raise
        self.revision = release_revision()
        self.dispatcher = None
        try:
            super().__init__(("127.0.0.1", port), HostedHandler)
            self.dispatcher = Dispatcher(workers=workers)
            for tenant in access.tenants():
                if (access.workspaces / tenant / "missions.sqlite3").is_file():
                    self.dispatcher.recover(self.controller_for(tenant))
        except BaseException:
            self.server_close()
            raise

    def controller_for(self, tenant):
        workspace_name(tenant)
        with self.lock:
            if tenant not in self.controllers:
                self.controllers[tenant] = self.factory(Store(self.access.workspaces / tenant,
                                                              daily_admissions=DAILY_ADMISSIONS))
            return self.controllers[tenant]

    def allow_login(self):
        minute = int(time.monotonic() // 60)
        with self.lock:
            if minute != self.login_minute:
                self.login_count, self.login_minute = 0, minute
            self.login_count += 1
            return self.login_count <= 60

    def process_request(self, request, client_address):
        request.settimeout(15)
        if not self.slots.acquire(False):
            try:
                request.settimeout(1)
                request.sendall(b"HTTP/1.0 503 Service Unavailable\r\nContent-Length: 0\r\nRetry-After: 5\r\n\r\n")
            except OSError:
                pass
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def enqueue_for(self, ctrl, run_id, version, *, retry=False):
        self.dispatcher.enqueue(ctrl, run_id, version, retry=retry)

    def server_close(self):
        if hasattr(self, "socket"):
            super().server_close()
        if self.dispatcher is not None:
            self.dispatcher.close()
            self.dispatcher = None
        if self.service_lock is not None:
            self.service_lock.close()
            self.service_lock = None


class HostedHandler(Handler):
    def end_headers(self):
        if getattr(self, "set_cookie_value", None):
            self.send_header("Set-Cookie", self.set_cookie_value)
        self.send_header("Strict-Transport-Security", "max-age=31536000")
        super().end_headers()

    def _origin_allowed(self, parts, post):
        if self.headers.get_all("Host", []) != [self.server.authority]:
            return False
        origins = self.headers.get_all("Origin", [])
        if post:
            return origins == [self.server.origin] and self.headers.get("Sec-Fetch-Site") != "cross-site"
        if origins and origins != [self.server.origin]:
            return False
        return parts.path in PUBLIC_FILES or self.headers.get("Sec-Fetch-Site") != "cross-site"

    def _session_token(self):
        values = [value.strip().partition("=")[2] for line in self.headers.get_all("Cookie", [])
                  for value in line.split(";") if value.strip().partition("=")[0] == COOKIE]
        return values[0] if len(values) == 1 else ""

    def _run_controller(self):
        self.tenant = self.server.access.principal(self._session_token())
        return self.server.controller_for(self.tenant) if self.tenant else None

    def _validate_create(self, ctrl, body):
        checked_scope(body)

    def _validate_action(self, ctrl, run_id, action, body):
        if action == "respond":
            raise StateError("Manual model responses are disabled in hosted live missions")

    def _public_request(self, parts, post):
        path = parts.path
        if not post and path in PUBLIC_FILES:
            file = PUBLIC_FILES[path]
            media = {".js": "text/javascript", ".css": "text/css", ".html": "text/html"}[Path(file).suffix]
            self._send(200, media+"; charset=utf-8", (PRODUCT / "web" / file).read_bytes())
        elif not post and path in {"/healthz", "/readyz"}:
            try:
                with self.server.access.connection() as db:
                    db.execute("SELECT env FROM setting WHERE id=1").fetchone()
                ready = path == "/healthz" or self.server.ready_probe()
            except (OSError, ValueError, sqlite3.Error, http.client.HTTPException):
                ready = False
            self._json({"status": "ok" if ready else "unavailable", "revision": self.server.revision}, 200 if ready else 503)
        elif not post and path == "/api/session":
            self._json({"authenticated": bool(self.server.access.principal(self._session_token())),
                        "environment": self.server.environment})
        elif post and path == "/api/session":
            if not self.server.allow_login():
                self._json({"error": "Sign-in temporarily rate limited"}, 429)
                return True
            body = self.request_body
            token = self.server.access.exchange(body["invite"]) if set(body) == {"invite"} else None
            if not token:
                self._json({"error": "Invitation unavailable"}, 401)
                return True
            self.set_cookie_value = f"{COOKIE}={token}; Path=/; Max-Age={SESSION_TTL}; HttpOnly; Secure; SameSite=Strict"
            self._json({"authenticated": True, "environment": self.server.environment})
        elif post and path == "/api/logout":
            self.server.access.logout(self._session_token())
            self.set_cookie_value = f"{COOKIE}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict"
            self._json({"authenticated": False, "environment": self.server.environment})
        elif not post and path == "/api/examples":
            if not self._run_controller():
                self._json({"error": "Sign in to this workspace"}, 401)
            else:
                self._json({"examples": [json.loads((PRODUCT / "examples" / f"{n}.json").read_bytes())
                                        for n in ("integrity", "migration", "unsupported")]})
        elif not path.startswith("/api/"):
            self._json({"error": "Unknown route"}, 404)
        else:
            return False
        return True


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--environment", choices=("staging", "production"), required=True)
    actions = parser.add_subparsers(dest="command", required=True)
    serve = actions.add_parser("serve")
    serve.add_argument("--origin", required=True)
    serve.add_argument("--port", type=int, default=8784)
    for command in ("invite", "revoke"):
        actions.add_parser(command).add_argument("workspace")
    actions.add_parser("backup").add_argument("destination", type=Path)
    actions.add_parser("restore").add_argument("source", type=Path)
    actions.add_parser("status")
    args = parser.parse_args()
    if args.command in {"backup", "restore"}:
        restoring = args.command == "restore"
        n = snapshot(args.source if restoring else args.state,
                     args.state if restoring else args.destination, args.environment, restore=restoring)
        print(json.dumps({"action": args.command, "verified_files": n}))
        return
    if args.command in {"invite", "revoke", "status"}:
        with exclusive(private_dir(args.state), shared=True):
            access = Access(args.state, args.environment)
            manage(args, access)
        return
    with exclusive(private_dir(args.state), shared=True):
        access = Access(args.state, args.environment)
    manage(args, access)


def manage(args, access):
    if args.command == "invite":
        print(access.issue(args.workspace))
    elif args.command == "revoke":
        access.revoke(args.workspace)
    elif args.command == "status":
        with access.connection() as db:
            print(json.dumps({"workspaces": len(access.tenants()), "environment": args.environment,
                              "audit_events": db.execute("SELECT count(*) FROM audit").fetchone()[0]}))
    else:
        from .provider import ModelProvider
        identity = ModelProvider.from_environment().identity()
        if identity["mode"] == "local":
            if not (1 <= identity["timeout_seconds"] <= 300 and identity["output_tokens"] <= 4096):
                raise StateError("Hosted local models require a timeout of 1–300 seconds and at most 4096 output tokens")
            if not identity.get("declared_model_sha256"):
                raise StateError("Hosted models must declare the operator-verified local weights digest")
        with HostedService(access, args.origin, args.port) as server:
            logging.warning("IGNITION service started; environment=%s", args.environment)
            stopping = threading.Event()
            def drain(signum, frame):
                if not stopping.is_set():
                    stopping.set()
                    threading.Thread(target=server.shutdown, daemon=True).start()
            previous = signal.signal(signal.SIGTERM, drain)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                signal.signal(signal.SIGTERM, previous)


if __name__ == "__main__":
    try:
        main()
    except (StateError, OSError, sqlite3.Error, ValueError) as exc:
        raise SystemExit(str(exc)) from None
