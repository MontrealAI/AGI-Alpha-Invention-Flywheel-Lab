import tempfile
import unittest
from pathlib import Path
from p0_multibranch_financial_closure import preflight, source_paths


class SourceClosureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def src(self, name, paths):
        p = self.root / name
        p.write_text('SOURCE_PATHS = ' + repr(tuple(paths)) + '\n')
        return p

    def test_four_way_union_and_missing_paths(self):
        a = self.src('main.py', ['common.py', 'finance.py'])
        b = self.src('migration.py', ['finance.py', 'migration.py'])
        c = self.src('capital.py', ['finance.py', 'terms.py'])
        d = self.src('channel.py', ['finance.py', 'channel.py'])
        future = self.src('proposed.py', ['channel.py', 'terms.py', 'finance.py', 'migration.py', 'common.py'])
        r = preflight([('main', a), ('migration', b), ('capital', c), ('channel', d)], future)
        self.assertEqual(r['required_count'], 5)
        self.assertTrue(r['candidate']['accepted'])
        self.assertEqual(r['required_missing_by_reference']['main'], ['channel.py', 'migration.py', 'terms.py'])

    def test_reject_missing_candidate_path(self):
        a = self.src('a.py', ['finance.py'])
        b = self.src('b.py', ['migration.py'])
        candidate = self.src('c.py', ['finance.py'])
        r = preflight([('a', a), ('b', b)], candidate)
        self.assertFalse(r['candidate']['accepted'])
        self.assertEqual(r['candidate']['missing_required_paths'], ['migration.py'])

    def test_reject_duplicate_or_tampered_lists(self):
        for text in ["SOURCE_PATHS=('a.py','a.py')", "SOURCE_PATHS=('a.py',)\nSOURCE_PATHS=('b.py',)", "SOURCE_PATHS=imported", "SOURCE_PATHS=('/tmp/a.py',)", "SOURCE_PATHS=('a/../b.py',)", "SOURCE_PATHS=('x\\\\z.py',)"]:
            with self.subTest(text=text), self.assertRaises((ValueError, SyntaxError)):
                source_paths(text.encode())

    def test_reject_duplicate_labels(self):
        a = self.src('a.py', ['finance.py'])
        with self.assertRaises(ValueError):
            preflight([('same', a), ('same', a)], a)

    def test_reject_symlink_and_missing_sources(self):
        a = self.src('a.py', ['finance.py'])
        link = self.root/'linked.py'
        link.symlink_to(a)
        with self.assertRaises(ValueError):
            preflight([('a', link)], a)
        with self.assertRaises(ValueError):
            preflight([('a', self.root/'missing.py')], a)

    def test_reject_unbounded_and_invalid_labels(self):
        a = self.src('a.py', ['finance.py'])
        with self.assertRaises(ValueError):
            preflight([('', a)], a)
        with self.assertRaises(ValueError):
            preflight([(str(i), a) for i in range(17)], a)


if __name__ == '__main__':
    unittest.main()
