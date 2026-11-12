import copy
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from enterprise078.runtime import materialize
from enterprise078.transactional_data.operator import ingest, project, export_csv
from enterprise078.transactional_data.run import fixture
from .contract import request, accept
from .offer import COSTS, compare

ROOT = Path(__file__).resolve().parents[2]


class NativeBoundaryTests(unittest.TestCase):
    def test_native_controls_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = materialize(ROOT, Path(tmp)/'science')
            env = dict(os.environ, PYTHONPATH=str(source))
            run = subprocess.run([sys.executable, str(Path(__file__).with_name('native_controls.py'))],
                                 cwd=source, env=env, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertTrue(result['accepted'])
            self.assertEqual(len(result['checks']), 6)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db, self.csv = Path(self.tmp.name)/'delivery.sqlite', Path(self.tmp.name)/'derived.csv'
        self.events = fixture(257)
        self.contract = request('sql-csv-257', self.events)
        ingest(self.db, self.events); project(self.db); export_csv(self.db, self.csv)

    def receipt(self):
        return accept(self.contract, self.events, self.db, self.csv)

    def test_actual_typed_output(self):
        r = self.receipt()
        self.assertTrue(r['accepted'])
        self.assertEqual(r['acceptance']['unique_events'], 257)
        self.assertFalse(r['native_catalog_admitted'])

    def test_lab_label_refused(self):
        self.contract['type'] = 'preparation'
        with self.assertRaisesRegex(ValueError, 'EXACT_TYPED_REQUEST'): self.receipt()

    def test_changed_input_refused(self):
        self.events[0]['quantity'] += 1
        with self.assertRaisesRegex(ValueError, 'EXACT_TYPED_REQUEST'): self.receipt()

    def test_csv_corruption(self):
        self.csv.write_text('account,units,event_count\ngroup-00,999,1\n')
        self.assertFalse(self.receipt()['accepted'])

    def test_database_corruption(self):
        c = sqlite3.connect(self.db)
        try:
            c.execute('UPDATE events SET quantity=quantity+1'); c.commit()
        finally: c.close()
        self.assertFalse(self.receipt()['accepted'])

    def test_live_wal_not_a_standalone_delivery(self):
        c = sqlite3.connect(self.db)
        try:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('UPDATE events SET quantity=quantity+1'); c.commit()
            with self.assertRaisesRegex(ValueError, 'CHECKPOINTED_STANDALONE'): self.receipt()
        finally: c.close()


class CompleteOfferTests(unittest.TestCase):
    def setUp(self):
        # Authored integer sensitivity fixture, not prices, demand or a forecast.
        self.args = dict(costs={k:1000000 for k in COSTS}, price=20000000,
                         buyer_value=50000000, buyer_budget=30000000,
                         outside_surplus=10000000, available=30000000,
                         earned=30000000, consent=True, acceptance=True)

    def test_favorable_still_not_native_admission(self):
        r = compare(**self.args)
        self.assertTrue(r['economic_conditions_met']); self.assertFalse(r['admitted'])
        self.assertEqual(r['conditional_surplus_microUSD'], 5000000)
        self.assertIsNone(r['forecast_expected_net'])

    def test_unknown_construction_and_host_never_zero(self):
        for key in ('construction', 'host_model'):
            args = copy.deepcopy(self.args); args['costs'][key] = None
            r = compare(**args)
            self.assertIn('UNKNOWN_COMPLETE_COST', r['reasons'])
            self.assertIsNone(r['conditional_surplus_microUSD'])

    def test_strong_outside_option_wins(self):
        self.args['outside_surplus'] = 31000000
        self.assertIn('BUYER_OUTSIDE_OPTION_WINS_OR_TIES', compare(**self.args)['reasons'])

    def test_zero_and_negative_surplus(self):
        for price in (15000000,14000000):
            self.args['price'] = price
            self.assertIn('NO_POSITIVE_COMPLETE_SURPLUS', compare(**self.args)['reasons'])

    def test_whole_delivery_not_next_step_affordability(self):
        self.args['available'] = 14000000
        self.assertIn('WHOLE_DELIVERY_NOT_EARNED_FUNDED', compare(**self.args)['reasons'])

    def test_no_consent_no_sale(self):
        self.args['consent'] = False
        self.assertIn('NO_VOLUNTARY_CONSENT', compare(**self.args)['reasons'])

    def test_missing_cost_category_rejected(self):
        del self.args['costs']['liability_tail']
        with self.assertRaisesRegex(ValueError, 'COMPLETE_COST'): compare(**self.args)

    def test_future_income_not_funding(self):
        self.args['earned'] = 0
        self.assertIn('WHOLE_DELIVERY_NOT_EARNED_FUNDED', compare(**self.args)['reasons'])


if __name__ == '__main__': unittest.main()
