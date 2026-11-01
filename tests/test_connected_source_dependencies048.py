"""Overnight executable drivers and their frozen inputs survive source export."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from connected_enterprise.runner import source_paths
ROOT=Path(__file__).resolve().parents[1]

class OvernightSourceDependencies(unittest.TestCase):
    def test_driver_inputs_and_operator_contracts_ship(self):
        names=set(source_paths(ROOT))
        self.assertTrue({'experiments/startup_acquisition048.py',
            'experiments/evidence_revalidation048.py','tests/test_evidence_revalidation048.py',
            'scripts/run_commoncost026.py','scripts/qualify_market_index049.py',
            'campaign/account-year-048/INPUT.json','campaign/composed-window-049/PROTOCOL.json',
            'campaign/evidence-revalidation-048/PREREGISTRATION.json',
            'docs/harness/STARTUP_ACQUISITION048.md','docs/harness/DEVELOPER_GUIDE.md'} <= names)

    def test_partial_overnight_distribution_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'connected_enterprise').mkdir()
            (root/'connected_enterprise/startup_acquisition048.py').touch()
            with patch('connected_enterprise.runner.inherited_paths',return_value=[]):
                with self.assertRaisesRegex(ValueError,'OVERNIGHT048_SOURCE_DEPENDENCY_MISSING'):
                    source_paths(root)

if __name__=='__main__':unittest.main()
