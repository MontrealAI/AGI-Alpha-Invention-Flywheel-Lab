import copy,unittest
from experiments.retroactive_market062 import construct,streams,request,protocol,deal_decision,MICRO
from experiments.retroactive_market062_verify import check_measurement

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

if __name__=='__main__':unittest.main()
