"""Single-operator loopback workbench. Private workspace data never enters the public site."""
from __future__ import annotations

import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from .store import Conflict, Missing, PRODUCT, StateError, canonical, strict_json


class Service(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, controller, port=8784):
        self.controller = controller
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ignition")
        super().__init__(("127.0.0.1", port), Handler)

    def enqueue(self, run_id, version):
        def work():
            try:
                self.controller.advance(run_id, version)
            except Conflict:
                pass  # Another worker owns the run, or an amendment superseded it.
            except Exception:
                logging.exception("Worker stopped. Inspect the private operator log before resuming.")
        self.pool.submit(work)

    def server_close(self):
        super().server_close()
        self.pool.shutdown(wait=True)


PRIVATE_CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
               "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")


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

    def _handle(self, post):
        port = self.server.server_port
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if (len(self.headers.get_all("Host",[])) != 1 or self.headers.get("Host") not in hosts
                or self.headers.get("Origin") not in (None, "http://"+self.headers["Host"])
                or self.headers.get("Sec-Fetch-Site") == "cross-site"):
            return self._json({"error":"This workspace accepts same-origin loopback requests only"},403)
        ctrl = self.server.controller
        parts = urlsplit(self.path)
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
        if not post and route in {"/", "/index.html", "/app.js", "/style.css", "/operator.css"}:
            name = route.lstrip("/") or "index.html"
            media = {"index.html":"text/html","app.js":"text/javascript","style.css":"text/css","operator.css":"text/css"}[name]
            return self._send(200,media+"; charset=utf-8",(PRODUCT/"web"/name).read_bytes())
        if not post and route == "/showcase":
            # The exhibit reads only its repository's public inputs. Its opaque
            # origin and independent no-connect CSP isolate private workspace APIs.
            from showcase.build import render, policy
            page = render()
            csp = (policy(page) + "; frame-ancestors 'none'; "
                   "sandbox allow-scripts allow-downloads allow-popups allow-popups-to-escape-sandbox")
            return self._send(200, "text/html; charset=utf-8", page.encode("utf-8"), csp=csp)
        if not post and route == "/api/status":
            provider = ctrl.identity()
            return self._json({"mode":provider["mode"],"provider":provider,"runtime":ctrl.source})
        if not post and route == "/api/examples":
            return self._json({"examples":[json.loads(p.read_text()) for p in sorted((PRODUCT/"examples").glob("*.json"))]})
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
        if post and route == "/api/runs":
            run_id, version = ctrl.create(body)
            self.server.enqueue(run_id,version)
            return self._json(ctrl.view(run_id),202)
        match = re.fullmatch(r"/api/runs/([a-f0-9]{32})(?:/(history|bundle|try|resume|amend|respond|approve|choose))?",route)
        if not match:
            raise Missing("Unknown route")
        run_id, action = match.groups()
        if not post and not action:
            return self._json(ctrl.view(run_id))
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
                _,version = ctrl.create(body,run_id)
            elif action in {"respond","approve","choose"}:
                ctrl.intervene(run_id,version,action,body)
            elif type(version) is not int or version != ctrl.store.get(run_id)["version"]:
                raise Conflict("Resume requires the current version")
            self.server.enqueue(run_id,version)
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
        except Exception:
            logging.exception("Request failed")
            self._json({"error":"Unexpected error. Inspect the private operator log."},500)

    def do_GET(self):
        self._dispatch(False)

    def do_POST(self):
        self._dispatch(True)
