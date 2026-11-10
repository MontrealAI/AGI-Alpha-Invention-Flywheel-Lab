#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Optional loopback-only connector. Double-click app/index.html for the offline workflow."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import json
import mimetypes
from pathlib import Path
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import webbrowser

if __package__:
    from .adapters import BridgeError, MAX_BODY, Runtime, retrieve_source, strict_json
else:
    from adapters import BridgeError, MAX_BODY, Runtime, retrieve_source, strict_json

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

    def __init__(self, address, runtime=None, app_path=APP):
        if address[0] != "127.0.0.1":
            raise BridgeError("BIND", "This connector binds only to 127.0.0.1.")
        self.runtime = runtime or Runtime()
        self.token = secrets.token_urlsafe(32)
        self.app_path = Path(app_path).resolve()
        self.native = NativeMechanism()
        super().__init__(address, Handler)
        self.host = f"127.0.0.1:{self.server_port}"
        self.origin = "http://" + self.host


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
        if size > MAX_BODY:
            raise BridgeError("BODY", "Request exceeds 1 MiB.", 413)
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
                data = self.server.runtime.status()
                data["native_mechanism_available"] = self.server.native.available()
                return self.json(200, data)
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
            if self.path == "/api/generate":
                result = self.server.runtime.generate(data)
                result["budget"] = self.server.runtime.budget.view()
            elif self.path == "/api/cancel":
                result = self.server.runtime.cancel(data.get("run_id"))
            elif self.path == "/api/models":
                result = self.server.runtime.discover(data.get("provider"))
            elif self.path == "/api/source":
                result = retrieve_source(data.get("url"), self.server.runtime.source_hosts, data.get("previous_sha256"))
            elif self.path == "/api/mechanism":
                result = self.server.native.compose(data.get("spec"))
            else:
                raise BridgeError("NOT_FOUND", "Connector action not found.", 404)
            self.json(200, result)
        except BridgeError as error:
            self.json(error.status, {"error": {"code": error.code, "message": error.message},
                                     "budget": self.server.runtime.budget.view()})
        except Exception:
            self.json(500, {"error": {"code": "INTERNAL", "message": "Connector failed safely. Inspect configuration and retry with a new run ID."},
                            "budget": self.server.runtime.budget.view()})

    def do_OPTIONS(self):
        self.json(403, {"error": {"code": "CORS", "message": "Cross-origin access is disabled."}})


def main():
    parser = argparse.ArgumentParser(description="Optional private loopback connector; no paid requests enabled by default.")
    parser.add_argument("--config", type=Path, help="Private JSON configuration containing environment names, never API keys")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        config = strict_json(args.config.read_bytes()) if args.config else {}
        runtime = Runtime(config)
        server = HarnessServer(("127.0.0.1", args.port), runtime)
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
