import copy
import json
import tempfile
import unittest
from pathlib import Path
from commercial.service import deliver, reconcile


def order():
    return {"scope": "SYNTHETIC_PUBLIC_WORKLOAD", "currency": "USD", "order_id": "test", "require_complete": True, "invoices": [{"id": "i1", "customer": "A", "amount_cents": 101}], "payments": [{"id": "p1", "customer": "A", "amount_cents": 101, "invoice_refs": ["i1"]}]}


class ServiceTests(unittest.TestCase):
    def test_split_and_bundled(self):
        x = order()
        x['invoices'].append({'id':'i2','customer':'A','amount_cents':199})
        x['payments'] = [{'id':'p1','customer':'A','amount_cents':120,'invoice_refs':['i1','i2']}, {'id':'p2','customer':'A','amount_cents':180,'invoice_refs':['i2','i1']}]
        y = reconcile(x)
        self.assertTrue(y['accepted'])
        self.assertEqual(y['totals']['matched_invoice_cents'],300)
        self.assertEqual(y['matches'][0]['payment_ids'],['p1','p2'])
    def test_equal_amount_ambiguity_is_not_forced(self):
        x = order()
        x['invoices'].append({'id':'i2','customer':'A','amount_cents':101})
        x['payments'][0]['invoice_refs'] = []
        y = reconcile(x)
        self.assertFalse(y['accepted'])
        self.assertEqual(y['matches'],[])
        x['require_complete'] = False
        self.assertTrue(reconcile(x)['accepted'])
    def test_customer_different_does_not_match(self):
        x = order()
        x['payments'][0].update(customer='B',invoice_refs=[])
        self.assertFalse(reconcile(x)['accepted'])
    def test_malformed_rejected(self):
        for mutate in [lambda x: x.update(currency='CAD'), lambda x: x['payments'][0].update(amount_cents=-101), lambda x: x['payments'][0].update(amount_cents=True), lambda x:x['invoices'][0].update(currency='EUR'), lambda x:x['payments'][0].update(invoice_refs=['missing']), lambda x:x['payments'][0].update(invoice_refs=['i1','i1'])]:
            x = order(); mutate(x)
            with self.assertRaises(ValueError): reconcile(x)
    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'delivery'
            deliver(order(),target)
            before=(target/'reconciliation.json').read_bytes()
            with self.assertRaises(FileExistsError): deliver(order(),target)
            self.assertEqual(before,(target/'reconciliation.json').read_bytes())
    def test_order_invariance_and_conservation(self):
        x=order()
        x['invoices'] += [{'id':f'i{k}','customer':'A','amount_cents':k*100+7} for k in range(2,18)]
        x['payments'] += [{'id':f'p{k}','customer':'A','amount_cents':k*100+7,'invoice_refs':[f'i{k}']} for k in range(2,18)]
        reference=reconcile(x)
        x['invoices'].reverse(); x['payments'].reverse()
        self.assertEqual(reconcile(x),reference)
        t=reference['totals']
        self.assertEqual(t['invoice_cents'],t['matched_invoice_cents']+t['open_invoice_cents'])
        self.assertEqual(t['payment_cents'],t['matched_payment_cents']+t['unallocated_payment_cents'])
    def test_overlapping_explicit_groups_quarantined(self):
        x=order(); x['require_complete']=False
        x['payments'] += [{'id':'p2','customer':'A','amount_cents':101,'invoice_refs':[]}]
        x['invoices'].append({'id':'i2','customer':'A','amount_cents':99})
        x['payments'].append({'id':'p3','customer':'A','amount_cents':200,'invoice_refs':['i1','i2']})
        self.assertEqual(reconcile(x)['matches'],[])
