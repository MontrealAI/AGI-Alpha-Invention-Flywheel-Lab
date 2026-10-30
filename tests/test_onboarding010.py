import json
from pathlib import Path
import tempfile
import unittest
from commercial.onboarding import prepare_delivery,prepare_order,synthetic_exports
from commercial.service import canonical
from commercial.service_verifier import audit_delivery
from commercial.service import reconcile


def specimen():
    return {'order_id':'quoted-export','scope':'SYNTHETIC_PUBLIC_WORKLOAD','currency':'USD','require_complete':True,'invoices':[{'id':'invoice,one','customer':'Buyer "A", LLC','amount_cents':12001}],'payments':[{'id':'payment-one','customer':'Buyer "A", LLC','amount_cents':12001,'invoice_refs':['invoice,one']}]}


class OnboardingTests(unittest.TestCase):
    def test_real_csv_quoting_and_exact_identity(self):
        order=specimen()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);paths=synthetic_exports(order,root/'exports')
            actual=prepare_delivery(paths/'contract.json',paths/'invoices.csv',paths/'payments.csv',root/'prepared')
            self.assertEqual(actual,order)
            self.assertEqual((root/'prepared/prepared-order.json').read_bytes(),canonical(order))
            self.assertTrue(audit_delivery(order,reconcile(actual))['accepted'])
            with self.assertRaises(FileExistsError): prepare_delivery(paths/'contract.json',paths/'invoices.csv',paths/'payments.csv',root/'prepared')
    def test_bad_csv_fail_closed(self):
        variants=[('id,customer,amount_cents,currency\nx,A,1,USD,extra\n','fieldcount'),('id,id,amount_cents,currency\nx,A,1,USD\n','duplicateheader'),('id,customer,amount_cents,currency\nx,A,1.00,USD\n','centsunit'),('id,customer,amount_cents,currency\nx,A,-1,USD\n','negative'),('id,customer,amount_cents,currency\nx,A,1,EUR\n','currency'),('id,customer,amount_cents,currency\n"unterminated','quotes'),('id,customer,amount_cents,currency\nx,A,1,USD\nx,A,1,USD\n','duplicateid'),('id,customer,amount_cents,currency\nx,A,0,USD\n','zero')]
        for contents,label in variants:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as td:
                p=synthetic_exports(specimen(),Path(td)/'exports');(p/'invoices.csv').write_text(contents)
                with self.assertRaises(ValueError): prepare_order(p/'contract.json',p/'invoices.csv',p/'payments.csv')
    def test_no_default_contract_or_units(self):
        with tempfile.TemporaryDirectory() as td:
            p=synthetic_exports(specimen(),Path(td)/'exports')
            for text in ['{"order_id":"x"}','{"order_id":"a","order_id":"b","scope":"SYNTHETIC_PUBLIC_WORKLOAD","currency":"USD","require_complete":true}']:
                (p/'contract.json').write_text(text)
                with self.assertRaises(ValueError): prepare_order(p/'contract.json',p/'invoices.csv',p/'payments.csv')
    def test_bom_supported_without_data_change(self):
        with tempfile.TemporaryDirectory() as td:
            p=synthetic_exports(specimen(),Path(td)/'exports');f=p/'invoices.csv';f.write_bytes(b'\xef\xbb\xbf'+f.read_bytes())
            self.assertEqual(prepare_order(p/'contract.json',p/'invoices.csv',p/'payments.csv'),specimen())
    def test_refs_json_customer_and_oversize_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=synthetic_exports(specimen(),Path(td)/'exports')
            for contents in ['id,customer,amount_cents,invoice_refs,currency\np,A,12001,NaN,USD\n','id,customer,amount_cents,invoice_refs,currency\np,A,12001,[],USD\n']:
                (p/'payments.csv').write_text(contents)
                if 'NaN' in contents:
                    with self.assertRaises(ValueError): prepare_order(p/'contract.json',p/'invoices.csv',p/'payments.csv')
                else:
                    actual=prepare_order(p/'contract.json',p/'invoices.csv',p/'payments.csv')
                    self.assertFalse(audit_delivery(actual,reconcile(actual))['accepted'])
            (p/'payments.csv').write_bytes(b'x'*2_000_001)
            with self.assertRaises(ValueError): prepare_order(p/'contract.json',p/'invoices.csv',p/'payments.csv')
