"""Engineering fixtures only; these mocks establish no commercial result."""
import copy
import unittest
from omega import expansion_market as m

class SpyBridge:
    def __init__(self,available=10_000_000,allow=True):
        self.available=available;self.hour=0;self.allow=allow;self.spends={};self.orders={};self.calls=[]
    def snapshot(self):
        return {'available_cents':self.available,'cash_cents':self.available,'profit_cents':0,
                'unrestricted_earned_cents':0,'hour':self.hour}
    def advance(self,hour):
        if hour<self.hour:raise ValueError('TIME_REVERSED')
        self.hour=hour
    def spend(self,event_id,cents,hour,category,**kwargs):
        self.advance(hour);self.calls.append(('spend',event_id))
        if event_id in self.spends:return self.spends[event_id]
        ok=self.allow and cents<=self.available
        if ok:self.available-=cents
        self.spends[event_id]=ok;return ok
    def deliver(self,order):
        self.advance(order['hour']);self.calls.append(('deliver',order['id']))
        if order['id'] not in self.orders:
            collected=order['pay'] and order['accept'] and order['delivery_ok']
            self.orders[order['id']]={'collected':collected,'status':'released' if collected else 'refunded',
                                     'contribution_cents':order['price_cents']-100 if collected else -100}
        return self.orders[order['id']]
    def order_receipt(self,order_id):return self.orders[order_id]

