"""Actual canonical producer and independent verifier: differential evidence tests."""
import copy
import json
import random
import unittest
from commercial import service, service_verifier, verified_delta as delta


def order(customers=20, per=3, *, require_complete=True):
    invoices, payments = [], []
    for i in range(customers):
        for j in range(per):
            ident = f'C{i:03d}-J{j:03d}'
            cents = 1000 + i*17 + j*13
            invoices.append({'id':f'I-{ident}', 'customer':f'C{i:03d}', 'amount_cents':cents})
            payments.append({'id':f'P-{ident}', 'customer':f'C{i:03d}', 'amount_cents':cents,
                             'invoice_refs':[f'I-{ident}']})
    return {'scope':'SYNTHETIC_PUBLIC_WORKLOAD','currency':'USD','order_id':'DELTA-044',
            'require_complete':require_complete,'invoices':invoices,'payments':payments}


class VerifiedDifferentialProductionTests(unittest.TestCase):
    def test_fresh_cold_proof_matches_direct_and_real_independent_checker(self):
        input_order=order()
        direct=service.reconcile(input_order)
        cert=delta.execute(input_order)
        self.assertEqual(cert['report'],direct)
        self.assertTrue(service_verifier.audit_delivery(input_order,cert['report'])['accepted'])
        receipt=delta.verify(input_order,cert,full=True)
        self.assertTrue(receipt['current_complete_outcome_accepted'])
        self.assertEqual(cert['fresh_groups'],20)
        self.assertEqual(cert['reused_groups'],0)
        self.assertEqual(cert['semantic_rows_rechecked'],120)
        self.assertIsNone(cert['actual_profit'])
        self.assertFalse(cert['financial_authority'])

    def test_successor_one_change_reuses_nineteen_freshly_pinned_proofs(self):
        o=order();first=delta.execute(o);delta.verify(o,first,full=True)
        successor=copy.deepcopy(o)
        successor['invoices'][0]['amount_cents']+=19
        successor['payments'][0]['amount_cents']+=19
        changed=delta.execute(successor,first,expected_previous_sha256=delta.digest(first))
        independent=delta.verify(successor,changed,first,expected_previous_sha256=delta.digest(first),full=True)
        self.assertEqual(changed['report'],service.reconcile(successor))
        self.assertTrue(independent['current_complete_outcome_accepted'])
        self.assertEqual((changed['reused_groups'],changed['fresh_groups']),(19,1))
        self.assertEqual(changed['semantic_rows_rechecked'],6)
        self.assertEqual(changed['global_input_rows_scanned'],120)

    def test_no_change_cannot_be_called_new_invention(self):
        o=order();initial=delta.execute(o);final=delta.execute(o,initial,expected_previous_sha256=delta.digest(initial))
        self.assertEqual(final['reused_groups'],20)
        self.assertEqual(final['semantic_rows_rechecked'],0)
        self.assertEqual(final['report'],service.reconcile(o))
        self.assertTrue(delta.verify(o,final,initial,expected_previous_sha256=delta.digest(initial),full=True)['fresh_full_comparison'])

    def test_missing_pin_or_altered_prior_is_refused(self):
        o=order();original=delta.execute(o)
        with self.assertRaisesRegex(ValueError,'PRIOR_CERTIFICATE_PIN_REQUIRED'):
            delta.execute(o,original)
        damaged=copy.deepcopy(original);damaged['groups']['C000']['report']['totals']['invoice_cents']+=1
        with self.assertRaisesRegex(ValueError,'PIN_MISMATCH'):
            delta.execute(o,damaged,expected_previous_sha256=delta.digest(original))

    def test_changed_source_does_not_inherit_proof(self):
        o=order();original=delta.execute(o);original['source_hashes']['checker']='0'*64
        with self.assertRaisesRegex(ValueError,'PRIOR_PROOF_OR_EXECUTING_SOURCE_CHANGED'):
            delta.execute(o,original,expected_previous_sha256=delta.digest(original))

    def test_cross_customer_reference_refused(self):
        o=order(2,1);o['payments'][0]['invoice_refs']=['I-C001-J000']
        with self.assertRaises(ValueError):delta.execute(o)

    def test_empty_sided_group_falls_back_to_current_specialist(self):
        o=order(2,1);o['payments'].pop()
        cert=delta.execute(o)
        self.assertEqual(cert['mode'],'DIRECT_FALLBACK')
        self.assertEqual(cert['report'],service.reconcile(o))
        self.assertFalse(cert['report']['accepted'])
        self.assertFalse(delta.verify(o,cert,full=True)['current_complete_outcome_accepted'])

    def test_false_completion_stays_rejected_after_reuse(self):
        o=order(3,2);o['payments'][0]['amount_cents']+=100
        first=delta.execute(o);self.assertFalse(first['report']['accepted'])
        self.assertFalse(delta.verify(o,first,full=True)['current_complete_outcome_accepted'])
        later=copy.deepcopy(o);later['invoices'][-1]['amount_cents']+=5;later['payments'][-1]['amount_cents']+=5
        changed=delta.execute(later,first,expected_previous_sha256=delta.digest(first))
        self.assertFalse(changed['report']['accepted'])
        self.assertEqual(changed['report'],service.reconcile(later))
        self.assertFalse(delta.verify(later,changed,first,expected_previous_sha256=delta.digest(first),full=True)['current_complete_outcome_accepted'])

    def test_forged_current_delivery_or_fake_collections_refused(self):
        o=order(4,2);first=delta.execute(o)
        for mutation in ('fake_profit','changed_report','broken_proof'):
            cert=copy.deepcopy(first)
            if mutation=='fake_profit':cert['actual_collections']=1000000000
            elif mutation=='changed_report':cert['report']['totals']['invoice_cents']+=7
            else:cert['groups']['C001']['report']['matches'].clear()
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                delta.verify(o,cert,full=True)

    def test_new_customer_synthesizes_one_new_shard_and_inherits_existing(self):
        o=order(3,2);first=delta.execute(o)
        successor=order(4,2)
        next_cert=delta.execute(successor,first,expected_previous_sha256=delta.digest(first))
        self.assertEqual(next_cert['reused_groups'],3)
        self.assertEqual(next_cert['fresh_groups'],1)
        self.assertEqual(next_cert['semantic_rows_rechecked'],4)
        delta.verify(successor,next_cert,first,expected_previous_sha256=delta.digest(first),full=True)

    def test_fresh_randomized_campaign_vs_direct_strong_specialist(self):
        rng=random.Random(2610310044)
        o=order(12,3);prior=None;pin=None
        total_direct_rows=0;total_delta_rows=0;total_scan_rows=0
        for turn in range(30):
            if turn:
                idx=rng.randrange(len(o['invoices']))
                if turn%5==0:
                    o['payments'][idx]['invoice_refs']=[]
                elif turn%7==0:
                    o['payments'][idx]['invoice_refs']=[o['invoices'][idx]['id']]
                o['invoices'][idx]['amount_cents']+=turn
                o['payments'][idx]['amount_cents']+=turn
            cert=delta.execute(o,prior,expected_previous_sha256=pin)
            self.assertEqual(cert['report'],service.reconcile(o))
            self.assertEqual(cert['report']['accepted'],service_verifier.audit_delivery(o,cert['report'])['accepted'])
            self.assertTrue(delta.verify(o,cert,prior,expected_previous_sha256=pin,full=True)['source_bound'])
            total_direct_rows+=len(o['invoices'])+len(o['payments'])
            total_delta_rows+=cert['semantic_rows_rechecked']
            total_scan_rows+=cert['global_input_rows_scanned']
            prior,pin=cert,delta.digest(cert)
        self.assertLess(total_delta_rows,total_direct_rows/4)
        self.assertEqual(total_scan_rows,total_direct_rows)

    def test_public_demo_is_reverifiable_and_forged_success_is_rejected(self):
        import tempfile
        from pathlib import Path
        from scripts import demo_verified_delta044 as demo
        with tempfile.TemporaryDirectory() as directory:
            bundle=Path(directory)/'proof'
            created=demo.build(bundle)
            self.assertTrue(created['verified'])
            self.assertEqual(created['demo']['reused_groups'],99)
            self.assertEqual(created['demo']['rows_semantically_rechecked'],10)
            self.assertTrue(demo.verify(bundle)['verified'])
            p=bundle/'DEMO.json';record=json.loads(p.read_text())
            record['actual_collections']=1000000000
            p.write_bytes(delta.canonical(record))
            with self.assertRaisesRegex(ValueError,'CURRENT_DEMO_RECEIPT_DOES_NOT_REDERIVE'):
                demo.verify(bundle)


if __name__=='__main__':unittest.main()
