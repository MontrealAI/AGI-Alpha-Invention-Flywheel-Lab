"""Regenerate deterministic exact studies. Uses no network, model, or account."""
import argparse,json,hashlib
from dataclasses import asdict,replace
from fractions import Fraction
from itertools import product
from pathlib import Path
from model import Case,Strategy,construct,recourse,financial_path
from oracle import oracle,check_witness,source_check,classify_criticism


def run():
    c=Case(); cases={
        'pre_frontier':replace(c,adapter_cost=6,cash=30),
        'new_frontier':c,
        'technical_only':replace(c,pooling_available=False,cash=30),
        'arrangement_only':replace(c,adapter_available=False,cash=30),
        'profitable_but_unfunded':replace(c,cash=12),
        'no_supplier_acceptance':replace(c,supplier_q_accepted=False,cash=30),
        'quote_at_break_even':replace(c,pooled_q_cost=5,cash=30),
        'additional_supplier_failure':replace(c,include_q_failure=True,cash=30),
        'higher_price_selects_existing_route':replace(c,include_q_failure=True,cash=30,price_per_buyer=12),
    }
    outcomes={}
    for name,case in cases.items():
        result=construct(case); check_witness(case,result)
        outcomes[name]={'input':asdict(case),'result':result,'cash_path':financial_path(case,result),
                        'full_conventional_oracle':oracle(case),
                        'least_technical_cost':oracle(case,financial=False)['cost']}
    rows=[]
    for t,q,b,p in product((0,2,4,6),(1,2,4,6),(10,13,16,20),(6,8,10)):
        case=Case(t,q,b,p);r=construct(case);o=oracle(case);check_witness(case,r)
        rows.append({'input':asdict(case),'decision':r['decision'],'cost':r['cost'],
                     'surplus':r['surplus'],'oracle_cost':None if o is None else o['cost']})
    required=('q1','q2','q3','q4');summary=('q1','q2','q4')
    omission={'required':required,'summary':summary,'fulfilled':summary,
              'summary_only_accepts':set(summary)==set(summary),
              'source_check':source_check(required,summary,summary),
              'legitimate_compression':source_check(required,required,required),
              'irrelevant_criticism':classify_criticism(required,(*required,'appendix'),summary,{'source_id':'appendix','present':False}),
              'false_criticism':classify_criticism(required,required,summary,{'source_id':'q1','present':False}),
              'fabricated_criticism':classify_criticism(required,required,summary,{'source_id':'nonexistent','present':False})}
    s=Strategy(False,False,('P',))
    local=[recourse(s,{'active':(a,),'failed':()}) for a in ('A','B')]
    joint=recourse(s,{'active':('A','B'),'failed':()})
    # A conditional mechanism-cost witness, not monetary savings measured in use.
    inherited={'gross_savings_per_use':2,'transfer_cost':3,'maintenance_cost':1,
               'acquisition_cost':2,'remaining_uses':4,
               'prospective_value':4*2-3-1,'whole_lifecycle_value':4*2-3-1-2,
               'short_horizon_lifecycle_value':1*2-3-1-2,
               'control_can_reconstruct_same_asset':True,
               'empirical_successor_advantage_established':False}
    return {'schema':'surf-exponential/exact-study/v1','kind':'AUTHORED_FINITE_MODEL',
            'actual_customer_receipts':0,'frontier_model_calls':0,'separate_llm_reviewer_invoked':False,
            'source_omission':omission,'noncomposition':{'local':local,'joint':joint,
            'cut':{'clients':['A','B'],'demand':8,'reachable_capacity':4,'deficit':4}},
            'construction_cases':outcomes,'grid':{'cases':len(rows),'admitted':sum(x['decision']=='ADMIT_MODEL' for x in rows),
            'declined':sum(x['decision']=='DECLINE' for x in rows),'all_oracle_checks_passed':True,'rows':rows},
            'critic_dependence':{'wrong_prior':'1/5','miss_rate':'1/4','critics':3,
            'independent_remaining_error':str(Fraction(1,5)*Fraction(1,4)**3),
            'perfectly_correlated_remaining_error':str(Fraction(1,5)*Fraction(1,4))},
            'inheritance_accounting':inherited}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args()
    target=Path(a.out)
    if target.exists():raise SystemExit('Refuse overwrite: choose a new evidence path.')
    r=run();data=(json.dumps(r,indent=2,sort_keys=True)+'\n').encode();target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    print(json.dumps({'cases':r['grid']['cases'],'admitted':r['grid']['admitted'],'declined':r['grid']['declined'],'sha256':hashlib.sha256(data).hexdigest()}))
