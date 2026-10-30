import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('generated_authority_checker', Path(__file__).with_name('cohort_check.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class GeneratedAuthorityIntegrityTests(unittest.TestCase):
    def evaluate(self, edit=None, stage='primary'):
        with tempfile.TemporaryDirectory(dir=ROOT / 'evidence/consequential009/verifier', prefix='generated-authority-') as temporary:
            directory = Path(temporary) / 'artifacts'
            shutil.copytree(ROOT / 'evidence/consequential009/resources/analog-r3/artifacts', directory)
            if edit is not None:
                path = directory / (stage + '-GENERATED.json')
                value = json.loads(path.read_text())
                edit(value)
                path.write_text(json.dumps(value, indent=2) + '\n')
            protocol = ROOT / 'research/consequential009/analog/PROTOCOL.json'
            result = checker.run(ROOT, directory, hashlib.sha256(protocol.read_bytes()).hexdigest(),
                                 hashlib.sha256((directory / 'REPORT.json').read_bytes()).hexdigest(), Path(temporary) / 'ACCEPTANCE.json')
            self.assertEqual(result['accepted'], edit is None)
            return [c['name'] for c in result['checks'] if not c['passed']]

    def test_untouched_native_generated_authority_passes(self):
        self.assertEqual(self.evaluate(), [])

    def test_unsupported_operator_rejected_in_both_stages(self):
        for stage in ['primary', 'fresh_successor']:
            with self.subTest(stage=stage):
                self.assertIn(stage + ': closed generated operator and retained authority',
                              self.evaluate(lambda value: value['generated_extension'].update(op='unsupported_operator'), stage))

    def test_malformed_or_boolean_version_rejected(self):
        for version in [0, True, '1']:
            with self.subTest(version=version):
                self.assertIn('primary: closed generated operator and retained authority',
                              self.evaluate(lambda value: value['generated_extension'].update(version=version)))

    def test_source_units_model_sensor_and_type_substitution_rejected(self):
        variants = [('source_sha256', '0' * 64), ('units', 'volts'), ('required_model', ['any network']),
                    ('sensor_obligation', 'no calibration required'), ('inherited', 'false')]
        for field, replacement in variants:
            with self.subTest(field=field):
                self.assertIn('primary: closed generated operator and retained authority',
                              self.evaluate(lambda value: value['generated_extension'].update({field: replacement})))

    def test_unadmitted_authority_field_rejected(self):
        self.assertIn('primary: closed generated operator and retained authority',
                      self.evaluate(lambda value: value['generated_extension'].update(arbitrary_authority={'op': 'run_code'})))

    def test_derivation_and_witness_substitution_rejected(self):
        edits = [lambda value: value['witness']['transformed_values'].update(r1='1'),
                 lambda value: value['witness'].update(current_different=[False] * 4),
                 lambda value: value['witness']['all_frequency_proof']['program'].update(r1=-1),
                 lambda value: value['witness']['all_frequency_proof']['relations'][0]['branch_law'].update(unit='volt')]
        for index, edit in enumerate(edits):
            with self.subTest(variant=index):
                self.assertIn('primary: independent derivation and complete generated witness', self.evaluate(edit))


if __name__ == '__main__':
    unittest.main()
