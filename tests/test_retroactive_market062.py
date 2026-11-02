import copy,unittest
from experiments.retroactive_market062 import construct,streams,request,protocol,deal_decision,MICRO
from experiments.retroactive_market062_verify import check_measurement,check_native_claim_binding,check_public_economic_claims

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
        before_costs={'shared-'+k:v for k,v in p['fixed_shared'].items()}
        before_costs.update({'market062-'+buyer+'-'+k:v
                             for buyer in 'AB' for k,v in p['per_order'].items()})
        before_costs['first-stage-profit-tax']=p['stage1_tax_microUSD']
        after_costs={'market062-C-'+k:v for k,v in p['per_order'].items()}
        after_costs['second-stage-profit-tax']=p['stage2_tax_microUSD']
        native={'ledger':{'config':{'contract':'market062-shared'},
                 'orders':[{'id':'market062-'+buyer,'buyer':buyer,'state':'released',
                            'price':str(1500*MICRO)} for buyer in 'ABC'],
                 'actions':([{'op':'cost','args':{'id':k,'amount':v}}
                             for k,v in before_costs.items()] +
                            [{'op':'offer','args':{'id':'market062-'+buyer,'buyer':buyer,
                            'job_id':'evidence_matrix-market062-'+buyer}} for buyer in 'AB'] +
                            [{'op':'reserve','args':{'id':receipt['plan_id']},'before':before},
                             {'op':'finish','args':{'id':receipt['plan_id']}},
                             {'op':'offer','args':{'id':'market062-C','buyer':'C',
                              'job_id':'evidence_matrix-market062-C'}}] +
                            [{'op':'cost','args':{'id':k,'amount':v}}
                             for k,v in after_costs.items()])},
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

    def test_valid_but_wrong_delivered_service_is_not_sensor_sale(self):
        # Every job ID here names a valid accepted service, but paying for
        # A's measurement cannot support a report about buyer C's output.
        p,m,n,r=self.fixture()
        next(a for a in n['ledger']['actions'] if a.get('op')=='offer'
             and a['args']['id']=='market062-C')['args']['job_id']='evidence_matrix-market062-A'
        with self.assertRaisesRegex(ValueError,'NATIVE_OFFER_DELIVERABLE_IDENTITY_MISMATCH'):
            check_native_claim_binding('shared',n,r,m,p)

    def test_missing_or_swapped_offer_identity_is_not_accepted(self):
        p,m,n,r=self.fixture()
        n['ledger']['actions']=[a for a in n['ledger']['actions']
            if a.get('op')!='offer' or a['args']['id']!='market062-C']
        with self.assertRaisesRegex(ValueError,'NATIVE_OFFER_DELIVERABLE_IDENTITY_MISMATCH'):
            check_native_claim_binding('shared',n,r,m,p)
        p,m,n,r=self.fixture()
        next(a for a in n['ledger']['actions'] if a.get('op')=='offer'
             and a['args']['id']=='market062-C')['args']['buyer']='A'
        with self.assertRaisesRegex(ValueError,'NATIVE_OFFER_DELIVERABLE_IDENTITY_MISMATCH'):
            check_native_claim_binding('shared',n,r,m,p)

    def test_full_authored_cost_schedule_is_mandatory(self):
        p,m,n,r=self.fixture()
        self.assertTrue(check_native_claim_binding('shared',n,r,m,p))
        n['ledger']['actions']=[a for a in n['ledger']['actions']
            if not(a.get('op')=='cost' and a['args']['id']=='market062-C-independent_check')]
        with self.assertRaisesRegex(ValueError,'NATIVE_COMPLETE_COST_SCHEDULE_MISMATCH'):
            check_native_claim_binding('shared',n,r,m,p)
        p,m,n,r=self.fixture()
        next(a for a in n['ledger']['actions'] if a.get('op')=='cost'
             and a['args']['id']=='shared-failed_search')['args']['amount']=0
        with self.assertRaisesRegex(ValueError,'NATIVE_COMPLETE_COST_SCHEDULE_MISMATCH'):
            check_native_claim_binding('shared',n,r,m,p)

    def test_earned_spend_cannot_precede_costed_stage_one(self):
        p,m,n,r=self.fixture()
        tape=n['ledger']['actions']
        tax=next(a for a in tape if a.get('op')=='cost'
                 and a['args']['id']=='first-stage-profit-tax')
        tape.remove(tax)
        tape.append(tax)
        with self.assertRaisesRegex(ValueError,'EARNED_RESERVATION_PRE_COST_BOUNDARY'):
            check_native_claim_binding('shared',n,r,m,p)

    def test_no_bid_still_charges_unwon_prospecting(self):
        p=protocol()
        n={'ledger':{'config':{'contract':'market062-cheap_rival'},'orders':[],
                     'actions':[{'op':'cost','args':{'id':'cheap-rival-prospecting',
                                                   'amount':p['no_bid_search_microUSD']}}]}}
        r={'sales':[],'decision':{'choice':'NO_BID'},'earned_receipt':None}
        self.assertTrue(check_native_claim_binding('cheap_rival',n,r,{},p))
        n['ledger']['actions'].clear()
        with self.assertRaisesRegex(ValueError,'NATIVE_COMPLETE_COST_SCHEDULE_MISMATCH'):
            check_native_claim_binding('cheap_rival',n,r,{},p)

    def test_earnings_expense_must_precede_successor_offer(self):
        p,m,n,r=self.fixture()
        tape=n['ledger']['actions']
        successor=next(a for a in tape if a.get('op')=='offer'
                       and a['args']['id']=='market062-C')
        tape.remove(successor)
        tape.insert(2,successor)
        with self.assertRaisesRegex(ValueError,'EARNED_ADAPTER_NOT_BEFORE_SUCCESSOR_OFFER'):
            check_native_claim_binding('shared',n,r,m,p)
        p,m,n,r=self.fixture()
        n['ledger']['actions']=[a for a in n['ledger']['actions']
            if a.get('op')!='finish']
        with self.assertRaisesRegex(ValueError,'EARNED_ADAPTER_NOT_BEFORE_SUCCESSOR_OFFER'):
            check_native_claim_binding('shared',n,r,m,p)

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


class PublicEconomicScopeTests(unittest.TestCase):
    def fixture(self):
        p=protocol()
        arms={'direct':{'summary':{'profit':-1480*MICRO}},
              'shared':{'summary':{'profit':987*MICRO},'earned_receipt':{'funding':'EARNED'}},
              'cheap_rival':{'summary':{'profit':-60*MICRO},'decision':{'choice':'NO_BID'}}}
        conclusions={
            'shared_positive':True,'matched_direct_negative':True,
            'earned_funded':True,'cheap_rival_no_bid':True,
            'actual_revenue_microUSD':0,'real_demand_observed':False,
            'complete_actual_host_cost_known':False,
            'recursive_or_market_novelty_proven':False,
            'successor_output_preconstructed_for_native_registration':True,
            'causal_necessity_of_adapter_not_proven':True,
            'ordinary_pooled_rival_excluded':False}
        fixed=sum(p['fixed_shared'].values())
        per=sum(p['per_order'].values())
        sensitivity={'ten_percent_fixed_cost_overrun_stage1_profit_microUSD':
                     int(2*p['quote_microUSD']-fixed*110//100-2*per-p['stage1_tax_microUSD']),
                     'first_stage_profit_hurdle_microUSD':p['earned_only_successor_adapter_microUSD']}
        return p,{'arms':arms,'conclusions':conclusions,'sensitivity':sensitivity}

    def test_authored_scenario_scope_is_explicit(self):
        p,r=self.fixture()
        self.assertTrue(check_public_economic_claims(r,p))

    def test_fake_real_revenue_and_causal_reclassification_rejected(self):
        for name,value in [('actual_revenue_microUSD',1500*MICRO),
                           ('real_demand_observed',True),
                           ('causal_necessity_of_adapter_not_proven',False),
                           ('complete_actual_host_cost_known',True)]:
            p,r=self.fixture()
            r['conclusions'][name]=value
            with self.assertRaisesRegex(ValueError,'PUBLIC_ECONOMIC_SCOPE_OR_CLAIM_TAMPERED'):
                check_public_economic_claims(r,p)

    def test_invented_profit_sensitivity_rejected(self):
        p,r=self.fixture()
        r['sensitivity']['ten_percent_fixed_cost_overrun_stage1_profit_microUSD']=200*MICRO
        with self.assertRaisesRegex(ValueError,'PUBLIC_ECONOMIC_SENSITIVITY_TAMPERED'):
            check_public_economic_claims(r,p)


class CompetentOrdinaryPoolingControlTests(unittest.TestCase):
    def test_source_matched_pool_without_adapter_can_deliver_same_successor(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from connected_enterprise.finance import JournalAccount
        from experiments.retroactive_market062 import ROOT,make_manifest,_pay,_deliver
        p=protocol()
        with TemporaryDirectory(prefix='.market062-ordinary-pooling-',dir=ROOT) as directory:
            output=Path(directory)
            manifest,measurement=make_manifest(ROOT,output,list('ABC'),streams())
            self.assertEqual(set(measurement),set('ABC'))
            account=JournalAccount(ROOT,manifest,output/'ordinary-pooled.sqlite',
                                   opening=p['opening_microUSD'],working=0,
                                   contract='market062-ordinary-pooling-control')
            try:
                for name,amount in p['fixed_shared'].items():
                    account.cost('shared-'+name,amount,0)
                orders={name:_pay(account,name,'evidence_matrix-market062-'+name,
                                  p['quote_microUSD'],0) for name in 'AB'}
                for day,name in enumerate('AB',1):
                    _deliver(account,orders[name],name,p,day)
                account.cost('first-stage-profit-tax',p['stage1_tax_microUSD'],2)
                self.assertEqual(account.snapshot()['summary']['profit'],153*MICRO)
                successor=_pay(account,'C','evidence_matrix-market062-C',
                               p['quote_microUSD'],4)
                _deliver(account,successor,'C',p,4)
                account.cost('second-stage-profit-tax',p['stage2_tax_microUSD'],4)
                exported=account.export()
                audit=account.audit()
                summary=account.snapshot()['summary']
            finally:
                account.close()
            self.assertTrue(audit['accepted'])
            self.assertEqual([o['state'] for o in exported['ledger']['orders']],
                             ['released','released','released'])
            self.assertEqual([o['id'] for o in exported['ledger']['orders']],
                             ['market062-A','market062-B','market062-C'])
            self.assertFalse([e for e in exported['connected_journal']['entries']
                              if e.get('key')=='spend:third-sensor-adapter'])
            expected=(3*p['quote_microUSD']-sum(p['fixed_shared'].values())
                      -3*sum(p['per_order'].values())
                      -p['stage1_tax_microUSD']-p['stage2_tax_microUSD'])
            self.assertEqual(expected,1107*MICRO)
            self.assertEqual(summary['profit'],expected)
            self.assertEqual(summary['collections'],3*p['quote_microUSD'])
            self.assertEqual(summary['profit']-987*MICRO,
                             p['earned_only_successor_adapter_microUSD'])

if __name__=='__main__':unittest.main()
