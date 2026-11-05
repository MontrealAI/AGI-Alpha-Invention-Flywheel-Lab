"""GENESIS103 active-checkpoint chronology, sourced from independently qualified PR249 fixtures.

The original PR249 tests and source remain immutable on their own branch.
"""
from pathlib import Path
import tempfile
import unittest

from genesis_enterprise import native
from genesis_enterprise.policy import choose, digest
from flexibility063.native import BusinessAccount
from flexibility063.kernel import solve
from flexibility063.verify import verify
from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.finance import audit_journal

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
                target = (i == 0 if mutation in {'missing_active', 'valid_prepared_active', 'funded_unprepared', 'unfunded_active', 'active_wrong_hour'} else i > 0)
                if target and mutation == 'unfunded_active':
                    state.update(phase='fund', active=row)
                    break
                def spend(day):
                    receipt = account.spend('genesis-production-' + ident, 'qualified-computational-delivery',
                        picked['resource_cost'], day,
                        {'binding': reg['binding'], 'request_sha256': digest(job['request']),
                         'executor': picked['tool'], 'scope': 'COMPUTATIONAL_ONLY'},
                        expected_net=picked['contribution'],
                        allow_seed=(i == 0 and p['first_delivery_may_use_seed']))
                    self.assertIsNotNone(receipt)
                    return receipt
                if not target or mutation == 'valid_prepared_active':
                    row['resource_receipt'] = spend(hour)
                if target and mutation in {'funded_unprepared', 'active_wrong_hour'}:
                    row['resource_receipt'] = spend(hour + int(mutation == 'active_wrong_hour'))
                    state.update(phase='produce', active=row)
                    break
                same_hour = target and mutation in {'same_hour', 'active_same_hour', 'seed_after_prepare'}
                artifact = solve(job['request'], picked['mode'])
                completion = account.complete_order(order, ident, artifact, hour if same_hour else hour + 1)
                ordinary = solve(job['request'], 'conventional')
                native._save(output / 'public/controls' / (ident + '.json'), ordinary)
                row.update(accepted=completion['accepted'], artifact_sha256=digest(artifact),
                           ordinary_accepted=verify(job['request'], ordinary)['accepted'])
                if target and mutation == 'valid_prepared_active':
                    state.update(phase='release', active=row)
                    break
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
            self.assertTrue(audit_journal(exported, root=output / 'source', manifest=manifest)['accepted'])
        native._save(output / 'public/native-export.json', exported)
        native._save(output / 'public/execution.json', state)

    def test_control_original_pilot_and_completed_resume(self):
        verdict = native.operate(self.output)
        self.assertTrue(verdict['accepted'])
        self.assertTrue(verdict['conditional_self_funding'])
        self.assertEqual(verdict['earned_funded_deliveries'], 3)
        self.assertEqual(verdict['simulated_profit_microUSD'], 135900000)
        before = (self.output / 'public/native-export.json').read_bytes()
        self.assertEqual(native.operate(self.output), verdict)
        self.assertEqual((self.output / 'public/native-export.json').read_bytes(), before)

    def rejected(self, mutation):
        self.make_native_case(mutation)
        with self.assertRaisesRegex(ValueError, '^ACTIVE_PRODUCTION_MUST_PRECEDE_DELIVERY$'):
            native.audit(self.output)

    def test_active_preparation_without_spend_rejected(self):
        self.rejected('missing_active')

    def test_active_same_hour_collection_before_spend_rejected(self):
        self.rejected('active_same_hour')

    def test_active_production_spend_wrong_hour_rejected(self):
        self.rejected('active_wrong_hour')

    def test_active_funded_before_preparation_remains_valid(self):
        self.make_native_case('funded_unprepared')
        self.assertTrue(native.audit(self.output)['accepted'])

    def test_active_funded_preparation_before_collection_remains_valid(self):
        self.make_native_case('valid_prepared_active')
        self.assertTrue(native.audit(self.output)['accepted'])

    def test_active_pending_order_without_spend_remains_valid(self):
        self.make_native_case('unfunded_active')
        self.assertTrue(native.audit(self.output)['accepted'])


if __name__ == '__main__':
    unittest.main()
