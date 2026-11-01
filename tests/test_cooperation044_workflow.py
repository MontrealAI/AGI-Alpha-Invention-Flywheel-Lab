"""Dependency-free guard for the explicit cooperation workflow export contract."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

def check_workflow(text):
    command = 'python -m pip install --only-binary=:all: -r requirements-commercial010.txt'
    if '      - run: |\n          ' + command not in text:
        raise ValueError('PIP_COMMAND_BLOCK_REQUIRED')
    if 'if: always()\n        uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02' not in text:
        raise ValueError('PINNED_COMPACT_UPLOAD_REQUIRED')
    marker = '          path: |\n'
    if text.count(marker) != 1:
        raise ValueError('ONE_EXPLICIT_PUBLIC_ALLOWLIST_REQUIRED')
    lines = []
    for line in text.split(marker, 1)[1].splitlines():
        if not line.startswith('            '):
            break
        lines.append(line.strip())
    if lines != ['${{ runner.temp }}/coop044-central.json', '${{ runner.temp }}/coop044-no_demand.json']:
        raise ValueError('PUBLIC_COMPARISON_PATHS_ONLY')
    if 'persist-credentials: false' not in text or 'contents: read' not in text:
        raise ValueError('READ_ONLY_CHECKOUT_REQUIRED')

class CooperationWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / '.github/workflows/cooperation044.yml').read_text()
    def test_contract(self): check_workflow(self.text)
    def test_unquoted_colon_rejected(self):
        with self.assertRaises(ValueError):
            check_workflow(self.text.replace('- run: |\n          python', '- run: python', 1))
    def test_private_directory_or_glob_rejected(self):
        for replacement in ['${{ runner.temp }}/coop044-*', '${{ runner.temp }}/coop044-central-fixed_capacity/private/RESULT.json']:
            with self.assertRaises(ValueError):
                check_workflow(self.text.replace('${{ runner.temp }}/coop044-central.json', replacement))
    def test_extra_path_rejected(self):
        with self.assertRaises(ValueError):
            check_workflow(self.text.replace('          if-no-files-found:', '            ${{ runner.temp }}/secret.json\n          if-no-files-found:'))
