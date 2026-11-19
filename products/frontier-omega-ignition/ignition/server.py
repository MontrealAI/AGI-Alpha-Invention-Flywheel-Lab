"""Single-operator loopback workbench. Private workspace data never enters the public site."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .dispatcher import Dispatcher
from .research import acquisition_summary
from .store import Conflict, Missing, PRODUCT, StateError, canonical, strict_json


class Service(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, controller, port=8784, *, recover=False):
        self.controller = controller
        super().__init__(("127.0.0.1", port), Handler)
        self.dispatcher = Dispatcher()
        if recover:
            self.dispatcher.recover(controller)

    def enqueue_for(self, ctrl, run_id, version, *, retry=False):
        self.dispatcher.enqueue(ctrl, run_id, version, retry=retry)

    def enqueue(self, run_id, version):
        self.enqueue_for(self.controller, run_id, version)

    def server_close(self):
        super().server_close()
        if hasattr(self, "dispatcher"):
            self.dispatcher.close()


PRIVATE_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
               "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
PUBLIC_EXHIBITS = {
    "/exhibition": "FRONTIER_IGNITION.html",
    "/frontier": "FRONTIER_LAB.html",
    "/field": "FRONTIER_FIELD.html",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "Ignition"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def log_message(self, format, *args):
        pass  # Mission IDs, paths and payloads stay out of access logs.

    def _send(self, status, media, content, attachment=None, *, csp=PRIVATE_CSP):
        self.send_response(status)
        for key, value in {
            "Content-Type":media, "Content-Length":str(len(content)),
            "X-Content-Type-Options":"nosniff", "Referrer-Policy":"no-referrer",
            "Cache-Control":"no-store", "X-Frame-Options":"DENY",
            "Content-Security-Policy":csp
        }.items():
            self.send_header(key, value)
        if attachment:
            self.send_header("Content-Disposition",f'attachment; filename="{attachment}"')
        self.end_headers()
        self.wfile.write(content)

    def _json(self, value, status=200):
        self._send(status, "application/json; charset=utf-8", canonical(value).encode())

    def _origin_allowed(self, parts, post):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        # An opaque exhibit may navigate to another public page or download it.
        public_route = parts.path in PUBLIC_EXHIBITS or parts.path == "/showcase"
        public_document = (not post and public_route
                           and self.headers.get("Sec-Fetch-Mode") == "navigate")
        return (len(self.headers.get_all("Host", [])) == 1 and self.headers.get("Host") in hosts
                and (public_document or (self.headers.get("Origin") in (None, "http://"+self.headers["Host"])
                     and self.headers.get("Sec-Fetch-Site") != "cross-site")))

    def _public_request(self, parts, post):
        if post:
            return False
        shells = {"/welcome": "welcome.html", "/studio": "studio.html", "/demo": "demo.html",
                  "/studio.js": "studio.js", "/studio.css": "studio.css"}
        if parts.path in shells:
            name = shells[parts.path]
            media = {"html":"text/html", "js":"text/javascript", "css":"text/css"}[name.split(".")[-1]]
            self._send(200, media+"; charset=utf-8", (PRODUCT/"web"/name).read_bytes())
            return True
        if parts.path == "/api/session":
            self._json({"authenticated": True, "environment": "local", "role": "operator"})
            return True
        return False

    def _run_controller(self):
        return self.server.controller

    def _validate_create(self, ctrl, body):
        pass

    def _validate_action(self, ctrl, run_id, action, body):
        pass

    def _handle(self, post):
        parts = urlsplit(self.path)
        if not self._origin_allowed(parts, post):
            return self._json({"error":"Request origin is not allowed"},403)
        route = parts.path
        if parts.scheme or parts.netloc:
            raise StateError("Use a local relative path")
        if post:
            if (self.headers.get("X-Ignition-Request") != "1" or self.headers.get_content_type() != "application/json"
                    or self.headers.get("Transfer-Encoding") or len(self.headers.get_all("Content-Length",[])) != 1):
                return self._json({"error":"JSON with X-Ignition-Request: 1 is required"},403)
            size = int(self.headers["Content-Length"])
            if not 0 < size <= 2_100_000:
                return self._json({"error":"Request exceeded the local transport size limit"},413)
            body = strict_json(self.rfile.read(size))
            if not isinstance(body,dict):
                raise StateError("Expected an object")
        self.request_body = body if post else None
        if self._public_request(parts, post):
            return
        if not post and route in {"/follow-up", "/followup.js", "/change-desk", "/change-desk.js"}:
            name = {"/follow-up": "followup.html", "/change-desk": "change-desk.html"}.get(route, route.lstrip("/"))
            media = "text/html" if name.endswith(".html") else "text/javascript"
            return self._send(200, media + "; charset=utf-8", (PRODUCT / "web" / name).read_bytes())
        if not post and route in {"/", "/index.html", "/app.js", "/style.css", "/operator.css"}:
            name = route.lstrip("/") or "index.html"
            media = {"index.html":"text/html","app.js":"text/javascript","style.css":"text/css","operator.css":"text/css"}[name]
            return self._send(200,media+"; charset=utf-8",(PRODUCT/"web"/name).read_bytes())
        public_route = route in PUBLIC_EXHIBITS or route == "/showcase"
        if not post and public_route:
            # The exhibit reads only its repository's public inputs. Its opaque
            # origin and independent no-connect CSP isolate private workspace APIs.
            from showcase.build import render, policy
            directory = PRODUCT.parents[1] / "docs/frontier-omega-ignition/continuation"
            page = render() if route == "/showcase" else (directory / PUBLIC_EXHIBITS[route]).read_text(encoding="utf-8")
            csp = (policy(page) + "; frame-ancestors 'none'; "
                   "sandbox allow-scripts allow-downloads allow-popups allow-popups-to-escape-sandbox")
            attachment = PUBLIC_EXHIBITS.get(route) if parse_qs(parts.query).get("download") == ["1"] else None
            return self._send(200, "text/html; charset=utf-8", page.encode("utf-8"), attachment, csp=csp)
        ctrl = self._run_controller()
        if ctrl is None:
            return self._json({"error": "Sign in to use the Mission Studio"}, 401)
        if not post and route == "/api/status":
            provider = ctrl.identity()
            return self._json({"mode":provider["mode"],"provider":provider,"runtime":ctrl.source})
        if not post and route == "/api/examples":
            available = (json.loads(p.read_text()) for p in sorted((PRODUCT/"examples").glob("*.json")))
            return self._json({"examples": [item for item in available if item.get("id") and item.get("mission")]})
        if not post and route == "/api/replays":
            items = [{"id":i, "title": json.loads((PRODUCT/"examples"/f"{i}.json").read_bytes())["title"]}
                     for i in ("integrity","migration","unsupported")]
            return self._json({"examples":items})
        replay = re.fullmatch(r"/api/replays/(integrity|migration|unsupported)(/bundle)?",route)
        if replay and not post:
            name, bundle = replay.groups()
            records = PRODUCT/"evidence"
            case = next(c for c in json.loads((records/"recipient-checks.json").read_bytes())["cases"] if c["mission"]==name)
            if bundle and not case.get("bundle_sha256"):
                raise Missing("This example ended without a verified bundle")
            field = "bundle_sha256" if bundle else "run_evidence_sha256"
            filename = f"{name}-artifact.zip" if bundle else f"{name}-run.json"
            data = (records/filename).read_bytes()
            if hashlib.sha256(data).hexdigest() != case[field]:
                raise Conflict("The archived example differs from its published receipt")
            if bundle:
                return self._send(200,"application/zip",data,filename)
            return self._send(200,"application/json; charset=utf-8",data)
        if route == "/api/runs" and not post:
            return self._json({"runs": list(ctrl.store.inventory())})
        if post and route == "/api/runs":
            self._validate_create(ctrl, body)
            run_id, version = ctrl.create(body)
            self.server.enqueue_for(ctrl, run_id, version)
            return self._json(ctrl.view(run_id),202)
        match = re.fullmatch(r"/api/runs/([a-f0-9]{32})(?:/(history|bundle|evidence|offer|successor|try|resume|amend|respond|approve|choose|operation|commercial))?",route)
        if not match:
            raise Missing("Unknown route")
        run_id, action = match.groups()
        self._validate_action(ctrl, run_id, action, self.request_body)
        if action == "successor":
            if not post:
                params = parse_qs(parts.query)
                versions = params.get("version", [])
                if set(params) != {"version"} or len(versions) != 1 or not versions[0].isdigit():
                    raise StateError("Select one successor source revision")
                parent = ctrl.view(run_id)
                eligible = (parent["version"] == int(versions[0]) and parent["status"] == "verified"
                            and parent["operation"]["state"] == "active"
                            and parent["mission"]["authority"].get("allow_program_reuse") is True
                            and (parent.get("artifact") or {}).get("kind") in {"manifest_audit", "record_migration"})
                return self._json({"eligible": eligible, "source_id": run_id, "source_version": parent["version"],
                                   "kind": (parent.get("artifact") or {}).get("kind")})
            if set(body) != {"version", "rights", "mission", "sources", "request_id"}:
                raise StateError("Supply the source revision, rights basis and a fresh mission request")
            ctrl.store.get(run_id)  # Resolve the source in the authenticated workspace.
            request = {k: body[k] for k in ("mission", "sources", "request_id")}
            self._validate_create(ctrl, request)
            child, version = ctrl.successor(run_id, body["version"], request, body["rights"], replay_first=True)
            self.server.enqueue_for(ctrl, child, version)
            return self._json(ctrl.view(child), 202)
        if not post and action == "offer":
            from .commercial_handoff import offer_draft
            params = parse_qs(parts.query, keep_blank_values=True)
            version = params.get("version", [])
            language = params.get("lang", ["en"])
            if set(params) - {"lang", "version"} or len(version) != 1 or not version[0].isdigit() or len(language) != 1:
                raise StateError("Select one current offer revision and language")
            document = offer_draft(ctrl, run_id, int(version[0]), language[0])
            return self._send(200, "text/plain; charset=utf-8", document.encode("utf-8"),
                              f"ignition-{run_id}-v{int(version[0])}-offer-{language[0]}.txt")
        if not post and action == "evidence":
            params = parse_qs(parts.query).get("version", [])
            if len(params) != 1 or not params[0].isdigit():
                raise StateError("Select one evidence revision")
            state = ctrl.view(run_id, int(params[0]))
            fields = ("id", "version", "input_sha256", "runtime", "provider", "created_at", "status", "stage",
                      "operation", "routing", "research", "evaluation", "contract_sha256", "acceptance_origin",
                      "events", "attempts", "economics", "error")
            result = {k: state.get(k) for k in fields}
            artifact = state.get("artifact") or {}
            result["artifact"] = {k: artifact[k] for k in ("kind", "sha256") if k in artifact}
            result["source_acquisition"] = acquisition_summary(state.get("source_result"))
            result["schema"] = "ignition.mission-evidence.v1"
            return self._send(200, "application/json; charset=utf-8", canonical(result).encode(),
                              f"ignition-{run_id}-v{params[0]}-evidence.json")
        if not post and not action:
            return self._json(ctrl.view(run_id))
        if not post and action == "commercial":
            from .commercial_handoff import status
            version = parse_qs(parts.query).get("version", [])
            if len(version) != 1:
                raise StateError("Select one mission revision")
            return self._json(status(ctrl.store, run_id, int(version[0])))
        if post and action == "operation":
            if set(body) != {"version", "sequence", "operation"} or type(body["sequence"]) is not int:
                raise StateError("Supply the current revision, control sequence and requested operation")
            record = ctrl.set_operation(run_id, body["version"], body["operation"],
                                        expected_sequence=body["sequence"])
            if body["operation"] == "resume":
                self.server.enqueue_for(ctrl, run_id, body["version"], retry=True)
            return self._json(record)
        if not post and action == "history":
            return self._json({"versions":[{k:v for k,v in ctrl.public(s).items() if k!="handoff"}
                                           for s in ctrl.store.history(run_id)]})
        if not post and action == "bundle":
            raw = parse_qs(parts.query).get("version")
            version = int(raw[0]) if raw else None
            data = ctrl.deliver(run_id,version)
            return self._send(200,"application/zip",data,f"ignition-{run_id}.zip")
        if post and action == "try":
            return self._json({"output":ctrl.deliver(run_id,body["version"],body["input"],trial=True)})
        if post and action in {"amend","respond","approve","choose","resume"}:
            version = body.get("version")
            if action == "amend":
                self._validate_create(ctrl, body)
                _,version = ctrl.create(body,run_id)
            elif action in {"respond","approve","choose"}:
                ctrl.intervene(run_id,version,action,body)
            elif type(version) is not int or version != ctrl.store.get(run_id)["version"]:
                raise Conflict("Resume requires the current version")
            elif action == "resume":
                ctrl.store.assert_operating(ctrl.store.get(run_id, version))
            self.server.enqueue_for(ctrl, run_id, version, retry=(action == "resume"))
            return self._json(ctrl.view(run_id),202)
        raise Missing("Unknown route or method")

    def _dispatch(self, post):
        try:
            self.connection.settimeout(15)
            self._handle(post)
        except (BrokenPipeError,ConnectionResetError):
            return
        except (ValueError, KeyError, TypeError, RecursionError) as exc:
            status = 404 if isinstance(exc,Missing) else 409 if isinstance(exc,Conflict) else 400
            self._json({"error":str(exc)[:1200]},status)
        except Exception as exc:
            # Exception messages may contain mission text, uploaded values or a private local path.
            logging.error("Request failed (%s)", type(exc).__name__)
            self._json({"error":"Unexpected error. Inspect the private operator log."},500)

    def do_GET(self):
        self._dispatch(False)

    def do_POST(self):
        self._dispatch(True)
