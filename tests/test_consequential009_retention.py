import hashlib, importlib.util, json, shutil, tempfile, unittest
from pathlib import Path
from experiments.consequential009_retention import run

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('retention_admission_checker', ROOT / 'verification/consequential009/cohort_check.py')
check = importlib.util.module_from_spec(spec); spec.loader.exec_module(check)

class RetainedAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.base = Path(cls.temp.name)
        cls.original = ROOT / 'evidence/consequential009/resources/analog-r3/artifacts'
        cls.receipt = cls.base / 'accepted.json'
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        accepted = check.run(ROOT, cls.original, digest(ROOT / 'research/consequential009/analog/PROTOCOL.json'),
                             digest(cls.original / 'REPORT.json'), cls.receipt)
        if not accepted['accepted']: raise AssertionError('native report must be accepted by current independent checker')
        cls.expected = digest(cls.receipt)

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_generated_program_substituted_after_receipt_is_refused(self):
        directory = self.base / 'substituted-generated'
        shutil.copytree(self.original, directory)
        path = directory / 'primary-GENERATED.json'
        data = json.loads(path.read_text()); data['generated_extension']['op'] = 'unsupported'
        path.write_text(json.dumps(data))
        output = self.base / 'must-not-store'
        with self.assertRaisesRegex(ValueError, 'ACCEPTED_GENERATIVE_SIDECAR_IDENTITY'):
            run(directory, self.receipt, self.expected, output)
        self.assertFalse(output.exists())

    def test_protocol_substituted_after_receipt_is_refused(self):
        directory = self.base / 'substituted-protocol'
        shutil.copytree(self.original, directory)
        path = directory / 'PROTOCOL.json'; data = json.loads(path.read_text()); data['allow_flux_extension'] = False
        path.write_text(json.dumps(data))
        output = self.base / 'must-not-adapt'
        with self.assertRaisesRegex(ValueError, 'PROTOCOL_IDENTITY'):
            run(directory, self.receipt, self.expected, output)
        self.assertFalse(output.exists())

    def test_unchanged_verified_program_executes_actual_memory_and_controls(self):
        result = run(self.original, self.receipt, self.expected, self.base / 'valid-control')
        self.assertEqual(len(result['arms']), 12)
        self.assertTrue(result['actual_negative_retrieval_refused'])
        self.assertTrue(result['equal_content_and_reset_tie'])

if __name__ == '__main__': unittest.main()
