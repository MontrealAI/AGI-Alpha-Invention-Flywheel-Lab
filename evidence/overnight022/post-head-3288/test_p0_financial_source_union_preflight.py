import unittest
from p0_financial_source_union_preflight import check, source_paths


class SourceUnionPreflightTests(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(check("SOURCE_PATHS=('a.py','b.py')", "SOURCE_PATHS=('a.py','b.py')")['accepted'])

    def test_expanded(self):
        result = check("SOURCE_PATHS=('a.py','b.py')", "SOURCE_PATHS=('b.py','c.py','a.py')")
        self.assertEqual((result['accepted'], result['union_paths'], result['missing_required_paths']), (True, 3, []))

    def test_missing(self):
        result = check("SOURCE_PATHS=('a.py','b.py')", "SOURCE_PATHS=('b.py','c.py')")
        self.assertFalse(result['accepted'])
        self.assertEqual(result['missing_required_paths'], ['a.py'])

    def test_missing_assignment(self):
        with self.assertRaisesRegex(ValueError, 'EXACT_SOURCE_PATHS_ASSIGNMENT_REQUIRED'):
            source_paths('PATHS=("a.py",)')

    def test_duplicate(self):
        with self.assertRaisesRegex(ValueError, 'REGULAR_UNIQUE_SOURCE_PATHS_REQUIRED'):
            source_paths("SOURCE_PATHS=('a.py','a.py')")

    def test_nonliteral_and_escape(self):
        for source in ("SOURCE_PATHS=unknown", "SOURCE_PATHS=('../other.py',)", "SOURCE_PATHS=('/root.py',)"):
            with self.subTest(source=source), self.assertRaises((ValueError, SyntaxError)):
                source_paths(source)


if __name__ == '__main__':
    unittest.main()
