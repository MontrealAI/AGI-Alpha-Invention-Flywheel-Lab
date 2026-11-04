"""Registered consequential-offer stress game. Authored hypotheses, not a forecast."""
from dataclasses import dataclass,asdict
from pathlib import Path
import argparse,itertools,json,math
import numpy as np

@dataclass(frozen=True)
class Offer:
 name:str; benefit:float; ai_cost:float; human_hours:float; setup:float; research:float; duration:int
OFFERS=(Offer('enterprise_ai_operations',5e6,250000,6000,500000,25000,1),
 Offer('sector_ai_consortium',5e7,4e6,100000,5e6,150000,2),
 Offer('verified_compute_enablement',1e8,1e7,200000,1e7,250000,2))
CAPITALS=(100000,1000000,100000000,1000000000)
MODES=('none','human_only','conventional','founder','autonomous','combined')
WORLDS=('central','weak_demand','strong_rival','cost_overrun','slow_collection','capability_unreliable','high_reach','zero_demand','high_capability')
PRICES=np.array([i/1000 for i in range(1001)])
WAGE=150.;TAX=.265

def params(world):
 d=dict(qualified_per_quarter=100,benefit=1.,cost=1.,acceptance=.85,rival_cost=1.,rival_quality=.85,delay=1,signal_sd=.25)
 d.update({'central':{},'high_capability':dict(acceptance=.95,signal_sd=.1,cost=.7),'high_reach':dict(qualified_per_quarter=1000),'zero_demand':dict(qualified_per_quarter=0),'weak_demand':dict(qualified_per_quarter=10,benefit=.5),
 'strong_rival':dict(rival_cost=.65,rival_quality=.95),'cost_overrun':dict(cost=2.),
 'slow_collection':dict(delay=3),'capability_unreliable':dict(acceptance=.55,signal_sd=.6)}[world]);return d

def responses(offer,prices,quality,world,benefit):
 """Exact follower best response on integer-cent prices for three buyer types.
 Utility/value and budgets are explicitly quantized to cents. A one-cent undercut
 is a valid attained action, not a floating epsilon or unattained supremum.
 """
 weights=np.array([.5,.35,.15]);value=offer.benefit*benefit*np.array([.5,1.,2.]);budget=np.floor(value*.65*100).astype(np.int64)
 hc=offer.human_hours*WAGE;hy=hc*.25+offer.ai_cost;ss=hc*.1
 outside=np.maximum.reduce([np.zeros(3),np.where(hc*100<=budget,np.rint((.95*value-hc)*100),-1e17),np.where(hy*100<=budget,np.rint((.90*value-hy)*100),-1e17),np.where(ss*100<=budget,np.rint((.45*value-ss)*100),-1e17)]).astype(np.int64)
 pc=np.rint(np.asarray(prices)*100).astype(np.int64);own_value=np.rint(quality*value*100).astype(np.int64);rv=np.rint(world['rival_quality']*value*100).astype(np.int64)
 own=np.where(pc[:,None]<=budget,own_value-pc[:,None],-10**17)
 fixed=np.concatenate(([0],budget,rv-outside));breaks=np.concatenate((np.broadcast_to(fixed,(len(pc),len(fixed))),rv-own),axis=1)
 breaks=np.where((breaks>=0)&(breaks<10**16),breaks,0);rp=np.concatenate((breaks,np.maximum(0,breaks-1)),axis=1)
 rival=np.where(rp[:,:,None]<=budget,rv-rp[:,:,None],-10**17)
 a=((own[:,None,:]>outside)&(own[:,None,:]>rival)).astype(float);b=((rival>outside)&(rival>own[:,None,:])).astype(float)
 tie=(own[:,None,:]>outside)&(own[:,None,:]==rival);a[tie]=.5;b[tie]=.5
 share=a@weights;other=b@weights;rc=offer.ai_cost*world['cost']*world['rival_cost']*1.025
 pay=other*(rp/100*world['rival_quality']*.97-rc);best=np.maximum(0.,pay.max(axis=1));mask=np.abs(pay-best[:,None])<=1e-8
 selected=np.where(mask,share,np.inf);j=selected.argmin(axis=1);ownshare=selected[np.arange(len(pc)),j]
 exitshare=(own>outside)@weights;ownshare=np.where(best==0,np.minimum(ownshare,exitshare),ownshare)
 return ownshare,rp[np.arange(len(pc)),j]/100

def price_response(offer,p,quality,world,benefit):
 shares,prices=responses(offer,[p],quality,world,benefit);return float(shares[0]),float(prices[0])

def competitive_game(offer,cost,quality,world,benefit_estimate):
 prices=np.rint(PRICES*offer.benefit*100)/100
 shares,rivals=responses(offer,prices,quality,world,benefit_estimate)
 margin=shares*(prices*quality*.97-cost*1.025);i=int(margin.argmax())
 if margin[i]<0:return dict(price=0.,rival_price=None,share=0.,margin=0.,quality=quality,cost=cost,grid_gap=0.)
 return dict(price=float(prices[i]),rival_price=float(rivals[i]),share=float(shares[i]),margin=float(margin[i]),quality=quality,cost=cost,grid_gap=0.)

