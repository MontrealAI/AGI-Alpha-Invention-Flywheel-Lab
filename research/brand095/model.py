"""Finite brand activation hypothesis; not native or actual commerce."""
import argparse,itertools,json,math
from pathlib import Path
import numpy as np
from research.strategic094.model import conditions,stage_game,PRICES,BASE,VALUE,BUDGET,HUMAN_HOURS,LOADED_WAGE,UNIT_COST,TYPE_WEIGHT,TAX,DEVELOPMENT,MAINTENANCE
POLICIES=('none','full','staged')
def matrix(seeds=range(95100,95112)):
 for n,mix,env,policy,seed in itertools.product((1000,10000),('small','mixed'),('lean','demanding'),POLICIES,seeds):
  yield dict(n=n,mix=mix,capital=100000,scenario='central',envelope=env,policy=policy,seed=seed)
 for mix,env,policy,seed in itertools.product(('small','mixed'),('lean','demanding'),POLICIES,seeds):
  yield dict(n=10000,mix=mix,capital=1000000,scenario='central',envelope=env,policy=policy,seed=seed)
 for cap,policy,seed in itertools.product((100000,1000000),POLICIES,seeds):
  yield dict(n=10000,mix='mixed',capital=cap,scenario='aggressive_rival',envelope='lean',policy=policy,seed=seed)
def capacity(counts,c):
 return float(np.sum(counts*UNIT_COST*c.cost_multiplier*.05*(1+counts/np.array([1000.,100.,10.]))))
def buy_probability(s,t,p,q,c):
 v=VALUE[s,t]*c.value_multiplier;b=BUDGET[s,t];h=HUMAN_HOURS[s]*LOADED_WAGE
 own=v*c.quality-BASE[s]*p if BASE[s]*p<=b else -math.inf
 rival=v*c.rival_quality-BASE[s]*q if BASE[s]*q<=b else -math.inf
 alt=max(0.,v*.99-h if h<=b else -math.inf,v*.96-h*.25-UNIT_COST[s] if h*.25+UNIT_COST[s]<=b else -math.inf,v*.65-h*.1 if h*.1<=b else -math.inf)
 return 0. if own<=alt or own<rival else (.5 if own==rival else 1.)
def audit(rows,capital):
 cum=opp=rev=coll=0.;oc=cc=ac=0
 for r in rows:
  cum+=r['profit'];opp+=r['founder_opportunity_cost'];rev+=r['revenue'];coll+=r['collected']
  assert abs(r['revenue']-r['cost']-r['profit'])<1e-5
  assert abs(rev-coll-r['receivables'])<1e-5
  assert ac<=r['accepted_cumulative']<=r['orders_cumulative']
  assert abs(r['cash']+r['receivables']-r['tax_payable']-capital-cum)<1e-5
  assert abs(r['economic_profit_cumulative']-cum+opp)<1e-5
  assert r['cash']+1e-5>=r['reserve']
  assert oc<=r['orders_cumulative']<=r['contacts_cumulative']<=r['audience']
  assert r['contacts_cumulative']>=cc
  assert r['duplicate_contacts']==r['buyer_budget_violations']==0
  oc=r['orders_cumulative'];cc=r['contacts_cumulative'];ac=r['accepted_cumulative']
 return len(rows)*9

