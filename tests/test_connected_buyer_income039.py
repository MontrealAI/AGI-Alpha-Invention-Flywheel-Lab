"""Native buyer purchasing-power renewal: actual engine + independent audit."""
import copy
import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest

from adaptive_enterprise.instruments import prepare_services
from adaptive_enterprise.runner import source_paths as adaptive_sources
from commercial.ledger import digest
from connected_enterprise.buyer_income import SCHEMA
from connected_enterprise.engine import _initial, default_config, run_world, validate_config
from connected_enterprise.finance import SOURCE_PATHS as finance_sources
from connected_enterprise.verify import audit, _check_external_buyer_income, check_budgets

ROOT = Path(__file__).resolve().parents[1]


def policy(**terms):
    result = {'schema': SCHEMA, 'first_day': 1, 'period_days': 2,
              'income_microUSD': 10_000_000, 'receipt_bps': 10000}
    result.update(terms)
    return result


class ExternalIncomeContracts(unittest.TestCase):
    def test_opt_in_only_and_no_default_change(self):
        cfg = default_config()
        self.assertNotIn('buyer_income_policy', cfg)
        self.assertEqual(validate_config(cfg), cfg)
        cfg.update(horizon_days=8, buyer_income_policy=policy())
        self.assertEqual(validate_config(cfg), cfg)
        state = _initial(cfg, 123, 'baseline', {'sha256': 'development-fixture'})
        self.assertEqual(state['buyers'][0]['external_income_total'], 0)
        times = [(row['time'], row['kind']) for row in state['queue'] if row['time'] == 24]
        self.assertEqual(times, [(24, 'buyer_income'), (24, 'plan')])

    def test_invalid_income_contracts_fail_closed(self):
        for change in [{'income_microUSD': 0}, {'period_days': 0},
                       {'first_day': 8}, {'receipt_bps': -1},
                       {'receipt_bps': 10001}, {'receipt_bps': True},
                       {'income_microUSD': 0.5}, {'schema': 'unapproved'}]:
            cfg = default_config()
            cfg.update(horizon_days=8, buyer_income_policy=policy(**change))
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_config(cfg)

    def test_inflated_external_income_cannot_satisfy_buyer_conservation(self):
        buyer = {'id': 'SIM-customer-000', 'initial_budget': 100,
                 'remaining_budget': 150, 'our_settled_spend': 0, 'outside_spend': 0,
                 'pending_commitments': {}, 'external_income_total': 50}
        self.assertEqual(check_budgets([buyer], [])['external_buyer_income_microUSD'], 50)
        changed = copy.deepcopy(buyer)
        changed['external_income_total'] = 51
        with self.assertRaisesRegex(ValueError, 'CONSERVATION'):
            check_budgets([changed], [])


class NativeExternalIncomeIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='income039-native-')
        cls.root = Path(cls.temp.name) / 'source'
        names = set(adaptive_sources(ROOT)) | set(finance_sources)
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'connected_enterprise').glob('*.py'))
        for name in sorted(names):
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        cls.source = {'files': {name: hashlib.sha256((cls.root / name).read_bytes()).hexdigest()
                                for name in sorted(names)}}
        cls.source['sha256'] = digest(cls.source['files'])
        cls.manifest = prepare_services(cls.root, 'service-inputs', cohort_seed=390031)
        cls.cfg = default_config()
        cls.cfg.update(horizon_days=8, customer_pool=8, opening=100_000_000_000,
                       setup_cost=10_000_000, nonpayment_bps=0, arrival_bps=10000,
                       buyer_income_policy=policy())
        cls.result = run_world(cls.root, cls.manifest, cls.cfg, 390031, 'baseline',
                               Path(cls.temp.name) / 'world', source=cls.source)
        cls.receipt = audit(cls.root, cls.manifest, cls.result)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_native_audit_and_incomes_stay_outside_enterprise_collections(self):
        self.assertTrue(self.result['complete'])
        self.assertTrue(self.receipt['accepted'])
        self.assertEqual(self.result['config']['opening'], 100_000_000_000)
        incomes = [e for e in self.result['events'] if e['kind'] == 'EXTERNAL_BUYER_INCOME']
        self.assertEqual(len(incomes), 32)
        self.assertEqual(self.receipt['external_buyer_income_events_recomputed'], 32)
        self.assertEqual(sum(e['amount_microUSD'] for e in incomes),
                         sum(b['external_income_total'] for b in self.result['buyers']))
        self.assertEqual(self.result['summary']['collections'],
                         sum(o['price'] for o in self.result['orders'] if o['outcome'] == 'SETTLED'))

    def test_missing_forged_and_changed_external_incomes_rejected(self):
        for mutation in (
            lambda r: r['events'].pop(next(i for i,e in enumerate(r['events']) if e['kind']=='EXTERNAL_BUYER_INCOME')),
            lambda r: next(e for e in r['events'] if e['kind']=='EXTERNAL_BUYER_INCOME').__setitem__('amount_microUSD', 90_000_000),
            lambda r: r['buyers'][0].__setitem__('external_income_total', 0),
            lambda r: r['events'].append({'id': 'fabricated', 'time': 999, 'kind': 'EXTERNAL_BUYER_INCOME',
                                         'customer_id': 'SIM-customer-000', 'amount_microUSD': 10_000_000,
                                         'evidence_role': 'AUTHORED_EXOGENOUS_BUYER_INCOME_NOT_ENTERPRISE_REVENUE'}),
        ):
            changed = copy.deepcopy(self.result)
            mutation(changed)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'EXOGENOUS_BUYER_INCOME'):
                _check_external_buyer_income(changed)

    def test_no_sales_means_no_enterprise_revenue_despite_new_buyer_income(self):
        cfg = copy.deepcopy(self.cfg)
        cfg.update(horizon_days=3, arrival_bps=0)
        result = run_world(self.root, self.manifest, cfg, 390032, 'baseline',
                           Path(self.temp.name) / 'no-orders', source=self.source)
        self.assertTrue(audit(self.root, self.manifest, result)['accepted'])
        self.assertGreater(sum(b['external_income_total'] for b in result['buyers']), 0)
        self.assertEqual(result['summary']['collections'], 0)
        self.assertLessEqual(result['summary']['profit'], 0)
        self.assertEqual(result['paid_jobs'], 0)


if __name__ == '__main__':
    unittest.main()
