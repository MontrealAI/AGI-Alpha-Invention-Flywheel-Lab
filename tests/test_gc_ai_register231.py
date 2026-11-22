"""Independent ordinary CSV control and adversarial boundary cases."""
import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from tools import gc_ai_register231 as new

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://example.org/authorized.csv'


def make(rows):
    output = io.StringIO(newline='')
    csv.writer(output).writerows(rows)
    return output.getvalue().encode()


def check(raw):
    rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'), newline=''), strict=True))
    r = new.scan(raw, source_url=URL)
    assert r['row_count'] == len(rows)-1
    assert r['column_count'] == len(rows[0])
    for i in range(len(rows[0])):
        cells = [v[i] for v in rows[1:]]
        assert r['columns'][i]['empty'] == sum(v == '' for v in cells)
        assert r['columns'][i]['whitespace_only'] == sum(bool(v) and not v.strip() for v in cells)
        assert r['columns'][i]['nonblank'] == sum(bool(v.strip()) for v in cells)
    return r


class Tests(unittest.TestCase):
    def test_standard_control_parity(self):
        self.assertEqual(check(make([['system','role'],['x','review'],['y','']]))['row_count'],2)
    def test_multiline_quoted(self):
        self.assertEqual(check(make([['a'],['one\ntwo']]))['row_count'],1)
    def test_utf8_bom(self):
        self.assertEqual(check(b'\xef\xbb\xbf'+make([['a'],['b']]))['columns'][0]['name'],'a')
    def test_unicode(self):
        self.assertEqual(check(make([['Nom'],['Québec']]))['row_count'],1)
    def test_empty_vs_whitespace(self):
        r=check(make([['c'],[''],['  '],['value']]))
        self.assertEqual((r['columns'][0]['empty'],r['columns'][0]['whitespace_only'],r['columns'][0]['nonblank']),(1,1,1))
    def test_na_and_unknown_not_semantics(self):
        r=check(make([['Risk'],['N/A'],['unknown']]))
        self.assertEqual((r['columns'][0]['literal_na'],r['columns'][0]['literal_unknown']),(1,1))
        self.assertEqual(r['system_risk_impact_compliance_claim'],'NONE')
    def test_duplicate_heading_rejected(self):
        with self.assertRaisesRegex(new.Rejected,'DUPLICATE_HEADER'):
            new.scan(make([['x','x'],['a','b']]),source_url=URL)
    def test_malformed_width_rejected(self):
        with self.assertRaisesRegex(new.Rejected,'ROW_WIDTH_MISMATCH'):
            new.scan(b'a,b\n1\n',source_url=URL)
    def test_bad_encoding_rejected(self):
        with self.assertRaisesRegex(new.Rejected,'UTF8_REQUIRED'):
            new.scan(b'a\n\xff',source_url=URL)
    def test_digest_mismatch(self):
        with self.assertRaisesRegex(new.Rejected,'SOURCE_DIGEST_MISMATCH'):
            new.scan(make([['x'],['y']]),source_url=URL,expected_sha256='0'*64)
    def test_exact_duplicates_not_dropped(self):
        r=check(make([['x'],['a'],['a'],['b']]))
        self.assertEqual((r['row_count'],r['exact_duplicate_row_groups'],r['extra_duplicate_row_instances']),(3,1,1))
    def test_missing_field_no_semantic_inference(self):
        r=new.scan(make([['system'],['x']]),source_url=URL,requested_fields=['risk'])
        self.assertEqual(r['requested_exact_fields'][0]['status'],'SCHEMA_FIELD_ABSENT')
        self.assertEqual(r['system_risk_impact_compliance_claim'],'NONE')
    def test_order_and_deterministic_receipt(self):
        b=make([['x','y'],['a','b'],['c','d']])
        self.assertEqual(new.scan(b,source_url=URL),new.scan(b,source_url=URL))
        a=new.scan(b,source_url=URL)
        c=new.scan(make([['x','y'],['c','d'],['a','b']]),source_url=URL)
        self.assertEqual(a['row_count'],c['row_count'])
        self.assertNotEqual(a['source_sha256'],c['source_sha256'])
    def test_cli_create_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv';o=Path(d)/'o.json';p.write_bytes(make([['h'],['v']]))
            cmd=[sys.executable,str(ROOT/'tools/gc_ai_register231.py'),str(p),'--source-url',URL,'--output',str(o)]
            a=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(a.returncode,0,a.stderr)
            b=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(b.returncode,2)
            self.assertEqual(json.loads(o.read_text())['row_count'],1)
    def test_empty_data(self):
        with self.assertRaisesRegex(new.Rejected,'EMPTY_DATASET'):
            new.scan(b'a\n',source_url=URL)
    def test_broken_quote(self):
        with self.assertRaisesRegex(new.Rejected,'INVALID_CSV'):
            new.scan(b'a\n"never ended',source_url=URL)


if __name__ == '__main__':
    unittest.main()
