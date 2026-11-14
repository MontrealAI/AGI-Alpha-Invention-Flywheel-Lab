"""Finite competitive planning model. NOT a native ledger or actual commerce.

Every monetary quantity is an explicit conditional projection in dollars.
No Account is opened; projection balances confer no spending authority.
"""
from dataclasses import dataclass, asdict
import itertools, json, math
from functools import lru_cache
from pathlib import Path
import numpy as np
from scipy.special import ndtr

PRICES = tuple([0.,.05]+[i/200 for i in range(20,101)]+[.6,.7,1.,1.4])
CAPITALS = (100_000, 1_000_000, 100_000_000, 1_000_000_000)
SCENARIOS = ('central','cost_value_stress','aggressive_rival','slow_payment','zero_demand')
POLICIES = ('organic','staged','adaptive')
FIRMS = np.array([6_281_253,93_341,21_041], dtype=float)
BASE = np.array([1_000.,10_000.,100_000.])
TYPE_WEIGHT = np.array([.5,.35,.15])
VALUE = BASE[:,None] * np.array([1.0,2.0,4.0])[None,:]
BUDGET = BASE[:,None] * np.array([.8,1.8,3.0])[None,:]
# These hours and token volumes are hypotheses. BLS rate is public evidence.
HUMAN_HOURS = np.array([20.,200.,2000.])
LOADED_WAGE = 74.42
# Model API-equivalent resource valuation only; no API requests occur.
TOKENS_IN = np.array([1e6,10e6,100e6])
TOKENS_OUT = TOKENS_IN / 10
AI_TOKEN_COST = TOKENS_IN / 1e6 * 2 + TOKENS_OUT / 1e6 * 10
# Each cost includes research/verification retries (factor2), deterministic tools,
# onboarding, support and failure envelope. Autonomous acceptance remains assumed.
UNIT_COST = 2 * AI_TOKEN_COST + np.array([150.,1500.,15000.])
CONTACT_COST = np.array([50.,500.,5000.])
TAX = .265
DEVELOPMENT = 50_000.
MAINTENANCE = 2_000.
PRICE_GAME_TOL = 1e-8

@dataclass(frozen=True)
class Conditions:
    eligibility: float = .10
    opportunities_year: float = 4.
    cost_multiplier: float = 1.
    value_multiplier: float = 1.
    rival_cost_multiplier: float = 1.
    rival_quality: float = .94
    quality: float = .95
    procurement_months: int = 2
    payment_months: int = 2
    bad_debt: float = .01
    acceptance: float = .95
    refund: float = .02
    common_log_sd: float = .35
    # Late fraction is revenue-weighted at equal-price cells; not customer defaults.
    late_share: float = .23
    late_months: int = 1


def conditions(name):
    if name not in SCENARIOS: raise ValueError('unknown scenario')
    updates = {
      'central': {},
      'cost_value_stress': {'cost_multiplier':2.,'value_multiplier':.6,'acceptance':.8},
      'aggressive_rival': {'rival_cost_multiplier':.6,'rival_quality':.98},
      'slow_payment': {'procurement_months':3,'payment_months':4,'bad_debt':.02},
      'zero_demand': {'eligibility':0.},
    }[name]
    return Conditions(**updates)


@lru_cache(maxsize=65536)
def buyer_shares(own_price, rival_price, c):
    """Public type-distribution demand; neither seller receives private draws.

    Indifference chooses outside option; seller ties split equally. No actor is
    forced to enter. Human+AI and self-service are explicit complete alternatives.
    """
    value = VALUE * c.value_multiplier
    ours = value*c.quality - BASE[:,None]*own_price
    theirs = value*c.rival_quality - BASE[:,None]*rival_price
    ours = np.where(BASE[:,None]*own_price <= BUDGET, ours, -np.inf)
    theirs = np.where(BASE[:,None]*rival_price <= BUDGET, theirs, -np.inf)
    human_cost=HUMAN_HOURS[:,None]*LOADED_WAGE
    hybrid_cost=HUMAN_HOURS[:,None]*.25*LOADED_WAGE+UNIT_COST[:,None]
    self_cost=HUMAN_HOURS[:,None]*.10*LOADED_WAGE
    human=np.where(human_cost<=BUDGET,value*.99-human_cost,-np.inf)
    hybrid=np.where(hybrid_cost<=BUDGET,value*.96-hybrid_cost,-np.inf)
    selfservice=np.where(self_cost<=BUDGET,value*.65-self_cost,-np.inf)
    outside = np.maximum.reduce([np.zeros_like(value),human,hybrid,selfservice])
    a = ((ours>outside)&(ours>theirs)).astype(float)
    b = ((theirs>outside)&(theirs>ours)).astype(float)
    ties = (ours>outside)&(ours==theirs)
    a[ties]=.5; b[ties]=.5
    return a@TYPE_WEIGHT,b@TYPE_WEIGHT


