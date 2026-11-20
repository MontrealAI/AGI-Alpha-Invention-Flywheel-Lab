"""Offline A2A v1 JSON-RPC bridge to the unchanged PR484 gate.

Research-only loopback server. No A2A credentials, client money, sales or agent
identity attestation. Caller MUST provide an extracted, source-pinned gate.py.
"""
from __future__ import annotations

import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
from pathlib import Path

MAX_BODY = 262144
DISCOVERY_PATH = '/.well-known/agent-card.json'
A2A_PATH = '/a2a'
# Canonical Git blob for the immutable PR484 gate.py at b333a5f4.
PINNED_GATE_GIT_BLOB = '115cf8531df65a66dcc679e2d35cb03394cea11a'


class Refused(ValueError):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _strict_json(raw: bytes):
    def pairs(items):
        obj = {}
        for key, val in items:
            if key in obj:
                raise Refused(-32600, 'Duplicate JSON field')
            obj[key] = val
        return obj

    def no_constant(_):
        raise Refused(-32600, 'Nonfinite JSON value')

    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                          parse_constant=no_constant)
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, Refused):
            raise
        raise Refused(-32700, 'Invalid JSON') from exc


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def card(port):
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError('invalid loopback port')
    return {
        'name': 'MONTREAL.AI Offline Machine Asset — Research Only',
        'description': 'Unadmitted bounded record transformer using the existing independent local checker; no payment, certified provenance, authenticity, external access, or deployed commerce.',
        'version': '0.0.1',
        'supportedInterfaces': [{'url': f'http://127.0.0.1:{port}{A2A_PATH}',
                                 'protocolBinding': 'JSONRPC', 'protocolVersion': '1.0'}],
        'capabilities': {'streaming': False, 'pushNotifications': False},
        'defaultInputModes': ['application/json'],
        'defaultOutputModes': ['application/json'],
        'skills': [{
            'id': 'bounded-transform-local',
            'name': 'Offline bounded record transformation',
            'description': 'Copy, strip, uppercase and lowercase caller-supplied records; independent local replay verifier. A free, conventional implementation is an equally competent alternative.',
            'tags': ['research-only', 'no-payment', 'unadmitted', 'record-transformation'],
        }],
    }


def error(id_value, code, message):
    return {'jsonrpc': '2.0', 'id': id_value,
            'error': {'code': code, 'message': message}}


def dispatch(raw: bytes, gate):
    request_id = None
    try:
        if len(raw) > MAX_BODY:
            raise Refused(-32600, 'Request too large')
        p = _strict_json(raw)
        try:
            _encode(p)  # Reject unpaired surrogates before any adapter execution.
        except (UnicodeError, ValueError, OverflowError) as exc:
            raise Refused(-32600, 'Invalid canonical RPC') from exc
        if type(p) is not dict:
            raise Refused(-32600, 'Invalid RPC envelope')
        id_val = p.get('id')
        if type(id_val) not in (str, int) or len(str(id_val)) > 128:
            raise Refused(-32600, 'Invalid RPC id')
        request_id = id_val
        if p.get('jsonrpc') != '2.0' or set(p) != {'jsonrpc', 'method', 'params', 'id'}:
            raise Refused(-32600, 'Invalid RPC envelope')
        if p['method'] != 'SendMessage':
            raise Refused(-32601, 'Method not supported')
        params = p['params']
        if type(params) is not dict or set(params) != {'message'}:
            raise Refused(-32602, 'Only a fresh message is supported')
        msg = params['message']
        if type(msg) is not dict or set(msg) != {'messageId', 'role', 'parts'}:
            raise Refused(-32602, 'Invalid message or task continuation')
        msg_id = msg['messageId']
        if type(msg_id) is not str or not 1 <= len(msg_id) <= 128 or msg['role'] != 'ROLE_USER':
            raise Refused(-32602, 'Invalid v1 message identity or role')
        parts = msg['parts']
        if type(parts) is not list or len(parts) != 1:
            raise Refused(-32602, 'One structured data part required')
        part = parts[0]
        if type(part) is not dict or set(part) not in ({'data'}, {'data', 'mediaType'}):
            raise Refused(-32602, 'A2A v1 structured data required')
        if 'mediaType' in part and part['mediaType'] != 'application/json':
            raise Refused(-32602, 'Unsupported media type')
        payload = part['data']
        if type(payload) is not dict:
            raise Refused(-32602, 'Structured contract required')
        try:
            gate.checked_request(payload)
            result = gate.run(payload)
        except (ValueError, TypeError, OverflowError, UnicodeError) as exc:
            raise Refused(-32602, 'Invalid source or contract') from exc
        if type(result) is not dict or type(result.get('receipt')) is not dict or result['receipt'].get('accepted') is not True:
            raise Refused(-32603, 'Independent local acceptance failed')
        output_id = 'a2a198-' + hashlib.sha256(
            _encode([str(id_val), msg_id, payload])).hexdigest()[:40]
        return {'jsonrpc': '2.0', 'id': request_id,
                'result': {'message': {
                    'messageId': output_id, 'role': 'ROLE_AGENT',
                    'parts': [{'data': result, 'mediaType': 'application/json'}],
                }}}
    except Refused as exc:
        return error(request_id, exc.code, exc.message)
    except (OverflowError, TypeError, UnicodeError) as exc:
        return error(request_id, -32600, 'Invalid RPC request')


def handler(gate, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def respond(self, status, payload):
            raw = _encode(payload)
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == DISCOVERY_PATH:
                return self.respond(200, card(port))
            if self.path == '/healthz':
                return self.respond(200, {'ok': True, 'research_only': True, 'payment': 'DISABLED'})
            return self.respond(404, {'error': 'NOT_FOUND'})

        def do_POST(self):
            if self.path != A2A_PATH:
                return self.respond(404, {'error': 'NOT_FOUND'})
            if self.headers.get_content_type() != 'application/json':
                return self.respond(415, error(None, -32600, 'JSON required'))
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                size = -1
            if size <= 0 or size > MAX_BODY:
                return self.respond(413, error(None, -32600, 'Request size refused'))
            return self.respond(200, dispatch(self.rfile.read(size), gate))

    return Handler


def load_gate(path):
    p = Path(path).resolve(strict=True)
    if p.name != 'gate.py':
        raise ValueError('explicit original gate.py required')
    raw = p.read_bytes()
    git_blob = hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\x00' + raw).hexdigest()
    if git_blob != PINNED_GATE_GIT_BLOB:
        raise ValueError('ORIGINAL_GATE_SOURCE_CHANGED_OR_UNPINNED')
    spec = importlib.util.spec_from_file_location('pinned_asset_gate', p)
    if spec is None or spec.loader is None:
        raise ValueError('unable to import pinned gate')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, 'run', None)) or not callable(getattr(module, 'checked_request', None)):
        raise ValueError('original checker missing')
    return module


def main():
    p = argparse.ArgumentParser(description='Research-only offline A2A bridge')
    p.add_argument('--gate', required=True, help='Path to the pinned PR484 gate.py')
    p.add_argument('--port', type=int, default=8795)
    args = p.parse_args()
    c = card(args.port)
    gate = load_gate(args.gate)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(gate, args.port))
    print(json.dumps({'listen': '127.0.0.1', 'port': args.port,
                      'interface': c['supportedInterfaces'][0]['protocolBinding'],
                      'research_only': True, 'payment': 'DISABLED'}), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
