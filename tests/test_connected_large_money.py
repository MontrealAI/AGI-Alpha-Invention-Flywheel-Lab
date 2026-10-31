"""Exact monetary representation controls, NOT achieved commercial scale."""
import copy,tempfile,unittest
from pathlib import Path
from commercial.ledger import amount,canonical,strict_json
from commercial.terms_exact_v2 import prospective_terms
from adaptive_enterprise.instruments import prepare_services
from adaptive_enterprise.strategies import offer_catalog,validate_offer
from connected_enterprise.finance import JournalAccount
from connected_enterprise.scale import trailing_profit
ROOT=Path(__file__).resolve().parents[1]
class LargeMoney(unittest.TestCase):
 def test_integer_validation_and_offer_terms(self):
  for n in (100_000_000_000*1_000_000+1,2**80+19):
   self.assertEqual(amount(n),n);self.assertEqual(strict_json(canonical({'amount':n}))['amount'],n)
   offer=copy.deepcopy(offer_catalog()[0]);offer.update(price_microUSD=n,upfront_cost_microUSD=n)
   self.assertEqual(validate_offer(offer)['price_microUSD'],n)
   self.assertEqual(prospective_terms('large',n,20,2,premium=n)['premium_microUSD'],n)
  for n in (-1,True,1.5,float('inf'),float('nan'),'100'):
   with self.assertRaises(ValueError):amount(n)
  with self.assertRaises(ValueError):amount(0,positive=True)
 def test_current_operating_loop_explicit_exact_versions(self):
  from connected_enterprise.engine import run_world,default_config,fresh_account_config
  from connected_enterprise.verify import audit
  from connected_enterprise.capital_lifecycle import default_policy
  with tempfile.TemporaryDirectory(prefix='.exact-operating-',dir=ROOT) as folder:
   folder=Path(folder);m=prepare_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=2610312145)
   for mode in ('exact-permanent-v2','exact-prospective-v2'):
    cfg,manifest=fresh_account_config(m,prospective_policy=default_policy() if mode=='exact-prospective-v2' else None)
    self.assertEqual(manifest['native_engine'],mode);self.assertNotIn('monetary_policy',default_config());self.assertNotIn('native_engine',m)
    cfg.update(horizon_days=4,customer_pool=4,arrival_bps=10000,nonpayment_bps=0,clearing_hours=1)
    result=run_world(ROOT,manifest,cfg,2610312145,'competitive_growth',folder/mode)
    self.assertTrue(result['orders']);self.assertTrue(audit(ROOT,manifest,result)['accepted'])
   cfg=default_config();cfg['monetary_policy']='exact-integer-v2'
   with self.assertRaisesRegex(ValueError,'FRESH_POLICY_NATIVE_ENGINE_REGISTRATION_MISMATCH'):
    run_world(ROOT,m,cfg,1,'competitive_growth',folder/'wrong-engine')
   self.assertFalse((folder/'wrong-engine'/'account.sqlite').exists())
 def test_fresh_native_payment_tax_profit_replay_above_100b_and_int64(self):
  with tempfile.TemporaryDirectory(prefix='.large-money-',dir=ROOT) as folder:
   folder=Path(folder);manifest=prepare_services(ROOT,str(folder.relative_to(ROOT)/'jobs'),cohort_seed=2610312239)
   job=next(j for j in manifest['jobs'] if j['service_id']=='reconciliation' and j['accepted'])
   for mode in ('exact-permanent-v2','exact-prospective-v2'):
    for price in (200_000_000_000*1_000_000+17,2**70+23):
     with self.subTest(mode=mode,price=price):
      m=copy.deepcopy(manifest)
      m['native_engine']=mode
      path=folder/(mode+'-'+str(price)+'.sqlite');opening=price*3;contract='large-money-engineering'
      a=JournalAccount(ROOT,m,path,opening=opening,working=1_000_000,contract=contract)
      try:
       production=5_000_000_000*1_000_000+3
       a.cost('actual-cost-envelope',production,0)
       offer={'id':'large','buyer':'buyer','price':price,'job_id':job['id'],'deadline':10}
       if mode=='exact-prospective-v2':
        terms=prospective_terms('large',price,20,2,residual=1_000_000,premium=250_000)
        a.execute('register_terms',{'id':'large-v1','terms':terms},0);offer['terms_id']='large-v1'
       a.execute('wallet',{'buyer':'buyer','amount':price},0);a.execute('offer',offer,0)
       for op in ('consent','fund','prepare','release'):
        a.execute('event',{'id':'large','action':op,'event_id':'large-'+op},2)
       before=a.snapshot()['summary'];tax=before['profit']*2000//10000
       a.cost('modeled-income-tax',tax,3)
       final=a.snapshot()['summary']
       self.assertEqual(final['collections'],price)
       self.assertEqual(final['profit'],before['profit']-tax)
       self.assertGreater(final['profit'],100_000_000_000*1_000_000)
       self.assertEqual(final['cash'],opening+price-final['expensePaid'])
       self.assertEqual(final['payables'],0)
       self.assertTrue(a.audit()['accepted'])
       exported=a.export();self.assertEqual(strict_json(canonical(exported)),exported)
       # Arithmetic window only: this deliberately does not certify a year's business operations.
       year=trailing_profit(exported['ledger'],operating_end_hour=365*24,operating_complete=False)
       self.assertEqual(year['observed_window_profit_microUSD'],final['profit'])
       self.assertIsNone(year['trailing_365_day_profit_microUSD'])
       self.assertFalse(year['complete_365_day_operating_history'])
       if mode=='exact-prospective-v2':
        mature=a.advance_financial(21)['summary'];self.assertEqual(mature['cash'],final['cash']);self.assertEqual(mature['profit'],final['profit'])
       # Controlled calendar arithmetic, not a market-scale success claim.
       for month in range(1,13):a.cost('calendar-maintenance-'+str(month),1,month*730-1)
       expected=a.snapshot()['summary'];self.assertTrue(a.audit()['accepted'])
       annual=trailing_profit(a.export()['ledger'],operating_end_hour=8760,operating_complete=True)
       self.assertEqual(annual['trailing_365_day_profit_microUSD'],expected['profit'])
       self.assertGreater(annual['trailing_365_day_profit_microUSD'],100_000_000_000*1_000_000)
       if mode=='exact-prospective-v2' and price>2**63:
        claim=price*5+1
        a.execute('claim',{'id':'large','claim_id':'large-unpaid','amount':claim,'kind':'provider_default'},8761)
        stopped=a.snapshot()['summary'];self.assertEqual(stopped['payables'],claim)
        self.assertTrue(stopped['investmentStopped']);self.assertEqual(stopped['unrestrictedEarned'],0)
        self.assertIsNone(a.spend('unsafe-late','production',1,8761,{},1,allow_seed=True))
        self.assertTrue(a.audit()['accepted']);expected=stopped
      finally:a.close()
      reopened=JournalAccount(ROOT,m,path,opening=opening,working=1_000_000,contract=contract)
      try:self.assertEqual(reopened.snapshot()['summary'],expected);self.assertTrue(reopened.audit()['accepted'])
      finally:reopened.close()
if __name__=='__main__':unittest.main()
