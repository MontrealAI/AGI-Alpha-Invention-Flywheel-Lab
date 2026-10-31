#!/usr/bin/env python3
"""Reconcile every preregistered public pair without selecting favorable cases."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def summarize(root):
    rows=[json.loads(p.read_text()) for p in sorted(root.rglob('SUMMARY.json'))]
    expected={('smoke','central',2610311624,a) for a in ('incumbent','joint')}
    expected|={('scale',c,s,a) for c in ('central','parity','adverse') for s in (2610311601,2610311602) for a in ('incumbent','joint')}
    found={};errors=[]
    for r in rows:
        key=tuple(r.get(k) for k in ('stage','case','seed','arm'))
        if key not in expected or key in found:errors.append('UNEXPECTED_OR_DUPLICATE:'+str(key))
        found[key]=r
        for field in ('protocol','config'):
            if field not in r or not r.get(field+'_sha256') or digest(r.get(field))!=r.get(field+'_sha256'):
                errors.append(field.upper()+'_DIGEST_MISMATCH:'+str(key))
        if r.get('status')=='COMPLETED':
            summary=r.get('summary',{})
            if any(type(summary.get(k)) is not int for k in ('profit','revenue','expenses')) or summary.get('profit')!=summary.get('revenue',0)-summary.get('expenses',0):
                errors.append('PROFIT_IDENTITY_MISMATCH:'+str(key))
        if r.get('status')!='COMPLETED' or not r.get('complete') or not r.get('audit',{}).get('accepted'):
            errors.append('INCOMPLETE_OR_REJECTED:'+str(key))
    errors.extend('MISSING:'+str(k) for k in sorted(expected-set(found)))
    if len({r.get('checkout_commit') for r in rows})!=1 or any(not r.get('checkout_commit') for r in rows):errors.append('CHECKOUT_COMMIT_MISMATCH')
    if len({r.get('protocol_sha256') for r in rows})!=1:errors.append('PROTOCOL_MISMATCH')
    if len({digest(r.get('source')) for r in rows})!=1 or any(not r.get('source') for r in rows):errors.append('ALL_RUN_RUNTIME_SOURCE_MISMATCH')
    if len({r.get('runner_sha256') for r in rows})!=1 or any(not r.get('runner_sha256') for r in rows):errors.append('RUNNER_SOURCE_MISMATCH')
    pairs=[]
    for stage,case,seed in sorted({k[:3] for k in expected}):
        left=found.get((stage,case,seed,'incumbent'));right=found.get((stage,case,seed,'joint'))
        if not left or not right or left.get('status')!='COMPLETED' or right.get('status')!='COMPLETED':continue
        lcfg=dict(left['config']);rcfg=dict(right['config'])
        for key in ('mechanism_policy','strategic_policy','strategic_allocation_policy'):rcfg.pop(key,None)
        rcfg['setup_cost']-=5000000;rcfg['qualification_cost']-=50000
        if lcfg!=rcfg:errors.append('MARKET_OR_CAPITAL_PAIR_MISMATCH:'+str((stage,case,seed)))
        if left['source']!=right['source']:errors.append('RUNTIME_SOURCE_PAIR_MISMATCH:'+str((stage,case,seed)))
        lp=left['summary']['profit'];rp=right['summary']['profit']
        pairs.append({'stage':stage,'case':case,'seed':seed,'incumbent_profit_microUSD':lp,'joint_profit_microUSD':rp,
          'paired_profit_difference_microUSD':rp-lp,'incumbent_paid':left['paid_jobs'],'joint_paid':right['paid_jobs'],
          'incumbent_conditional_gate':left['conditional_simulated_commercial_success'],
          'joint_conditional_gate':right['conditional_simulated_commercial_success']})
    return {'schema':'strategic024-public-pair-comparison/v1','complete':not errors,'errors':errors,'pairs':pairs,
      'expected_runs':len(expected),'received_runs':len(rows),'checkout_commit':rows[0].get('checkout_commit') if rows else None,
      'scope':'Separate paired simulated enterprises; no pooled business, annualization, global optimality or actual commerce claim. Compact in-job audit evidence is not portable independent financial reproduction.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=summarize(a.input);a.output.mkdir(parents=True,exist_ok=True);(a.output/'COMPARISON.json').write_text(json.dumps(r,sort_keys=True,indent=2)+'\n')
    text=['## Fixed paired commercial comparison','Complete: '+str(r['complete']),r['scope']]
    for x in r['pairs']:
        text.append('- %s / %s / %s: incumbent $%.6f, joint $%.6f, paired difference $%.6f; paid %s → %s.' % (x['stage'],x['case'],x['seed'],x['incumbent_profit_microUSD']/1e6,x['joint_profit_microUSD']/1e6,x['paired_profit_difference_microUSD']/1e6,x['incumbent_paid'],x['joint_paid']))
    text.extend(r['errors']);md='\n'.join(text)+'\n';(a.output/'COMPARISON.md').write_text(md)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:f.write(md)
    print(md)
    if not r['complete']:raise SystemExit(1)

if __name__=='__main__':main()
