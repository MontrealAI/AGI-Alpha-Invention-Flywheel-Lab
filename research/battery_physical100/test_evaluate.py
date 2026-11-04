"""Pipeline unit fixtures are synthetic, not empirical prognosis evidence."""
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch
from . import evaluate
from .test_prognosis import feature_fixture
from .prognosis import prefix_features

class EvaluationTests(unittest.TestCase):
    def test_seal_before_target_and_partial_denominator(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'results';p=prefix_features(feature_fixture());test_labels=[]
            def acquire(entry,manifest,path):
                path.write_text('unit fixture only')
                return {'url':'unit-fixture','bytes':0,'sha256':'unit-fixture','attempts':[]}
            def measure(entry,path,full=False):
                r={'cell':entry['cell'],'group':entry['group'],'role':entry['role'],'prefix':p}
                if full:
                    if entry['role']=='test':
                        seal=json.loads((out/'sealed_predictions.json').read_text())
                        self.assertEqual(len(seal['predictions']),54);test_labels.append(entry['cell'])
                    r.update(targets={'500':.9,'1000':.85},unavailable_target_cycles=[],reference_checks=[])
                    if entry['role']=='test' and len(test_labels)==1:
                        del r['targets']['1000'];r['unavailable_target_cycles']=[1000]
                return r
            with patch.object(evaluate,'acquire',acquire),patch.object(evaluate,'measure_record',measure),patch.object(evaluate,'version',lambda x:'unit-fixture'),patch.object(evaluate,'screen',lambda *a,**k:{'status':'UNIT_FIXTURE','group':'g'}),redirect_stdout(StringIO()):
                evaluate.run(out)
            result=json.loads((out/'evaluation.json').read_text())
            self.assertEqual(len(test_labels),9)
            self.assertFalse(result['accepted'])
            primary=[x for x in result['results'] if x['method']=='adjusted_peer']
            self.assertEqual(sum(len(x['metrics']) for x in primary),17)
            self.assertEqual(len(result['test_records']),9)

if __name__=='__main__':unittest.main()
