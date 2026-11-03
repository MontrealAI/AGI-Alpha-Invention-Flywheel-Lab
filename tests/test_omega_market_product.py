"""Native price, complete voluntary bundle, real output and recovery regressions.

Every account here is a disposable, explicitly synthetic test fixture. None is
the experiment's historical primary account or authority to continue it.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from commercial.ledger import canonical, digest
from connected_enterprise.finance import JournalAccount
from omega import product
from omega.market_buyer import to_receipt
from omega.process import fixture


ROOT = Path(__file__).resolve().parents[1]
MICRO = product.MICRO


def receipts(*, bundle=False, price=149*MICRO, consent=True):
    persona = {'id':'authored-buyer', 'budget_cents':100000, 'value_cents':100000,
               'software_setup_cents':40000 if bundle else 0,
               'webinar_learning_cents':0, 'founder_access_cents':0,
               'switching_cents':0, 'buyer_compute_cents':100,
               'webinar_setup_reduction_cents':40000 if bundle else 0,
               'private_session_prerequisites_met':False, 'required_capability':1,
               'outside_options':[{'id':'competent-free-route', 'price_cents':0,
                   'effort_cents':80000, 'capability':1, 'trust_bps':10000, 'reliability_bps':10000}]}
    offers = [{'id':'software', 'product':'self_hosted', 'price_cents':price//10000,
               'capability':1, 'effort_cents':0, 'trust_bps':10000, 'reliability_bps':10000}]
    if bundle:
        offers.append({'id':'webinar', 'product':'group_webinar', 'price_cents':9900,
                       'capability':1, 'effort_cents':1000, 'trust_bps':10000, 'reliability_bps':5000})
    return [to_receipt(persona, offers, offer['id'], consent=consent, choice_id='authored-one-decision')
            for offer in offers]


class MarketProductTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT)
        self.path = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def manifest(self, **kwargs):
        return product.prepare_manifest(ROOT, self.path/'products', hypothetical_rights=True, **kwargs)

    def account(self, manifest, *, opening=100000*MICRO):
        return JournalAccount(ROOT, manifest, self.path/'account.sqlite', opening=opening,
                              working=0, contract='disposable-market-product-regression')

    def one(self, account, manifest, **kwargs):
        return product.fulfill(account, ROOT, manifest, manifest['jobs'][0]['id'],
                               order_id='authored-order', buyer='authored-buyer', hour=0, **kwargs)

    def bundle(self, account, manifest):
        return product.fulfill_bundle(account, ROOT, manifest,
            [job['id'] for job in manifest['jobs']], order_id_prefix='authored-bundle',
            buyer='authored-buyer', hour=0)

    def bundle_manifest(self, **kwargs):
        return self.manifest(jobs=['self_hosted', 'group_webinar'], prices=[149*MICRO, 99*MICRO],
                             choices=receipts(bundle=True), **kwargs)

    def manually_fund(self, account, manifest, *, price=None):
        job = manifest['jobs'][0]
        price = job.get('price', product.PRICE[job['product']]) if price is None else price
        for ident, amount in product.cost_rows(job, 'manual', manifest['costs']):
            account.cost(ident, amount, 0)
        account.execute('register_terms', {'id':'manual:terms',
            'terms':product.terms_for(manifest, 'manual', job['product'], 0, price)}, 0)
        account.execute('wallet', {'buyer':'authored-manual', 'amount':price}, 0)
        account.execute('offer', {'id':'manual', 'buyer':'authored-manual', 'price':price,
            'job_id':job['id'], 'deadline':24, 'terms_id':'manual:terms'}, 0)
        for action in ('consent', 'fund'):
            account.execute('event', {'id':'manual', 'action':action, 'event_id':'manual:'+action}, 0)
        return product.produce(ROOT, manifest, job['id'])

    def test_variable_price_job_costs_and_custom_buyer_request_are_bound(self):
        water = json.loads((ROOT/'omega/request.json').read_text())
        water['name'] = 'Buyer supplied unfamiliar request identity'
        costs = {'payment_friction':5_515_000, 'delivery':MICRO}
        manifest = self.manifest(prices=[149*MICRO], choices=receipts(),
                                 water_requests=[water], job_costs=[costs])
        with self.account(manifest) as account:
            self.assertEqual(self.one(account, manifest)['collected'], 149*MICRO)
            record = account.export()
            self.assertEqual(record['ledger']['summary']['expensePaid'], sum(costs.values()))
            self.assertEqual(record['ledger']['summary']['profit'], 149*MICRO-sum(costs.values()))
            self.assertTrue(product.replay(record, root=ROOT, manifest=manifest)['accepted'])
        audit = product.audit_order(ROOT, manifest, manifest['jobs'][0]['id'])
        self.assertEqual(audit['price_microUSD'], 149*MICRO)
        self.assertTrue(audit['bound_simulated_consent'])
        self.assertFalse(audit['observed_customer_demand'])
        artifact = product.delivery(ROOT, manifest, manifest['jobs'][0]['id'])
        self.assertEqual(artifact['buyer_result']['request_sha256'], digest(water))

    def test_quote_change_budget_net_and_missing_bundle_rejected_before_files(self):
        malformed = []
        changed = receipts(); changed[0]['budget_microUSD'] = 149*MICRO
        malformed.append(changed)
        changed = receipts(); changed[0]['alternatives'][1]['net_utility_microUSD'] += 1
        malformed.append(changed)
        changed = receipts(); changed[0]['consent'] = 1
        malformed.append(changed)
        malformed.append(receipts(bundle=True)[:1])
        for choices in malformed:
            with self.assertRaises(ValueError):
                self.manifest(prices=[149*MICRO], choices=choices)
            self.assertFalse((self.path/'products').exists())
        with self.assertRaisesRegex(ValueError, 'PRODUCT_PRICE_OR_LINE_ITEM'):
            self.manifest(prices=[499*MICRO], choices=receipts())

    def test_consent_false_has_no_financial_effect_and_cannot_native_prepare(self):
        manifest = self.manifest(prices=[149*MICRO], choices=receipts(consent=False))
        with self.account(manifest) as account:
            before = account.export()
            self.assertEqual(self.one(account, manifest)['status'], 'declined')
            self.assertEqual(before, account.export())
            artifact = self.manually_fund(account, manifest)
            with self.assertRaisesRegex(ValueError, 'BOUND_VOLUNTARY_BUYER_CONSENT'):
                account.execute('event', {'id':'manual', 'action':'prepare', 'event_id':'bad-prepare',
                                          'artifact_sha256':digest(artifact)}, 0)
            self.assertEqual(account.export()['ledger']['summary']['collections'], 0)

    def test_wrong_native_price_cannot_prepare_even_with_valid_terms(self):
        manifest = self.manifest(prices=[149*MICRO], choices=receipts())
        with self.account(manifest) as account:
            artifact = self.manually_fund(account, manifest, price=299*MICRO)
            with self.assertRaisesRegex(ValueError, 'PRODUCT_PRICE_CHANGED'):
                account.execute('event', {'id':'manual', 'action':'prepare', 'event_id':'bad-prepare',
                                          'artifact_sha256':digest(artifact)}, 0)
            self.assertEqual(account.export()['ledger']['summary']['collections'], 0)

    def test_nonpayment_is_unfunded_and_zero_collection_after_restart(self):
        manifest = self.manifest(prices=[149*MICRO], choices=receipts(), outcomes=[{'paid':False}])
        with self.account(manifest) as account:
            self.assertEqual(self.one(account, manifest)['status'], 'unpaid')
            before = account.export()
            self.assertEqual(before['ledger']['summary']['collections'], 0)
            self.assertEqual(before['ledger']['summary']['custodyRestricted'], 0)
            self.assertGreater(before['ledger']['summary']['expensePaid'], 0)
            self.assertFalse(any(a['op']=='event' and a['args']['action']=='fund' for a in before['ledger']['actions']))
            self.assertTrue(product.replay(before, root=ROOT, manifest=manifest)['accepted'])
        with self.account(manifest) as account:
            self.assertEqual(self.one(account, manifest)['status'], 'unpaid')
            self.assertEqual(account.export(), before)

    def test_manual_funding_cannot_bypass_nonpayment_receipt(self):
        manifest = self.manifest(outcomes=[{'paid':False}])
        with self.account(manifest) as account:
            artifact = self.manually_fund(account, manifest)
            self.assertTrue(product.check_delivery(ROOT, manifest, manifest['jobs'][0]['id'], artifact)['accepted'])
            with self.assertRaisesRegex(ValueError, 'SCENARIO_NONPAYMENT'):
                account.execute('event', {'id':'manual', 'action':'prepare', 'event_id':'bad-prepare',
                                          'artifact_sha256':digest(artifact)}, 0)

    def test_process_delivery_is_independently_checked_and_runs_when_extracted(self):
        request = fixture(True)
        manifest = self.manifest(prices=[149*MICRO], choices=receipts(), process_requests=[request])
        with self.account(manifest) as account:
            self.assertEqual(self.one(account, manifest)['status'], 'released')
            self.assertTrue(product.replay(account.export(), root=ROOT, manifest=manifest)['accepted'])
        artifact = product.delivery(ROOT, manifest, manifest['jobs'][0]['id'])
        self.assertEqual(artifact['workflow'], 'process')
        self.assertTrue(artifact['buyer_result']['certificate']['accepted'])
        extract = self.path/'extracted'
        for name, text in artifact['files'].items():
            target = extract/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        request_path = extract/'buyer-request.json'
        request_path.write_bytes(canonical(request))
        command = [sys.executable, '-m', 'omega.process', 'new', '--session', str(extract/'buyer.sqlite'),
                   '--request', str(request_path)]
        result = subprocess.run(command, cwd=extract, capture_output=True, text=True, check=True)
        report = json.loads(result.stdout)
        self.assertEqual(report['policy'], artifact['buyer_result']['plan'])
        model, step = request['models'][0], 0
        while report['state']['status'] == 'WAITING':
            node = report['state']['node']
            step += 1
            if node['kind'] == 'test':
                args = ['observe', '--experiment', node['experiment_id'], '--value', str(model['responses'][node['experiment_id']])]
            else:
                args = ['accept', '--recipe', node['recipe_id'], '--yield-value', str(model['yields'][node['recipe_id']])]
            result = subprocess.run([sys.executable, '-m', 'omega.process', *args,
                '--session', str(extract/'buyer.sqlite'), '--action-id', 'authored-observation-'+str(step)],
                cwd=extract, capture_output=True, text=True, check=True)
            report = json.loads(result.stdout)
        self.assertEqual(report['state']['status'], 'ACCEPTED')
        self.assertFalse(report['independent_physical_acceptance'])
        self.assertEqual(report['model_api_calls'], 0)

    def test_process_refusal_never_becomes_paid_acceptance(self):
        request = fixture(); request['max_total_cost_cents'] = 0
        manifest = self.manifest(process_requests=[request])
        with self.account(manifest) as account:
            result = self.one(account, manifest)
            self.assertEqual(result['status'], 'refunded')
            self.assertEqual(account.export()['ledger']['summary']['collections'], 0)
            self.assertTrue(product.replay(account.export(), root=ROOT, manifest=manifest)['accepted'])

    def test_every_bundle_output_prepares_before_any_release_and_reuse_is_exact(self):
        manifest = self.bundle_manifest(job_costs=[{'delivery':MICRO}, {'seat':2*MICRO}])
        with self.account(manifest) as account:
            result = self.bundle(account, manifest)
            self.assertTrue(result['complete'])
            self.assertEqual(result['collected'], 248*MICRO)
            before = account.export()
            events = [a['args']['action'] for a in before['ledger']['actions'] if a['op']=='event']
            self.assertLess(max(i for i,a in enumerate(events) if a=='prepare'), min(i for i,a in enumerate(events) if a=='release'))
            self.assertEqual(before['ledger']['summary']['expensePaid'], 3*MICRO+sum(manifest['costs']['group_session'].values()))
            self.assertTrue(product.replay(before, root=ROOT, manifest=manifest)['accepted'])
            self.assertEqual(self.bundle(account, manifest), result)
            self.assertEqual(account.export(), before)

    def test_rejected_companion_refunds_all_and_individual_fulfill_is_refused(self):
        manifest = self.bundle_manifest(outcomes=[{}, {'attended':False}])
        with self.account(manifest) as account:
            with self.assertRaisesRegex(ValueError, 'REQUIRES_FULFILL_BUNDLE'):
                self.one(account, manifest)
            result = self.bundle(account, manifest)
            self.assertEqual(result['status'], 'refunded')
            self.assertFalse(result['complete'])
            self.assertTrue(result['settled'])
            self.assertEqual(result['collected'], 0)
            self.assertEqual({i['state'] for i in result['items']}, {'refunded'})
            self.assertGreater(account.export()['ledger']['summary']['expenses'], 0)
            self.assertTrue(product.replay(account.export(), root=ROOT, manifest=manifest)['accepted'])

    def test_interrupted_release_prefix_reopens_without_double_collection(self):
        manifest = self.bundle_manifest()
        with self.account(manifest) as account:
            execute = account.execute
            def interrupt(op, args, hour):
                if op == 'event' and args['action'] == 'release' and args['id'].endswith('omega-product-1'):
                    raise InterruptedError('authored interruption between native releases')
                return execute(op, args, hour)
            with patch.object(account, 'execute', side_effect=interrupt):
                with self.assertRaises(InterruptedError):
                    self.bundle(account, manifest)
            partial = product.bundle_status(account, ROOT, manifest, [j['id'] for j in manifest['jobs']],
                order_id_prefix='authored-bundle', buyer='authored-buyer')
            self.assertFalse(partial['complete'])
            self.assertEqual(partial['collected'], 149*MICRO)
            self.assertTrue(product.replay(account.export(), root=ROOT, manifest=manifest)['accepted'])
        with self.account(manifest) as account:
            result = self.bundle(account, manifest)
            self.assertTrue(result['complete'])
            self.assertEqual(result['collected'], 248*MICRO)
            before = account.export()
            self.bundle(account, manifest)
            self.assertEqual(account.export(), before)

    def test_definitive_mid_release_failure_compensates_all_and_preserves_breach(self):
        manifest = self.bundle_manifest()
        with self.account(manifest) as account:
            execute = account.execute
            def fail(op, args, hour):
                if op == 'event' and args['action'] == 'release' and args['id'].endswith('omega-product-1'):
                    raise ValueError('authored definitive second-item failure')
                return execute(op, args, hour)
            with patch.object(account, 'execute', side_effect=fail):
                result = self.bundle(account, manifest)
            self.assertEqual(result['status'], 'refunded')
            self.assertFalse(result['complete'])
            self.assertTrue(result['settled'])
            self.assertEqual(result['collected'], 0)
            summary = account.export()['ledger']['summary']
            self.assertEqual(summary['revenue'], 0)
            self.assertEqual(summary['collections'], 0)
            self.assertTrue(summary['investmentStopped'])
            self.assertEqual(summary['profit'], -summary['expenses'])
            self.assertTrue(product.replay(account.export(), root=ROOT, manifest=manifest)['accepted'])
            before = account.export()
            self.assertEqual(self.bundle(account, manifest)['status'], 'refunded')
            self.assertEqual(account.export(), before)

    def test_insufficient_current_cash_defers_whole_bundle_without_postings(self):
        manifest = self.bundle_manifest()
        with self.account(manifest, opening=100*MICRO) as account:
            before = account.export()
            result = self.bundle(account, manifest)
            self.assertEqual(result['status'], 'deferred')
            self.assertFalse(result['complete'])
            self.assertEqual(before, account.export())
            self.assertFalse(any((ROOT/job['output']).exists() for job in manifest['jobs']))

    def test_changed_job_costs_cannot_create_new_unbound_prices_or_obligations(self):
        manifest = self.manifest(prices=[149*MICRO], choices=receipts(), job_costs=[{'delivery':MICRO}])
        changed = copy.deepcopy(manifest)
        changed['jobs'][0]['job_costs']['delivery'] = 0
        with self.assertRaisesRegex(ValueError, 'JOB_COST_BINDING_CHANGED'):
            product.load_contracts(ROOT, changed)
        changed = copy.deepcopy(manifest)
        changed['jobs'][0]['price'] = 499*MICRO
        with self.assertRaisesRegex(ValueError, 'PRODUCT_REQUEST_BINDING_CHANGED'):
            product.load_contracts(ROOT, changed)

    def test_campaign_liquidity_buffer_defers_before_any_attempt_cost(self):
        manifest = self.manifest(prices=[149*MICRO], choices=receipts(), job_costs=[{'delivery':MICRO}])
        with self.account(manifest, opening=150*MICRO) as account:
            before = account.export()
            result = self.one(account, manifest)
            self.assertEqual(result['status'], 'deferred')
            self.assertEqual(result['required_microUSD'], 150*MICRO+200_000)
            self.assertEqual(account.export(), before)

    def test_repeated_decline_does_not_hide_prior_collection(self):
        manifest = self.manifest(prices=[149*MICRO], choices=receipts())
        with self.account(manifest) as account:
            self.one(account, manifest)
            before = account.export()
            result = self.one(account, manifest, consent=False)
            self.assertEqual(result['status'], 'declined')
            self.assertEqual(result['collected'], 149*MICRO)
            self.assertTrue(result['complete'])
            self.assertEqual(account.export(), before)

    def test_process_claimed_certificate_does_not_replace_independent_check(self):
        manifest = self.manifest(process_requests=[fixture()])
        artifact = product.produce(ROOT, manifest, manifest['jobs'][0]['id'])
        artifact['buyer_result']['plan']['worst_cost_cents'] = 0
        # A malicious producer controls both its delivered proposal and its own
        # reported success. The independent checker still rejects the bytes.
        (ROOT/manifest['jobs'][0]['output']).write_bytes(canonical(artifact))
        self.assertFalse(product.check_delivery(ROOT, manifest, manifest['jobs'][0]['id'], artifact)['accepted'])

    def test_bundle_native_order_follows_manifest_across_two_digit_job_ids(self):
        manifest = self.manifest(jobs=11, job_costs=[{'delivery':0} for _ in range(11)])
        with self.account(manifest) as account:
            result = product.fulfill_bundle(account, ROOT, manifest,
                ['omega-product-10', 'omega-product-9'], order_id_prefix='numbered', buyer='synthetic', hour=0)
            self.assertTrue(result['complete'])
            offers = [a['args']['job_id'] for a in account.export()['ledger']['actions'] if a['op']=='offer']
            self.assertEqual(offers, ['omega-product-9', 'omega-product-10'])

    def test_companion_refund_invalidates_remaining_bundle_release(self):
        manifest = self.bundle_manifest()
        with self.account(manifest) as account:
            execute = account.execute
            def interrupt(op, args, hour):
                if op == 'event' and args['action'] == 'release':
                    raise InterruptedError('authored interruption after all prepares')
                return execute(op, args, hour)
            with patch.object(account, 'execute', side_effect=interrupt):
                with self.assertRaises(InterruptedError):
                    self.bundle(account, manifest)
            account.execute('event', {'id':'authored-bundle:omega-product-1', 'action':'refund',
                                      'event_id':'authored-companion-refund'}, 0)
            with self.assertRaisesRegex(ValueError, 'WHOLE_BUYER_BUNDLE_HAS_TERMINAL'):
                account.execute('event', {'id':'authored-bundle:omega-product-0', 'action':'release',
                                          'event_id':'forbidden-partial-release'}, 0)
            self.assertEqual(account.export()['ledger']['summary']['collections'], 0)
            self.assertTrue(product.replay(account.export(), root=ROOT, manifest=manifest)['accepted'])
            result = self.bundle(account, manifest)
            self.assertEqual(result['status'], 'refunded')
            self.assertTrue(result['settled'])
            self.assertFalse(result['complete'])
            self.assertEqual(result['collected'], 0)


if __name__ == '__main__':
    unittest.main()
