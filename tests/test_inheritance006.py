import copy
import json
from pathlib import Path
import tempfile
import unittest

from experiments.norman006 import inheritance
from flywheel import retention

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / 'evidence/cycle-006/acquired-scientific-operator/CAPABILITY.json'
CONDITIONS = {'representation': 'single-intervention-panel-means', 'unordered_simultaneous_inputs': True, 'gene_axis_available': True}


class InheritedScientificOperatorTests(unittest.TestCase):
    def test_discovered_group_action_constructs_repair_and_rejects_wrong_boundary(self):
        mapped = inheritance.exchange_mapping('independently_named_pair')
        self.assertEqual(mapped['permutations'], [['A', 'B'], ['B', 'A']])
        self.assertEqual(mapped['report']['status'], 'ambiguous')
        self.assertTrue(mapped['transformation']['symmetric'])
        for kwargs in ({'simultaneous': False}, {'unit': 'seconds'}):
            with self.assertRaises(ValueError):
                inheritance.exchange_mapping('not_exchangeable', **kwargs)

    def test_actual_memory_path_and_equivalent_ordinary_content(self):
        record = json.loads(RECORD.read_text())
        with tempfile.TemporaryDirectory() as temporary:
            identity = retention.store(temporary, record)
            self.assertEqual(identity, retention.store(temporary, record))
            inherited = inheritance.retrieve_and_generate(temporary, {**CONDITIONS, 'cell_line': 'fresh-context'}, ROOT, count=4)
            ordinary = inheritance.ordinary_generate([record], ROOT, count=4)
            self.assertEqual(inherited['candidates'][0]['generated'], ordinary[0]['generated'])
            self.assertEqual(len(inherited['candidates'][0]['generated']['configurations']), 4)
            self.assertNotIn('coefficient', record['generative_operator']['program'])
            wrong = inheritance.retrieve_and_generate(temporary, {**CONDITIONS, 'unordered_simultaneous_inputs': False}, ROOT)
            self.assertFalse(wrong['candidates'])
            path = Path(temporary) / (identity + '.json')
            path.chmod(0o600)
            path.write_bytes(path.read_bytes() + b' ')
            self.assertFalse(inheritance.retrieve_and_generate(temporary, CONDITIONS, ROOT)['candidates'])

    def test_forged_generator_and_stale_dependency_cannot_supply_operator(self):
        record = json.loads(RECORD.read_text())
        forged = copy.deepcopy(record)
        forged['generative_operator']['program']['configuration']['expressions'] = [['__import__', 'a0', 'b0']]
        with self.assertRaises(ValueError):
            inheritance.generate_related(forged, ROOT)
        stale = copy.deepcopy(record)
        stale['provenance']['source_pins']['verification/cycle006_symmetry_adjudication.py'] = '0' * 64
        with self.assertRaises(ValueError):
            inheritance.generate_related(stale, ROOT)


if __name__ == '__main__':
    unittest.main()
