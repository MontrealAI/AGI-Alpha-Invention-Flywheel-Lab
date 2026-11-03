import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
from .help import README, diagnose


class HelpTests(unittest.TestCase):
    def test_known_errors_cite_actual_current_sections(self):
        examples = {
            'ModuleNotFoundError: No module named scipy': 'installation',
            'EXACT_ORACLE_RESOURCE_CHECKPOINT_NOT_INFEASIBILITY': 'resources',
            'REQUEST_BINDING_MISMATCH': 'input',
            'EXTERNAL_PROPOSAL_FILE_REQUIRED_NO_ACCOUNT_WILL_BE_CALLED': 'external',
            'model unavailable': 'external',
            'OUTPUT_EXISTS_AND_IS_NOT_IDENTICAL_REGULAR_FILE': 'output',
        }
        document = README.read_text(encoding='utf-8')
        for error, topic in examples.items():
            with self.subTest(error=error):
                result = diagnose(error)
                self.assertEqual(result['status'], 'DOCUMENTED')
                self.assertEqual(result['topic'], topic)
                self.assertEqual(result['documentation_sha256'], hashlib.sha256(document.encode()).hexdigest())
                citation = result['citations'][0]
                self.assertIn(citation['excerpt'], document)
                self.assertEqual(document.splitlines()[citation['line']-1], '### ' + citation['section'])

    def test_unknown_and_conflicting_queries_do_not_invent_diagnosis(self):
        for query in ['Is this plant safe to operate?', 'resource checkpoint and module installation failure']:
            result = diagnose(query)
            self.assertEqual(result['status'], 'UNKNOWN')
            self.assertIn('Stop the affected step', result['next_step'])
            self.assertEqual(result['citations'][0]['section'], 'Unknown or unresolved issues')

    def test_reads_only_product_document_and_does_not_echo_question(self):
        real_read = Path.read_text
        calls = []
        def read(path, *args, **kwargs):
            calls.append(path)
            return real_read(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read):
            result = diagnose('/tmp/unrelated-private-file-is-not-a-document-source')
        self.assertEqual(calls, [README])
        self.assertNotIn('/tmp/', json.dumps(result))

    def test_cli_exposes_document_lookup(self):
        result = subprocess.run([sys.executable, '-m', 'omega.help', 'model unavailable'], cwd=README.parents[1], text=True, capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)['topic'], 'external')


if __name__ == '__main__':
    unittest.main()
