"""Independent LP replay and deterministic fixture comparison, not plant validation."""
import importlib.util,json,sys
import numpy as np
from water_lp import minimum_store,FIXTURES

def run(path,observed=None):
    spec=importlib.util.spec_from_file_location('water_candidate',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    cases=list((k,p,d) for k,(p,d) in FIXTURES.items())
    for seed in (20261102,20261103,20261104):
      rng=np.random.default_rng(seed)
      for n in (4,24):
       d=rng.uniform(.1,5,n);base=rng.uniform(0,1,n);base*=sum(d)/sum(base)
       for factor in (.8,1.,1.2):cases.append((f'{seed}-{n}-{factor}',(base*factor).tolist(),d.tolist()))
    if observed:
      data=json.load(open(observed))
      for row in data['cases']:
       if row.get('source_hash_ok') and row.get('data_status')!='missing':
        for daily in (500,1000,2000,5000):cases.append((row['name']+f'-{daily}',row['production_l'],[daily/24]*24))
    out=[]
    for name,p,d in cases:
      actual=m.construct(p,d);reference=minimum_store(p,d,True)
      agreement=actual['feasible']==reference['feasible'];gap=None;balance=None
      if actual['feasible'] and reference['feasible']:
        gap=abs(actual['capacity_l']-reference['capacity_l'])
        # Full trajectory accounting independently from total flows.
        balance=abs(actual['terminal_l']-actual['initial_l']-sum(p)+sum(d)+actual['spill_l'])
        agreement=agreement and gap<=1e-6 and balance<=1e-6 and actual['unserved_l']<=1e-8 and actual['terminal_l']>=actual['initial_l']-1e-8
      out.append({'case':name,'pass':bool(agreement),'candidate_feasible':actual['feasible'],'lp_feasible':reference['feasible'],'capacity_gap_l':gap,'balance_error_l':balance})
    return {'pass':all(x['pass'] for x in out),'cases':out,'scope':'Linear hourly stock/spill model only. Observed quantities conditional on parser and quality validity; no potable service, linear plant replication, or commercial acceptance validated.'}
if __name__=='__main__':print(json.dumps(run(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None),indent=2))
