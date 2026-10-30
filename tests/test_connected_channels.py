import copy
import json
import unittest
from connected_enterprise.channels import ChannelBook,default_contracts,validate_contracts


class ConnectedChannelTests(unittest.TestCase):
    def setUp(self):
        self.contracts=default_contracts()
        for terms in self.contracts.values():
            terms.update(activation_reliability_bps=10000,realization_bps=10000)
        self.prospects=[{'id':f'customer-{i:02d}'} for i in range(24)]

    def test_lead_time_expiry_and_no_free_orders(self):
        book=ChannelBook(5,self.contracts)
        receipt=book.purchase('pilot',2,'funded-plan')
        self.assertEqual(receipt['invoice_microUSD'],6_250_000)
        self.assertEqual(book.expose(3,self.prospects),[])
        rows=book.expose(4,self.prospects)
        self.assertTrue(rows)
        self.assertTrue(all(set(r)=={'customer_id','source_plan_id','contract_id','exposure_id'} for r in rows))
        self.assertFalse(any(r['customer_id'] in {p['id'] for p in self.prospects[:4]} for r in rows))
        self.assertEqual(book.expose(receipt['expiry_day'],self.prospects),[])
        self.assertEqual(book.export()['instances']['funded-plan']['state'],'EXPIRED')

    def test_same_day_idempotent_and_population_binding(self):
        book=ChannelBook(5,self.contracts)
        receipt=book.purchase('pilot',0,'plan')
        rows=book.expose(2,self.prospects)
        state=book.export()
        self.assertEqual(book.expose(2,self.prospects),rows)
        self.assertEqual(book.export(),state)
        self.assertEqual(book.purchase('pilot',0,'plan'),receipt)
        with self.assertRaises(ValueError):book.expose(2,self.prospects[:-1])
        with self.assertRaises(ValueError):book.purchase('extended',0,'plan')

    def test_overlap_deduplicates_and_fatigue_limits_contact(self):
        contracts=copy.deepcopy(self.contracts)
        for terms in contracts.values():terms.update(overlap_bps=10000,slots_per_day=20,contact_cooldown_days=2,max_contacts_per_customer=2)
        book=ChannelBook(10,contracts)
        book.purchase('pilot',0,'p1');book.purchase('extended',0,'p2')
        for day in range(3,24):
            rows=book.expose(day,self.prospects)
            self.assertEqual(len(rows),len({r['customer_id'] for r in rows}))
        state=book.export()
        self.assertTrue(all(len(h)<=2 for h in state['contacts'].values()))
        self.assertGreater(sum(i['unused_slots'] for i in state['instances'].values()),0)
        self.assertTrue(all(h[1]['day']-h[0]['day']>=2 for h in state['contacts'].values() if len(h)==2))

    def test_failed_activation_is_credit_receivable_not_cash(self):
        self.contracts['pilot'].update(activation_reliability_bps=0,prepaid_retry_attempts=0,failure_credit_bps=5000)
        book=ChannelBook(1,self.contracts)
        book.purchase('pilot',0,'bad-plan')
        self.assertEqual(book.expose(2,self.prospects),[])
        state=book.export()
        instance=state['instances']['bad-plan']
        self.assertEqual(instance['state'],'FAILED')
        self.assertEqual(instance['failure_credit_due_microUSD'],3_000_000)
        self.assertEqual(state['events'][-1]['credit_status'],'RECEIVABLE_NOT_CASH')
        self.assertNotIn('cash',state)

    def test_prepaid_retry_is_bounded_with_original_expiry(self):
        self.contracts['pilot'].update(activation_reliability_bps=0)
        book=ChannelBook(1,self.contracts);receipt=book.purchase('pilot',0,'p1')
        self.assertEqual(book.expose(2,self.prospects),[])
        self.assertEqual(book.export()['instances']['p1']['state'],'RETRY_SCHEDULED')
        self.assertEqual(book.expose(3,self.prospects),[])
        instance=book.export()['instances']['p1']
        self.assertEqual(instance['state'],'FAILED')
        self.assertEqual(instance['activation_attempts'],2)
        self.assertEqual(instance['expiry_day'],receipt['expiry_day'])
        self.assertEqual(instance['failure_credit_due_microUSD'],0)

    def test_slot_metrics_charge_realized_and_unused_capacity(self):
        self.contracts['pilot']['realization_bps']=0
        book=ChannelBook(1,self.contracts);book.purchase('pilot',0,'p1')
        book.expose(2,self.prospects)
        metrics=book.export()['exposures_by_day']['2']
        self.assertEqual(metrics['attempted_slots'],2)
        self.assertEqual(metrics['realized_exposures'],0)
        self.assertEqual(metrics['unused_slots'],2)

    def test_restart_matches_uninterrupted_exposures(self):
        first=ChannelBook(888,self.contracts);first.purchase('pilot',0,'p1')
        for day in range(10):first.expose(day,self.prospects)
        restored=ChannelBook(888,self.contracts,json.loads(json.dumps(first.export())))
        for day in range(10,30):
            self.assertEqual(first.expose(day,self.prospects),restored.expose(day,self.prospects))
        self.assertEqual(first.export(),restored.export())
        with self.assertRaises(ValueError):ChannelBook(889,self.contracts,first.export())
        changed=copy.deepcopy(self.contracts);changed['pilot']['price_microUSD']+=1
        with self.assertRaises(ValueError):ChannelBook(888,changed,first.export())

    def test_renewal_requires_new_funded_plan_and_supplier_limit(self):
        book=ChannelBook(17,self.contracts)
        book.purchase('pilot',0,'p1');book.purchase('pilot',1,'p2')
        with self.assertRaises(ValueError):book.purchase('pilot',2,'p3')
        book.expose(24,self.prospects)
        renewed=book.purchase('pilot',24,'p3')
        self.assertEqual(renewed['activation_day'],26)
        self.assertEqual(len(book.export()['instances']),3)

    def test_strict_terms_and_negative_clock(self):
        for key,value in [('realization_bps',10001),('price_microUSD',False),('duration_days',0),('slots_per_day',0)]:
            altered=copy.deepcopy(self.contracts);altered['pilot'][key]=value
            with self.assertRaises(ValueError):validate_contracts(altered)
        book=ChannelBook(1,self.contracts)
        with self.assertRaises(ValueError):book.purchase('pilot',-1,'p')
        book.expose(4,self.prospects)
        with self.assertRaises(ValueError):book.expose(3,self.prospects)
        with self.assertRaises(ValueError):book.expose(5,[{'id':'same'},{'id':'same'}])


if __name__=='__main__':unittest.main()
