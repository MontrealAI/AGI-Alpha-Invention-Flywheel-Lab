"""Pure proposal tests: no accounts or economic campaign."""
import unittest
from copy import deepcopy
from unittest.mock import patch
from growth067.registration import design
from growth066 import policy as old
from growth067.policy import *

class RenewalTests(unittest.TestCase):
    def setUp(self):
        self.reg=design();self.reg['price_candidates_usd']=[25]
        self.w={**self.reg['worlds']['central'],'reachable_firms':1280,'renewal_affinity_usd':0,'reactivation_cooldown_months':2,'contact_optout_probability':.1,'backlog_expiry_months':3}
        self.cash={'available':10**12,'unrestrictedEarned':10**12,'profit':10**12,'tailReserve':0,'custodyReserve':0,'workingCapital':0}
    def runp(self,s=None,**kwargs):return propose(initial_state() if s is None else s,self.cash,self.w,self.reg,123,10,10**12,**kwargs)
    def test_population_and_paid_recontacts(self):
        s=initial_state();total=repeat=0
        for _ in range(24):
            p=self.runp(s);s=p['state_after'];self.assertEqual(population_total(s),1280)
            self.assertEqual(p['costs_microUSD']['acquisition'],p['lead_attempts']*p['lead_unit_microUSD'])
            total+=p['lead_attempts'];repeat+=p['repeat_units']
        self.assertGreater(total,1280);self.assertGreater(repeat,0);self.assertEqual(total,s['lead_attempts_total'])
    def test_cooldown_and_optout(self):
        self.w.update(lead_activation=0,contact_optout_probability=0)
        p=self.runp();q=self.runp(p['state_after']);r=self.runp(q['state_after'])
        self.assertEqual(p['lead_attempts'],1280);self.assertEqual(q['lead_attempts'],0);self.assertEqual(r['lead_attempts'],1280)
        self.w['contact_optout_probability']=1;p=self.runp();s=p['state_after']
        self.assertEqual(s['opted_out'],1280)
        for _ in range(4):p=self.runp(s);s=p['state_after'];self.assertEqual(p['lead_attempts'],0)
    def waiting(self):
        s=self.runp()['state_after'];v=[10]*BINS
        s.update(active=0,active_bins=zero(),untouched=0,untouched_bins=zero(),inactive=0,inactive_bins=zero(),opted_out=0,opted_out_bins=zero(),cooldown=[],pending_leads=[cohort(v,active=1,expires=2,willing=True,repeat=False,quote=25)])
        return s
    def test_backlog_expiry(self):
        s=self.waiting();self.w['supplier_outage_probability']=1
        p=self.runp(s,grow=False);q=self.runp(p['state_after'],grow=False);r=self.runp(q['state_after'],grow=False)
        self.assertEqual(sum(c['count'] for c in q['state_after']['pending_leads']),1280)
        self.assertEqual(r['state_after']['expired_leads'],1280)
    def test_persistent_unchanged_and_switching(self):
        self.w.update(relationship_failure_probability=0,quality_probability=1,supplier_outage_probability=0,lead_activation=1,contact_optout_probability=0)
        s=self.runp()['state_after'];s['capacity']=5000;p=self.runp(s);s=p['state_after'];active=s['active']
        q=self.runp(s,grow=False)
        self.assertEqual(q['repeat_units'],active)
        stable=q['state_after']
        for _ in range(7):
            unchanged=self.runp(stable);stable=unchanged['state_after']
            self.assertEqual(stable['active'],active)
        self.w['rival_price_usd']=0
        r=self.runp(s,grow=False);self.assertLess(r['repeat_units'],active)
        # Stable reactivation never changes a high-quantile reject into willing.
        self.assertEqual(willing([1]*BINS,.25),willing([1]*BINS,.25))
        self.assertEqual(sum(willing([0]*96+[1]*32,.25)),0)
    def test_no_double_churn_or_affinity_bonus(self):
        s=self.runp()['state_after'];p=self.runp(s)
        self.w.update(monthly_churn=1,renewal_affinity_usd=1000)
        self.assertEqual(p,self.runp(s))
    def test_budget_no_future_outcomes(self):
        s=self.runp()['state_after'];a=self.runp(s)
        with patch('growth067.policy.outcomes',lambda n,*args:{'attempted':n,'quality_accepted':0,'quality_failed':n,'collected_units':0,'uncollected_units':0}):b=self.runp(s)
        for key in ['funding','lead_attempts','capacity_added','chosen_orders','costs_microUSD']:self.assertEqual(a[key],b[key])
    def test_liquidity_provision_and_aggressive_control(self):
        self.cash['available']=90_000_000_000;self.w['reachable_firms']=1_000_000
        a=self.runp();self.w['allocation_mode']='aggressive';b=self.runp()
        self.assertGreater(a['funding']['downstream_provision_microUSD'],0)
        self.assertLess(a['lead_attempts'],b['lead_attempts'])
        self.assertNotIn('provision',a['costs_microUSD'])
    def test_price_uses_current_cohorts_and_rival(self):
        prices=[15,25,40,60,80,100,150]
        def q(w,active):return choose_current_price(prices,10,w,1,zero(),active,[],10000)['selected']['price_usd']
        loyal=[10]*16+[0]*112
        self.assertNotEqual(q(self.w,loyal),q(self.w,[10]*BINS))
        self.assertNotEqual(q(self.w,loyal),q({**self.w,'rival_price_usd':0},loyal))
    def test_legacy_exact(self):
        self.assertEqual(self.runp(renewal_mode='legacy'),old.propose(initial_state(),self.cash,self.w,self.reg,123,10,10**12))

if __name__=='__main__':unittest.main()
