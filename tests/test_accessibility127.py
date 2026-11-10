import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.accessibility127 import produce, render, validate
from research.verify_accessibility127 import verify

INPUT = ROOT / 'campaign/accessibility127/PUBLIC_FACTS.json'


class PreregisteredAccessTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(INPUT.read_text())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)

    def files(self):
        produce(INPUT, self.out)
        return self.out / 'fact_sheet.html', self.out / 'MANIFEST.json'

    def test_T0_T1_deterministic_and_independent_replay(self):
        a, m = self.files()
        before = (a.read_bytes(), m.read_bytes())
        produce(INPUT, self.out)
        self.assertEqual(before, (a.read_bytes(), m.read_bytes()))
        report = verify(INPUT, a, m)
        self.assertTrue(report['accepted'])
        self.assertEqual(report['records'], 3)

    def test_T2_missing_and_insecure_source(self):
        for url in ['', 'http://example.org', 'javascript:alert(1)', 'https://u:p@example.org/']:
            mutated = copy.deepcopy(self.data)
            mutated['records'][0]['source_url'] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                render(mutated)

    def test_T3_duplicate_or_unknown_grade(self):
        for field, value in [('id', self.data['records'][0]['id']), ('grade', 'self-asserted-official')]:
            mutated = copy.deepcopy(self.data)
            mutated['records'][1][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                render(mutated)

    def test_T4_html_in_title_escaped(self):
        mutated = copy.deepcopy(self.data)
        mutated['records'][0]['name'] = '<script>alert(1)</script> chart & story'
        out = render(mutated)
        self.assertNotIn(b'<script>', out)
        self.assertIn(b'&lt;script&gt;', out)

    def test_T5_input_changed_with_old_manifest(self):
        a, m = self.files()
        new_input = self.out / 'changed.json'
        mutated = copy.deepcopy(self.data)
        mutated['records'][0]['status'] = 'Signed customer contract'
        new_input.write_text(json.dumps(mutated), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'HASH_MISMATCH'):
            verify(new_input, a, m)

    def test_T6_missing_fact_invented_budget_invalid_date(self):
        for change in [('fact', ''), ('tender_budget_cad', '200000.00'), ('date', '2026-02-31')]:
            mutated = copy.deepcopy(self.data)
            if change[0] == 'tender_budget_cad':
                mutated[change[0]] = change[1]
            else:
                mutated['records'][1][change[0]] = change[1]
            with self.subTest(change=change), self.assertRaises(ValueError):
                render(mutated)

    def test_T7_no_tender_budget_or_conflated_fee(self):
        out = render(self.data).decode()
        self.assertIn('no tender budget or collected revenue', out.lower())
        self.assertNotIn('25,000', out)
        self.assertNotIn('100,000', out)
        self.assertIn('download fee is not a contract award', out)

    def test_T8_semantics_independently_verified(self):
        html, manifest = self.files()
        self.assertTrue(verify(INPUT, html, manifest)['accepted'])
        page = html.read_text()
        for required in ('<main id="main">', '<caption>', 'scope="row"', 'scope="col"', 'lang="en"', '<h1>', '<h2>', 'NO-BID / NO-DEPLOY'):
            self.assertIn(required, page)

    def test_T9_html_tamper_rejected(self):
        html, manifest = self.files()
        html.write_bytes(html.read_bytes().replace(b'NO-BID / NO-DEPLOY', b'APPROVED BID!', 1))
        with self.assertRaisesRegex(ValueError, 'HASH_MISMATCH'):
            verify(INPUT, html, manifest)

    def test_T9b_manifest_rehash_does_not_launder_changed_fact(self):
        html, manifest = self.files()
        original = html.read_bytes()
        modified = original.replace(b'Awarded listing; value unknown', b'Awarded listing; value verified', 1)
        self.assertNotEqual(original, modified)
        html.write_bytes(modified)
        m = json.loads(manifest.read_text())
        m['html_sha256'] = hashlib.sha256(html.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, 'FACT_MISMATCH'):
            verify(INPUT, html, manifest)


    def test_T10_rehashed_extra_commercial_claim_rejected(self):
        html, manifest = self.files()
        original = html.read_bytes()
        modified = original.replace(
            b'</main>', b'<p>Government signed a million-dollar order with us.</p></main>', 1)
        self.assertNotEqual(original, modified)
        html.write_bytes(modified)
        m = json.loads(manifest.read_text())
        m['html_sha256'] = hashlib.sha256(modified).hexdigest()
        manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError, 'UNEXPECTED_STATIC_TEXT'):
            verify(INPUT, html, manifest)

    def test_T11_rehashed_active_browser_markup_rejected(self):
        for injection in (b'<meta http-equiv="refresh" content="0;url=https://example.org/">',
                          b'<link rel="stylesheet" href="https://example.org/style.css">'):
            with self.subTest(injection=injection):
                html, manifest = self.files()
                original = html.read_bytes()
                modified = original.replace(b'<head>', b'<head>' + injection, 1)
                self.assertNotEqual(original, modified)
                html.write_bytes(modified)
                m = json.loads(manifest.read_text())
                m['html_sha256'] = hashlib.sha256(modified).hexdigest()
                manifest.write_text(json.dumps(m))
                with self.assertRaisesRegex(ValueError, 'UNSAFE_HTML_TAG_OR_ATTRIBUTE'):
                    verify(INPUT, html, manifest)


if __name__ == '__main__':
    unittest.main()
