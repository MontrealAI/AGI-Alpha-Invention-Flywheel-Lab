"""Cross-check early TESS epochs using a separately reduced timing catalogue."""

import argparse
import csv
from collections import defaultdict
from io import StringIO
from math import hypot
from pathlib import Path

from covariance_study import FENCE, decimals, elements, observations, source
from science_substrate import canonical, read_json


def key(name):
    return ''.join(char for char in name.casefold() if char.isascii() and char.isalnum())


def host_key(name):
    name=name[:-1] if name and 'b'<=name[-1]<='z' else name
    return key(name)


def indexed(rows,t,p):
    chosen={}
    for y,s,line in rows:
        n=round((y-t)/p)
        if abs(y-t-n*p)>=p/8:
            continue
        value=(s,line,y)
        if n not in chosen or value<chosen[n]:
            chosen[n]=value
    return chosen


def audit(args):
    specs=read_json(args.sources)
    catalog=elements(source(args.elements,'early_elements',specs))
    drc=observations(source(args.older,'early_observations',specs),True)
    text=source(args.independent,'independent_timing',specs).decode('utf-8')
    external=source(args.independent_elements,'independent_elements',specs).decode('utf-8')
    periods=defaultdict(list)
    for row in csv.DictReader(StringIO(external)):
        if row['Time system'] in ('BJD_TDB','BJD TDB'):
            periods[key(row['System'])].append(decimals((row['Period (days)'],))[0])
    by_target=defaultdict(list)
    aliases=defaultdict(set)
    for line,row in enumerate(csv.DictReader(StringIO(text)),2):
        if row['Reference']!='This work' or row['Time System'] not in ('BJD_TDB','BJD TDB'):
            continue
        y,s=decimals((row['T_mid'],row['Uncertainty (days)']))
        if s<=0:
            raise ValueError('TIMING_REFERENCE_UNCERTAINTY')
        if y<FENCE:
            normalized=key(row['System'])
            by_target[normalized].append((y,s,line))
            aliases[normalized].add(row['System'])
    cases=[r for r in read_json(args.trial)['cases'] if r['used_for']=='confirmation']
    tail=sorted(cases,key=lambda r:(-abs(r['forecasts']['weighted'][0]),r['target']))[:5]
    worst={r['target'] for r in tail}
    results={}
    normalized_names=defaultdict(set)
    host_names=defaultdict(set)
    for name in catalog:
        normalized_names[key(name)].add(name)
        host_names[host_key(name)].add(name)
    for case in cases:
        name=case['target']
        normalized=key(name)
        t,_,p,_=catalog[name]
        eligible=len(aliases[normalized])==len(normalized_names[normalized])==1
        method='exact_name' if eligible else 'unmatched'
        host=host_key(name)
        if (not eligible and len(host_names[host])==1 and len(aliases[host])==len(periods[host])==1
                and abs(periods[host][0]-p)*10_000<=p):
            normalized=host
            eligible=True
            method='unique_host_and_period'
        left=indexed([(y,s,line) for y,s,kind,identifier,line in drc[name]
                      if kind=='space' and identifier.endswith('_TESS')],t,p)
        right=indexed(by_target[normalized],t,p) if eligible else {}
        epochs=sorted(set(left)&set(right))
        flagged=[]
        for epoch in epochs:
            ls,ll,ly=left[epoch]
            rs,rl,ry=right[epoch]
            delta=float(abs(ly-ry))*86400
            sigma=hypot(float(ls),float(rs))*86400
            if delta>60 and delta>3*sigma:
                flagged.append({'epoch':epoch,'disagreement_s':delta,'quadrature_s':sigma,
                                'earlier_locator':f'drc:mid_time:L{ll}','independent_locator':f'table4:L{rl}'})
        results[name]={'matched_epochs':len(epochs),'earlier_epochs':len(left),'independent_epochs':len(right),'matching':method,
                       'flagged':flagged}
    return {'scope':'Exploratory cross-reduction audit on shared earlier TESS events; no new forecast acceptance.',
            'cohort_targets':len(cases),'matched_targets':sum(bool(v['matched_epochs']) for v in results.values()),
            'matched_epochs':sum(v['matched_epochs'] for v in results.values()),
            'exact_name_matched_targets':sum(v['matching']=='exact_name' and bool(v['matched_epochs']) for v in results.values()),
            'host_period_matched_targets':sum(v['matching']=='unique_host_and_period' and bool(v['matched_epochs']) for v in results.values()),
            'disagreeing_epochs':sum(len(v['flagged']) for v in results.values()),
            'top_five_checked':sum(bool(results[name]['matched_epochs']) for name in worst),
            'top_five':{r['target']:results[r['target']] for r in tail},
            'other_flagged':{name:v['flagged'] for name,v in results.items() if name not in worst and v['flagged']},
            'operational_authority':'ABSTAIN'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('sources','elements','older','independent','independent-elements','trial'):
        parser.add_argument('--'+name,type=Path,required=True)
    print(canonical(audit(parser.parse_args())).decode())
