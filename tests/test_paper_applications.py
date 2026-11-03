"""Paper coverage is a maintenance gate, never a semantic qualification badge."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('paper_applications', ROOT / 'scripts/check_paper_applications.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class PaperApplicationCoverage(unittest.TestCase):
    def setUp(self):
        self.audit = gate.read_json(ROOT / 'docs/harness/PAPER_APPLICATIONS.json')

    def rejected(self, audit, reason):
        with self.assertRaisesRegex(ValueError, reason):
            gate.validate(ROOT, audit)

    def test_current_catalogue_has_reviewed_paths_without_qualification_claim(self):
        result = gate.validate(ROOT)
        self.assertEqual(result['paper_editions'], 20)
        self.assertEqual(result['status'], 'COVERAGE_AND_REVIEWED_IDENTITIES_VALID')
        self.assertIn('No execution, correctness, optimality', result['scope'])
        self.assertGreater(result['statuses']['guidance_only'], 0)

    def test_all_pr_workflow_invokes_gate_without_incomplete_runtime_export(self):
        for name in ('connected014.yml', 'connected014-release.yml'):
            workflow = (ROOT / '.github/workflows' / name).read_text()
            self.assertIn("run: python -m unittest discover -s tests -p 'test_paper_applications.py' -v", workflow)
            self.assertIn('  pull_request:', workflow)
            if name == 'connected014-release.yml':
                self.assertIn('  push:\n    branches: [main]', workflow)
                self.assertEqual(workflow.count('Check paper application coverage'), 1)
                self.assertLess(workflow.index('Check paper application coverage'),
                                workflow.index('Bind immutable release assets'))
        self.assertFalse(Path(__file__).name.startswith('test_connected'))

    def test_missing_paper_fails(self):
        self.audit['papers'].pop()
        self.rejected(self.audit, 'COMPLETE_PUBLICATION_COVERAGE_REQUIRED')

    def test_duplicate_paper_cannot_hide_an_omission(self):
        self.audit['papers'][-1] = copy.deepcopy(self.audit['papers'][0])
        self.rejected(self.audit, 'COMPLETE_PUBLICATION_COVERAGE_REQUIRED')

    def test_changed_pdf_edition_requires_a_new_applicability_review(self):
        self.audit['papers'][0]['pdf_sha256'] = '0' * 64
        self.rejected(self.audit, 'PAPER_EDITION_CHANGED')

    def test_a_citation_cannot_claim_implementation(self):
        row = next(r for r in self.audit['papers'] if r['status'] == 'partial_runtime')
        for field in ('observed_code', 'checks'):
            bad = copy.deepcopy(self.audit)
            next(r for r in bad['papers'] if r['paper'] == row['paper'])[field] = []
            self.rejected(bad, 'CITATION_ONLY_IMPLEMENTATION_REFUSED')

    def test_truth_optimality_deployment_cannot_be_encoded_as_a_status(self):
        for status in ('implemented', 'optimal', 'qualified', 'deployed', True):
            bad = copy.deepcopy(self.audit)
            bad['papers'][0]['status'] = status
            self.rejected(bad, 'QUALIFICATION_OR_OPTIMALITY|EXPLICIT_APPLICATION_SCOPE')

    def test_stale_source_digest_fails(self):
        self.audit['papers'][0]['observed_code'][0]['sha256'] = '0' * 64
        self.rejected(self.audit, 'REVIEWED_SOURCE_CHANGED')

    def test_a_real_file_with_an_invented_symbol_fails(self):
        self.audit['papers'][0]['observed_code'][0]['symbol'] = 'does_not_exist'
        self.rejected(self.audit, 'EXECUTABLE_SYMBOL_NOT_FOUND')

    def test_scope_and_gap_cannot_be_omitted(self):
        for field in ('method', 'applicability', 'gap', 'next_step', 'pages'):
            bad = copy.deepcopy(self.audit)
            bad['papers'][0][field] = ' '
            self.rejected(bad, 'EXPLICIT_APPLICATION_SCOPE_REQUIRED')

    def test_a_markdown_link_is_not_executable_evidence(self):
        self.audit['papers'][0]['observed_code'][0]['path'] = 'AGENTS.md'
        self.rejected(self.audit, 'EXECUTABLE_PYTHON_SOURCE_REQUIRED')

    def test_path_traversal_and_symlink_are_rejected(self):
        for name in ('../AGENTS.md', '/etc/passwd', 'docs/../AGENTS.md', './AGENTS.md'):
            with self.assertRaisesRegex(ValueError, 'RELATIVE_SOURCE_PATH_REQUIRED'):
                gate.regular(ROOT, name)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'linked.py').symlink_to(ROOT / 'scripts/check_paper_applications.py')
            with self.assertRaisesRegex(ValueError, 'REGULAR_SOURCE_REQUIRED'):
                gate.regular(root, 'linked.py')

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'audit.json'
            path.write_text('{"status": "standalone", "status": "qualified"}')
            with self.assertRaisesRegex(ValueError, 'DUPLICATE_JSON_KEY'):
                gate.read_json(path)

    def test_changed_source_bytes_require_review_even_when_symbol_survives(self):
        reference = copy.deepcopy(self.audit['papers'][0]['observed_code'][0])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / reference['path']
            path.parent.mkdir(parents=True)
            path.write_bytes((ROOT / reference['path']).read_bytes() + b'\nCHANGED_IMPORT_OR_POLICY = True\n')
            with self.assertRaisesRegex(ValueError, 'REVIEWED_SOURCE_CHANGED'):
                gate.check_reference(root, reference)

    def test_unscoped_extra_claim_is_rejected(self):
        self.audit['papers'][0]['all_papers_correctly_used'] = True
        self.rejected(self.audit, 'EXACT_APPLICATION_FIELDS_REQUIRED')


if __name__ == '__main__':
    unittest.main()
