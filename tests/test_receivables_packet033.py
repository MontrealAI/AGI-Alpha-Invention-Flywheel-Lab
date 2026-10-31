import copy
import unittest
from unittest.mock import patch
from connected_enterprise.packet_contract import synthetic_input,validate_input,work_contract,digest,source_material
from connected_enterprise.receivables_packet import produce
from connected_enterprise.receivables_packet_verify import audit_packet

class ReceivablesPacket(unittest.TestCase):
    def setUp(self): self.raw=synthetic_input(0,'engineering-packet-033',40)
    def test_actual_components_and_unresolved_exceptions(self):
        artifact=produce(self.raw);checked=audit_packet(self.raw,artifact)
        self.assertTrue(checked['accepted'],checked)
        self.assertEqual(len(artifact['components']),3)
        m=artifact['components']['receivables_metrics']
        self.assertEqual(m['opening_outstanding_cents']+m['period_invoiced_cents']-m['applied_receipts_cents'],m['closing_unresolved_receivables_cents'])
        self.assertGreater(m['unresolved_invoice_count'],0)
        self.assertTrue(artifact['components']['exception_evidence']['issues'])
        self.assertEqual(artifact['work_observation']['instrumented_source_row_visits'],len(self.raw['invoices'])+len(artifact['components']['exception_evidence']['issues']))
    def test_independent_checker_does_not_call_producer(self):
        artifact=produce(self.raw)
        with patch('connected_enterprise.receivables_packet.produce',side_effect=AssertionError('producer called')):
            self.assertTrue(audit_packet(self.raw,artifact)['accepted'])
    def test_cross_entity_period_source_mismatch(self):
        a=produce(self.raw)
        for field,value in [('entity_id','wrong'),('period',{'start_inclusive':'2026-09-01','end_exclusive':'2026-10-01'}),('source_sha256','0'*64)]:
            bad=copy.deepcopy(a);bad[field]=value
            self.assertFalse(audit_packet(self.raw,bad)['accepted'])
    def test_missing_source_or_component_rejected(self):
        a=produce(self.raw);bad=copy.deepcopy(self.raw);bad['invoices'].pop()
        self.assertFalse(audit_packet(bad,a)['accepted'])
        bad=copy.deepcopy(a);del bad['components']['exception_evidence']
        self.assertFalse(audit_packet(self.raw,bad)['accepted'])
    def test_metrics_and_suppressed_exception_rejected(self):
        a=produce(self.raw);bad=copy.deepcopy(a);bad['components']['receivables_metrics']['closing_unresolved_receivables_cents']+=1
        self.assertFalse(audit_packet(self.raw,bad)['accepted'])
        bad=copy.deepcopy(a);bad['components']['exception_evidence']['issues']=[]
        self.assertFalse(audit_packet(self.raw,bad)['accepted'])
    def test_unsupported_scope_negative_and_customer_leak(self):
        for mutate in (lambda r:r.update(requested_scope='full_books_certification'),lambda r:r['invoices'][0].update(amount_cents=-1),lambda r:r['payments'][0].update(customer='other')):
            bad=copy.deepcopy(self.raw);mutate(bad);bad['source_sha256']=digest(source_material(bad))
            with self.assertRaises(ValueError):validate_input(bad)
    def test_atomic_work_identity_units_and_no_native_authority(self):
        c=work_contract(self.raw);other=copy.deepcopy(self.raw);other['order_id']='another-order-same-work'
        self.assertEqual(c['work_keys'],work_contract(other)['work_keys'])
        other['source_id']='renamed-export';other['source_sha256']=digest(source_material(other))
        self.assertEqual(c['work_keys'],work_contract(other)['work_keys'])
        self.assertEqual(len(set(c['work_keys'])),3)
        for k in ('production_units','supplier_units','support_units','capacity_units'):self.assertEqual(c[k],3)
        self.assertNotIn('authorized_digest',c)
        self.assertNotIn('price',c)
    def test_readonly_bounded_dates(self):
        prior=copy.deepcopy(self.raw);produce(self.raw);self.assertEqual(prior,self.raw)
        bad=copy.deepcopy(self.raw);bad['payments'][0]['received_date']='2026-11-01';bad['source_sha256']=digest(source_material(bad))
        with self.assertRaisesRegex(ValueError,'PAYMENT_PERIOD'):validate_input(bad)

if __name__=='__main__':unittest.main()
