import argparse,hashlib,json
from decimal import Decimal,localcontext
from pathlib import Path
D=Decimal

def cost(price,interval,horizon,rate,include_terminal):
    purchases=[]
    t=0
    while t<horizon or include_terminal and t==horizon:
        amount=price/(1+rate)**t
        purchases.append({'year':t,'discounted_USD_per_kWh':float(amount),'serves_pre_horizon':t<horizon})
        t+=interval
    return sum(D(str(p['discounted_USD_per_kWh'])) for p in purchases),purchases

def reference():
    out=[]
    for second in [D(214),D(643)/3]:
        for rate in [D(0),D('.05')]:
            for interval in [6,7,8]:
                rows=[]
                for terminal in [False,True]:
                    new,np=cost(D(271),10,20,rate,terminal)
                    used,up=cost(second,interval,20,rate,terminal)
                    rows.append({'include_terminal_replacement':terminal,'new_npv_USD_per_kWh':float(new),'second_npv_USD_per_kWh':float(used),'second_minus_new_fraction':float(used/new-1),'new_purchases':np,'second_purchases':up})
                out.append({'second_price_USD_per_kWh':float(second),'discount_rate':float(rate),'second_interval_years':interval,'service_horizon_years':20,'boundary_conventions':rows,'preference_reverses':(rows[0]['second_minus_new_fraction']>0)!=(rows[1]['second_minus_new_fraction']>0)})
    return {'schema':'independent-terminal-boundary-reference/v1','spec_sha256':'fbd6f0964dd22f8244c7fd14eb7d98b49b3053b594a146f8bdec92f8af6e47f7','results':out,'verdict':'TERMINAL_BOUNDARY_CAN_REVERSE_CONDITIONAL_CAPEX_PREFERENCE; FULL_SERVICE_ECONOMICS_UNKNOWN','source_reproduction':'Not claimed: full source workbook, rate/path and installed cost set unavailable','interpretation':'A replacement att=Tservesnopre-Tload. Differencecanbechargedonlywithpost-Tassetvalueaccountedunderfrozencontract. This is source-backed counterexample to unqualifiedthresholdnotproofactualsuppliercostsarewrong.','alpha_spent':0}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    with localcontext() as c:c.prec=40;r=reference()
    (a.output/'TERMINAL_REFERENCE.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'cases':len(r['results']),'preference_reversals':sum(x['preference_reverses'] for x in r['results']),'full_service_economics':'UNKNOWN'}))
