"""Declared execution dependencies must survive adaptive frozen-source export."""
from pathlib import Path
import tempfile
import unittest
from adaptive_enterprise.instruments import SOURCE_PATHS
from adaptive_enterprise.runner import source_paths
ROOT=Path(__file__).resolve().parents[1]
class AdaptiveSourceDependencies(unittest.TestCase):
 def test_declared_instrument_dependencies_are_frozen(self):
  self.assertTrue(set(SOURCE_PATHS)<=set(source_paths(ROOT)))
  self.assertIn('connected_enterprise/__init__.py',source_paths(ROOT))
 def test_missing_declared_source_fails_closed(self):
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaisesRegex(ValueError,'ADAPTIVE_INSTRUMENT_SOURCE_DEPENDENCY_MISSING'):
    source_paths(Path(folder))
if __name__=='__main__':unittest.main()
