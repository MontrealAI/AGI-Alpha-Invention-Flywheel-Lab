import math
from datetime import date,timedelta

def project(name,contacts_per_day,conversion,capacity,price_decline,collection_rate):
 rows=[];active=0.0;capacity_now=0.0;units_total=0.0
 for day in range(730):
  contacted=contacts_per_day*min(1,(day+1)/90)
  new=contacted*conversion
  active=active*(1-0.02/30)+new
  returning=active*0.5/90
  capacity_now=min(capacity,capacity_now+capacity/180)
  orders=min(capacity_now,new+returning)
  price=12000*(1-price_decline*min(1,day/365))
  buyer_budget=14000;outside_price=14000*(1-0.25*min(1,day/365))
  if price>=min(buyer_budget,outside_price): orders=0
  accepted=orders*0.95;collected=accepted*collection_rate
  revenue=collected*price
  cost=contacted*40+orders*800+accepted*500+500+new*600
  if day==0: cost+=6000
  pretax=revenue-cost;tax=max(0,pretax)*0.25
  rows.append({'day':day,'date':str(date(2026,11,3)+timedelta(days=day)),'orders':orders,'accepted':accepted,'revenue':revenue,'incurred_cost':cost+tax,'profit':pretax-tax,'support_tail_protected':accepted*500,'engineering_capacity':capacity_now})
  units_total+=accepted
 final=rows[365:730];profit=sum(r['profit'] for r in final)
 operating=sum(r['incurred_cost'] for r in final);revenue=sum(r['revenue'] for r in final)
 return {'region':name,'window_days':[365,730],'coverage_days':len(final),'annual_profit_usd':profit,'annual_revenue_usd':revenue,'annual_incurred_cost_usd':operating,'accepted_units':sum(r['accepted'] for r in final),'assumptions':{'contacts_per_day':contacts_per_day,'conversion':conversion,'capacity_per_day':capacity,'price_decline':price_decline,'collection_rate':collection_rate,'monthly_churn':0.02,'returning_order_rate_per_90days':0.5},'status':'UNFUNDED_ANALYTICAL_DEMAND_AND_CAPACITY_SENSITIVITY_NOT_NATIVE_EXECUTION','minimum_profit_only_units_for_3B_at_final_margin':math.ceil(3e9/max(1,(12000*(1-price_decline)-800-500-600)*0.75)),'required_financing':'UNKNOWN: procurement, acquisition commitments and scaled production bills not validated; projection cannot authorize operation','daily_events':rows}

def report():
 cases=[('favorable',1000,0.05,100,0.05,1),('central',200,0.02,20,0.2,0.98),('weak',100,0.002,5,0.35,0.9),('adverse',100,0,5,0.5,0)]
 return {'scope':'CONDITIONAL_UNFUNDED_ARITHMETIC_NOT_A_SECOND_OPERATING_LEDGER','no_probability_weights':True,'no_new_native_sales':True,'milestone_qualified':False,'rows':[project(*r) for r in cases],'unit_cost_scope':'Uses registered resource envelopes. Acquisition rates, demand, retention, acceptance, scalability and price paths are authored, not calibrated. Human comparator, physical commissioning and unknown scale-financing costs prevent a complete-enterprise or 3B success claim. No fixed market ceiling is asserted.'}