@lru_cache(maxsize=128)
def expected_receipt(price,c):
    if c.acceptance==0:return np.zeros(3)
    mu=math.log(c.acceptance)-.5*.10**2
    acceptance=math.exp(mu+.5*.10**2)*ndtr((-mu-.10**2)/.10)+1-ndtr(-mu/.10)
    return BASE*price*acceptance*(1-c.refund)*(1-c.bad_debt)


@lru_cache(maxsize=32)
def game_templates(c):
    a=np.empty((len(PRICES),len(PRICES),3));b=np.empty_like(a)
    realization=2*ndtr(-c.common_log_sd/2)
    for i,p in enumerate(PRICES):
      for j,q in enumerate(PRICES):
        share,other=buyer_shares(p,q,c)
        a[i,j]=realization*share*(expected_receipt(p,c)-UNIT_COST*c.cost_multiplier)
        b[i,j]=realization*other*(expected_receipt(q,c)-UNIT_COST*c.cost_multiplier*c.rival_cost_multiplier)
    return a,b

def stage_game(contacts,c,details=True):
    """Exact finite leader-price / follower-price expected-contribution game.

    Marketing cost is sunk before the rival response and therefore cannot alter
    its price ranking. Zero-sales has zero variable profit, including exit.
    Capacity is handled by capping contacts before this function, not afterward.
    """
    contacts=np.asarray(contacts,float)
    if np.any(contacts<0): raise ValueError('nonnegative contacts')
    template_a,template_b=game_templates(c)
    a=np.einsum('ijs,s->ij',template_a,contacts)
    b=np.einsum('ijs,s->ij',template_b,contacts)
    best=np.maximum(0.,b.max(axis=1))
    mask=np.abs(b-best[:,None])<=PRICE_GAME_TOL
    response_values=np.where(mask,a,np.inf)
    js=response_values.argmin(axis=1)
    leader=response_values[np.arange(len(PRICES)),js]
    for i,p in enumerate(PRICES):
      if best[i]==0:
        share,_=buyer_shares(p,float('inf'),c)
        exit_pay=float(np.sum(contacts*share*(expected_receipt(p,c)-UNIT_COST*c.cost_multiplier)))*2*ndtr(-c.common_log_sd/2)
        if exit_pay<=leader[i]:leader[i]=exit_pay;js[i]=-1
    i=int(np.argmax(leader));j=int(js[i])
    result={'leader_value':float(leader[i]),'price_index':i,'rival_index':j,
       'rival_value':float(best[i]),'finite_grid_gap':float(leader.max()-leader[i])}
    if details:result.update(leader_payoffs=a.tolist(),rival_payoffs=b.tolist(),
       leader_commitment_values=leader.tolist(),rival_response_indices=js.tolist())
    return result


def plan(cash,reserved,organic,c,policy):
    """Cash-constrained acquisition; no realized future demand enters here."""
    free=max(0.,cash-reserved-3*MAINTENANCE)
    ceiling=0. if policy=='organic' else (free*.01 if policy=='staged' else free)
    budgets=[0.]+[float(a*10**k) for k in range(2,max(2,int(math.log10(max(1.,ceiling)))+1))
                    for a in (1,2,5) if a*10**k<=ceiling]
    candidates=[]
    market_month=FIRMS*c.eligibility*c.opportunities_year/12
    for budget in budgets:
      # Spend proportions fixed ex ante, not inferred from unseen customer values.
      paid=np.floor(np.minimum(market_month*.20,budget*np.array([.3,.3,.4])/CONTACT_COST))
      # Organic/paid overlap: 10% of paid reach is already accessible.
      contacts=np.floor(np.minimum(market_month,organic+paid*.9))
      # Reserve maximum production cost before accepting any new contract.
      variable=UNIT_COST*c.cost_multiplier
      forecast_reserve=float(np.sum(contacts*variable))
      acquisition=float(np.sum(paid*CONTACT_COST))
      # Prepaid dated compute/tool/support slots: convex supplier congestion price.
      # Reference scales are hypotheses, not universal throughput limits.
      capacity_fee=float(np.sum(contacts*variable*.05*(1+contacts/np.array([1000.,100.,10.]))))
      spend=acquisition+capacity_fee
      if forecast_reserve+spend>free and forecast_reserve:
        scale=free/(forecast_reserve+spend)
        contacts=np.floor(contacts*scale);paid=np.floor(paid*scale)
        acquisition=float(np.sum(paid*CONTACT_COST))
        capacity_fee=float(np.sum(contacts*variable*.05*(1+contacts/np.array([1000.,100.,10.]))))
        spend=acquisition+capacity_fee
        forecast_reserve=float(np.sum(contacts*variable))
      game=stage_game(contacts,c,details=False)
      i,j=game['price_index'],game['rival_index'];p=PRICES[i]
      q=PRICES[j] if j>=0 else float('inf');gain=game['leader_value']
      candidates.append({'spend':spend,'acquisition':acquisition,'capacity_fee':capacity_fee,
        'contacts':contacts,'capacity_slots':np.floor(contacts).astype(int),'reserve_bound':forecast_reserve,
        'price':p,'rival_price':q,'expected_contribution':gain-spend,
        'game':game})
    candidates.append({'spend':0.,'acquisition':0.,'capacity_fee':0.,'contacts':np.zeros(3),
      'capacity_slots':np.zeros(3,dtype=int),'reserve_bound':0.,
      'price':PRICES[0],'rival_price':PRICES[0],'expected_contribution':0.,'game':None})
    # Non-entry and hold-cash remain feasible, no forced innovation spending.
    return max(candidates,key=lambda d:(d['expected_contribution'],-d['spend']))


