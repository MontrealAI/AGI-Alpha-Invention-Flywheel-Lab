"""Fresh temporary UNIT TEST accounts; never the economic campaign."""
from pathlib import Path
import copy
import shutil
import tempfile
import unittest
from commercial.ledger import digest
from commercial.terms_exact_v2 import prospective_terms
from connected_enterprise.finance import source_paths_for_manifest
from growth067.native import Native
from growth067 import service,quality,producer

ROOT=Path(__file__).resolve().parents[1]
MICRO=1_000_000
FIELDS=('cash','profit','revenue','expenses','collections','expensePaid','payables',
        'custodyRestricted','custodyReserve','tailReserve','workingCapital','available',
        'unrestrictedEarned','reservedInvestment','recoveryIncome','strictEarnedControl',
        'equityProtectionBacking','earnedProtectionBacking','netEarnedAfterIncurredObligations',
        'conditionalEarned','investmentStopped')

class NativeDifferentialTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='growth067-unit-only-')
        self.root=Path(self.temp.name)/'source';self.root.mkdir()
        for name in source_paths_for_manifest({'schema':service.SCHEMA}):
            source=ROOT/name;target=self.root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
        self.books=[]
    def tearDown(self):
        for book in self.books:book.close()
        self.temp.cleanup()
    def account(self,name,units):
        manifest=service.manifest(self.root,name,units)
        # Homogeneous actual-template class for an exact batching comparison.
        for job in manifest['jobs']:job['request']['actual_seed']=quality.HOLDOUT_SEEDS[0]
        service.load_contracts(self.root,manifest)
        book=Native(self.root,manifest,Path(self.temp.name)/(name+'.json'),1000*MICRO)
        self.books.append(book);return book
    def artifact(self,book,index,count):
        request=book.manifest['jobs'][index]['request']
        packet=quality.public_packet(request['actual_seed'])
        return {'schema':'growth067/bulk-delivery/v1','request_sha256':digest(request),
                'actual_output':producer.reconcile(packet),'modeled_fulfillment_count':count,
                'actual_template_count':1,'empirical_per_unit_acceptance':False,
                'market_receipt':{'production_capacity':count,'chosen_orders':count,'quality_accepted':count,'collected_units':count}}
    def offer_with_nonzero_terms_fee(self,book,ident,job,quantity,hour=1,collection=30,maturity=80):
        price=quantity*20*MICRO
        terms=prospective_terms(ident,price,maturity,collection,exposure=quantity*(20*MICRO+200_000),
                                residual=quantity*MICRO,fee=quantity*300_000)
        api=book.book
        api.execute('wallet',{'buyer':ident,'amount':price},hour)
        api.execute('register_terms',{'id':ident+'-terms','terms':terms},hour)
        api.execute('offer',{'id':ident,'buyer':ident,'price':price,'job_id':job,'deadline':collection+24,'terms_id':ident+'-terms'},hour)
        for event in ('consent','fund'):api.execute('event',{'id':ident,'action':event,'event_id':ident+'-'+event},hour)
    def equal(self,bulk,units,label):
        a,b=bulk.summary(),units.summary()
        for field in FIELDS:
            with self.subTest(stage=label,field=field):self.assertEqual(a[field],b[field])
    def test_three_unit_bulk_equals_unrolled_at_every_common_event_boundary(self):
        n=3;bulk=self.account('bulk',1);units=self.account('units',n)
        bulk.spend('setup',n*2*MICRO,0,{'unit_test':True},0,seed=True)
        for i in range(n):units.spend('setup'+str(i),2*MICRO,0,{'unit_test':True},0,seed=True)
        self.equal(bulk,units,'prepaid production')
        self.offer_with_nonzero_terms_fee(bulk,'b','bulk-m0',n)
        for i in range(n):self.offer_with_nonzero_terms_fee(units,'u'+str(i),'units-m'+str(i),1)
        self.equal(bulk,units,'funded custody with multiplied fees')
        bulk.prepare('b','bulk-m0',self.artifact(bulk,0,n),2)
        for i in range(n):units.prepare('u'+str(i),'units-m'+str(i),self.artifact(units,i,1),2)
        self.equal(bulk,units,'accepted but uncollected')
        # Delayed collections are unavailable for earned-funded investment.
        before=digest(bulk.export())
        self.assertIsNone(bulk.spend('too-early',MICRO,3,{'unit_test':True},MICRO,seed=False))
        self.assertEqual(before,digest(bulk.export()))
        bulk.release('b',30)
        for i in range(n):units.release('u'+str(i),30)
        self.equal(bulk,units,'collected with full exposure')
        self.assertEqual(bulk.summary()['tailReserve'],n*(20*MICRO+200_000))
        bulk.advance(80);units.advance(80)
        self.equal(bulk,units,'inclusive maturity boundary')
        self.assertEqual(bulk.summary()['tailReserve'],n*(20*MICRO+200_000))
        bulk.advance(81);units.advance(81)
        self.equal(bulk,units,'matured residual')
        self.assertEqual(bulk.summary()['tailReserve'],n*MICRO)
        b=bulk.spend('earned',3*MICRO,82,{'unit_test':True},MICRO,seed=False)
        u=units.spend('earned',3*MICRO,82,{'unit_test':True},MICRO,seed=False)
        self.assertEqual(b['funding'],'EARNED');self.assertEqual(u['funding'],'EARNED')
        self.equal(bulk,units,'earned reserve and finish')
        self.assertTrue(bulk.audit()['accepted']);self.assertTrue(units.audit()['accepted'])
    def test_two_unit_refund_bulk_equals_unrolled(self):
        bulk=self.account('refund-b',1);units=self.account('refund-u',2)
        self.offer_with_nonzero_terms_fee(bulk,'b','refund-b-m0',2)
        for i in range(2):self.offer_with_nonzero_terms_fee(units,'u'+str(i),'refund-u-m'+str(i),1)
        bulk.refund('b',2)
        for i in range(2):units.refund('u'+str(i),2)
        self.equal(bulk,units,'full refund retaining incurred fee')
        self.assertEqual(bulk.summary()['profit'],-600_000)
        self.assertTrue(bulk.audit()['accepted']);self.assertTrue(units.audit()['accepted'])
    def test_corrupt_template_refuses_prepare_without_native_mutation(self):
        book=self.account('corrupt',1);book.offer('b','corrupt-m0',2,20*MICRO,1,30,80,MICRO)
        payload=self.artifact(book,0,2);payload['actual_output']['reconciliation']['bridge']['closing_balance_cents']+=1
        before=digest(book.export())
        with self.assertRaisesRegex(ValueError,'BULK_DELIVERY_REJECTED'):book.prepare('b','corrupt-m0',payload,2)
        self.assertEqual(before,digest(book.export()))
        self.assertFalse((self.root/'growth067/deliveries/corrupt-m0.json').exists())
    def test_corrupt_count_inequality_refused(self):
        book=self.account('count',1);payload=self.artifact(book,0,2)
        payload['market_receipt']['quality_accepted']=1
        self.assertFalse(service.check_delivery(self.root,book.manifest,'count-m0',payload)['accepted'])

    def test_order_quantity_cannot_be_satisfied_by_smaller_artifact(self):
        book=self.account('mismatch',1)
        book.offer('b','mismatch-m0',3,20*MICRO,1,30,80,MICRO)
        payload=self.artifact(book,0,1)
        before=digest(book.export())
        with self.assertRaises(ValueError):book.prepare('b','mismatch-m0',payload,2)
        self.assertEqual(before,digest(book.export()))
    def test_bool_template_count_rejected(self):
        book=self.account('boolcount',1);payload=self.artifact(book,0,1)
        payload['actual_template_count']=True
        self.assertFalse(service.check_delivery(self.root,book.manifest,'boolcount-m0',payload)['accepted'])

    def test_candidate_cannot_invent_market_capacity(self):
        book=self.account('invented',1);payload=self.artifact(book,0,10**12)
        self.assertFalse(service.check_delivery(self.root,book.manifest,'invented-m0',payload)['accepted'])

if __name__=='__main__':unittest.main()
