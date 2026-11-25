# SPDX-License-Identifier: Apache-2.0
"""Check evidence field recovery and the draft-only authority boundary."""

import unittest

from qualify import frozen_cases, prepare, restore


class Qualification(unittest.TestCase):
    def test_pinned_operating_and_evidence_sources(self):
        _, cases = frozen_cases()
        self.assertEqual({case['cohort'] for case in cases}, {'operating', 'evidence'})
        self.assertEqual(len(cases), 10)
        self.assertEqual(len({case['id'] for case in cases}), 10)
        for case in cases:
            prepared, fields = prepare(case)
            restored = restore(case, prepared)
            self.assertEqual(len(fields), len(case['fields']))
            self.assertEqual(restored['status'], 'DRAFT_FOR_BILINGUAL_REVIEW')
            self.assertTrue(all(field['fr'] in restored['text'] for field in case['fields']))

    def test_refuses_missing_duplicated_alien_or_damaged_fields(self):
        case = {'english': 'Exactly 4/8 comparable records.', 'fields': [{'en': '4/8', 'fr': '4/8'}]}
        for response in ('Sans donnée', '⟦E01⟧ puis ⟦E01⟧',
                         '⟦E01⟧ ⟦E99⟧', '⟦E01⟧ ⟦ E02 ⟧', '⟦E01]'):
            self.assertEqual(restore(case, response)['status'], 'HOLD_FIELDS')
            self.assertIsNone(restore(case, response)['text'])

    def test_preserved_evidence_fields_cannot_approve_a_claim(self):
        case = {'english': 'No test on Device X qualified.', 'fields': [{'en': 'Device X', 'fr': 'appareil X'}]}
        contrary = restore(case, 'Tous les tests sur l’⟦E01⟧ ont réussi.')
        self.assertEqual(contrary['text'], 'Tous les tests sur l’appareil X ont réussi.')
        self.assertEqual(contrary['status'], 'DRAFT_FOR_BILINGUAL_REVIEW')

    def test_refuses_empty_draft(self):
        self.assertEqual(restore({'english': 'No fields.', 'fields': []}, '   ')['status'], 'HOLD_EMPTY')


if __name__ == '__main__':
    unittest.main()
