"""Read-only economic sensitivity; never holds or mutates a financial balance."""
from pathlib import Path
import argparse,itertools,json

def sensitivity(reg):
 rows=[];rates=reg['costs']['price_proxy']
 for delivery in ('first','second'):
  for (inp,out),minutes in itertools.product(reg['costs'][delivery+'_sensitivity_tokens'],[0,15,60]):
   model=inp/1e6*rates['input_per_million_usd']+out/1e6*rates['output_per_million_usd']
   intervention=minutes/60*reg['human']['loaded_hourly_usd'][1]
   before_fees=model+reg['costs'][delivery]['other_resources_usd']+intervention
   price=reg['market']['quotes_usd'][0 if delivery=='first' else 1]
   full=before_fees+price*reg['costs']['payment_percent']+reg['costs']['payment_fixed_usd']+reg['costs']['native_fee_usd']
   pre=price-full;tax=max(0,pre)*reg['costs']['tax_positive_profit']
   rows.append({'delivery':delivery,'estimated_input_tokens':inp,'estimated_output_tokens':out,'hypothetical_human_minutes':minutes,'label':'hybrid' if minutes else 'zero_intervention_scenario_not_measured_user_time','model_valuation_usd':model,'cost_before_commercial_fees_usd':before_fees,'full_pretax_cost_usd':round(full,6),'profit_after_provision_usd':round(pre-tax,6),'break_even_price_usd':round((before_fees+reg['costs']['payment_fixed_usd']+reg['costs']['native_fee_usd'])/(1-reg['costs']['payment_percent']),6),'human_hours_break_even_low_wage':round(before_fees/reg['human']['loaded_hourly_usd'][0],6) if delivery=='first' else None,'human_hours_break_even_median_wage':round(before_fees/reg['human']['loaded_hourly_usd'][1],6) if delivery=='first' else None})
 return {'scope':'READ_ONLY_ESTIMATED_COST_SURFACE_NOT_NATIVE_BALANCES','rows':rows,'human_labor_usd':{'low':5.5*46.95,'central':9*61.09,'high':14.25*86.53,'strong_turnkey_low':2*46.95,'strong_turnkey_high':4*86.53},'human_software_allocation_usd':[0,15],'no_empirical_human_trial':True,'actual_total_billing':None}

def main():
 p=argparse.ArgumentParser();p.add_argument('--registration',type=Path,default=Path('business_productivity065/PREREGISTRATION.json'));p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(sensitivity(json.loads(a.registration.read_text())),indent=2)+'\n')
if __name__=='__main__':main()
