"""Source-bound finite comparison. Never opens a native or real financial account."""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path
import numpy
import scipy
from .inputs import registration, CAMPAIGN
from .construct import construct
from .verify import verify
from .costs import cost_requirements
from .policy import replay

ROOT=Path(__file__).resolve().parents[1]


def closure():
    paths=list((ROOT/'grid_service_envelope').glob('*.py'))+list((ROOT/'tests').glob('test_grid_service_envelope.py'))
    paths+=list((CAMPAIGN/'data').glob('*'))+[CAMPAIGN/'REGISTRATION.json',CAMPAIGN/'AMENDMENT_01.json',ROOT/'requirements-grid-envelope.txt']
    files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    return {'files':files,'sha256':hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()}


def execute(output, role):
    output=Path(output); output.mkdir(parents=True,exist_ok=False)
    frozen=closure(); reg=registration();start=time.time()
    frozen.update(role=role,started_unix=start,python=platform.python_version(),numpy=numpy.__version__,scipy=scipy.__version__)
    (output/'FROZEN.json').write_text(json.dumps(frozen,indent=2)+'\n')
    days=reg['development_days'] if role=='development' else reg['confirmation_days']
    rows=[]
    for day in days:
        for site in reg['buses']:
            for scale in reg['it_capacity_mw']:
                for control in ('primary','no_equipment','fixed_work'):
                    key=f'{day}-{site}-{scale}-{control}'
                    w=construct(CAMPAIGN/'data',day,site,scale,control)
                    receipt=verify(w,CAMPAIGN/'data')
                    w['accepted']=receipt['accepted']
                    raw=json.dumps(w,separators=(',',':'))+'\n'
                    (output/(key+'.json')).write_text(raw)
                    row={k:v for k,v in w.items() if k not in ('plans','work','thermal_commitment')}
                    row['witness_sha256']=hashlib.sha256(raw.encode()).hexdigest()
                    row['independent_check']={k:v for k,v in receipt.items() if k!='checks'}
                    row['checks_executed']=len(receipt['checks'])
                    row['max_check_residual']=max((float(v['detail']) for v in receipt['checks'].values() if isinstance(v.get('detail'),(int,float))),default=None)
                    if w['accepted']:
                        row['costs']=cost_requirements(w)
                        row['policy_replay']=replay(w)
                    if control=='primary':
                        row['ordinary_complete_route']={'accepted':w['accepted'],'same_feasible_set_and_information':True,'same_equipment_and_cost_permissions':True,'same_plan_available':w['accepted'],'comparison':'Analytic identity under equal permissions; no claim of independent solver-performance superiority','residual_verdict':'REJECTED_BY_ORDINARY_COMPLETE_ROUTE' if w['accepted'] else 'NOT_ESTABLISHED'}
                    rows.append(row)
                    (output/'ROWS.json').write_text(json.dumps(rows,indent=2)+'\n')
                    print(json.dumps({'case':key,'solver_status':w['solver_status'],'independently_accepted':w['accepted'],'error':receipt.get('error'),'seconds':w['elapsed_seconds']}),flush=True)
                    if closure()['sha256'] != frozen['sha256']:raise RuntimeError('Source changed during comparison; retain incomplete output')
    primary=[r for r in rows if r['control']=='primary']
    summary={'role':role,'source_sha256':frozen['sha256'],'completed':True,'rows':len(rows),'primary_count':len(primary),'primary_accepted':sum(r['accepted'] for r in primary),'solver_infeasible_count':sum(r['solver_status']==2 for r in rows),'unverified_infeasibility_note':'Solver-reported within restricted fixed-commitment policy; no independent Farkas/MIP infeasibility proof or physical impossibility claim','ordinary_same_outcome_same_budget':sum(r['accepted'] for r in primary),'blue_sky_admitted':False,'commercial_qualified':False,'real_profit':None,'elapsed_seconds':time.time()-start,'verdict':'No new enabling residual established; ordinary complete route matches every accepted constructed case. Physical, rights, demand and finance qualification unresolved.'}
    (output/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
    return summary


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--role',choices=('development','confirmation','reproduction'),required=True);args=p.parse_args();execute(args.output,args.role)
if __name__=='__main__':main()
