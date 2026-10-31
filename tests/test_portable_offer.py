"""Portable buyer-side outcome verification and tamper/qualification regressions."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from commercial.portable_offer import build, verify, canonical

ROOT = Path(__file__).resolve().parents[1]


def task(complete=True):
    return {'scope': 'SYNTHETIC_PUBLIC_WORKLOAD', 'currency': 'USD', 'order_id': 'SAMPLE-RECON-001',
            'require_complete': complete,
            'invoices': [{'id': 'invoice-1', 'customer': 'SYNTHETIC-CUSTOMER', 'amount_cents': 8700},
                         {'id': 'invoice-2', 'customer': 'SYNTHETIC-CUSTOMER', 'amount_cents': 3300}],
            'payments': [{'id': 'payment-1', 'customer': 'SYNTHETIC-CUSTOMER', 'amount_cents': 8700, 'invoice_refs': ['invoice-1']},
                         {'id': 'payment-2', 'customer': 'SYNTHETIC-CUSTOMER', 'amount_cents': 3300, 'invoice_refs': ['invoice-2']}]}


class PortableOfferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'bundle'

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, order=None, price=15000):
        return build(task() if order is None else order, self.path, price_cents=price)

    def test_complete_service_proof_reproduces(self):
        result = self.make()
        self.assertEqual(result['qualification'], 'QUALIFIED_SYNTHETIC_DELIVERY')
        self.assertTrue(result['recomputed_independently'])
        self.assertEqual(result['actual_collections_cents'], 0)
        self.assertEqual(result, verify(self.path))

    def test_paid_quote_is_never_a_sale_or_payment(self):
        self.make()
        offer = json.loads((self.path/'OFFER.json').read_bytes())
        self.assertEqual(offer['quoted_terms'], 'HYPOTHETICAL_PRICE_NOT_ACCEPTED_OR_PAYABLE')
        self.assertIs(offer['consent_or_payment_collected'], False)
        self.assertEqual(json.loads((self.path/'VERDICT.json').read_bytes())['observed_revenue_cents'], 0)

    def test_mismatched_row_is_disclosed_not_marked_accepted(self):
        order=task();order['payments'][1]['amount_cents']=2800
        r=self.make(order)
        self.assertEqual(r['qualification'], 'NOT_QUALIFIED')
        self.assertEqual(json.loads((self.path/'OFFER.json').read_bytes())['exceptions_disclosed'],2)

    def test_missing_completeness_can_still_be_disclosed_when_permitted(self):
        order=task(False);order['payments'][1]['amount_cents']=2800
        r=self.make(order)
        self.assertEqual(r['qualification'],'QUALIFIED_SYNTHETIC_DELIVERY')
        self.assertEqual(json.loads((self.path/'OFFER.json').read_bytes())['exceptions_disclosed'],2)

    def test_any_delivery_byte_mutation_is_detected(self):
        self.make()
        file=self.path/'DELIVERY/reconciliation.json'
        file.write_bytes(file.read_bytes().replace(b'8700',b'8701'))
        with self.assertRaisesRegex(ValueError,'IDENTITY_MISMATCH'):
            verify(self.path)

    def test_forged_receipt_even_with_rehashed_manifest_is_detected(self):
        self.make()
        p=self.path/'VERDICT.json';raw=json.loads(p.read_text());raw['observed_revenue_cents']=1234
        p.write_bytes(canonical(raw))
        m=self.path/'MANIFEST.json';manifest=json.loads(m.read_text())
        manifest['files']['VERDICT.json']={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':len(p.read_bytes())}
        m.write_bytes(canonical(manifest))
        with self.assertRaisesRegex(ValueError,'INDEPENDENT_ACCEPTANCE_RECOMPUTATION_FAILED'):
            verify(self.path)

    def test_rehashed_acceptance_forgery_rejected_by_checker(self):
        self.make()
        p=self.path/'DELIVERY/reconciliation.json';r=json.loads(p.read_text());r['totals']['invoice_cents']+=10
        p.write_bytes(canonical(r))
        m=self.path/'MANIFEST.json';manifest=json.loads(m.read_text())
        manifest['files']['DELIVERY/reconciliation.json']={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':len(p.read_bytes())}
        m.write_bytes(canonical(manifest))
        with self.assertRaisesRegex(ValueError,'INDEPENDENT_ACCEPTANCE_RECOMPUTATION_FAILED'):
            verify(self.path)

    def test_exception_file_rehash_does_not_bypass_independence(self):
        order=task(False);order['payments'][1]['amount_cents']=2800
        self.make(order)
        p=self.path/'DELIVERY/exceptions.csv';p.write_text('order_id,kind,row_id\n')
        m=self.path/'MANIFEST.json';manifest=json.loads(m.read_text())
        manifest['files']['DELIVERY/exceptions.csv']={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':len(p.read_bytes())}
        m.write_bytes(canonical(manifest))
        with self.assertRaisesRegex(ValueError,'EXCEPTION_SCHEDULE_CHANGED'):
            verify(self.path)

    def test_package_extra_file_refused(self):
        self.make();(self.path/'SIDE_CHANNEL.txt').write_text('unexpected')
        with self.assertRaisesRegex(ValueError,'EXACT_PACKAGE_CLOSURE'):
            verify(self.path)

    def test_symlink_cannot_replace_a_bound_artifact(self):
        self.make()
        p=self.path/'ORDER.json';p.unlink();p.symlink_to(self.path/'OFFER.json')
        with self.assertRaisesRegex(ValueError,'SYMLINK_PATH_REFUSED'):
            verify(self.path)

    def test_existing_bundle_never_overwritten(self):
        first=self.make();original=(self.path/'MANIFEST.json').read_bytes()
        with self.assertRaises(FileExistsError):self.make()
        self.assertEqual(original,(self.path/'MANIFEST.json').read_bytes())
        self.assertEqual(first,verify(self.path))

    def test_synthetic_only_public_workload(self):
        order=task();order['scope']='PRIVATE_CUSTOMER_FILES'
        with self.assertRaises(ValueError):self.make(order)
        self.assertFalse(self.path.exists())

    def test_invalid_offer_price_refused(self):
        for price in [0,-1,True,1.5,10**15]:
            with self.subTest(price=price),self.assertRaises(ValueError):self.make(price=price)
        self.assertFalse(self.path.exists())

    def test_duplicate_json_fields_refused_at_cli(self):
        p=Path(self.tmp.name)/'task.json';p.write_text('{"scope":"SYNTHETIC_PUBLIC_WORKLOAD","scope":"PRIVATE"}')
        cmd=[sys.executable,'-m','commercial.portable_offer','build','--input',str(p),
             '--output',str(self.path),'--price-cents','1000']
        proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(proc.returncode,2)
        self.assertFalse(self.path.exists())

    def test_cli_roundtrip(self):
        p=Path(self.tmp.name)/'task.json';p.write_bytes(canonical(task()))
        cmd=[sys.executable,'-m','commercial.portable_offer','build','--input',str(p),
             '--output',str(self.path),'--price-cents','15000']
        proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr)
        check=subprocess.run([sys.executable,'-m','commercial.portable_offer','verify',
                              '--path',str(self.path)],cwd=ROOT,capture_output=True,text=True,timeout=10)
        self.assertEqual(check.returncode,0,check.stderr)
        self.assertEqual(json.loads(proc.stdout),json.loads(check.stdout))


if __name__=='__main__':unittest.main()
