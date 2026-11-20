"""P200 frozen original-source positive-reference tests (actual loopback HTTP)."""
from __future__ import annotations

import http.client
import json
import os
import threading
import unittest

import a2a_adapter as original
import version_reference as fixed


def business_payload():
    return {'contract': {'id_field': 'id', 'rules': [
        {'from': 'name', 'to': 'customer', 'op': 'strip'},
        {'from': 'country', 'to': 'region', 'op': 'upper'}]},
        'source_rows': [{'id': 'a', 'name': '  Ana  ', 'country': 'ca'}]}


def message():
    return {'jsonrpc': '2.0', 'id': 'req-1', 'method': 'SendMessage',
            'params': {'message': {'messageId': 'msg-1',
                                   'role': 'ROLE_USER',
                                   'parts': [{'data': business_payload(),
                                              'mediaType': 'application/json'}]}}}


class CountedOriginal:
    def __init__(self, original_gate):
        self.source = original_gate
        self.checks = 0
        self.executions = 0

    def checked_request(self, value):
        self.checks += 1
        return self.source.checked_request(value)

    def run(self, value):
        self.executions += 1
        return self.source.run(value)


class FixedVersionHTTP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = os.environ.get('A2A200_GATE')
        if not source:
            raise RuntimeError('A2A200_GATE must be the pinned original PR484 source')
        cls.original_gate = original.load_gate(source)
        cls.gate = CountedOriginal(cls.original_gate)
        cls.server = original.ThreadingHTTPServer(
            ('127.0.0.1', 0), fixed.reference_handler(cls.gate, 8795))
        cls.server.RequestHandlerClass = fixed.reference_handler(
            cls.gate, cls.server.server_port)
        cls.worker = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.worker.join(timeout=4)
        cls.server.server_close()

    def setUp(self):
        self.gate.checks = self.gate.executions = 0

    def http_post(self, versions, path=original.A2A_PATH):
        raw = original._encode(message())
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=4)
        try:
            conn.putrequest('POST', path)
            conn.putheader('Content-Type', 'application/json')
            conn.putheader('Content-Length', str(len(raw)))
            for value in versions:
                conn.putheader('A2A-Version', value)
            conn.endheaders()
            conn.send(raw)
            res = conn.getresponse()
            return res.status, json.loads(res.read())
        finally:
            conn.close()

    def assert_rejected(self, versions):
        code, answer = self.http_post(versions)
        self.assertEqual(code, 200)
        self.assertEqual(answer['error']['code'], -32009)
        self.assertNotIn('result', answer)
        self.assertEqual(self.gate.checks, 0)
        self.assertEqual(self.gate.executions, 0)

    def assert_accepted(self, versions):
        code, answer = self.http_post(versions)
        self.assertEqual(code, 200)
        self.assertEqual(answer['id'], 'req-1')
        self.assertNotIn('error', answer)
        self.assertEqual(self.gate.checks, 1)
        self.assertEqual(self.gate.executions, 1)
        delivered = answer['result']['message']['parts'][0]['data']
        self.assertEqual(delivered, self.original_gate.run(business_payload()))
        self.assertTrue(delivered['receipt']['accepted'])

    def test_V1_v1_is_original_gate_parity(self):
        self.assert_accepted(['1.0'])

    def test_V2_absent_is_legacy_03_and_refused(self):
        self.assert_rejected([])

    def test_V3_explicit_03_refused(self):
        self.assert_rejected(['0.3'])

    def test_V4_future_20_refused(self):
        self.assert_rejected(['2.0'])

    def test_V5_patch_version_ignored(self):
        self.assert_accepted(['1.0.3'])

    def test_V6_empty_is_legacy_03_and_refused(self):
        self.assert_rejected([''])

    def test_V7_mixed_duplicate_versions_refused(self):
        self.assert_rejected(['1.0', '2.0'])

    def test_V8_identical_duplicate_versions_refused(self):
        self.assert_rejected(['1.0', '1.0'])

    def test_V9_comma_list_refused(self):
        self.assert_rejected(['1.0,2.0'])

    def test_V10_malformed_version_refused(self):
        self.assert_rejected(['v1.0'])

    def test_V11_advertised_discovery_remains_v1(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=4)
        try:
            conn.request('GET', original.DISCOVERY_PATH)
            res = conn.getresponse()
            card = json.loads(res.read())
            self.assertEqual(res.status, 200)
            self.assertEqual(card['supportedInterfaces'][0]['protocolVersion'], '1.0')
            self.assertEqual(self.gate.executions, 0)
        finally:
            conn.close()

    def test_V12_wrong_path_original_404(self):
        code, response = self.http_post(['1.0'], '/v1/claim')
        self.assertEqual(code, 404)
        self.assertEqual(response['error'], 'NOT_FOUND')
        self.assertEqual(self.gate.executions, 0)

    def test_V13_original_unversioned_http_test_must_be_updated(self):
        # Previous PR498 test_a2a.py helper sends Content-Type only.
        # Do not edit that original source or reclassify its old green run.
        self.assert_rejected([])
        # The original direct, non-HTTP function still works identically.
        direct = original.dispatch(original._encode(message()), self.original_gate)
        self.assertTrue(direct['result']['message']['parts'][0]['data']['receipt']['accepted'])
        self.assertEqual(self.gate.executions, 0)


if __name__ == '__main__':
    unittest.main()
