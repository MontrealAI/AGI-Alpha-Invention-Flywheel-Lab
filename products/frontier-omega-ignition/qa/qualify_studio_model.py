"""Authenticated live local-model smoke through the real TLS staging HTTP service."""
from __future__ import annotations

import base64
import contextlib
from hashlib import sha256
from http.cookiejar import CookieJar
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import time
from urllib import error, request

import qualify_live as q

REPORT_PATH = "docs/frontier-omega-ignition/continuation/beneficiary-pursuit/REPORT.md"
REPORT_SHA = "dfe208fb567e6193b031c17f1313c386d455751acfad52c67a5094a52630cfd6"


def exercise(work, model_port, record, *, protocol=None):
    env = {**os.environ, "IGNITION_MODEL_PROVIDER": "llama-cpp", "IGNITION_MODEL_ID": q.MODEL_ALIAS,
           "IGNITION_MODEL_PORT": str(model_port), "IGNITION_MODEL_SHA256": q.pinned.MODEL_SHA,
           "IGNITION_MODEL_SCHEMA": "1", "IGNITION_MODEL_STREAM": "1", "IGNITION_MODEL_TIMEOUT": "300",
           "IGNITION_MODEL_OUTPUT_TOKENS": "2048" if protocol else "512"}
    with subprocess.Popen([sys.executable, "-B", str(q.PRODUCT / "qa/studio_staging.py")], cwd=q.PRODUCT,
                          env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.DEVNULL, text=True) as child:
        try:
            config = json.loads(child.stdout.readline())
            root = config["origin"]
            context = ssl.create_default_context(cadata=config["ca_pem"])
            client = request.build_opener(request.ProxyHandler({}), request.HTTPSHandler(context=context),
                                          request.HTTPCookieProcessor(CookieJar()))
            def call(route, data=None):
                message = request.Request(root + route, data=None if data is None else json.dumps(data).encode(),
                                          headers={"Origin": root, "X-Ignition-Request": "1",
                                                   "Content-Type": "application/json"})
                with client.open(message, timeout=15) as answer:
                    return (json.load(answer) if answer.headers.get_content_type() == "application/json"
                            else answer.read())
            try:
                call("/api/runs")
            except error.HTTPError as denied:
                record["unauthenticated_status"] = denied.code
                denied.close()
            record["authentication"] = call("/api/session", {"invite": config["invites"][0]})
            try:
                record["readiness"] = call("/readyz")
                record["readiness_status"] = 200
            except error.HTTPError as unavailable:
                record["readiness_status"] = unavailable.code
                unavailable.close()
                return False
            record["configuration"] = call("/api/status")["provider"]
            if protocol is not None:
                return protocol(work, call, record)
            report = (q.REPO / REPORT_PATH).read_bytes()
            if sha256(report).hexdigest() != REPORT_SHA:
                raise ValueError("Unrecognized published report")
            purpose = "Verify the public scroll-normalizer delivery report against a separately pinned digest."
            payload = {"files": {"REPORT.md": base64.b64encode(report).decode("ascii")}}
            clean = {"matched": ["REPORT.md"], "changed": [], "missing": [], "unexpected": [], "ok": True}
            absent = {"matched": [], "changed": [], "missing": ["REPORT.md"], "unexpected": [], "ok": False}
            mission = {"purpose": purpose, "beneficiary": "MONTREAL.AI instrument recipient",
                       "resources": {"execution_strategy": "adaptive", "direct_method": "model",
                                     "max_model_calls": 2, "max_repairs": 1},
                       "authority": {"local_model": True}, "requirements": [
                           "Classify the supplied file against the trusted digest and report an omitted file."],
                       "construction_spec": {"kind": "manifest_audit", "purpose": purpose,
                            "definition": {"manifest": {"REPORT.md": REPORT_SHA}},
                            "cases": [{"name": "File received", "input": payload, "expected": clean},
                                      {"name": "File absent", "input": {"files": {}}, "expected": absent}]}}
            start = time.monotonic()
            run = call("/api/runs", {"request_id": "local-receiver-smoke", "mission": mission, "sources": []})
            endpoint = "/api/runs/" + run["id"]
            while run["status"] in {"running", "queued"} and time.monotonic() - start < 330:
                time.sleep(0.4)
                run = call(endpoint)
            record.update(status=run["status"], stage=run["stage"], reason=run.get("error"),
                          dispatch_wall_seconds=round(time.monotonic()-start, 3),
                          events=[e["stage"] for e in run["events"]], attempts=run["attempts"])
            evidence = call(endpoint + "/evidence?version=1")
            record.update(artifact=evidence["artifact"], usage=(evidence.get("economics") or {}).get("usage"))
            if run["status"] != "verified":
                return False
            bundle = call(endpoint + "/bundle?version=1")
            (work / "recipient.zip").write_bytes(bundle)
            replay = q.check_portable(bundle, work)
            extra = {"files": {"REPORT.md": base64.b64encode(report + b"\n").decode("ascii")}}
            trial = call(endpoint + "/try", {"version": 1, "input": extra})
            record.update(receiver=replay, altered_input=trial, bundle_sha256=sha256(bundle).hexdigest())
            return (record.get("unauthenticated_status") == 401
                    and record["authentication"] == {"authenticated": True, "environment": "staging"}
                    and record["readiness"] == {"status": "ok", "revision": record["source_revision"]}
                    and record["configuration"]["declared_model_sha256"] == q.pinned.MODEL_SHA
                    and record["configuration"]["timeout_seconds"] == 300
                    and "construct" in record["events"] and 1 <= record["attempts"] <= 2
                    and record["usage"]["recorded_application_model_calls"] == record["attempts"]
                    and replay["verified_exit"] == replay["example_exit"] == 0
                    and trial["output"]["changed"] == ["REPORT.md"] and trial["output"]["ok"] is False)
        finally:
            with contextlib.suppress(BrokenPipeError):
                child.stdin.close()
