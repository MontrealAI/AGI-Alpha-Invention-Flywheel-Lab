#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Optional loopback-only connector. Double-click app/index.html for the offline workflow."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import io
import json
import mimetypes
from pathlib import Path
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import webbrowser
import zipfile

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bridge.adapters import BridgeError, MAX_BODY, Runtime, retrieve_source, strict_json
from bridge.services import AccessRuntime

PRODUCT = Path(__file__).resolve().parent.parent
APP = PRODUCT / "app"
STATIC_FILES = {"/": "index.html", "/index.html": "index.html", "/app.js": "app.js",
                "/engine.js": "engine.js", "/styles.css": "styles.css"}


class NativeMechanism:
    """Optional existing-source adapter; no copied code, account, native cash or authority."""
    def __init__(self):
        self.source = PRODUCT.parent.parent / "mechanism_harness" / "core.py"
        self._module = None
        self._lock = threading.Lock()

    def available(self):
        return self.source.is_file() and not self.source.is_symlink()

    def compose(self, spec):
        if not self.available():
            raise BridgeError("NATIVE_UNAVAILABLE", "This optional adapter needs the original repository checkout. It is not bundled or relicensed.", 409)
        with self._lock:
            # Load only this fixed, local, repository-owned source path. Never a user path.
            before = hashlib.sha256(self.source.read_bytes()).hexdigest()
            name = "alpha_harness_canonical_mechanism"
            loader = importlib.util.spec_from_file_location(name, self.source)
            module = importlib.util.module_from_spec(loader)
            sys.modules[name] = module
            loader.loader.exec_module(module)
            after = hashlib.sha256(self.source.read_bytes()).hexdigest()
            if before != after:
                raise BridgeError("NATIVE_CHANGED", "Canonical source changed during import. Retry only after source is stable.", 409)
            try:
                plan = module.compose(spec)
                check = module.audit(spec, plan)
                capsule = module.capability_capsule(spec, plan, check) if check["goal_achieved_symbolically"] else None
            except (ValueError, TypeError, KeyError):
                raise BridgeError("NATIVE_SPEC", "The symbolic specification does not satisfy the canonical mechanism contract.") from None
            return {"plan": plan, "check": check, "capsule": capsule, "source_sha256": after,
                    "source": "mechanism_harness/core.py", "scope": "Original finite symbolic composer and independent replay only; no real-world qualification, execution authority or financial mutation."}


class HarnessServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, runtime=None, app_path=APP, *, config=None, workspace=None):
        if address[0] != "127.0.0.1":
            raise BridgeError("BIND", "This connector binds only to 127.0.0.1.")
        self.config = config or {}
        self.workspace = Path(workspace or Path.home() / ".alpha-genesis-harness" / "workspaces").absolute()
        self.runtime = AccessRuntime(runtime, self.config)
        self._workflows = None
        self._genesis_next = None
        self._local_connections = None
        self._upgrade_foundry = None
        self._frontier_monitor = None
        self._workflow_lock = threading.RLock()
        self.token = secrets.token_urlsafe(32)
        self.app_path = Path(app_path).resolve()
        self.native = NativeMechanism()
        super().__init__(address, Handler)
        self.host = f"127.0.0.1:{self.server_port}"
        self.origin = "http://" + self.host
        # Resume only monitor jobs carrying explicit persisted restart consent.
        # An unused installation performs no network work or workspace creation.
        if (self.workspace / "frontier-monitor" / "state.json").exists():
            try:
                self.frontier_monitor
            except Exception:
                self.server_close()
                raise

    @property
    def workflows(self):
        with self._workflow_lock:
            if self._workflows is None:
                from bridge.workflows import WorkflowService
                self._workflows = WorkflowService(self.runtime, self.workspace)
            return self._workflows

    def server_close(self):
        if self._frontier_monitor is not None:
            self._frontier_monitor.close()
        if self._upgrade_foundry is not None:
            self._upgrade_foundry.close()
        if self._workflows is not None and hasattr(self._workflows, "close"):
            self._workflows.close()
        self.runtime.close()
        super().server_close()

    @property
    def genesis_next(self):
        with self._workflow_lock:
            if self._genesis_next is None:
                from bridge.genesis_next import GenesisNextService
                self._genesis_next = GenesisNextService(self.workflows)
            return self._genesis_next

    @property
    def local_connections(self):
        with self._workflow_lock:
            if self._local_connections is None:
                from bridge.onboarding import LocalConnectionService
                self._local_connections = LocalConnectionService(self.runtime, self.workspace)
            return self._local_connections

    @property
    def upgrade_foundry(self):
        with self._workflow_lock:
            if self._upgrade_foundry is None:
                from bridge.upgrade_foundry import UpgradeFoundryService
                self._upgrade_foundry = UpgradeFoundryService(self.workflows, self.runtime.service("codex"))
            return self._upgrade_foundry

    @property
    def frontier_monitor(self):
        with self._workflow_lock:
            if self._frontier_monitor is None:
                from bridge.frontier_monitor import FrontierMonitorService
                self._frontier_monitor = FrontierMonitorService(self.workflows, self.genesis_next)
            return self._frontier_monitor


