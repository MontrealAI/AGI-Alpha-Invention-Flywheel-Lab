"""Whole-buyer receipt -> native delivery for all three defined offers.

Disposable synthetic engineering fixtures only; no market-policy/evaluation run,
business account, actual demand, Zoom session or work by Vincent is represented.
Cash costs use the frozen market functions. Owner time is modeled separately as
noncash opportunity cost, never posted as fictional employee wages.
"""
from pathlib import Path
import tempfile
import unittest

from connected_enterprise.finance import JournalAccount
from omega import market, market_buyer, product


ROOT = Path(__file__).resolve().parents[1]
CENT = 10_000
MICRO = product.MICRO


class MarketServicesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT, prefix='omega-service-engineering-')
        self.path = Path(self.tmp.name)
        self.rates = market.Rates()

    def tearDown(self):
        self.tmp.cleanup()

    def buyer_inputs(self, kind):
        segment = 'training' if kind == 'group_webinar' else 'convenience'
        buyer = market.persona(segment, 'authored-service-' + kind,
                               founder_access=kind == 'founder_private')
        action = market.Action('operate', 29900, 'community', (kind,))
        offers = market.quoted_offers(action, market.PublicState())
        return buyer, offers

    def manifest(self, kinds, *, consent=True, outcomes=None):
        choices, prices, costs = [], [], []
        for kind in kinds:
            buyer, offers = self.buyer_inputs(kind)
            decision = market_buyer.decide(buyer, offers)
            self.assertEqual(decision['selected_offer_ids'], [kind])
            self.assertGreater(decision['increment_over_best_outside_microUSD'], 0)
            self.assertFalse(decision['consent'])  # Choice alone never supplies consent.
            self.assertEqual({o['id'] for o in buyer['outside_options']},
                             {'free_core', 'ordinary_reuse', 'specialist'})
            self.assertTrue(all(o['capability'] == 1 for o in buyer['outside_options']))
            receipt = market_buyer.to_receipt(buyer, offers, kind, consent=consent)
            if consent:
                self.assertTrue(market_buyer.verify_quote_receipt(buyer, offers, receipt)['accepted'])
            choices.append(receipt)
            price = offers[0]['price_cents']
            prices.append(price * CENT)
            costs.append({name: value * CENT for name, value in
                          market.variable_costs(kind, price, 'community').items()})
        # Same division as market_native: selected fixed costs are separately
        # prepaid; each item freezes its exact variable costs. No default choice.
        defaults = {kind: {'unused_default': 0} for kind in market.PRODUCTS}
        defaults['group_session'] = {'prepaid_selected_action': 0}
        return product.prepare_manifest(ROOT, self.path / 'products', jobs=list(kinds),
            hypothetical_rights=True, choices=choices, prices=prices, job_costs=costs,
            costs=defaults, outcomes=outcomes)

    def account(self, manifest):
        return JournalAccount(ROOT, manifest, self.path / 'account.sqlite',
            opening=100_000 * MICRO, working=0,
            contract='disposable-whole-buyer-service-engineering')

    def prepay_selected_fixed_costs(self, account, kinds):
        action = market.Action('operate', 29900, 'community', tuple(kinds))
        rows = market.fixed_costs(action, market.PublicState(), self.rates)
        for kind, cents in rows.items():
            account.cost('engineering-fixed:' + kind, cents * CENT, 0)
        return sum(rows.values()) * CENT

    def fulfill(self, account, manifest, index, *, consent=True):
        job = manifest['jobs'][index]
        return product.fulfill(account, ROOT, manifest, job['id'],
            order_id='engineering-order-' + str(index),
            buyer='authored-service-' + job['product'], hour=0, consent=consent)

    def modeled_owner_cost(self, kinds):
        minutes = (self.rates.webinar_minutes if 'group_webinar' in kinds else 0)
        minutes += self.rates.private_minutes if 'founder_private' in kinds else 0
        return minutes, market.opportunity_cost(minutes, self.rates) * CENT

    def test_three_products_explicit_choice_accept_collect_reopen_exactly_once(self):
        kinds = market.PRODUCTS
        manifest = self.manifest(kinds)
        variable = sum(sum(j['job_costs'].values()) for j in manifest['jobs'])
        with self.account(manifest) as account:
            fixed = self.prepay_selected_fixed_costs(account, kinds)
            for index, kind in enumerate(kinds):
                result = self.fulfill(account, manifest, index)
                self.assertEqual(result['status'], 'released')
                self.assertEqual(result['collected'], product.PRICE[kind])
                order = product.audit_order(ROOT, manifest, manifest['jobs'][index]['id'])
                self.assertTrue(order['bound_simulated_consent'])
                self.assertFalse(order['observed_customer_demand'])
                artifact = product.delivery(ROOT, manifest, manifest['jobs'][index]['id'])
                self.assertTrue(product.check_delivery(ROOT, manifest,
                    manifest['jobs'][index]['id'], artifact)['accepted'])
                if kind == 'self_hosted':
                    self.assertIsNotNone(artifact['buyer_result'])
                    self.assertIsNotNone(artifact['files'])
                else:
                    self.assertTrue(artifact['session_record']['fictional'])
                    self.assertEqual(artifact['founder_minutes'], 30 if kind == 'founder_private' else 0)
            before = account.export()
            summary = before['ledger']['summary']
            self.assertEqual(summary['collections'], sum(product.PRICE.values()))
            self.assertEqual(summary['revenue'], sum(product.PRICE.values()))
            self.assertEqual(summary['expensePaid'], fixed + variable)
            self.assertEqual(summary['expenses'], fixed + variable)
            self.assertTrue(product.replay(before, root=ROOT, manifest=manifest)['accepted'])
        with self.account(manifest) as account:
            self.assertEqual(account.export(), before)
            for index in range(len(kinds)):
                self.assertEqual(self.fulfill(account, manifest, index)['status'], 'released')
            self.assertEqual(account.export(), before)
        minutes, noncash_owner_cost = self.modeled_owner_cost(kinds)
        self.assertEqual((minutes, noncash_owner_cost), (435, 1450 * MICRO))
        # This allowance is a model quantity, not actual labor or a native wage.
        self.assertEqual(summary['profit'], summary['revenue'] - fixed - variable)

    def test_rejected_sessions_refund_preserve_costs_and_reopen_without_repayment(self):
        kinds = ('group_webinar', 'founder_private')
        manifest = self.manifest(kinds, outcomes=[{'attended': False}, {'completed': False}])
        variable = sum(sum(j['job_costs'].values()) for j in manifest['jobs'])
        with self.account(manifest) as account:
            fixed = self.prepay_selected_fixed_costs(account, kinds)
            for index in range(2):
                result = self.fulfill(account, manifest, index)
                self.assertEqual(result['status'], 'refunded')
                self.assertTrue(result['settled'])
                self.assertEqual(result['collected'], 0)
            before = account.export()
            summary = before['ledger']['summary']
            self.assertEqual(summary['collections'], 0)
            self.assertEqual(summary['revenue'], 0)
            self.assertEqual(summary['custodyRestricted'], 0)
            self.assertEqual(summary['expensePaid'], fixed + variable)
            self.assertGreater(summary['expensePaid'], 0)
            self.assertEqual(summary['profit'], -(fixed + variable))
            self.assertEqual({o['state'] for o in before['ledger']['orders']}, {'refunded'})
            self.assertTrue(product.replay(before, root=ROOT, manifest=manifest)['accepted'])
        with self.account(manifest) as account:
            self.assertEqual(account.export(), before)
            for index in range(2):
                self.assertEqual(self.fulfill(account, manifest, index)['status'], 'refunded')
            self.assertEqual(account.export(), before)
        # Frozen market costing charges paid service attempts even if rejected.
        self.assertEqual(self.modeled_owner_cost(kinds), (435, 1450 * MICRO))

    def test_unqualified_private_buyer_cannot_create_receipt_or_payment_fixture(self):
        buyer, offers = self.buyer_inputs('founder_private')
        # Keep the adequate budget and positive access value: isolate eligibility.
        buyer['private_session_prerequisites_met'] = False
        self.assertGreater(buyer['budget_cents'], offers[0]['price_cents'])
        self.assertFalse(market_buyer.decide(buyer, offers)['selected_offer_ids'])
        with self.assertRaisesRegex(ValueError, 'LINE_ITEM_NOT_IN_VOLUNTARY_SELECTED_BUNDLE'):
            market_buyer.to_receipt(buyer, offers, 'founder_private', consent=True)
        self.assertEqual(list(self.path.iterdir()), [])

    def test_declining_private_receipt_has_no_payment_even_if_caller_consents(self):
        manifest = self.manifest(('founder_private',), consent=False)
        with self.account(manifest) as account:
            before = account.export()
            self.assertEqual(self.fulfill(account, manifest, 0, consent=True)['status'], 'declined')
            self.assertEqual(account.export(), before)
            self.assertEqual(before['ledger']['summary']['collections'], 0)
            self.assertEqual(before['ledger']['summary']['expensePaid'], 0)
            self.assertEqual(before['ledger']['orders'], [])
        with self.account(manifest) as account:
            self.assertEqual(self.fulfill(account, manifest, 0, consent=True)['status'], 'declined')
            self.assertEqual(account.export(), before)
        self.assertFalse((ROOT / manifest['jobs'][0]['output']).exists())


if __name__ == '__main__':
    unittest.main()
