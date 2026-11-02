"""Necessary-scale arithmetic, not simulated sales or an economic outcome."""
from .registration import design

def bounds():
    r=design();rows=[]
    for name in ('favorable','central','adverse'):
        w=r['worlds'][name]
        for cost in r['resource_cases_usd']:
            for price in r['price_candidates_usd']:
                # Optimistic twelve calendar-month comparison: no acquisition,
                # setup, onboarding, failures, financing, fixed or capacity cost.
                net=(price*(1-w['payment_rate'])-w['payment_fixed_usd']-cost)*(1-r['tax_rate'])
                required=r['primary_target_trailing365_profit_usd']/(12*net) if net>0 else None
                rows.append({'world':name,'price_usd':price,'core_cost_usd':cost,
                  'optimistic_aftertax_contribution_usd':net,
                  'necessary_active_merchants_12months':required,
                  'necessary_share_serviceable_stock':required/w['reachable_firms'] if required else None,
                  'all_serviceable_stock_optimistic_annual_profit_usd':12*net*w['reachable_firms'],
                  'not_demand_forecast':True})
    return {'scope':'RELAXED_NECESSARY_SCALE_NOT_NATIVE_RESULT; 12calendar months distinct from30day simulator', 'rows':rows}
if __name__=='__main__':
    import json
    print(json.dumps(bounds(),sort_keys=True,indent=2))
