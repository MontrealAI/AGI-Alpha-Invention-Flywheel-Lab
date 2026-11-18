from pathlib import Path
import json
import shutil
import tempfile
import unittest

from invention.early_survey import survey


class EarlySurvey(unittest.TestCase):
    def test_as_of_admission_and_first_witness_deadline(self):
        self.assertEqual(survey.calculate('2026-10-24T23:59:59Z')['cohorts'], [])
        before = survey.calculate('2026-10-25T23:59:59Z')
        self.assertEqual([len(c['alerts']) for c in before['cohorts']], [0, 0])
        issue = survey.calculate('2026-10-26T00:00:00Z')
        cold, warm = issue['cohorts']
        self.assertEqual(cold['alerts'], [])
        self.assertEqual([(a['target_id'], a['band'], a['status']) for a in warm['alerts']], [
            ('ZTF26acbezdh', 'g', 'awaiting_repeat'), ('ZTF26acbezdh', 'r', 'awaiting_repeat')])
        self.assertEqual(warm['eligible_baseline_history_rows'], 28)
        for cutoff, status in [('2026-10-28T23:59:59Z', 'awaiting_repeat'),
                               ('2026-10-29T00:00:00Z', 'coverage_gap')]:
            alerts = survey.calculate(cutoff)['cohorts'][1]['alerts']
            self.assertEqual([(a['status'], a['followup']) for a in alerts], [(status, None), (status, None)])

    def test_reference_identity_and_broker_rate_are_separate_measurements(self):
        result = survey.calculate()
        cold, warm = result['cohorts']
        self.assertEqual(cold['targets'], warm['targets'])
        green, red = warm['alerts']
        self.assertEqual([green['delta_mag'], red['delta_mag']], [-0.836744, -0.557955])
        self.assertEqual(green['reference_image'], {'status': 'matched', 'rfids': ['505120158'] * 2})
        self.assertEqual(red['reference_image']['rfids'], ['505120258'] * 2)
        self.assertEqual(green['broker_at_trigger']['from_upper'], False)
        self.assertNotEqual(green['rate_mag_per_day'], green['broker_at_trigger']['rate_mag_per_day'])
        self.assertEqual(result, json.loads((survey.HERE / 'RESULT.json').read_bytes()))

    def test_unknown_reference_is_explicit_and_changed_metadata_is_rejected(self):
        alert = {'baseline': {'candid': '1'}, 'trigger': {'candid': '2'}, 'followup': None}
        source = {k: {'i:objectId': 'T', 'i:field': 505, 'i:rcid': 58} for k in (1, 2)}
        references = {1: dict(source[1], **{'i:rfid': 36})}
        survey.broker_and_reference(alert, source, references)
        self.assertEqual(alert['reference_image'], {'status': 'unknown', 'rfids': ['36', None]})
        self.assertIsNone(alert['broker_at_trigger']['rate_mag_per_day'])
        references[2] = dict(source[2], **{'i:rfid': 10})
        survey.broker_and_reference(alert, source, references)
        self.assertEqual(alert['reference_image']['status'], 'changed')
        references[2]['i:rcid'] = 57
        with self.assertRaises(ValueError):
            survey.broker_and_reference(alert, source, references)

    def test_pinned_request_identity_is_checked_before_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'input'
            shutil.copytree(survey.HERE / 'sources', folder)
            index = folder / 'index.json'
            index.write_bytes(index.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'digest'):
                survey.calculate(folder=folder)
