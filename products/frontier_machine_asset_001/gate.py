"""Machine Asset 001: bounded, source-to-output transformation with replayable acceptance.

Supporting agent-commerce feasibility instrument, not a commercial or scientific
breakthrough claim. Standard library only. No network fetching, model calls,
payment processing, credentials, file writes, or arbitrary code execution.
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re
import sys

VERSION = "montreal.ai/machine-asset-001/v0"
MAX_BODY = 262_144
MAX_ROWS = 1_000
MAX_RULES = 32
FIELD = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
OPERATIONS = {"copy", "strip", "upper", "lower"}


class Refused(ValueError):
    pass


def strict_json(raw: str):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise Refused("DUPLICATE_JSON_KEY")
            obj[key] = value
        return obj

    def nonfinite(_):
        raise Refused("NONFINITE_NUMBER")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, TypeError) as exc:
        raise Refused("INVALID_JSON: " + str(exc)) from exc


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def checked_request(request):
    if type(request) is not dict or set(request) != {"contract", "source_rows"}:
        raise Refused("EXACT_REQUEST_FIELDS_REQUIRED")
    contract, rows = request["contract"], request["source_rows"]
    if type(contract) is not dict or set(contract) != {"id_field", "rules"}:
        raise Refused("EXACT_CONTRACT_FIELDS_REQUIRED")
    key, rules = contract["id_field"], contract["rules"]
    if type(key) is not str or not FIELD.fullmatch(key):
        raise Refused("INVALID_ID_FIELD")
    if type(rules) is not list or not 1 <= len(rules) <= MAX_RULES:
        raise Refused("RULE_COUNT")
    if type(rows) is not list or not 1 <= len(rows) <= MAX_ROWS:
        raise Refused("ROW_COUNT")
    targets = {key}
    for rule in rules:
        if type(rule) is not dict or set(rule) != {"from", "to", "op"}:
            raise Refused("EXACT_RULE_FIELDS_REQUIRED")
        a, b, op = rule["from"], rule["to"], rule["op"]
        if not all(type(k) is str and FIELD.fullmatch(k) for k in (a, b)):
            raise Refused("INVALID_FIELD")
        if b in targets:
            raise Refused("DUPLICATE_OR_RESERVED_TARGET")
        targets.add(b)
        if op not in OPERATIONS:
            raise Refused("UNSUPPORTED_OPERATION")
    seen = set()
    for row in rows:
        if type(row) is not dict or key not in row:
            raise Refused("INVALID_ROW")
        rid = row[key]
        if type(rid) is not str or not rid or len(rid) > 128 or rid in seen:
            raise Refused("INVALID_OR_DUPLICATE_ROW_ID")
        seen.add(rid)
        for rule in rules:
            if rule["from"] not in row:
                raise Refused("MISSING_SOURCE_FIELD")
            val = row[rule["from"]]
            if rule["op"] != "copy" and type(val) is not str:
                raise Refused("TEXT_OPERATION_REQUIRES_STRING")
            if type(val) not in (str, int, float, bool, type(None)):
                raise Refused("NESTED_OR_UNSUPPORTED_SOURCE_VALUE")
            if type(val) is str and len(val) > 10_000:
                raise Refused("SOURCE_VALUE_TOO_LARGE")
    try:
        canonical(request)
    except (TypeError, ValueError, OverflowError) as exc:
        raise Refused("INVALID_CANONICAL_SOURCE") from exc
    return contract, rows


def produce(contract, rows):
    """Construct normalized records from the caller's explicit mapping."""
    results = []
    key = contract["id_field"]
    for row in rows:
        output = {key: row[key]}
        for rule in contract["rules"]:
            value = row[rule["from"]]
            action = rule["op"]
            if action == "strip":
                value = value.strip()
            elif action == "upper":
                value = value.upper()
            elif action == "lower":
                value = value.lower()
            output[rule["to"]] = value
        results.append(output)
    return results


