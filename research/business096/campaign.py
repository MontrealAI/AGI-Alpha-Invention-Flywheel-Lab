"""Freeze protocol before invocation. Calibration and confirmation are disjoint."""
import argparse,csv,itertools,json,time
from pathlib import Path
import numpy as np
from research.business096.model import *

def campaign(output,development=False):
 output.mkdir(parents=True,exist_ok=True);start=time.monotonic()
 seeds=range(96030,96032) if development else range(96040,96052)
 screens=[]
 for capital,mode in itertools.product(CAPITALS,MODES):
  prior=[]
  for world,seed in itertools.product(WORLDS,seeds):
   r=run(capital,mode,world,seed,external_finance=True)
   weight=(.5 if world=='central' else .5/(len(WORLDS)-1))/len(seeds)
   investor=capital+min(0.,r['settled_profit'])+.8*max(0.,r['settled_profit'])
   prior.append((r,weight,investor))
  expected=sum(weight*iv for r,weight,iv in prior)
  worst=min(iv for r,weight,iv in prior)
  approved=bool(mode!='none' and expected>=capital*1.15**6.5 and worst>=capital*.75)
  screens.append(dict(capital=capital,mode=mode,expected_investor_cash=expected,worst_investor_cash=worst,
   hurdle=capital*1.15**6.5,approved=approved,calibration_rows=len(prior),calibration_seeds=list(seeds)))
 (output/'FUNDING.json').write_text(json.dumps(screens,indent=2,default=lambda x:x.item())+'\n')
 # All own-equity numerical counterfactuals are retained, including declined finance.
 rows=[];seeds=range(96000,96002) if development else range(96100,96112)
 for capital,mode,world,seed in itertools.product(CAPITALS,MODES,WORLDS,seeds):
  r=run(capital,mode,world,seed,trace=True);r['external_equity_approved']=next(s['approved'] for s in screens if s['capital']==capital and s['mode']==mode);rows.append(r)
 for capital,mode,seed in itertools.product(CAPITALS,MODES,seeds):
  rows.append(run(capital,mode,'central',seed,trace=True,inherited_assets=False))
 # Separate external-finance episodes only for approved capital-policy pairs.
 funded=[]
 for screen in screens:
  if screen['approved']:
   for world,seed in itertools.product(WORLDS,seeds):
    funded.append(run(screen['capital'],screen['mode'],world,seed,trace=True,external_finance=True))
 (output/'RUNS.json').write_text(json.dumps(rows,indent=2,default=lambda x:x.item())+'\n')
 (output/'FUNDED_RUNS.json').write_text(json.dumps(funded,indent=2,default=lambda x:x.item())+'\n')
 summary=dict(rows=len(rows),funded_rows=len(funded),approved_financing_pairs=sum(s['approved'] for s in screens),
  positive_years=sum(r['trailing_year_profit']>0 for r in rows),max_trailing_year_profit=max(r['trailing_year_profit'] for r in rows),
  max_settled_profit=max(r['settled_profit'] for r in rows),three_billion=sum(r['three_billion'] for r in rows),elapsed_seconds=time.monotonic()-start)
 (output/'SUMMARY.json').write_text(json.dumps(summary,indent=2,default=lambda x:x.item())+'\n');print(summary)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--development',action='store_true');a=p.parse_args();campaign(a.output,a.development)