class Handler(BaseHTTPRequestHandler):
    server_version = "AlphaGenesisHarness"
    sys_version = ""

    def log_message(self, *_):
        pass  # Never write URLs, prompts, model output or credentials to console logs.

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def send_bytes(self, status, data, mime="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def json(self, status, value):
        raw = json.dumps(value, ensure_ascii=False, allow_nan=False)
        self.send_bytes(status, self.server.runtime.redact(raw).encode("utf-8"))

    def boundary(self, authenticated=False, bootstrap=False):
        if self.headers.get_all("Host") != [self.server.host]:
            raise BridgeError("HOST", "Use the exact loopback URL printed by the connector.", 403)
        origin = self.headers.get("Origin")
        if origin is not None and origin != self.server.origin:
            raise BridgeError("ORIGIN", "Cross-origin connector requests are refused.", 403)
        if self.headers.get("Sec-Fetch-Site") not in {None, "same-origin", "none"}:
            raise BridgeError("ORIGIN", "Cross-site connector requests are refused.", 403)
        if bootstrap and self.headers.get("X-Harness-Client") != "browser":
            raise BridgeError("SESSION", "The application must request its connector session.", 403)
        if authenticated and not hmac.compare_digest(self.headers.get("X-Harness-Token", ""), self.server.token):
            raise BridgeError("TOKEN", "Connector session expired. Reload the application.", 403)

    def body(self):
        if self.headers.get("Content-Type", "").split(";", 1)[0].lower() != "application/json":
            raise BridgeError("CONTENT_TYPE", "Use application/json.", 415)
        if self.headers.get("Transfer-Encoding"):
            raise BridgeError("BODY", "Chunked input is not supported.")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not lengths[0].isdigit():
            raise BridgeError("BODY", "A single content length is required.")
        size = int(lengths[0])
        # Portable run archives may be larger than an individual prompt. This
        # exception applies only to import; generated content remains bounded.
        limit = 17 * 1024 * 1024 if self.path == "/api/workflows/import" else MAX_BODY
        if size > limit:
            raise BridgeError("BODY", f"Request exceeds {limit // (1024 * 1024)} MiB.", 413)
        data = self.rfile.read(size)
        if len(data) != size:
            raise BridgeError("BODY", "Incomplete request body.")
        value = strict_json(data)
        if not isinstance(value, dict):
            raise BridgeError("BODY", "Request must be a JSON object.")
        return value

    def do_GET(self):
        try:
            self.boundary()
            if self.path == "/api/session":
                self.boundary(bootstrap=True)
                return self.json(200, {"token": self.server.token})
            if self.path == "/api/status":
                self.boundary(authenticated=True)
                # Restoring previously consented local settings performs no inference.
                self.server.local_connections
                data = self.server.runtime.status()
                data["native_mechanism_available"] = self.server.native.available()
                data["workflow_engine_available"] = True
                data["genesis_next_available"] = True
                return self.json(200, data)
            if self.path == "/api/genesis-next/status":
                self.boundary(authenticated=True)
                return self.json(200, self.server.genesis_next.status())
            if self.path == "/api/upgrade-foundry/status":
                self.boundary(authenticated=True)
                return self.json(200, self.server.upgrade_foundry.status())
            if self.path == "/api/frontier-monitor/status":
                self.boundary(authenticated=True)
                return self.json(200, self.server.frontier_monitor.status())
            if self.path in {"/api/chatgpt/status", "/api/codex/status"}:
                self.boundary(authenticated=True)
                return self.json(200, self.connection_status(self.path.split("/")[2]))
            if self.path not in STATIC_FILES:
                raise BridgeError("NOT_FOUND", "Resource not found.", 404)
            path = self.server.app_path / STATIC_FILES[self.path]
            if path.is_symlink() or not path.is_file() or path.resolve().parent != self.server.app_path:
                raise BridgeError("NOT_FOUND", "Application file not found.", 404)
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            return self.send_bytes(200, path.read_bytes(), mime + "; charset=utf-8")
        except BridgeError as error:
            self.json(error.status, {"error": {"code": error.code, "message": error.message}})
        except (OSError, ValueError):
            self.json(500, {"error": {"code": "LOCAL_IO", "message": "Application resource unavailable."}})

    def do_POST(self):
        try:
            self.boundary(authenticated=True)
            data = self.body()
            if self.path == "/api/generate-stream":
                return self.stream_generation(data)
            if self.path == "/api/workflows/download":
                exported = self.server.workflows.export(data.get("run_id"))
                output = io.BytesIO()
                with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                    for name, content in exported["files"].items():
                        bundle.writestr("artifacts/" + name, content.encode("utf-8"))
                    bundle.writestr("WORKFLOW-EXPORT.json", json.dumps(exported, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8"))
                return self.send_bytes(200, output.getvalue(), "application/zip")
            if self.path == "/api/generate":
                result = self.server.runtime.generate(data)
                result["budget"] = self.server.runtime.budget.view()
            elif self.path == "/api/cancel":
                result = self.server.runtime.cancel(data.get("run_id"))
            elif self.path == "/api/models":
                result = self.server.runtime.discover(data.get("provider"))
            elif self.path == "/api/source":
                if self.server.runtime.status().get("local_only"):
                    raise BridgeError("LOCAL_ONLY", "External source retrieval is disabled in local-only mode.", 403)
                result = retrieve_source(data.get("url"), self.server.runtime.source_hosts, data.get("previous_sha256"))
            elif self.path == "/api/mechanism":
                result = self.server.native.compose(data.get("spec"))
            elif self.path.startswith("/api/workflows/"):
                result = self.workflow_action(self.path.rsplit("/", 1)[1], data)
            elif self.path == "/api/capabilities":
                result = self.server.workflows.capabilities()
            elif self.path.startswith("/api/genesis-next/"):
                result = self.genesis_next_action(self.path.rsplit("/", 1)[1], data)
            elif self.path.startswith("/api/local-models/"):
                result = self.local_model_action(self.path.rsplit("/", 1)[1], data)
            elif self.path == "/api/proof-to-market/assess":
                from bridge.proof_to_market import assess
                result = assess(data)
            elif self.path.startswith("/api/upgrade-foundry/"):
                result = self.upgrade_foundry_action(self.path.rsplit("/", 1)[1], data)
            elif self.path.startswith("/api/frontier-monitor/"):
                result = self.frontier_monitor_action(self.path.rsplit("/", 1)[1], data)
            elif self.path.startswith("/api/chatgpt/") or self.path.startswith("/api/codex/"):
                result = self.connection_action(self.path.split("/")[2], self.path.rsplit("/", 1)[1], data)
            else:
                raise BridgeError("NOT_FOUND", "Connector action not found.", 404)
            self.json(200, result)
        except BridgeError as error:
            self.json(error.status, {"error": {"code": error.code, "message": error.message},
                                     "budget": self.server.runtime.budget.view()})
        except Exception:
            self.json(500, {"error": {"code": "INTERNAL", "message": "Connector failed safely. Inspect configuration and retry with a new run ID."},
                            "budget": self.server.runtime.budget.view()})

    def connection_action(self, category, action, data):
        allowed = {"status", "connect", "select", "disconnect", "models", "generate", "cancel"}
        if category == "codex":
            allowed.add("resume")
        if action not in allowed:
            raise BridgeError("NOT_FOUND", "Unknown connection action.", 404)
        if category == "codex" and action in {"connect", "select", "disconnect"}:
            raise BridgeError("CODEX_SHARED_AUTH", "Codex uses the HARNESS ChatGPT connection. Manage that account in the ChatGPT panel.", 409)
        if action not in {"status", "disconnect", "cancel"}:
            self.server.runtime._network_allowed()
        service = self.server.runtime.service(category)
        if action == "status":
            return self.connection_status(category)
        if action == "connect":
            reconsent = data.get("reconsent", False)
            if type(reconsent) is not bool:
                raise BridgeError("INPUT", "Reconsent must be true or false.")
            return service.start_sign_in(data.get("account_id"), reconsent=reconsent)
        if action == "select":
            return service.select_account(data.get("account_id"))
        if action == "disconnect":
            if category == "chatgpt":
                return service.disconnect(data.get("account_id"),
                                          revoke_remote=not self.server.runtime.status().get("local_only"))
            return service.disconnect(data.get("account_id"))
        if action == "models":
            return service.discover()
        if action == "generate":
            return self.server.runtime.generate(dict(data, provider=category))
        if action == "resume":
            return self.server.runtime.resume(dict(data, provider=category))
        return self.server.runtime.cancel(data.get("run_id"))

    def connection_status(self, category):
        result = self.server.runtime.service(category).status()
        if self.server.runtime.status().get("local_only"):
            result.update(enabled=False, ready=False,
                          reason="Local-only mode disables this remote connection. Existing local credentials can still be removed.")
        return result

    def stream_generation(self, data):
        """Authenticated POST stream; no tokens or user data in URLs or console logs."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        def emit(event):
            raw = json.dumps(event, ensure_ascii=False, allow_nan=False)
            try:
                self.wfile.write((self.server.runtime.redact(raw) + "\n").encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                if isinstance(data.get("run_id"), str):
                    self.server.runtime.cancel(data["run_id"])
                raise BridgeError("CANCELLED", "Client disconnected; local stream stopped.", 409) from None

        try:
            result = self.server.runtime.generate(dict(data, stream=True), on_event=emit)
            emit({"type": "completed", "result": result, "budget": self.server.runtime.budget.view()})
        except BridgeError as error:
            try:
                emit({"type": "error", "error": {"code": error.code, "message": error.message},
                      "budget": self.server.runtime.budget.view()})
            except BridgeError:
                pass
        except Exception:
            try:
                emit({"type": "error", "error": {"code": "INTERNAL", "message": "The stream failed safely."}})
            except BridgeError:
                pass

    def workflow_action(self, action, data):
        # Fixed dispatch table: untrusted names cannot select arbitrary methods.
        if action == "create":
            return self.server.workflows.create(data.get("spec", data))
        if action == "list":
            return self.server.workflows.list()
        if action == "import":
            return self.server.workflows.import_archive(data.get("archive", data))
        if action == "reuse":
            return self.server.workflows.reuse(data.get("capability_id"), data.get("input"))
        if action not in {"start", "step", "pause", "cancel", "resume", "get", "export"}:
            raise BridgeError("NOT_FOUND", "Unknown workflow action.", 404)
        return getattr(self.server.workflows, action)(data.get("run_id"))

    def genesis_next_action(self, action, data):
        # Fixed routes retain independent evaluator and source authority.
        if action not in {"status", "opportunity", "replay", "discover", "demo", "export", "verify"}:
            raise BridgeError("NOT_FOUND", "Unknown GENESIS NEXT action.", 404)
        service = self.server.genesis_next
        if action == "status":
            return service.status()
        if action == "opportunity":
            return service.add_opportunity(data)
        if action == "replay":
            return service.replay(data)
        if action == "discover":
            return service.discover()
        if action == "demo":
            return service.run_demo(data)
        if action == "verify":
            return service.verify_instrument(data)
        return service.export()

    def local_model_action(self, action, data):
        if action not in {"presets", "discover", "connect", "disconnect"}:
            raise BridgeError("NOT_FOUND", "Unknown local connection action.", 404)
        service = self.server.local_connections
        if action == "presets":
            return service.presets()
        if action == "discover":
            return service.discover(data)
        if action == "connect":
            return service.connect(data)
        return service.disconnect(data)

    def upgrade_foundry_action(self, action, data):
        if action not in {"status", "register", "construct", "qualify", "activate", "rollback", "evaluate", "export", "cancel"}:
            raise BridgeError("NOT_FOUND", "Unknown upgrade foundry action.", 404)
        if action == "construct":
            self.server.runtime._network_allowed()
        service = self.server.upgrade_foundry
        if action == "status":
            return service.status()
        if action == "evaluate":
            return service.evaluate_retained(data)
        return getattr(service, action)(data)

    def frontier_monitor_action(self, action, data):
        if action not in {"status", "add", "poll", "start", "stop", "remove"}:
            raise BridgeError("NOT_FOUND", "Unknown frontier monitor action.", 404)
        service = self.server.frontier_monitor
        if action == "status":
            return service.status()
        return getattr(service, action)(data)

    def do_OPTIONS(self):
        self.json(403, {"error": {"code": "CORS", "message": "Cross-origin access is disabled."}})


def main():
    parser = argparse.ArgumentParser(description="Optional private loopback connector; no paid requests enabled by default.")
    parser.add_argument("--config", type=Path, help="Private JSON configuration containing environment names, never API keys")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--workspace", type=Path, help="Private persistent workflow directory (outside the application)")
    args = parser.parse_args()
    try:
        config = strict_json(args.config.read_bytes()) if args.config else {}
        runtime = Runtime(config)
        server = HarnessServer(("127.0.0.1", args.port), runtime, config=config, workspace=args.workspace)
    except (BridgeError, OSError, KeyError, TypeError, ValueError):
        print("Connector could not start. Check the private configuration and choose an available loopback port.", file=sys.stderr)
        return 1
    print(f"ALPHA GENESIS HARNESS: {server.origin}")
    print("Private process-session connector. Closing it resets this session guard; it does not reset provider bills.")
    if not args.no_browser:
        webbrowser.open(server.origin)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
