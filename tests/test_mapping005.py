import copy
import unittest
from mechanisms.mapping import MappingRefused, compile_mapping, discover, discover_one, target_from_task


def donor():
    return {'id': 'database-write', 'nodes': [
        {'id': 'durable-resource', 'kind': 'reserve', 'unit': 'event'},
        {'id': 'first-effect', 'kind': 'emit', 'unit': 'event'}],
        'relations': [['durable-resource', 'precedes', 'first-effect']],
        'conditions': {'exclusive': True},
        'obligations': [{'kind': 'protect', 'role_ids': ['first-effect']}]}


def task():
    return {'id': 'archive-production', 'phases': [
        {'id': 'q7', 'kind': 'reserve', 'deps': [], 'unit': 'event'},
        {'id': 'm2', 'kind': 'emit', 'deps': ['q7'], 'unit': 'event'},
        {'id': 'z9', 'kind': 'emit', 'deps': ['m2'], 'unit': 'event'}],
        'conditions': {'exclusive': True, 'filesystem': 'local'}}


class MappingTests(unittest.TestCase):
    def test_discovery_constructs_the_actual_target_obligation(self):
        result = discover_one(donor(), target_from_task(task()))
        self.assertEqual(result['role_map'], {'durable-resource': 'q7', 'first-effect': 'm2'})
        self.assertEqual(result['obligations'][0]['phase_ids'], ['m2'])
        self.assertEqual(result['obligations'][0]['provenance']['origin'], 'structural-transfer-hypothesis')
        self.assertNotIn('established', str(result))

    def test_same_target_different_valid_maps_construct_different_sets(self):
        target = target_from_task(task())
        target['relations'].append(['q7', 'precedes', 'z9'])
        report = discover([donor()], target)[0]
        self.assertEqual(report['status'], 'ambiguous')
        variants = [compile_mapping(donor(), target, mapping) for mapping in report['correspondences']]
        self.assertEqual({tuple(v['obligations'][0]['phase_ids']) for v in variants}, {('m2',), ('z9',)})
        with self.assertRaisesRegex(MappingRefused, 'AMBIGUOUS'):
            discover_one(donor(), target)

    def test_renaming_and_permutation_preserve_the_structural_construction(self):
        original = target_from_task(task())
        labels = {'q7': 'omega', 'm2': 'beta', 'z9': 'alpha'}
        renamed = copy.deepcopy(original)
        renamed['nodes'].reverse()
        for node in renamed['nodes']:
            node['id'] = labels[node['id']]
            node['event'] = 'event-' + node['id']
        renamed['relations'] = [[labels[a], relation, labels[b]] for a, relation, b in original['relations']][::-1]
        result = discover_one(donor(), renamed)
        self.assertEqual(result['obligations'][0]['phase_ids'], ['event-beta'])

    def test_misleading_names_do_not_override_incompatible_units_or_causality(self):
        target = target_from_task(task())
        target['nodes'][1]['unit'] = 'USD'
        self.assertEqual(discover([donor()], target)[0]['status'], 'refused')
        target = target_from_task(task())
        target['relations'] = [[b, relation, a] for a, relation, b in target['relations']]
        self.assertEqual(discover([donor()], target)[0]['status'], 'refused')

    def test_boundary_conditions_are_typed_and_target_extra_conditions_are_allowed(self):
        target = target_from_task(task())
        self.assertEqual(discover([donor()], target)[0]['status'], 'unique')
        target['conditions']['exclusive'] = 1
        self.assertEqual(discover([donor()], target)[0]['unresolved_mismatches'], ['exclusive'])
        with self.assertRaisesRegex(MappingRefused, 'MAPPING_REFUSED'):
            discover_one(donor(), target)

    def test_forged_correspondence_rechecked_before_compilation(self):
        target = target_from_task(task())
        with self.assertRaisesRegex(MappingRefused, 'DIRECTED_RELATION'):
            compile_mapping(donor(), target, {'durable-resource': 'q7', 'first-effect': 'z9'})
        with self.assertRaisesRegex(MappingRefused, 'INJECTIVE'):
            compile_mapping(donor(), target, {'durable-resource': 'q7', 'first-effect': 'q7'})

    def test_search_exhaustion_cannot_be_promoted_to_unique(self):
        target = target_from_task(task())
        report = discover([donor()], target, max_search=1)[0]
        self.assertEqual(report['status'], 'bounded')
        self.assertFalse(report['search_complete'])
        with self.assertRaisesRegex(MappingRefused, 'BOUNDED'):
            discover_one(donor(), target, max_search=1)

    def test_role_parameterized_atomic_and_compensation_recipes(self):
        source = donor()
        source['strategy_recipe'] = [{'kind': 'atomic_publish', 'role_ids': ['first-effect']},
                                     {'kind': 'compensate', 'role_ids': ['first-effect'], 'resource_role_ids': ['durable-resource']}]
        result = discover_one(source, target_from_task(task()))
        self.assertEqual(result['strategy_recipe'][0]['phase_ids'], ['m2'])
        self.assertEqual(result['strategy_recipe'][1]['resource_phase_ids'], ['q7'])

    def test_no_recipe_and_unknown_role_refuse_instead_of_silent_fallback(self):
        source = donor(); source['obligations'] = []
        with self.assertRaisesRegex(MappingRefused, 'NO_ROLE_PARAMETERIZED'):
            discover_one(source, target_from_task(task()))
        source['obligations'] = [{'kind': 'protect', 'role_ids': ['invented-role']}]
        with self.assertRaisesRegex(MappingRefused, 'TRANSFORM_ROLE'):
            discover_one(source, target_from_task(task()))

    def test_unknown_target_phase_reference_is_rejected(self):
        invalid = task(); invalid['phases'][1]['deps'] = ['missing']
        with self.assertRaisesRegex(MappingRefused, 'RELATION_ENDPOINT'):
            target_from_task(invalid)


if __name__ == '__main__':
    unittest.main()
