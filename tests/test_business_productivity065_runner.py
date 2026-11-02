"""Failure handling tests do not open business accounts or claim acceptance."""
from pathlib import Path
import json,subprocess,tempfile,unittest
from unittest.mock import patch
from business_productivity065.run import produce

class ProducerFailureTests(unittest.TestCase):
 def test_failed_producer_persists_telemetry_and_returns_rejection(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);destination=root/'producer';job={'request':{'instance_path':'input.json'}}
   with patch('business_productivity065.run.subprocess.run',return_value=subprocess.CompletedProcess([],2,'','intentional injected failure')):
    artifact,receipt=produce(root,job,destination,{'funding':'SEED'})
   self.assertIsNone(artifact);self.assertEqual(receipt['exit_code'],2)
   self.assertEqual(json.loads((root/'producer-resource.json').read_text())['exit_code'],2)
 def test_start_failure_preserves_costed_resource_receipt(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch('business_productivity065.run.subprocess.run',side_effect=OSError('intentional start failure')):
    artifact,receipt=produce(root,{'request':{'instance_path':'input.json'}},root/'producer',{'funding':'EARNED'})
   self.assertIsNone(artifact);self.assertEqual(receipt['exit_code'],127)
   self.assertTrue((root/'producer-resource.json').is_file())
 def test_exit_zero_missing_artifact_is_rejection_not_lost_account(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with patch('business_productivity065.run.subprocess.run',return_value=subprocess.CompletedProcess([],0,'','')):
    artifact,receipt=produce(root,{'request':{'instance_path':'input.json'}},root/'producer',{'funding':'SEED'})
   self.assertIsNone(artifact);self.assertIn('artifact_error',receipt)
   self.assertIn('artifact_error',json.loads((root/'producer-resource.json').read_text()))
if __name__=='__main__':unittest.main()