def run(capital,mode,world,seed,trace=False,inherited_assets=True,external_finance=False):
 w=params(world)
 if not inherited_assets:w['qualified_per_quarter']=int(w['qualified_per_quarter']*.25)
 financing_fee=.01*capital if external_finance and mode!='none' else 0.
 cash=float(capital)-financing_fee;reserved=recv=taxdue=profit=loss_cf=0.;queue=[];payments=[];rows=[]
 active={};research_spend=founder_hours=human_hours=accepted=orders=contacts=0;billings=0.;insolvent=False
 # The same latent market paths are paired across all modes and capital arms.
 def rng(q,p):return np.random.default_rng(np.random.SeedSequence([seed,q,p]))
 for q in range(26):
  revenue=collected=0.;expense=financing_fee if q==0 else 0.;hours=0.;founder_effort=0.;selected_offer=selected_variant=selected_channel=None;selected_price=0.;new_orders=0
  collected=sum(p[1] for p in payments if p[0]==q);payments=[p for p in payments if p[0]!=q];cash+=collected;recv-=collected
  for b in [b for b in queue if b['due']==q]:
   reserved-=b['bound'];cash-=b['cost'];expense+=b['cost'];hours+=b['hours']
   ok=int(rng(q,300+b['offer']).binomial(b['orders'],b['true_quality']))
   if b['repair']:ok+=int(rng(q,350+b['offer']).binomial(b['orders']-ok,.3 if world=='capability_unreliable' else .6))
   accepted+=ok
   net=ok*b['price']*.97;revenue+=net;recv+=net;billings+=net
   payments.extend([(q+w['delay'],net*.77),(q+w['delay']+1,net*.23)])
  queue=[b for b in queue if b['due']!=q]
  if q<20 and mode!='none' and not insolvent:
   # Existing brand/network access is a conditional finite yearly opportunity flow,
   # not followers. This arrangement does not spend an asset valuation as cash.
   overhead=50000.;research_budget=min(max(0.,cash-reserved-taxdue-overhead),max(0.,cash*.02))
   candidates=[]
   for k,o in enumerate(OFFERS):
    # Equal productive choices; modes differ only in costed information acquisition.
    # Effort figures and effect ranges are hypotheses, not measured capability.
    variants=('human',) if mode=='human_only' else ('human','ai','repair')
    research_cost=o.research*(1. if mode in ('human_only','conventional','founder') else .2)
    research_hours=o.research/WAGE if mode in ('human_only','conventional','founder') else 0.
    oversight=20. if mode in ('human_only','conventional','founder','combined') else 0.
    fee=research_cost+oversight*WAGE
    if founder_effort+oversight>500:continue
    if fee>research_budget:continue
    research_budget-=fee;cash-=fee;expense+=fee;research_spend+=fee;hours+=research_hours;founder_effort+=oversight
    truebenefit=w['benefit']*rng(q,10+k).lognormal(-.5*.2**2,.2)
    # Noisy research result: policy cannot inspect truebenefit directly.
    signal=truebenefit*rng(q,30+k).lognormal(-.5*w['signal_sd']**2,w['signal_sd'])
    # The research fee covers technical, valuation and channel probes.
    samples=8
    if mode!='none':
     # Second conditionally independent expert signal is separately paid.
     extra=o.research*.2
     if extra<=research_budget:
      research_budget-=extra;cash-=extra;expense+=extra;research_spend+=extra
      samples=16
      signal=(signal+truebenefit*rng(q,60+k).lognormal(-.5*w['signal_sd']**2,w['signal_sd']))/2
    pilot_success=int(rng(q,400+k).binomial(samples,w['acceptance']))
    belief=(17+pilot_success)/(20+samples)
    for variant in variants:
     if variant=='human':cost=o.human_hours*WAGE*w['cost'];quality=.92;labor=o.human_hours
     elif variant=='ai':cost=o.ai_cost*w['cost'];quality=belief;labor=0.
     else:cost=o.ai_cost*w['cost']*1.3;quality=belief+(1-belief)*.6;labor=0.
     # Repair is a paid contingent attempt, available to every policy; not a founder premium.
     g=competitive_game(o,cost,quality,w,signal)
     setup=0. if k in active else o.setup
     # Paid warm introductions and a costed stakeholder-convening channel.
     # Both are available to every mode; no actual relationship or endorsement is assumed.
     for channel,fixed,unit,reach,eligibility in (('warm',0.,5000. if inherited_assets else 25000.,w['qualified_per_quarter'],.8),('convene',100000.,2000.,4*w['qualified_per_quarter'],.4)):
      probe=int(rng(q,500+k+(channel=='convene')*10).binomial(8,eligibility))
      belief_eligible=(4+probe)/13.
      free=max(0.,cash-reserved-taxdue-overhead-setup-fixed)
      maxn=min(reach,int(free//(cost*1.25+unit)))
      for fraction in (.1,.25,.5,1.):
       quantity=int(maxn*fraction);expected=quantity*(g['margin']*belief_eligible-unit)-setup-overhead-fixed
       if quantity>0:candidates.append((expected,k,variant,g,quantity,setup,truebenefit,labor,fixed,unit,eligibility,belief_eligible,channel))
   choice=max(candidates,key=lambda x:x[0]) if candidates else None
   if choice:
    # Re-evaluate every candidate after all research costs, not just a stale winner.
    revised=[]
    for item in candidates:
     _,kk,vv,gg,nn,ss,tt,ll,ff,uu,ee,eb,ch=item
     nn=min(nn,int(max(0.,cash-reserved-taxdue-overhead-ss-ff)//(gg['cost']*1.25+uu)))
     revised.append((nn*(gg['margin']*eb-uu)-ss-overhead-ff,kk,vv,gg,nn,ss,tt,ll,ff,uu,ee,eb,ch))
    choice=max(revised,key=lambda x:x[0])
   if choice and choice[0]>0 and choice[4]>0:
    _,k,var,g,n,setup,truebenefit,labor,fixed,unit,eligibility,eb,channel=choice;o=OFFERS[k]
    cash-=overhead+setup+fixed+n*unit;expense+=overhead+setup+fixed+n*unit;active[k]=True;contacts+=n
    # Chosen price is fixed before observing true realized demand.
    # Actual voluntary demand evaluates chosen price against best-response rival
    # under true public-value environment, not a clairvoyant price change.
    # Recompute shares at the chosen price by a dedicated evaluator.
    share=realized_share(o,g['price'],g['quality'],w,truebenefit)*eligibility
    count=int(rng(q,100+k).binomial(n,share));orders+=count;new_orders=count
    selected_offer=o.name;selected_variant=var;selected_channel=channel;selected_price=g['price']
    bound=count*g['cost']*1.25;reserved+=bound
    # Repair reserves and charges the full additional envelope, including unsuccessful retries.
    realized_cost=count*g['cost']*float(rng(q,200+k).uniform(.8,1.25))
    queue.append(dict(due=q+o.duration,offer=k,orders=count,bound=bound,cost=realized_cost,
      true_quality=.92 if var=='human' else w['acceptance'],repair=var=='repair',price=g['price'],hours=count*labor))
  pretax=revenue-expense;taxable=max(0.,pretax-loss_cf);loss_cf=max(0.,loss_cf-pretax);tax=taxable*TAX
  taxdue+=tax;paid=min(taxdue,max(0.,cash-reserved));cash-=paid;taxdue-=paid
  insolvent=taxdue>1e-7;profit+=pretax-tax;founder_hours+=founder_effort;human_hours+=hours
  rows.append(dict(quarter=q+1,revenue=revenue,expense=expense+tax,profit=pretax-tax,cash=cash,
   reserved=reserved,receivables=recv,tax_payable=taxdue,collected=collected,orders=orders,accepted=accepted,contacts=contacts,human_hours=hours,founder_hours=founder_effort,selected_offer=selected_offer,selected_variant=selected_variant,selected_channel=selected_channel,selected_price=selected_price,new_orders=new_orders))
  assert cash>=reserved-1e-5 and abs(cash+recv-taxdue-capital-profit)<max(1e-5,capital*1e-10)
 assert not queue and not payments and abs(recv)<1e-5 and abs(reserved)<1e-5
 out=dict(external_finance=external_finance,financing_fee=financing_fee,inherited_assets=inherited_assets,capital=capital,mode=mode,world=world,seed=seed,trailing_year_profit=sum(r['profit'] for r in rows[16:20]),
  settled_profit=profit,cash=cash,obligations=reserved+taxdue,receivables=recv,accepted=accepted,orders=orders,contacts=contacts,
  research_spend=research_spend,founder_hours=founder_hours,human_hours=human_hours,three_billion=sum(r['profit'] for r in rows[16:20])>=3e9,
  autonomy='HYBRID' if human_hours+founder_hours>0 else 'STRICT_AUTONOMOUS_MODELED',scope='CONDITIONAL_COMPLETE_OFFER_STRESS_GAME_NOT_NATIVE_OR_ACTUAL_COMMERCE')
 if trace:out['trace']=rows
 return out

def realized_share(o,p,quality,w,benefit):
 return price_response(o,p,quality,w,benefit)[0]

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--development',action='store_true');a=p.parse_args()
 seeds=range(96000,96002) if a.development else range(96100,96112)
 rows=[run(*x,trace=True) for x in itertools.product(CAPITALS,MODES,WORLDS,seeds)]
 a.output.write_text(json.dumps(rows,indent=2,default=lambda x:x.item())+'\n')
 print(len(rows),max(x['trailing_year_profit'] for x in rows))
if __name__=='__main__':main()
