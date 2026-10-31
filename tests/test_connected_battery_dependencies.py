import unittest
from pathlib import Path
from unittest.mock import patch
from connected_enterprise.runner import source_paths
from connected_enterprise.research_service import DEPENDENCIES
ROOT=Path(__file__).resolve().parents[1]
class BatteryDependencies(unittest.TestCase):
 def test_all_runtime_checker_and_test_dependencies_bound(self):
  names=set(source_paths(ROOT))
  self.assertTrue(set(DEPENDENCIES)<=names)
  self.assertIn('battery_service/study.py',names)
  self.assertIn('tests/test_pending_battery_native.py',names)
  self.assertIn('requirements-battery040.txt',names)
 def test_missing_physics_dependency_fails_closed(self):
  original=Path.is_file
  def present(p):return False if p==ROOT/'battery_service/physics.py' else original(p)
  with patch.object(Path,'is_file',present):
   with self.assertRaisesRegex(ValueError,'RESEARCH_SOURCE_DEPENDENCY_MISSING'):source_paths(ROOT)