def simulate(capital,scenario,policy,seed,months=60,keep_trace=False):
    if capital<=0 or policy not in POLICIES or months<12:raise ValueError('invalid run')
    c=conditions(scenario)
    def stream(month,purpose):
        return np.random.default_rng(np.random.SeedSequence([seed,month,purpose]))
    cash=float(capital)-DEVELOPMENT; reserved=0.; receivables=0.;loss_cf=DEVELOPMENT
    pending=[];payments=[]; trace=[];history=[];settled=0;accepted_total=0;tax_arrears=0.
    earnings_cash=-DEVELOPMENT;earned_acquisition=0.;total_spend=0.;min_free=cash
    # Organic reach is a disclosed hypothesis, not a free huge installed base.
    organic=np.array([10.,2.,.25]);failed=False
    for month in range(months):
      revenue=0.;cost=0.;collected=0.;orders=0;accepted=0;production=0.;released=0.
      duepay=[x for x in payments if x[0]==month];payments=[x for x in payments if x[0]!=month]
      collected=sum(x[1] for x in duepay);cash+=collected;receivables-=collected;earnings_cash+=collected
      arrears_paid=min(tax_arrears,max(0.,cash-reserved))
      cash-=arrears_paid;tax_arrears-=arrears_paid;earnings_cash-=arrears_paid
      due=[x for x in pending if x['due']==month];pending=[x for x in pending if x['due']!=month]
      for batch in due:
        released+=batch['reserve'];reserved-=batch['reserve']
        counts=batch['counts']; production=float(np.dot(counts,UNIT_COST*c.cost_multiplier))
        cost+=production;cash-=production;earnings_cash-=production
        # Common failure shock shared across all segments in a monthly cohort.
        quality=np.clip(c.acceptance*stream(month,1).lognormal(-.5*.10**2,.10),0,1)
        ok=stream(month,2).binomial(counts,quality); accepted+=int(ok.sum())
        gross=float(np.dot(ok,BASE*batch['price']))
        net=gross*(1-c.refund)*(1-c.bad_debt)
        revenue+=net;receivables+=net
        payments.extend([(month+c.payment_months,net*(1-c.late_share)),
                         (month+c.payment_months+c.late_months,net*c.late_share)])
      # Maintenance spent only while solvent; unpaid maintenance closes entry.
      if not failed and cash-reserved-tax_arrears>=MAINTENANCE:
        cash-=MAINTENANCE;cost+=MAINTENANCE;earnings_cash-=MAINTENANCE
      elif not failed:failed=True
      choice=None;acquisition=0.;newreserve=0.
      if not failed:
        choice=plan(cash,reserved,organic,c,policy)
        acquisition=choice['acquisition']; before_earned=max(0.,earnings_cash)
        cash-=choice['spend'];cost+=choice['spend'];earnings_cash-=choice['spend']
        earned_acquisition+=min(before_earned,acquisition);total_spend+=acquisition
        # Post-decision correlated market-wide uncertainty. Only available contacts
        # are attempted; shock reduces realization, never enlarges paid rights.
        shock=min(1.,stream(month,3).lognormal(-.5*c.common_log_sd**2,c.common_log_sd))
        share,_=buyer_shares(choice['price'],choice['rival_price'],c)
        contacts=np.floor(choice['contacts']).astype(int)
        counts=stream(month,4).binomial(contacts,np.clip(share*shock,0,1))
        if np.any(counts>choice['capacity_slots']):raise AssertionError('uncontracted capacity')
        newreserve=float(np.dot(counts,UNIT_COST*c.cost_multiplier))
        if newreserve>cash-reserved+1e-6:raise AssertionError('unfunded production')
        reserved+=newreserve;orders=int(counts.sum())
        pending.append({'due':month+c.procurement_months,'counts':counts,
                        'reserve':newreserve,'price':choice['price']})
      pretax=revenue-cost
      taxable=max(0.,pretax-loss_cf);loss_cf=max(0.,loss_cf-pretax)
      tax=taxable*TAX
      # Tax liability is recognized immediately, paid only from currently free cash.
      # If unpaid, preserve it and stop entry, never erase an obligation.
      tax_paid=min(tax,max(0.,cash-reserved));cash-=tax_paid;earnings_cash-=tax_paid
      unpaid_tax=tax-tax_paid;tax_arrears+=unpaid_tax
      if unpaid_tax>1e-6:failed=True
      profit=pretax-tax
      if month==0:profit-=DEVELOPMENT;cost+=DEVELOPMENT
      history.append(profit);settled+=int(sum(1 for x in duepay if x[1]>0));accepted_total+=accepted
      free=cash-reserved-tax_arrears;min_free=min(min_free,free)
      if cash < -1e-5:raise AssertionError('negative cash')
      row={'month':month+1,'recognized_net_revenue':revenue,'incurred_cost':cost+tax,
        'profit':profit,'collected':collected,'cash':cash,'receivables':receivables,
        'funded_production_reserve':reserved,'tax_payable':tax_arrears,'available':free,'orders':orders,'accepted':accepted,
        'acquisition':acquisition,'price_multiplier':choice['price'] if choice else None,
        'rival_price_multiplier':choice['rival_price'] if choice and math.isfinite(choice['rival_price']) else None,
        'trailing_year_profit':sum(history[-12:]) if month>=11 else None}
      trace.append(row)
      # Organic reach from completed accepted customers only, with decay. This is
      # an explicit referral/retention hypothesis; future pipeline is not clients.
      organic=np.minimum(FIRMS*c.eligibility*c.opportunities_year/12,
                         organic*.9+np.array([accepted*.02,accepted*.005,accepted*.001]))
    last=trace[-1];cum=sum(history)
    # Cash reconciliation: unpaid taxes remain liability; receivable plus cash
    # minus all liabilities equals equity plus recognized cumulative net profit.
    identity=cash+receivables-reserved-tax_arrears-capital-cum
    # Reserved future-production costs are commitments, not incurred expenses.
    future_production=sum(x['reserve'] for x in pending)
    identity+=future_production
    if abs(identity)>max(1e-4,abs(capital)*1e-10):raise AssertionError(('accounting identity',identity))
    result={'capital':capital,'scenario':scenario,'policy':policy,'seed':seed,
      'months':months,'trailing_year_profit':last['trailing_year_profit'],
      'cumulative_profit':cum,'cash':cash,'receivables':receivables,'obligations':reserved+tax_arrears,
      'future_production_reserve':future_production,'tax_arrears':tax_arrears,
      'min_available':min_free,'unfunded_obligation_observed':min_free<-.00001,
      'accepted_orders':accepted_total,'acquisition_total':total_spend,
      'acquisition_from_collected_surplus':earned_acquisition,'stopped_entry':failed,
      'cash_reconciliation_error':identity,
      'investor_terminal_hurdle':capital*(1.15**(months/12)),
      'book_equity_before_future_delivery':capital+cum,
      'investor_hurdle_met':capital+cum>=capital*(1.15**(months/12)),
      'three_billion_year':last['trailing_year_profit']>=3e9,
      'ten_billion_year':last['trailing_year_profit']>=1e10,
      'scope':'CONDITIONAL_PROJECTION_NOT_NATIVE_ACCEPTED_DELIVERY_SCALE',
      'checkpoints':[r for r in trace if r['month']%12==0]}
    if keep_trace:result['trace']=trace
    return result


def main():
    import argparse,time
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--engineering',action='store_true');a=p.parse_args()
    seeds=range(94001,94005) if a.engineering else range(94100,94124)
    rows=[];start=time.monotonic()
    for scenario,capital,policy,seed in itertools.product(SCENARIOS,CAPITALS,POLICIES,seeds):
      rows.append(simulate(capital,scenario,policy,seed))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps({'scope':'conditional projection','rows':rows,
      'elapsed_seconds':time.monotonic()-start},indent=2,allow_nan=False)+'\n')
    print(json.dumps({'rows':len(rows),'elapsed_seconds':time.monotonic()-start,
                     'max_trailing_year_profit':max(r['trailing_year_profit'] for r in rows)}))
if __name__=='__main__':main()
