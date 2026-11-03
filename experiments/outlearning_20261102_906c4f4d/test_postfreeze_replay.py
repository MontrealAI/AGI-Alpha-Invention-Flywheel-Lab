import unittest

from .postfreeze_replay import _same_construction_field


class PostfreezeVerifierRepresentationTests(unittest.TestCase):
    def test_persisted_phase_keys_and_roles_have_equal_json_meaning(self):
        recorded = {'phases': {'provider': {'0': True}}, 'roles': ['direct', 'prepared']}
        regenerated = {'phases': {'provider': {0: True}}, 'roles': ('direct', 'prepared')}
        self.assertTrue(_same_construction_field('construction', recorded, regenerated))

    def test_changed_construction_fact_is_rejected(self):
        recorded = {'phases': {'provider': {'0': True}}}
        regenerated = {'phases': {'provider': {0: False}}}
        self.assertFalse(_same_construction_field('construction', recorded, regenerated))

    def test_omitted_construction_evidence_is_rejected(self):
        self.assertFalse(_same_construction_field('construction', {'probe': {'result': 'DONE'}}, {}))

    def test_changed_role_assignment_is_rejected(self):
        self.assertFalse(_same_construction_field('construction', {'roles': ['direct']}, {'roles': ('prepared',)}))

    def test_program_fields_do_not_gain_a_normalization_exception(self):
        self.assertFalse(_same_construction_field('program', {'0': True}, {0: True}))

    def test_probe_fields_do_not_gain_a_normalization_exception(self):
        self.assertFalse(_same_construction_field('probe_transcript', {'0': True}, {0: True}))


if __name__ == '__main__':
    unittest.main()