def simulate(n,mix,capital,scenario,envelope,policy,seed,trace=False):
 assert n>=0 and mix in ('small','mixed') and capital>0 and policy in POLICIES
 config=dict(n=n,mix=mix,capital=capital,scenario=scenario,envelope=envelope,policy=policy,seed=seed)
 c=conditions(scenario);rng=np.random.default_rng(seed);segments=np.zeros(n,dtype=int)
 if mix=='mixed':segments[int(.90*n):int(.99*n)]=1;segments[int(.99*n):]=2
 rng.shuffle(segments);types=rng.choice(3,n,p=TYPE_WEIGHT);purchase=rng.random(n);accepted=rng.random(n)
 contacted=set();ordered=set();queue=[];payments=[];rows=[]
 cash=float(capital);reserve=recv=tax_payable=loss_cf=cum=opp=total_collected=0.
 total_production=total_capacity=activation_paid=hours=0.;orders=accepts=0
 cost_cash,hour_total=(1000.,8.) if envelope=='lean' else (10000.,40.)
 pilot=int(n*.1);expanded=policy=='full';decision=None;closed=False
 if policy!='none':cash-=DEVELOPMENT
 def stream(m,p):return np.random.default_rng(np.random.SeedSequence([seed,m,p]))
 for month in range(18):
  revenue=0.;expense=DEVELOPMENT if month==0 and policy!='none' else 0.;newopp=0.
  collected=sum(p[1] for p in payments if p[0]==month);payments=[p for p in payments if p[0]!=month]
  cash+=collected;recv-=collected;total_collected+=collected
  for b in [b for b in queue if b['due']==month]:
   reserve-=b['reserve'];cash-=b['reserve'];expense+=b['reserve'];total_production+=b['reserve']
   quality=min(1.,c.acceptance*stream(month,1).lognormal(-.5*.1**2,.1))
   ids=[i for i in b['ids'] if accepted[i]<quality];accepts+=len(ids)
   net=sum(BASE[segments[i]]*b['price'] for i in ids)*(1-c.refund)*(1-c.bad_debt)
   revenue+=net;recv+=net
   payments.extend([(month+c.payment_months,net*(1-c.late_share)),(month+c.payment_months+c.late_months,net*c.late_share)])
  queue=[b for b in queue if b['due']!=month]
  if policy=='staged' and month==6:
   decision=total_collected-total_production-total_capacity-activation_paid-opp-6*MAINTENANCE-reserve-tax_payable>0;expanded=bool(decision)
  if policy!='none' and month<12 and not closed:
   f=(1. if policy=='full' else .1) if month==0 else (.9 if policy=='staged' and month==6 and expanded else 0.)
   activate=f*cost_cash;newhours=f*hour_total
   if cash-reserve < MAINTENANCE+activate:closed=True
   else:
    cash-=MAINTENANCE+activate;expense+=MAINTENANCE+activate;activation_paid+=activate
    hours+=newhours;newopp=newhours*150.;opp+=newopp
    if policy=='full':allowed=int(n*(month+1)/12)
    elif month<3:allowed=int(pilot*(month+1)/3)
    elif month<6 or not expanded:allowed=pilot
    else:allowed=pilot+int((n-pilot)*(month-5)/6)
    available=[i for i in range(allowed) if i not in contacted];candidates=[]
    for frac in (0.,.1,.25,.5,1.):
     ids=available[:int(len(available)*frac)];counts=np.bincount(segments[ids],minlength=3) if ids else np.zeros(3)
     fee=capacity(counts,c);bound=float(np.dot(counts,UNIT_COST*c.cost_multiplier))
     if fee+bound>cash-reserve:continue
     game=stage_game(counts,c,False);p=PRICES[game['price_index']];j=game['rival_index'];q=PRICES[j] if j>=0 else math.inf
     candidates.append((game['leader_value']-fee,-fee,ids,p,q,fee))
    _,_,ids,p,q,fee=max(candidates,key=lambda x:(x[0],x[1]));cash-=fee;expense+=fee;total_capacity+=fee
    shock=min(1.,stream(month,3).lognormal(-.5*c.common_log_sd**2,c.common_log_sd));bought=[]
    for i in ids:
     assert i not in contacted;contacted.add(i)
     if purchase[i]<buy_probability(segments[i],types[i],p,q,c)*shock:
      assert i not in ordered and BASE[segments[i]]*p<=BUDGET[segments[i],types[i]]
      ordered.add(i);bought.append(i)
    bound=sum(UNIT_COST[segments[i]]*c.cost_multiplier for i in bought);reserve+=bound;orders+=len(bought)
    queue.append(dict(due=month+c.procurement_months,ids=bought,reserve=bound,price=p))
  pretax=revenue-expense;taxable=max(0.,pretax-loss_cf);loss_cf=max(0.,loss_cf-pretax);tax=taxable*TAX
  payable=tax+tax_payable;paid=min(payable,max(0.,cash-reserve));cash-=paid;tax_payable=payable-paid
  if tax_payable>1e-6:closed=True
  profit=pretax-tax;cum+=profit
  rows.append(dict(month=month+1,audience=n,cash=cash,reserve=reserve,receivables=recv,tax_payable=tax_payable,
   revenue=revenue,cost=expense+tax,profit=profit,collected=collected,founder_opportunity_cost=newopp,
   economic_profit_cumulative=cum-opp,orders_cumulative=orders,accepted_cumulative=accepts,
   contacts_cumulative=len(contacted),duplicate_contacts=0,buyer_budget_violations=0))
 checks=audit(rows,capital)
 assert not queue and not payments and abs(recv)<1e-5 and reserve<1e-5
 config.update(first_year_profit=sum(x['profit'] for x in rows[:12]),settled_episode_profit=cum,
  settled_economic_profit=cum-opp,cash=cash,receivables=recv,obligations=reserve+tax_payable,orders=orders,
  accepted=accepts,contacts=len(contacted),activation_cash=activation_paid,founder_hours=hours,
  founder_opportunity_cost=opp,expanded=expanded,expansion_decision=decision,closed=closed,checks=checks,
  positive_after_founder_cost=cum-opp>0,scope='HYPOTHETICAL_BRAND_ACTIVATION_NOT_NATIVE_OR_ACTUAL_COMMERCE')
 if trace:config['trace']=rows
 return config

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--development',action='store_true');a=p.parse_args()
 rows=[simulate(**case,trace=True) for case in matrix(range(95000,95002) if a.development else range(95100,95112))]
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(rows,indent=2,allow_nan=False,default=lambda x:x.item())+'\n')
 print(json.dumps(dict(rows=len(rows),positive=int(sum(r['positive_after_founder_cost'] for r in rows)),max_profit=max(r['settled_economic_profit'] for r in rows))))
if __name__=='__main__':main()
