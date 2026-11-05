"""Strict production-phase regressions using disposable canonical accounts."""
from pathlib import Path
import tempfile
import unittest

from genesis_enterprise import native
from genesis_enterprise.policy import choose, digest
from flexibility063.native import BusinessAccount
from flexibility063.kernel import solve
from flexibility063.verify import verify
from commercial.terms_exact_v2 import prospective_terms

ROOT = Path(__file__).resolve().parents[1]


class ProductionChronologyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='genesis-chronology-test-')
        self.output = Path(self.tmp.name) / 'operation'
        native.register(ROOT, self.output, ROOT / 'campaign/genesis-enterprise-002/PROTOCOL.json')

    def tearDown(self):
        self.tmp.cleanup()

    def make_native_case(self, mutation):
        output = self.output
        p, manifest, source, reg = native._bound(output)
        state = {'binding': reg['binding'], 'index': 0, 'phase': 'complete', 'rows': [], 'active': None}
        with BusinessAccount(output / 'source', manifest, output / 'disposable-account',
                             opening=p['opening'], working=0, contract=reg['contract']) as account:
            account.cost('genesis-development', p['development'], 0)
            for i, job in enumerate(manifest['jobs']):
                ident, hour = job['id'], 24 * (i + 1)
                order = 'g002-' + ident
                account.advance(hour)
                for kind in ('acquisition', 'maintenance'):
                    if p[kind]:
                        account.cost('genesis-' + kind + '-' + ident, p[kind], hour)
                before = account.export()['ledger']['summary']
                decision = choose(p['offer'], p['tools'], available=before['available'],
                                  earned=before['unrestrictedEarned'],
                                  seed_allowed=(i == 0 and p['first_delivery_may_use_seed']))
                picked = decision['selected']
                self.assertIsNotNone(picked)
                row = {'job_id': ident, 'decision': decision,
                       'decision_state': {k: before[k] for k in ('available', 'unrestrictedEarned')},
                       'accepted': False, 'resource_receipt': None, 'artifact_sha256': None,
                       'ordinary_accepted': None, 'construction_cpu_seconds': 0}
                terms = prospective_terms(order, picked['price'], hour + 10, hour + 2,
                    residual=p['offer']['reserve'] - p['offer']['fee'], fee=p['offer']['fee'],
                    counterparty_obligations='Synthetic purchase of independently checked computational dispatch only. No physical energy delivery or real customer money.')
                account.begin_order(ident, order, 'buyer-' + order, picked['price'],
                                    p['offer']['budget'], hour, hour + 3, terms)
                target = (i == 0 if mutation in {'seed_after_prepare', 'wrong_hour', 'missing_active'} else i > 0)
                def spend(day):
                    receipt = account.spend('genesis-production-' + ident, 'qualified-computational-delivery',
                        picked['resource_cost'], day,
                        {'binding': reg['binding'], 'request_sha256': digest(job['request']),
                         'executor': picked['tool'], 'scope': 'COMPUTATIONAL_ONLY'},
                        expected_net=picked['contribution'],
                        allow_seed=(i == 0 and p['first_delivery_may_use_seed']))
                    self.assertIsNotNone(receipt)
                    return receipt
                if not target or mutation == 'wrong_hour':
                    row['resource_receipt'] = spend(hour + int(target and mutation == 'wrong_hour'))
                same_hour = target and mutation in {'same_hour', 'active_same_hour', 'seed_after_prepare'}
                artifact = solve(job['request'], picked['mode'])
                completion = account.complete_order(order, ident, artifact, hour if same_hour else hour + 1)
                ordinary = solve(job['request'], 'conventional')
                native._save(output / 'public/controls' / (ident + '.json'), ordinary)
                row.update(accepted=completion['accepted'], artifact_sha256=digest(artifact),
                           ordinary_accepted=verify(job['request'], ordinary)['accepted'])
                if target and mutation == 'seed_after_prepare':
                    row['resource_receipt'] = spend(hour)
                    self.assertEqual(row['resource_receipt']['funding'], 'SEED')
                if target and mutation == 'missing_active':
                    state.update(phase='release', active=row)
                    break
                account.release(order, hour if same_hour and mutation != 'seed_after_prepare' else hour + 2)
                if target and mutation not in {'seed_after_prepare', 'wrong_hour'}:
                    row['resource_receipt'] = spend(hour if same_hour else hour + 2)
                    self.assertEqual(row['resource_receipt']['funding'], 'EARNED')
                if target and mutation == 'active_same_hour':
                    state.update(phase='finish', active=row)
                    break
                native._tax(account, p, ident, hour + 3)
                state['rows'].append(row)
                state['index'] += 1
            if state['phase'] == 'complete':
                account.advance(24 * (len(manifest['jobs']) + 1))
            exported = account.export()
            self.assertTrue(account.audit()['accepted'])
        native._save(output / 'public/native-export.json', exported)
        native._save(output / 'public/execution.json', state)

    def test_normal_control_and_completed_resume(self):
        verdict = native.operate(self.output)
        self.assertTrue(verdict['conditional_self_funding'])
        self.assertEqual(verdict['earned_funded_deliveries'], 3)
        self.assertEqual(verdict['simulated_profit_microUSD'], 135900000)
        before = (self.output / 'public/native-export.json').read_bytes()
        self.assertEqual(native.operate(self.output), verdict)
        self.assertEqual((self.output / 'public/native-export.json').read_bytes(), before)

    def rejected(self, mutation, error):
        self.make_native_case(mutation)
        with self.assertRaisesRegex(ValueError, '^' + error + '$'):
            native.audit(self.output)

    def test_production_after_collection_rejected(self):
        self.rejected('late', 'REGISTERED_PRODUCTION_HOUR_CHANGED')

    def test_registered_hour_alone_cannot_hide_reordered_collection(self):
        self.rejected('same_hour', 'PRODUCTION_MUST_PRECEDE_DELIVERY')

    def test_registered_hour_alone_cannot_hide_reordered_seed_preparation(self):
        self.rejected('seed_after_prepare', 'PRODUCTION_MUST_PRECEDE_DELIVERY')

    def test_valid_sequence_still_requires_registered_production_hour(self):
        self.rejected('wrong_hour', 'REGISTERED_PRODUCTION_HOUR_CHANGED')

    def test_active_checkpoint_rejects_postcollection_spend(self):
        self.rejected('active_same_hour', 'PRODUCTION_MUST_PRECEDE_DELIVERY')

    def test_active_preparation_requires_completed_production(self):
        self.rejected('missing_active', 'PRODUCTION_MUST_PRECEDE_DELIVERY')


if __name__ == '__main__':
    unittest.main()
