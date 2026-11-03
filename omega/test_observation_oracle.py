from itertools import combinations, product
from random import Random
import unittest

from omega.observation import select_panel
from omega.observation_verify import conventional_panel


class RawReadingOracleTests(unittest.TestCase):
    def test_250_exposed_development_cases_seed_76191(self):
        rng = Random(76191)
        for case in range(250):
            worlds = [{'id': str(i), 'state': [rng.randrange(4), rng.randrange(4)],
                       'accepted_actions': [a for a in ['a', 'b', 'c'] if rng.randrange(2)] or ['a']}
                      for i in range(rng.randrange(2, 6))]
            sensors = [{'id': str(i), 'coefficients': [rng.randrange(-1, 2), rng.randrange(-1, 2)],
                        'offset': rng.randrange(-1, 2), 'error_bound': rng.randrange(2),
                        'setup_cost_cents': rng.randrange(3), 'sample_cost_cents': rng.randrange(3),
                        'authorized': bool(rng.randrange(2))}
                       for i in range(rng.randrange(4))]
            request = {'schema': 'omega-observation/v1', 'case_id': str(case), 'context_id': 'u',
                       'hypotheses': worlds, 'sensors': sensors, 'budget_cents': rng.randrange(8),
                       'prior_observations': [], 'inherited_recipes': []}
            best = None
            allowed = [sensor for sensor in sensors if sensor['authorized']]
            for size in range(len(allowed) + 1):
                for panel in combinations(allowed, size):
                    cost = sum(sensor['setup_cost_cents'] + sensor['sample_cost_cents'] for sensor in panel)
                    if cost > request['budget_cents']:
                        continue
                    axes = []
                    for sensor in panel:
                        readings = set()
                        for world in worlds:
                            center = sum(a*b for a, b in zip(sensor['coefficients'], world['state'])) + sensor['offset']
                            readings.update(range(center - sensor['error_bound'], center + sensor['error_bound'] + 1))
                        axes.append(sorted(readings))
                    valid = True
                    for readings in product(*axes):
                        remaining = [world for world in worlds
                                     if all(abs(sum(a*b for a, b in zip(sensor['coefficients'], world['state']))
                                                + sensor['offset'] - value) <= sensor['error_bound']
                                            for sensor, value in zip(panel, readings))]
                        if remaining and not set.intersection(*(set(world['accepted_actions']) for world in remaining)):
                            valid = False
                            break
                    key = cost, tuple(sensor['id'] for sensor in panel)
                    if valid and (best is None or key < best):
                        best = key
            for label, result in [('candidate', select_panel(request)), ('reference', conventional_panel(request))]:
                actual = (result['cost_cents'], tuple(result['panel'])) if result['status'] == 'PANEL_READY' else None
                with self.subTest(case=case, solver=label):
                    self.assertEqual(actual, best, request)


if __name__ == '__main__':
    unittest.main()
