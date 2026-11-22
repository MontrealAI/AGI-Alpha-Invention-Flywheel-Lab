"""Read a frozen prediction and a separately retrieved outcome snapshot; never refit."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np

def score(forecast,actual):
    for field in ('issue_date','delivery_date','t0','n'):
        if forecast[field]!=actual[field]: raise ValueError('Mismatched '+field)
    results={}; wins=0; complete=True
    for key,entry in forecast['series'].items():
        observed=actual.get('series',{}).get(key,{}).get('actual')
        if entry['status']!='available' or not isinstance(observed,list) or len(observed)!=96:
            results[key]={'status':'pending-or-unavailable'};complete=False;continue
        mask=np.array([isinstance(x,(int,float)) and np.isfinite(x) for x in observed]);count=int(mask.sum())
        if count==0:results[key]={'status':'pending'};complete=False;continue
        complete=complete and count==96
        y=np.array([x if ok else 0 for x,ok in zip(observed,mask)])[mask]
        errors={m:float(np.mean(abs(np.array(p)[mask]-y))) for m,p in entry['predictions'].items()}
        denom=errors.get('naive_weekly')
        ratios={m:(e/denom if denom and denom>0 else None) for m,e in errors.items()}
        # Later-information operator reference never counted as a deployable incumbent.
        rivals={m:e for m,e in errors.items() if m not in ('candidate','tso_final')}
        win=errors['candidate']<errors.get('selected_incumbent',-1) and errors['candidate']<errors.get('ens_hybrid',-1)
        wins+=win
        results[key]={'status':'complete' if count==96 else 'partial','observed_points':count,'mae':errors,'relative_mae':ratios,'beats_both_primary_controls':bool(win),'strongest_observed_comparator':min(rivals,key=rivals.get) if rivals else None}
    macros={}
    if complete:
        names=set.intersection(*(set(r['relative_mae']) for r in results.values()))
        for name in names:
            values=[r['relative_mae'][name] for r in results.values()]
            macros[name]=float(np.mean(values)) if all(x is not None for x in values) else None
    pairwise={}
    for name in sorted({m for r in results.values() for m in r.get('mae',{}) if m not in ('candidate','tso_final')}):
        keys=[k for k,r in results.items() if name in r.get('mae',{}) and r['relative_mae'].get(name) is not None]
        if keys:
            pairwise[name]={'series_count':len(keys),'series':keys,'candidate_macro_relative_mae':float(np.mean([results[k]['relative_mae']['candidate'] for k in keys])),'comparator_macro_relative_mae':float(np.mean([results[k]['relative_mae'][name] for k in keys])),'candidate_series_wins':sum(results[k]['mae']['candidate']<results[k]['mae'][name] for k in keys)}
    accepted=bool(complete and len(results)==12 and wins>=9 and macros.get('candidate') is not None and all(macros.get(m) is not None and macros['candidate']<macros[m] for m in ['selected_incumbent','ens_hybrid']))
    return {'complete_96_points_all_series':bool(complete),'restricted_primary_accuracy_criterion_met':accepted,'wins_on_both_primary_controls':wins,'macro_relative_mae':macros,'series':results,'pairwise_comparator_coverage':pairwise,'source_phase':actual.get('phase'),'source_revisions':actual.get('revisions'),'source_actual_sources':actual.get('actual_sources'),'interpretation':'Accuracy only; no profit, demand, novelty, trading or superior-successor evidence. Completeness is not finality; source revisions remain possible.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('forecast',type=Path);p.add_argument('actual',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    f=a.forecast.read_bytes();y=a.actual.read_bytes();r=score(json.loads(f),json.loads(y));r.update(forecast_sha256=hashlib.sha256(f).hexdigest(),actual_snapshot_sha256=hashlib.sha256(y).hexdigest());a.out.write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='series'},indent=2))
