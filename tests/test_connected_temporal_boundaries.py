import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from commercial.ledger import digest
from connected_enterprise.engine import MICRO, _initial, _prepare_plan, default_config, run_world, validate_config


class AccountView:
    def snapshot(self):
        return {'summary': {'available': 5000 * MICRO, 'unrestrictedEarned': 0}}


class ConnectedTemporalBoundaries(unittest.TestCase):
    def state(self, moment=0, maximum=4):
        cfg = default_config(); cfg.update(customer_pool=4, arrival_bps=10000, maximum_slots=maximum)
        state = _initial(cfg, 13, 'growth', {})
        state['queue'] = [{'id': 'engineering-plan', 'time': moment, 'kind': 'plan'}]
        return state

    def offer(self, jobs, state, buyer, cfg):
        ident = 'engineering-job-' + buyer['id']
        return {'job': {'id': ident, 'work_keys': [ident]}}, {'service_id': 'reconciliation', 'price_microUSD': 5 * MICRO}, 25 * MICRO

    def prepare(self, state):
        with patch('connected_enterprise.engine._offer', side_effect=self.offer):
            return _prepare_plan(state, AccountView(), {})

    def capacity(self, ident, activation, expiry):
        return {'plan_id': ident, 'kind': 'capacity', 'activation_time': activation, 'expiry_time': expiry}

    def test_invalid_complete_lifecycle_rejects_before_account_or_output_creation(self):
        cfg = default_config(); cfg.update(production_hours=2, acceptance_hours=1, clearing_hours=2, payment_deadline_hours=2)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root / 'marker.txt').write_text('engineering source marker')
            files = {'marker.txt': hashlib.sha256((root / 'marker.txt').read_bytes()).hexdigest()}
            output = root / 'must-not-exist'
            with patch('connected_enterprise.engine.JournalAccount', side_effect=AssertionError('FINANCIAL_ACCOUNT_MUST_NOT_OPEN')) as account:
                with self.assertRaisesRegex(ValueError, 'COMPLETE_LIFECYCLE_EXCEEDS_PAYMENT_DEADLINE'):
                    run_world(root, {}, cfg, 13, 'growth', output, source={'files': files, 'sha256': digest(files)})
                account.assert_not_called()
            self.assertFalse(output.exists())

    def test_deadline_equality_and_one_hour_shorter(self):
        cfg = default_config(); cfg.update(production_hours=2, acceptance_hours=1, clearing_hours=2, payment_deadline_hours=5)
        self.assertEqual(validate_config(cfg), cfg)
        cfg['payment_deadline_hours'] = 4
        with self.assertRaisesRegex(ValueError, 'COMPLETE_LIFECYCLE_EXCEEDS_PAYMENT_DEADLINE'):
            validate_config(cfg)

    def test_capacity_expiring_at_or_before_production_cannot_admit_extra_order(self):
        for expiry in [1, 2]:
            with self.subTest(expiry=expiry):
                state = self.state(); state['investments'] = [self.capacity('expiring', 0, expiry)]
                plan = self.prepare(state)
                self.assertEqual(len(plan['orders']), 1)
                self.assertIsNone(plan['orders'][0]['capacity_source_plan_id'])
                self.assertEqual(sum(row['kind'] == 'capacity_decline' for row in plan['declines']), 3)

    def test_valid_assets_are_shared_between_counting_and_order_assignment(self):
        state = self.state()
        state['investments'] = [self.capacity('expired-at-production', 0, 2), self.capacity('valid-first', 0, 3),
                                self.capacity('not-yet-active', 1, 20), self.capacity('valid-second', 0, 4)]
        plan = self.prepare(state)
        self.assertEqual([row['capacity_source_plan_id'] for row in plan['orders']], [None, 'valid-first', 'valid-second'])
        self.assertEqual([row['production_time'] for row in plan['orders']], [2, 2, 2])
        state['config']['maximum_slots'] = 2
        limited = self.prepare(state)
        self.assertEqual([row['capacity_source_plan_id'] for row in limited['orders']], [None, 'valid-first'])

    def test_declined_buyer_does_not_consume_or_shift_capacity_assignment(self):
        state = self.state()
        state['investments'] = [self.capacity('short-lived', 0, 1), self.capacity('first', 0, 3), self.capacity('second', 0, 4)]
        state['buyers'][0]['remaining_budget'] = 0
        plan = self.prepare(state)
        self.assertEqual([row['capacity_source_plan_id'] for row in plan['orders']], [None, 'first', 'second'])
        self.assertNotIn(state['buyers'][0]['id'], [row['customer_id'] for row in plan['orders']])

    def test_activation_boundary_and_production_duration_are_respected(self):
        for duration in [5, 25]:
            with self.subTest(duration=duration):
                state = self.state(moment=24); state['config']['production_hours'] = duration
                production = 24 + duration
                state['investments'] = [self.capacity('activates-now', 24, production + 1), self.capacity('expires-exactly', 0, production),
                                        self.capacity('activates-later', 25, production + 10)]
                plan = self.prepare(state)
                self.assertEqual([row['capacity_source_plan_id'] for row in plan['orders']], [None, 'activates-now'])
                self.assertEqual([row['production_time'] for row in plan['orders']], [production, production])

    def test_preparation_is_deterministic_across_state_roundtrip(self):
        state = self.state(moment=24)
        state['investments'] = [self.capacity('expires-before-work', 0, 25), self.capacity('usable', 0, 27)]
        before = copy.deepcopy(state); first = self.prepare(state)
        resumed = self.prepare(json.loads(json.dumps(before)))
        self.assertEqual(first, resumed)
        self.assertEqual(state, before)
        self.assertEqual([row['capacity_source_plan_id'] for row in first['orders']], [None, 'usable'])
        persisted = json.loads(json.dumps({'current': first}))
        self.assertEqual(persisted['current']['orders'], first['orders'])


if __name__ == '__main__':
    unittest.main()
