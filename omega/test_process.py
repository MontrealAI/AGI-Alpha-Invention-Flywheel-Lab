from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from omega.process import BuyerSession, construct, fixture, help_for, route, run_simulated_buyer
from omega.process_verify import conventional_policy, unfamiliar_cases, verify_policy


class BuyerProcessTests(unittest.TestCase):
    def test_all_policies_equal_strong_conventional_cost_and_status(self):
        for request in [fixture(), fixture(True), *unfamiliar_cases()]:
            candidate, control = construct(request), conventional_policy(request)
            self.assertEqual((candidate['status'], candidate['worst_cost_cents']),
                             (control['status'], control['worst_cost_cents']))
            verify_policy(request, candidate)

    def test_complete_buyer_paths_with_interruptions_and_independent_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            for successor in (False, True):
                request = fixture(successor)
                for world in request['models']:
                    result = run_simulated_buyer(Path(tmp)/f'{successor}-{world["id"]}.sqlite', request,
                                                 world['responses'], world['yields'], interrupt=True)
                    self.assertEqual(result['buyer']['state']['status'], 'ACCEPTED')
                    self.assertTrue(result['independent_execution']['production_accepted'])

    def test_unknown_mechanism_cannot_borrow_in_model_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = fixture()
            actual = copy.deepcopy(request['models'][0]); actual['yields']['a'] = 0
            result = run_simulated_buyer(Path(tmp)/'alias.sqlite', request, actual['responses'], actual['yields'])
            self.assertEqual(result['buyer']['state']['status'], 'PRODUCTION_REJECTED')
            actual['responses']['a'] = 99
            result = run_simulated_buyer(Path(tmp)/'mismatch.sqlite', request, actual['responses'], actual['yields'])
            self.assertEqual(result['buyer']['state']['status'], 'MODEL_MISMATCH')

    def test_declining_does_not_erase_incurred_work_or_allow_production(self):
        with tempfile.TemporaryDirectory() as tmp:
            with BuyerSession(Path(tmp)/'buyer.sqlite', fixture()) as buyer:
                buyer.act('first', 'observe', experiment_id='a', value=0)
                buyer.act('stop', 'decline')
                self.assertEqual(buyer.report()['state']['cost_cents'], 4)
                with self.assertRaises(ValueError):
                    buyer.act('extra', 'observe', experiment_id='b', value=1)

    def test_changed_action_id_and_request_refused_without_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'buyer.sqlite'
            with BuyerSession(path, fixture()) as buyer:
                first = buyer.act('one', 'observe', experiment_id='a', value=1)
                self.assertEqual(buyer.act('one', 'observe', experiment_id='a', value=1), first)
                with self.assertRaises(ValueError):
                    buyer.act('one', 'observe', experiment_id='a', value=0)
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):
                BuyerSession(path, fixture(True))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_existing_unrelated_database_and_missing_recovery_are_not_mutated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'existing.sqlite'
            con = sqlite3.connect(path); con.execute('CREATE TABLE original (x)'); con.commit(); con.close()
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                BuyerSession(path, fixture())
            self.assertEqual(before, path.read_bytes())
            missing = Path(tmp)/'missing.sqlite'
            with self.assertRaises(ValueError):
                BuyerSession(missing)
            self.assertFalse(missing.exists())

    def test_unclear_model_limits_budget_and_provider_unavailability(self):
        request = fixture(); del request['ambition']
        with self.assertRaises(ValueError):
            construct(request)
        request = fixture(); request['max_total_cost_cents'] = 30
        self.assertEqual(construct(request)['status'], 'NO_QUALIFIED_POLICY')
        request['max_experiments'] = 5
        with self.assertRaisesRegex(ValueError, 'RESOURCE_LIMIT'):
            construct(request)
        for kwargs in ({'memory_mib': 1}, {'choice': 'local_model'}, {'choice': 'external_model'},
                       {'choice': 'external_model', 'external_authorized': True, 'external_max_usd': 1, 'data_scope': 'test'}):
            with self.assertRaises(ValueError):
                route(**kwargs)
        self.assertEqual(route()['network_calls'], 0)

    def test_documentation_helper_states_uncertainty_and_source(self):
        known, unknown = help_for('MODEL_MISMATCH'), help_for('UNSEEN_ERROR')
        self.assertTrue(known['known_diagnostic'])
        self.assertFalse(known['resolved'])
        self.assertFalse(unknown['known_diagnostic'])
        self.assertEqual(len(known['documentation_sha256']), 64)


if __name__ == '__main__':
    unittest.main()