def verify(contract, source_rows, delivered_rows):
    """Independently rederive field requirements; does not call produce."""
    failures = []
    key = contract["id_field"]
    if type(delivered_rows) is not list or len(delivered_rows) != len(source_rows):
        return ["ROW_COMPLETENESS"]
    mapped = {}
    for output in delivered_rows:
        if type(output) is not dict or type(output.get(key)) is not str:
            return ["OUTPUT_IDENTITY"]
        oid = output[key]
        if oid in mapped:
            return ["DUPLICATE_OUTPUT_ID"]
        mapped[oid] = output
    for source in source_rows:
        oid = source[key]
        actual = mapped.get(oid)
        if actual is None:
            failures.append("MISSING_OUTPUT_ROW")
            continue
        required = {key} | {rule["to"] for rule in contract["rules"]}
        if set(actual) != required:
            failures.append("OUTPUT_FIELDS")
            continue
        for rule in contract["rules"]:
            x = source[rule["from"]]
            mode = rule["op"]
            # Independent derivation, deliberately separate from the producer.
            if mode == "copy":
                expected = x
            elif mode == "strip":
                expected = str(x).strip()
            elif mode == "upper":
                expected = str(x).upper()
            else:
                expected = str(x).lower()
            if type(actual[rule["to"]]) is not type(expected) or actual[rule["to"]] != expected:
                failures.append("VALUE_MISMATCH")
    return sorted(set(failures))


def run(request):
    """Return result + hash-bound local replay record; NOT a signed attestation."""
    try:
        contract, rows = checked_request(request)
        delivery = produce(contract, rows)
        failures = verify(contract, rows, delivery)
        verdict = {
            "schema": VERSION,
            "accepted": not failures,
            "errors": failures,
            "source_sha256": digest(rows),
            "contract_sha256": digest(contract),
            "delivery_sha256": digest(delivery),
            "verification": "separate local recomputation; not external certification",
        }
        verdict["receipt_sha256"] = digest(verdict)
        return {"delivery": delivery, "receipt": verdict}
    except Refused as exc:
        return {"delivery": None, "receipt": {
            "schema": VERSION, "accepted": False, "errors": [str(exc)],
            "verification": "input refused; no delivery",
        }}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, _format, *_args):
        # Do not log request bodies or user-controlled identifiers.
        return

    def do_GET(self):
        if self.path != "/healthz":
            return self.reply(404, {"error": "NOT_FOUND"})
        self.reply(200, {"ready": True, "version": VERSION, "payments": "disabled"})

    def do_POST(self):
        if self.path != "/v0/transform":
            return self.reply(404, {"error": "NOT_FOUND"})
        if self.headers.get_content_type() != "application/json":
            return self.reply(415, {"error": "JSON_REQUIRED"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.reply(400, {"error": "INVALID_CONTENT_LENGTH"})
        if not 0 < length <= MAX_BODY:
            return self.reply(413, {"error": "REQUEST_SIZE"})
        raw = self.rfile.read(length)
        try:
            result = run(strict_json(raw.decode("utf-8")))
        except (Refused, UnicodeDecodeError) as exc:
            return self.reply(400, {"error": str(exc)})
        self.reply(200 if result["receipt"]["accepted"] else 422, result)

    def reply(self, code, data):
        body = canonical(data)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--serve", action="store_true", help="local loopback API only")
    p.add_argument("--port", type=int, default=8788)
    opts = p.parse_args()
    if opts.serve:
        if not 1024 <= opts.port <= 65535:
            raise SystemExit("Port must be between 1024 and 65535")
        server = ThreadingHTTPServer(("127.0.0.1", opts.port), Handler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    else:
        raw = sys.stdin.buffer.read(MAX_BODY + 1)
        if len(raw) > MAX_BODY:
            raise SystemExit("Input too large")
        try:
            print(json.dumps(run(strict_json(raw.decode("utf-8"))),
                             ensure_ascii=False, sort_keys=True))
        except (Refused, UnicodeDecodeError) as exc:
            raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