class ExpansionMarketTests(unittest.TestCase):
    def public(self):
        r=m.MarketRunner(m.worlds()['capability_gap'])
        return m.public_state(r.state,SpyBridge().snapshot())
    def test_current_rival_quote_changes_price_without_future_or_decline_inference(self):
        p=self.public();p['built']=True
        self.assertEqual(m.decide(p)['price_cents'],29900)
        p['rival_quote_cents']=19900
        self.assertEqual(m.decide(p)['price_cents'],14900)
        self.assertEqual(m.decide(p,'simple')['price_cents'],29900)
        self.assertEqual(m.decide(p,'ordinary_reuse')['price_cents'],14900)
        p['rival_quote_cents']=10000
        self.assertEqual(m.decide(p)['kind'],'wait')
    def test_refusals_alone_do_not_change_posted_price(self):
        p=self.public();p.update(built=True,observations=[{'contacts':100,'orders':1,'declines':99,'net_cents':1,'size':100,'settled':True}])
        self.assertEqual(m.decide(p)['price_cents'],29900)
    def test_invalid_probability_and_seed_overlap_refused(self):
        for weights in ({'x':-1,'y':2},{'x':'nan'},{'x':'1/3'},{'x':'2/0'}):
            with self.subTest(weights=weights),self.assertRaises(ValueError):m.validate_prior(weights)
        self.assertEqual(sum(m.validate_prior({'a':'1/3','b':'2/3'})),1)
        with self.assertRaises(ValueError):m.config(confirmation_seeds=[17])
    def test_hidden_information_rejected(self):
        for key in ('world','seed','private_value','future_collection'):
            with self.subTest(key=key),self.assertRaises(ValueError):m.decide({**self.public(),key:1})
    def test_independent_budget_and_nonpurchase(self):
        w=m.worlds()['capability_gap']
        for i in range(30):
            b=f'buyer-{i}'
            choices=[m.buyer_choice(w,17,b,0,p,False) for p in m.PRICES]
            self.assertEqual(len({x['budget_cents'] for x in choices}),1)
            for x in choices:
                if x['provider']=='us':self.assertLessEqual(x['price_cents']+x['adoption_cents'],x['budget_cents'])
        w['need_bps']=0
        self.assertTrue(all(m.buyer_choice(w,17,str(i),0,14900,False)['provider']=='decline' for i in range(20)))
    def test_nonentry_never_forces_cost(self):
        b=SpyBridge();r=m.MarketRunner(m.worlds()['capability_gap'],'nonentry',17,m.config(horizon_days=5))
        r.run(b)
        self.assertEqual(b.spends,{})
        self.assertEqual(b.orders,{})
    def test_earned_profit_does_not_replace_available_cash(self):
        p=self.public();p.update(profit_cents=1_000_000,earned_cents=0,available_cents=0)
        self.assertEqual(m.decide(p)['kind'],'wait')
        p.update(available_cents=500000,earned_cents=1)
        self.assertEqual(m.decide(p)['kind'],'build')
    def test_no_spend_no_reach_or_order(self):
        b=SpyBridge(allow=False);r=m.MarketRunner(m.worlds()['capability_gap'],seed=17,settings=m.config(horizon_days=3))
        r.run(b)
        self.assertFalse(r.state['campaigns']);self.assertFalse(b.orders)
    def test_paid_acquisition_can_expand_beyond_initial_cohort(self):
        p=self.public();p.update(built=True,last_size=8,observations=[{'contacts':8,'orders':3,'declines':5,'net_cents':30000,'size':8,'settled':True}])
        action=m.decide(p)
        self.assertEqual(action['kind'],'campaign');self.assertGreater(action['size'],8)
        p['last_size']=10**9;p['available_cents']=10**15
        self.assertGreater(m.decide(p)['size'],10**6)
    def test_observed_loss_stops_commerce(self):
        p=self.public();p.update(built=True,observations=[{'contacts':8,'orders':0,'declines':8,'net_cents':-4500,'size':8,'settled':True}]*2)
        self.assertEqual(m.decide(p,'commerce_only')['kind'],'wait')
        self.assertEqual(m.decide(p,'joint')['kind'],'survey')
    def test_uncollected_results_are_not_negative_demand_evidence(self):
        p=self.public();p.update(built=True,observations=[{'contacts':8,'orders':0,'declines':0,'net_cents':-4500,'size':8,'settled':False}])
        self.assertEqual(m.decide(p,'joint')['kind'],'campaign')
    def test_no_invented_upgrade_cost_or_reuse_bonus(self):
        p=self.public();p.update(built=True,observations=[{'contacts':8,'orders':7,'declines':1,'net_cents':80000,'size':8,'settled':True}])
        self.assertEqual(m.decide(p,'joint'),m.decide(p,'ordinary_reuse'))
        self.assertNotEqual(m.decide(p,'joint')['kind'],'enhance')
        self.assertNotEqual(m.decide(p,'no_inheritance')['kind'],'enhance')
    def test_campaign_draw_independent_of_policy_name(self):
        w=m.worlds()['capability_gap'];a=m.MarketRunner(w,'joint',17);b=m.MarketRunner(w,'ordinary_reuse',17)
        campaign={'id':'joint-0','size':100,'day':0,'channel':0,'cost_cents':50500}
        x,_=a._contacts(campaign);y,_=b._contacts({**campaign,'id':'ordinary-0'})
        self.assertEqual(x,y)
    def test_overlap_cannot_be_fresh_demand(self):
        r=m.MarketRunner(m.worlds()['capability_gap'],seed=29)
        c={'id':'c1','size':100,'day':0,'channel':0,'cost_cents':50500}
        x,_=r._contacts(c);r.state['contacted']=[p['customer_id'] for p in x]
        y,_=r._contacts({**c,'id':'c2'})
        self.assertEqual(y,[])
    def test_qualified_alternative_channel_can_receive_a_paid_pilot(self):
        p=self.public();p.update(built=True,channel=0,survey={'qualified':10,'sample_size':20,'paid_day':1},
            observations=[{'contacts':8,'orders':0,'declines':8,'net_cents':-4500,'size':8,'settled':True,'channel':0}])
        self.assertEqual(m.decide(p)['kind'],'pivot')
        p['channel']=1
        self.assertEqual(m.decide(p)['kind'],'campaign')
    def test_campaign_cadence_does_not_change_same_day_market(self):
        w=m.worlds()['capability_gap'];a=m.MarketRunner(w,seed=17,settings=m.config(cadence_days=7));b=m.MarketRunner(w,seed=17)
        c={'id':'c','size':50,'day':28,'channel':0,'cost_cents':25500}
        self.assertEqual(a._contacts(c),b._contacts(c))
    def test_hosting_charged_once_per_day_and_clock_monotone(self):
        b=SpyBridge();r=m.MarketRunner(m.worlds()['capability_gap'],seed=17,settings=m.config(horizon_days=4))
        r.run(b)
        self.assertEqual(sum(k=='hosting-day-0' for k in b.spends),1)
        self.assertTrue(r.state['completed'])
        self.assertLessEqual(b.hour,4*24-1)
    def test_intent_precedes_financial_action(self):
        b=SpyBridge();saved=[];r=m.MarketRunner(m.worlds()['capability_gap'],seed=17)
        def save(s):
            saved.append(s)
            if s['pending'] and not b.calls:self.assertEqual(s['pending']['action']['kind'],'build')
        r.step(b,save)
        self.assertIsNotNone(saved[0]['pending'])
        self.assertIsNone(saved[-1]['pending'])
    def test_zero_capacity_cannot_grant_reach(self):
        # There is no capacity argument granting a customer. Unfunded acquisition cannot expose anyone.
        b=SpyBridge(available=0);r=m.MarketRunner(m.worlds()['capability_gap'],seed=17,settings=m.config(horizon_days=2))
        r.state['built']=True;r.state['enhanced']=True;r.run(b)
        self.assertFalse(r.state['contacted']);self.assertFalse(b.orders)

if __name__=='__main__':unittest.main()
