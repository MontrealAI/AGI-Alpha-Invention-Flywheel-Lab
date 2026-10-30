import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('reference_dsl_checker', Path(__file__).with_name('reference_check.py'))
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class ReferenceDSLAdmissionTests(unittest.TestCase):
    def evaluate(self, edit=None):
        with tempfile.TemporaryDirectory(dir=ROOT / 'evidence/consequential009/verifier', prefix='reference-dsl-') as temporary:
            directory = Path(temporary) / 'artifacts'
            shutil.copytree(ROOT / 'evidence/consequential009/resources/reference-r1/artifacts', directory)
            if edit is not None:
                path = directory / 'primary-STRATEGY.json'
                value = json.loads(path.read_text())
                edit(value)
                path.write_text(json.dumps(value, indent=2) + '\n')
            protocol = ROOT / 'research/consequential009/analog/REFERENCE_PROTOCOL.json'
            result = checker.run(ROOT, directory, hashlib.sha256(protocol.read_bytes()).hexdigest(),
                                 hashlib.sha256((directory / 'REPORT.json').read_bytes()).hexdigest(), Path(temporary) / 'ACCEPTANCE.json')
            self.assertEqual(result['accepted'], edit is None)
            return [c['name'] for c in result['checks'] if not c['passed']]

    def test_untouched_native_reference_program_passes(self):
        self.assertEqual(self.evaluate(), [])

    def test_unsupported_operator_or_expression_rejected(self):
        for field, replacement in [('op', 'unsupported_operator'), ('expression', 'return_zero')]:
            with self.subTest(field=field):
                self.assertIn('primary: closed paired-reference operator, actions, expression and obligations',
                              self.evaluate(lambda value: value['dsl'].update({field: replacement})))

    def test_changed_off_on_action_and_removed_obligation_rejected(self):
        edits = [lambda value: value['dsl']['actions'][1].update(reference='off'),
                 lambda value: value['dsl'].update(requires=['no stability needed']),
                 lambda value: value['dsl'].update(unadmitted_authority='run anything')]
        for index, edit in enumerate(edits):
            with self.subTest(variant=index):
                self.assertIn('primary: closed paired-reference operator, actions, expression and obligations', self.evaluate(edit))

    def test_reference_source_or_generated_constraint_substitution_rejected(self):
        edits = [lambda value: value.update(source_sha256='0' * 64),
                 lambda value: value.update(generated_from={'kind': 'unverified arbitrary scope'})]
        for index, edit in enumerate(edits):
            with self.subTest(variant=index):
                self.assertIn('primary: source-bound reference derivation', self.evaluate(edit))


if __name__ == '__main__':
    unittest.main()
