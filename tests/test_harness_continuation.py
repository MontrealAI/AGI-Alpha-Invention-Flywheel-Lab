import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('continuation_proof', ROOT/'scripts/prove_harness_continuation.py')
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)


class ContinuationProofBoundaryTests(unittest.TestCase):
    def test_fault_refuses_unmarked_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'ISOLATED_PROOF_FIXTURE_REQUIRED'):
                proof.interrupt(Path(tmp))

    def test_checkpoint_refuses_unmarked_existing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'ISOLATED_PROOF_FIXTURE_REQUIRED'):
                proof.checkpoint(Path(tmp))

    def test_marker_is_bound_to_disposable_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'.isolated-continuation-proof.json').write_text(json.dumps(
                {'purpose':'DISPOSABLE_SYNTHETIC_CONTINUATION_PROOF','output':'/other'}))
            with self.assertRaisesRegex(ValueError, 'ISOLATED_PROOF_FIXTURE_REQUIRED'):
                proof.require_fixture(root)

    def test_optimized_python_cannot_skip_proof_assertions(self):
        result = subprocess.run([sys.executable,'-O',str(ROOT/'scripts/prove_harness_continuation.py')],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('ASSERTION_ENABLED_PROOF_REQUIRED',result.stderr)

    def test_reference_projection_retains_economics_and_events(self):
        sample = {'summary':{'profit':10,'cash':20},'events':[{'time':7,'kind':'clear'}],
                  'resource_receipt':{'wall_seconds':1},'orders':[{'price':12}]}
        for mutation in [lambda x:x['summary'].update(profit=11),
                         lambda x:x['events'][0].update(time=8),
                         lambda x:x['orders'][0].update(price=13)]:
            changed = copy.deepcopy(sample); mutation(changed)
            self.assertNotEqual(proof.stable(sample), proof.stable(changed))
        changed = copy.deepcopy(sample); changed['resource_receipt']['wall_seconds']=2
        self.assertEqual(proof.stable(sample), proof.stable(changed))


if __name__ == '__main__': unittest.main()
