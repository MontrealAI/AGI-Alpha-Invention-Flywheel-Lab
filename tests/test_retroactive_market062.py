import copy,unittest
from experiments.retroactive_market062 import construct,streams,request,protocol,deal_decision,MICRO
from experiments.retroactive_market062_verify import check_measurement,check_native_claim_binding

class Market062Tests(unittest.TestCase):
    def test_instrument_realized_and_independently_checked(self):
        data=streams()
        for person in 'ABC':
            self.assertTrue(check_measurement(request(person),data,construct(request(person),data)))

    def test_duplicate_or_missing_source_unknown(self):
        r=construct(request('A'),streams());self.assertEqual(r['unknown_count'],2)
        self.assertEqual(r['measurements'][3]['status'],'UNKNOWN')
        self.assertEqual(r['measurements'][5]['status'],'UNKNOWN')

    def test_question_changes_measurement_not_historical_data(self):
        a,b=construct(request('A'),streams()),construct(request('B'),streams())
        self.assertNotEqual(a['event_count'],b['event_count'])
        self.assertEqual(a['source_sha256'],b['source_sha256'])

    def test_instrument_counterfeit_fails(self):
        a=construct(request('A'),streams());a['event_count']+=1
        with self.assertRaisesRegex(ValueError,'EVENT_COUNT'):
            check_measurement(request('A'),streams(),a)

    def test_unsupported_event_fails(self):
        a=construct(request('A'),streams());a['measurements'][3]['status']='EVENT'
        with self.assertRaisesRegex(ValueError,'CONTRADICTS'):
            check_measurement(request('A'),streams(),a)

    def test_voluntary_game_exits(self):
        p=protocol();self.assertEqual(deal_decision(p,['A','B'])['choice'],'SHARED_CONTRACT')
        self.assertEqual(deal_decision(p,['A'])['choice'],'NO_BID')
        self.assertEqual(deal_decision(p,['A','B'],rival_price=p['cheap_rival_microUSD'])['choice'],'NO_BID')
        for b in 'AB':
            q=copy.deepcopy(p);q['buyers'][b]['valuation_microUSD']=p['quote_microUSD']-1
            self.assertEqual(deal_decision(q,['A','B'])['choice'],'NO_BID')

    def test_economic_arithmetic_prefrozen(self):
        p=protocol();fixed=sum(p['fixed_shared'].values());per=sum(p['per_order'].values())
        two=2*p['quote_microUSD']-fixed-2*per-p['stage1_tax_microUSD']
        final=3*p['quote_microUSD']-fixed-3*per-p['earned_only_successor_adapter_microUSD']-p['stage1_tax_microUSD']-p['stage2_tax_microUSD']
        direct=2*p['quote_microUSD']-2*p['fixed_per_independent_buyer']-2*per-p['fixed_shared']['failed_search']-p['fixed_shared']['support_and_maintenance']
        self.assertEqual((two,final,direct),(153*MICRO,987*MICRO,-1480*MICRO))
        self.assertGreater(two,p['earned_only_successor_adapter_microUSD'])


class NativePublicClaimBindingTests(unittest.TestCase):
    @staticmethod
    def fixture():
        p=protocol()
        measurement={buyer:{'sha256':buyer} for buyer in 'ABC'}
        before={'cash':100153*MICRO,'profit':153*MICRO,'collections':3000*MICRO,
                'expenses':2847*MICRO,'available':100033*MICRO,'unrestrictedEarned':153*MICRO}
        receipt={'funding':'EARNED','amount':120*MICRO,'plan_id':'native-adapter-plan'}
        request={'operation':'spend','id':'third-sensor-adapter',
                 'kind':'new_archival_signal_instrument','amount':120*MICRO,'day':3,
                 'work':{'source_measurement':['A','B'],'new_domain':'leakage-anomaly',
                         'new_archives':['flow','pressure'],'expected_successor':'C'},
                 'expected_net':834*MICRO,'allow_seed':False}
        native={'ledger':{'config':{'contract':'market062-shared'},
                 'orders':[{'id':'market062-'+buyer,'buyer':buyer,'state':'released',
                            'price':1500*MICRO} for buyer in 'ABC'],
                 'actions':[{'op':'reserve','args':{'id':receipt['plan_id']},'before':before}]},
                'connected_journal':{'entries':[{'key':'spend:third-sensor-adapter',
                     'status':'COMPLETE','funding':'EARNED','request':request,'receipt':receipt}]}}
        reported={'sales':[{'id':'market062-'+buyer,'status':'ACCEPTED_AND_COLLECTED',
                  'native_collection_microUSD':1500*MICRO,'artifact':measurement[buyer]}
                  for buyer in 'ABC'],'decision':{'choice':'SHARED_CONTRACT'},
                  'earned_receipt':copy.deepcopy(receipt),'after_two':copy.deepcopy(before)}
        return p,measurement,native,reported

    def test_native_receipt_and_sales_are_bound(self):
        p,m,n,r=self.fixture()
        self.assertTrue(check_native_claim_binding('shared',n,r,m,p))

    def test_advertised_adapter_receipt_cannot_be_forged(self):
        p,m,n,r=self.fixture()
        r['earned_receipt']['amount']=1
        with self.assertRaisesRegex(ValueError,'NATIVE_EARNED_ADAPTER_RECEIPT_UNBOUND'):
            check_native_claim_binding('shared',n,r,m,p)
        p,m,n,r=self.fixture()
        n['connected_journal']['entries'][0]['funding']='SEED'
        with self.assertRaisesRegex(ValueError,'NATIVE_EARNED_ADAPTER_RECEIPT_UNBOUND'):
            check_native_claim_binding('shared',n,r,m,p)

    def test_claimed_successor_requires_native_paid_order(self):
        p,m,n,r=self.fixture()
        n['ledger']['orders'][-1]['state']='refunded'
        with self.assertRaisesRegex(ValueError,'NATIVE_SALE_REPORT_NOT_SUPPORTED_BY_LEDGER'):
            check_native_claim_binding('shared',n,r,m,p)
        p,m,n,r=self.fixture()
        r['sales'][-1]['native_collection_microUSD']=999*MICRO
        with self.assertRaisesRegex(ValueError,'NATIVE_SALE_REPORT_NOT_SUPPORTED_BY_LEDGER'):
            check_native_claim_binding('shared',n,r,m,p)

    def test_preinvestment_earned_profit_must_equal_native_prefix(self):
        p,m,n,r=self.fixture()
        r['after_two']['profit']+=MICRO
        with self.assertRaisesRegex(ValueError,'NATIVE_EARNINGS_PREFIX_NOT_BOUND'):
            check_native_claim_binding('shared',n,r,m,p)

if __name__=='__main__':unittest.main()
