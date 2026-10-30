"""Illustrative human-versus-frontier-AI unit economics; not commercial evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

COST_FIELDS = ('tools_usd','rework_usd','acquisition_usd','development_allocation_usd','support_risk_usd')
CASE_FIELDS = {'id','outcome','role','human_hours','model','input_tokens','output_tokens','ai_review_hours',*COST_FIELDS,'assumed_price_usd'}
MONEY = Decimal('0.01')

def d(value):
    if type(value) not in (str,int,float) or isinstance(value, bool):
        raise ValueError('Expected a finite decimal amount')
    try: x = Decimal(str(value))
    except InvalidOperation as exc: raise ValueError('Invalid decimal') from exc
    if not x.is_finite() or x < 0: raise ValueError('Nonfinite or negative amount')
    return x

def usd(x): return str(x.quantize(MONEY, rounding=ROUND_HALF_UP))
def sha(obj): return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def analyze(data):
    if not isinstance(data,dict) or set(data)!={'metadata','wage_burden','roles','models','cases'}:
        raise ValueError('Unexpected top-level benchmark structure')
    m=data['metadata']
    if m.get('evidence_status')!='ILLUSTRATIVE_UNVALIDATED' or m.get('same_outcome_independently_verified') is not False or m.get('actual_sales')!=0:
        raise ValueError('The study cannot imply measured acceptance or sales')
    burden=data['wage_burden']; ratio=d(burden['employer_cost_per_hour'])/d(burden['wage_salary_per_hour'])
    if not (Decimal('1')<=ratio<=Decimal('3')): raise ValueError('Invalid benefits multiplier')
    if not isinstance(data['cases'],list) or not data['cases']: raise ValueError('No cases')
    seen=set(); out=[]
    for c in data['cases']:
        if not isinstance(c,dict) or set(c)!=CASE_FIELDS: raise ValueError('Case does not match fixed schema')
        name=c['id']; role=c['role']; model=c['model']
        if not isinstance(name,str) or not name or name in seen: raise ValueError('Bad or duplicate ID')
        if not isinstance(c['outcome'],str) or not c['outcome']: raise ValueError('Outcome required')
        seen.add(name)
        if role not in data['roles'] or model not in data['models']: raise ValueError('Missing role or model rate')
        for k in ('input_tokens','output_tokens'):
            if type(c[k]) is not int or c[k]<0 or c[k]>10000000: raise ValueError('Invalid token count')
        hours=d(c['human_hours']); review=d(c['ai_review_hours'])
        if not (hours>0 and review>=0): raise ValueError('Invalid hours')
        wage=d(data['roles'][role]['wage_usd_per_hour']); loaded=wage*ratio
        H=hours*loaded
        r=data['models'][model]
        tokens=(Decimal(c['input_tokens'])*d(r['input_usd_per_million'])+
                Decimal(c['output_tokens'])*d(r['output_usd_per_million']))/Decimal(1000000)
        review_cost=review*loaded
        extras=sum((d(c[k]) for k in COST_FIELDS),Decimal(0))
        A=tokens+review_cost+extras
        price=d(c['assumed_price_usd'])
        out.append({'id':name,'outcome':c['outcome'],'human_role':role,
                    'human_hours_assumed':str(hours),'frontier_model':model,
                    'human_loaded_hourly_usd':usd(loaded),'human_loaded_labor_usd':usd(H),
                    'ai_model_token_usd':usd(tokens),'ai_review_labor_usd':usd(review_cost),
                    'ai_other_costs_usd':usd(extras),'ai_total_modeled_usd':usd(A),
                    'assumed_sale_price_usd':usd(price),
                    'human_labor_only_contribution_at_price_usd':usd(price-H),
                    'ai_modeled_contribution_at_price_usd':usd(price-A),
                    'human_minus_ai_modeled_cost_usd':usd(H-A),
                    'quality_and_same_outcome_verified':False,
                    'commercial_conclusion':'ILLUSTRATIVE_ONLY'})
    return {'schema':'alpha-human-frontier-benchmark/v1','inputs_sha256':sha(data),'wage_loading_factor':str(ratio),
            'comparison_priority':'PRIMARY_HUMAN_FULLY_LOADED_LABOR_VS_FRONTIER_AI_OPERATION',
            'secondary_comparators':['human_delivered_ai_assisted_service','competent_alternative_autonomous_ai','no_launch'],
            'caveat':'Human task hours, AI tokens, review, rates and offered price are scenario assumptions. Wage benchmarks and published model tariffs are sourced. Human wage excludes business overhead; AI other categories are illustrative allowances, not complete observed costs.',
            'cost_status':'NOT_MEASURED','actual_customer_receipts_usd':'0','all_outcomes_confirmed':False,
            'commercial_success':'UNESTABLISHED','full_invention_flywheel':'UNESTABLISHED','cases':out}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',default=str(Path(__file__).with_name('illustrative_cases.json')))
    ap.add_argument('--output',required=True)
    args=ap.parse_args()
    out=Path(args.output)
    try:
        if out.exists(): raise FileExistsError('Preserve prior output: target already exists')
        inp=Path(args.input)
        if inp.stat().st_size>1000000: raise ValueError('Input exceeds 1 MB')
        result=analyze(json.loads(inp.read_text()))
        with out.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2,ensure_ascii=False);f.write('\n')
    except (OSError, ValueError, TypeError, InvalidOperation) as exc: ap.exit(2,f'REFUSED: {exc}\n')
    print('Wrote '+str(out)+'; hypothetical comparisons only; no validated profit')
if __name__=='__main__': main()
