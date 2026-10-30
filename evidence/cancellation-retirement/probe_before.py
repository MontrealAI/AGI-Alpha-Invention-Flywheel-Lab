import json,tempfile
from pathlib import Path
from tests.test_adaptive_account import AdaptiveAccountTests,_plan
from adaptive_enterprise.account import action_digest
AdaptiveAccountTests.setUpClass()
test=AdaptiveAccountTests('test_native_earned_reserve_finish_and_public_audit');test.setUp()
try:
 with test.open() as account:
  test.earn(account)
  job=[j for j in test.manifest['jobs'] if j['service_id']=='reconciliation'][1]
  option={'id':'delivery','kind':'delivery','upfront_cost':10000000,'later_liabilities':{'ordinary':3700000},'execution':{'kind':'delivery','job_id':job['id'],'customer_id':'second-customer','payment_bps':290,'payment_fixed_microUSD':300000,'onboarding_microUSD':500000}}
  plan=dict(_plan(),selected_options=[option],upfront_cost=10000000,worst_later_reserve=3700000,reserve_amount=13700000,expected_net=10000000)
  state=account.snapshot()['state_digest'];account.reserve(plan,expected_state_digest=state,authorized_digest=action_digest(plan,state,13700000,10000000),amount=13700000,expected_net=10000000,day=1)
  account.execute('wallet',{'buyer':'second-wallet','amount':100000000},1)
  account.execute('offer',{'id':'second-order','buyer':'second-wallet','price':100000000,'job_id':job['id'],'deadline':100},1)
  for action in ['consent','fund','prepare']:account.execute('event',{'id':'second-order','event_id':'second-'+action,'action':action},1)
  before=account.snapshot()['summary'];account.execute('cancel_investment',{'id':plan['plan_id']},1);after=account.snapshot()['summary'];accepted=account.audit()['accepted']
  print(json.dumps({'source':'b60eb7018fc7090ff3d7876c7b4e6b87a5e86922','scope':'DEVELOPMENT_COUNTEREXAMPLE','review':'discussion_r4427015349','before':before,'after':after,'audit_accepted':accepted,'declared_upfront_incurred_microUSD':10000000,'declared_later_liabilities_microUSD':3700000},sort_keys=True,indent=2))
finally:test.tearDown();AdaptiveAccountTests.tearDownClass()
