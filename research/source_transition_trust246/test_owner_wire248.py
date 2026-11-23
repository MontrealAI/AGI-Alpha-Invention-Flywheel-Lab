"""Fixed adversarial tests for P0-248's synthetic owner-v2 wire reference."""
import ast
import copy
from pathlib import Path
import unittest

from owner_wire248 import (BASE_FIELDS, MAX_BLOB_BYTES, MAX_TICKET_BYTES, V2,
                           canonical, externalize_owner_v2,
                           owner_pre_sign_compare, strict_blob)


def fixture(queued=True):
    r = {k: {"sha256": "a" * 64} for k in ("from_source", "to_source")}
    r.update(schema='agi-alpha/native-source-transition/v1',
             id='SYNTHETIC_NO_ACCOUNT', account_path='no/real/account',
             counter=2, expected_state_digest='d' * 64, day=14,
             historical_root='none', verifier_files={'x.py': 'c' * 64},
             prior_record={'cash': 80, 'claims': 25, 'permanent_tail': [25],
                           'ledger': [{'event': 'COLLECTED', 'amount': 80}]},
             prior_envelope={'body': {'actions': [1, 2]},
                             'signature': 'SYNTHETIC_NOT_REAL'},
             operating={'prior_checkpoint': {'processed_events': 4,
                  'queue': [{'kind': 'settlement', 'due': 18}] if queued else [],
                  'claims': [{'amount': 25, 'due': 28}]},
                  'from_runtime': 'old'})
    return r


class OwnerWire248Test(unittest.TestCase):
    def test_v2_three_blob_fields_exact_owner_wire_shape(self):
        old = fixture()
        before = copy.deepcopy(old)
        wire, blobs = externalize_owner_v2(old)
        self.assertEqual(set(wire), BASE_FIELDS | {'evidence'})
        self.assertEqual(wire['schema'], V2)
        self.assertEqual(set(wire['evidence']), {'prior_record', 'prior_envelope', 'operating'})
        self.assertEqual(len(blobs), 3)
        self.assertLess(len(canonical({'body':wire,'signature':'0'*64})), MAX_TICKET_BYTES)
        self.assertEqual(owner_pre_sign_compare(old, wire, blobs), canonical(wire))
        self.assertEqual(old, before)

    def test_two_field_legacy_no_operating_compatible(self):
        old = fixture(); old.pop('operating')
        wire, blobs = externalize_owner_v2(old)
        self.assertEqual(set(wire['evidence']), {'prior_record', 'prior_envelope'})
        self.assertEqual(owner_pre_sign_compare(old, wire, blobs), canonical(wire))

    def test_oversized_operating_outside_16mb_signed_ticket_can_externalize(self):
        old = fixture()
        old['operating']['prior_checkpoint']['synthetic_large_queue'] = 'Q' * (16_000_000 + 100)
        self.assertGreater(len(canonical(old)), MAX_TICKET_BYTES)
        wire, blobs = externalize_owner_v2(old)
        self.assertEqual(len(blobs), 3)
        self.assertLessEqual(max(map(len, blobs.values())), MAX_BLOB_BYTES)
        self.assertLess(len(canonical({'body':wire,'signature':'0'*64})), MAX_TICKET_BYTES)
        self.assertEqual(owner_pre_sign_compare(old, wire, blobs), canonical(wire))

    def test_missing_operating_ref_and_queue_modification_fail(self):
        old = fixture(); wire, blobs = externalize_owner_v2(old)
        lost = copy.deepcopy(wire); del lost['evidence']['operating']
        with self.assertRaises(ValueError):owner_pre_sign_compare(old, lost, blobs)
        altered = copy.deepcopy(old); altered['operating']['prior_checkpoint']['queue'] = []
        with self.assertRaises(ValueError):owner_pre_sign_compare(altered, wire, blobs)

    def test_cash_claim_source_counter_day_and_account_tamper_fail(self):
        old = fixture(); wire, blobs = externalize_owner_v2(old)
        for field, value in [('counter',3), ('day',15),
                             ('account_path','different/account'),
                             ('from_source', {'sha256':'x'*64})]:
            candidate = copy.deepcopy(wire); candidate[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                owner_pre_sign_compare(old, candidate, blobs)
        for field, value in [('cash',999), ('claims',0), ('permanent_tail',[])]:
            altered = copy.deepcopy(old); altered['prior_record'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                owner_pre_sign_compare(altered, wire, blobs)

    def test_missing_swapped_modified_extra_blobs_fail(self):
        old = fixture(); wire, blobs = externalize_owner_v2(old)
        b = dict(blobs); b.pop(wire['evidence']['operating']['sha256'])
        with self.assertRaises(ValueError):owner_pre_sign_compare(old, wire, b)
        b = dict(blobs); sha = wire['evidence']['prior_record']['sha256']
        b[sha] = b[sha].replace(b'"cash":80', b'"cash":90')
        with self.assertRaises(ValueError):owner_pre_sign_compare(old, wire, b)
        b = dict(blobs); b['f'*64] = b'{}'
        with self.assertRaises(ValueError):owner_pre_sign_compare(old, wire, b)
        bad = copy.deepcopy(wire)
        bad['evidence']['operating'], bad['evidence']['prior_record'] = (
            bad['evidence']['prior_record'], bad['evidence']['operating'])
        with self.assertRaises(ValueError):owner_pre_sign_compare(old, bad, blobs)

    def test_wrong_digest_length_and_schema_fail(self):
        old = fixture(); wire, blobs = externalize_owner_v2(old)
        for field, value in [('sha256','0'*64),('bytes',0),('bytes',MAX_BLOB_BYTES+1)]:
            bad = copy.deepcopy(wire); bad['evidence']['operating'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                owner_pre_sign_compare(old,bad,blobs)
        bad = copy.deepcopy(wire); bad['schema'] = 'downgrade'
        with self.assertRaises(ValueError):owner_pre_sign_compare(old,bad,blobs)

    def test_strict_blob_rejects_duplicate_noncanonical_depth_and_nonfinite(self):
        raws = [b'{"x":1,"x":2}', b' {"a":1}', b'{"z":2,"a":1}',
                b'{"x":NaN}', b'{"x":1e999}', b'\xff',
                b'['*129 + b'1' + b']'*129]
        for raw in raws:
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):strict_blob(raw)

    def test_no_operating_code_execution_or_real_account_access(self):
        old = fixture()
        old['operating']['prior_checkpoint']['code_as_text'] = "__import__('os').getenv('SECRET')"
        wire, blobs = externalize_owner_v2(old)
        self.assertEqual(owner_pre_sign_compare(old,wire,blobs),canonical(wire))
        module = Path(__file__).with_name('owner_wire248.py').read_text()
        tree = ast.parse(module)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import,ast.ImportFrom)):
                root = (node.module or '').split('.')[0] if isinstance(node,ast.ImportFrom) else ''
                imports = {root} if root else {x.name.split('.')[0] for x in node.names}
                self.assertFalse(imports & {'os','subprocess','importlib','pathlib'})
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                self.assertNotIn(node.func.id, {'exec','eval','open','__import__'})
        self.assertNotIn('JournalAccount',module)
        self.assertNotIn('_account._key',module)


if __name__ == '__main__':
    unittest.main()
