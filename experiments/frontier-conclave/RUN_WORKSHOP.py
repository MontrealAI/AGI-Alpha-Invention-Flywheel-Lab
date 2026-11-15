#!/usr/bin/env python3
"""Omega.001 offline adapter, using the unmodified released HARNESS evaluator."""
import argparse,json,sys
from pathlib import Path
from vendor.instruments import evaluate,strict_portable_json
ROOT=Path(__file__).resolve().parent
NUMS=('cap_a','cap_b','cap_c','a','b','c','cost','contingency')
CONS=('consent_a','consent_b','consent_c')
def load(path): return strict_portable_json(Path(path).read_text(encoding='utf-8'))
def run(data,spec=None):
    if not isinstance(data,dict) or set(data)!=set(NUMS+CONS): raise ValueError('Require exactly the declared input fields.')
    for k in NUMS:
        if type(data[k]) is not int or abs(data[k])>1000000000: raise ValueError(k+': integer units within +/-1 billion required; booleans are not numbers.')
    for k in CONS:
        if type(data[k]) is not bool: raise ValueError(k+': explicit boolean required.')
    result=evaluate(spec if spec is not None else load(ROOT/'instrument.json'),data)['output']
    expected=oracle(data)
    if set(result)!=set(expected) or any(type(result[k]) is not type(expected[k]) for k in expected): raise ValueError('Exact output fields and integer/boolean types required.')
    return result
def oracle(v):
    total=v['a']+v['b']+v['c'];required=v['cost']+v['contingency']
    caps=all(v[k]<=v['cap_'+k] for k in ('a','b','c'));consent=all(v[k] for k in CONS)
    return dict(total=total,required=required,gap=max(0,required-total),surplus=max(0,total-required),within_caps=caps,all_consent=consent,accepted=all(v[k]>=0 for k in NUMS) and caps and consent and total>=required,capacity_sufficient=sum(v['cap_'+k] for k in ('a','b','c'))>=required)
def check(spec=None):
    rows=load(ROOT/'development-cases.json')+load(ROOT/'challenge-cases.json')
    results=[{'name':r['name'],'passed':run(r['input'],spec)==oracle(r['input'])} for r in rows]
    return {'mode':'prepared-reference regression; challenge cases are disclosed in this kit','passed':sum(x['passed'] for x in results),'total':len(results),'results':results}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['check','run']);ap.add_argument('input',nargs='?');ap.add_argument('--instrument',type=Path);a=ap.parse_args()
    try:
        spec=load(a.instrument) if a.instrument else None
        result=check(spec) if a.action=='check' else run(load(a.input),spec)
        print(json.dumps(result,indent=2,allow_nan=False))
        return 1 if a.action=='check' and result['passed']!=result['total'] else 0
    except (ValueError,TypeError,OSError) as e:
        print(json.dumps({'error':str(e),'accepted':False}));return 2
if __name__=='__main__': sys.exit(main())
