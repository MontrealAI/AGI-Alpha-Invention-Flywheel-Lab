"""Frozen A2A198 checks using the exact PR484 original gate module.

A2A198_GATE must be the original gate.py, pinned by the hosted workflow.
"""
from __future__ import annotations

import http.client
import json
import os
import threading
import unittest

import a2a_adapter as bridge


def payload():
    return {'contract': {'id_field': 'id', 'rules': [
        {'from': 'name', 'to': 'customer', 'op': 'strip'},
        {'from': 'country', 'to': 'region', 'op': 'upper'}]},
        'source_rows': [{'id': 'a', 'name': '  Ana  ', 'country': 'ca'}]}


def request(value=None):
    return {'jsonrpc': '2.0', 'id': 'req-1', 'method': 'SendMessage',
            'params': {'message': {'messageId': 'msg-1', 'role': 'ROLE_USER',
                                   'parts': [{'data': value if value is not None else payload(),
                                              'mediaType': 'application/json'}]}}}


class P198(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gate_path = os.environ.get('A2A198_GATE')
        if not gate_path:
            raise RuntimeError('A2A198_GATE must name the independently checked original PR484 gate.py')
        cls.gate = bridge.load_gate(gate_path)
        cls.server = bridge.ThreadingHTTPServer(('127.0.0.1', 0), bridge.handler(cls.gate, 8795))
        # The server handler must advertise the dynamically allocated actual test port.
        cls.server.RequestHandlerClass = bridge.handler(cls.gate, cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=3)
        cls.server.server_close()

    def http(self, method, path, data=None, content_type='application/json'):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=4)
        try:
            headers = {'Content-Type': content_type}
            if data is None:
                conn.request(method, path)
            else:
                if not isinstance(data, bytes):
                    data = bridge._encode(data)
                conn.request(method, path, body=data, headers=headers)
            resp = conn.getresponse()
            return resp.status, json.loads(resp.read())
        finally:
            conn.close()

    def test_A1_v1_card_honestly_scoped(self):
        c = bridge.card(8795)
        self.assertEqual(c['supportedInterfaces'][0]['protocolBinding'], 'JSONRPC')
        self.assertEqual(c['supportedInterfaces'][0]['protocolVersion'], '1.0')
        self.assertEqual(c['capabilities']['streaming'], False)
        self.assertEqual(c['capabilities']['pushNotifications'], False)
        self.assertIn('Research Only', c['name'])
        self.assertNotIn('securitySchemes', c)
        self.assertEqual(len(c['skills']), 1)

    def test_A2_actual_discovery_GET(self):
        code, c = self.http('GET', bridge.DISCOVERY_PATH)
        self.assertEqual(code, 200)
        self.assertEqual(c['supportedInterfaces'][0]['url'],
                         f'http://127.0.0.1:{self.server.server_port}/a2a')

    def test_A3_actual_loopback_sendmessage_original_gate(self):
        code, outcome = self.http('POST', bridge.A2A_PATH, request())
        self.assertEqual(code, 200)
        self.assertEqual(outcome['id'], 'req-1')
        msg = outcome['result']['message']
        self.assertEqual(msg['role'], 'ROLE_AGENT')
        self.assertTrue(msg['parts'][0]['data']['receipt']['accepted'])
        self.assertEqual(msg['parts'][0]['data']['delivery'][0]['customer'], 'Ana')

    def test_A4_exact_direct_incumbent_parity(self):
        direct = self.gate.run(payload())
        bridged = bridge.dispatch(bridge._encode(request()), self.gate)
        result = bridged['result']['message']['parts'][0]['data']
        self.assertEqual(result, direct)
        self.assertEqual(result['receipt']['source_sha256'], direct['receipt']['source_sha256'])
        self.assertEqual(result['receipt']['delivery_sha256'], direct['receipt']['delivery_sha256'])

    def test_A5_duplicate_or_nonfinite_JSON_refused(self):
        for bad in (b'{"id":"x","id":"y"}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.subTest(bad=bad):
                self.assertIn('error', bridge.dispatch(bad, self.gate))

    def test_A6_v03_role_or_kind_refused(self):
        x = request(); x['params']['message']['role'] = 'user'
        self.assertIn('error', bridge.dispatch(bridge._encode(x), self.gate))
        x = request(); x['params']['message']['parts'][0]['kind'] = 'data'
        self.assertIn('error', bridge.dispatch(bridge._encode(x), self.gate))

    def test_A7_wrong_method_and_invalid_envelope(self):
        x = request(); x['method'] = 'message/send'
        self.assertEqual(bridge.dispatch(bridge._encode(x), self.gate)['error']['code'], -32601)
        x = request(); x['jsonrpc'] = '1.0'
        self.assertEqual(bridge.dispatch(bridge._encode(x), self.gate)['error']['code'], -32600)
        x = request(); x['id'] = True
        self.assertEqual(bridge.dispatch(bridge._encode(x), self.gate)['error']['code'], -32600)

    def test_A8_unsupported_multiple_parts_or_tasks(self):
        x = request(); x['params']['message']['parts'].append({'text': 'extra'})
        self.assertIn('error', bridge.dispatch(bridge._encode(x), self.gate))
        x = request(); x['params']['message']['taskId'] = 'something'
        self.assertIn('error', bridge.dispatch(bridge._encode(x), self.gate))
        x = request(); x['params']['message']['parts'] = [{'raw': 'AQID'}]
        self.assertIn('error', bridge.dispatch(bridge._encode(x), self.gate))

    def test_A9_oversized_body_refused(self):
        self.assertEqual(bridge.dispatch(b'x' * (bridge.MAX_BODY + 1), self.gate)['error']['code'], -32600)
        code, body = self.http('POST', bridge.A2A_PATH, b'x' * (bridge.MAX_BODY + 1))
        self.assertEqual(code, 413)
        self.assertIn('error', body)

    def test_A10_invalid_original_contract_refused_without_leakage(self):
        x = request(); x['params']['message']['parts'][0]['data']['contract']['rules'][0]['op'] = 'exec'
        response = bridge.dispatch(bridge._encode(x), self.gate)
        self.assertEqual(response['error']['code'], -32602)
        self.assertNotIn('source_rows', json.dumps(response))
        x = request(); x['params']['message']['parts'][0]['data'] = {'secret': 'private'}
        response = bridge.dispatch(bridge._encode(x), self.gate)
        self.assertNotIn('private', json.dumps(response))

    def test_A11_same_message_deterministic_not_two_sales(self):
        first = bridge.dispatch(bridge._encode(request()), self.gate)
        second = bridge.dispatch(bridge._encode(request()), self.gate)
        self.assertEqual(first, second)
        self.assertNotIn('payment', first)
        self.assertNotIn('settlement', first)

    def test_A12_bound_loopback_and_payments_disabled(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')
        code, status = self.http('GET', '/healthz')
        self.assertEqual(code, 200)
        self.assertEqual(status['payment'], 'DISABLED')
        self.assertRaises(ValueError, bridge.card, 80)
        self.assertEqual(self.http('POST', '/v1/quote', request())[0], 404)
        self.assertEqual(self.http('POST', '/v1/claim', request())[0], 404)


if __name__ == '__main__':
    unittest.main()
