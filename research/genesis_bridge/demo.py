"""Finite registered integration demonstration, not a commercial simulation."""
import argparse,copy,json,pathlib,statistics
from .core import ROOT,read,save,digest,request,probe,plan,execute,retain,reuse,verify_sources,accept,execute_from_design
CONTEXT={'domain':'synthetic_homogeneous_nonmedical_rod','gain_model':'constant_bounded_per_session',
         'sense_geometry':'fixed_fraction_half','calibration':'authored_bounds_not_physical','output_class':'bulk_contact_change'}

def fixture_request(case,op='analyze',inputs=None):
    req=request(op,case['id'],CONTEXT,case['observation'] if inputs is None else inputs)
    return req,{'request_sha256':digest(req),'truth':case['truth'],'registration':'campaign/genesis-execution-bridge/FIXTURES.json'}

def run_demo(out):
    out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=False)
    cases=read(ROOT/'campaign/genesis-execution-bridge/FIXTURES.json');canary=cases[0]
    observation=read(ROOT/'campaign/genesis-execution-bridge/OBSERVATION.json')
    req,fx=fixture_request(canary);p=probe(req,fx,out/'probe')
    before=plan(observation,[]);after=plan(observation,[p])
    save(out/'plan-before-probe.json',before);save(out/'plan-after-probe.json',after)
    if before['proposal'] is not None or after['proposal'] is None:raise AssertionError('access gate')
    # Execute the proposed route. No label in the plan is accepted as execution.
    available=set(after['available_capabilities']);route=[]
    missing=copy.deepcopy(canary['observation'])
    for phase in ('baseline','after'):
        for row in missing[phase]['records']:row['v4']=None
    for op in after['proposal']['operations']:
        spec=next(x for x in after['scenario']['operations'] if x['id']==op)
        if not set(spec['requires'])<=available:break
        if op=='compile':
            design={'maximum_current_A':.001,'maximum_specimen_power_W':.001,'maximum_bulk_ohm':40,'current_menu_A':[.0005,.001]}
            q=request(op,'design-001',CONTEXT,design);f={'request_sha256':digest(q)}
        else:q,f=fixture_request(canary,inputs=missing)
        if op=='compile':
            r,a=execute(q,out/('route-'+op),f);design_proof=(q,r,f)
        else:r,a=execute_from_design(q,out/('route-'+op),f,*design_proof)
        route.append({'operation':op,'acceptance':a,'receipt_sha256':digest(r)})
        if a['status']=='PASS':available.update(spec['provides'])
        else:break
    if 'accepted_analysis' in available:raise AssertionError('abstention promoted capability')
    replay_req,replay_fx=fixture_request(canary,'replay',{'previous':missing,'current':canary['observation']})
    rr,ra=execute(replay_req,out/'replay',replay_fx)
    if ra['status']!='PASS':raise AssertionError('same-context replay must pass frozen canary')
    method=retain(replay_req,rr,replay_fx);save(out/'method.json',method)
    rows=[]
    # Matched inputs/content, independently implemented direct comparator and identical-kernel ordinary reuse.
    for case in cases[1:]:
        q,f=fixture_request(case)
        r,a=reuse(method,replay_req,rr,replay_fx,q,out/(case['id']+'-retained'),f)
        rows.append({'case':case['id'],'arm':'retained','acceptance':a['status'],'cpu_seconds':r['worker']['cpu_seconds'],'wall_seconds':r['wall_seconds'],'output_sha256':r['worker']['output_sha256']})
        for arm in ('ordinary','direct'):
            q,f=fixture_request(case,arm);r,a=execute(q,out/(case['id']+'-'+arm),f)
            rows.append({'case':case['id'],'arm':arm,'acceptance':a['status'],'cpu_seconds':r['worker']['cpu_seconds'],'wall_seconds':r['wall_seconds'],'output_sha256':r['worker']['output_sha256']})
    summary={'scope':'offline source-bound synthetic execution bridge','source_lock_sha256':verify_sources(),
             'metadata_only_plan':before['proposal'],'probed_plan':after['proposal'],'route':route,
             'actual_capabilities_after_route':sorted(available),'replay_acceptance':ra,'successors':rows,
             'method_retained':True,'same_kernel_equal_outputs':all(next(r for r in rows if r['case']==c['id'] and r['arm']=='retained')['output_sha256']==next(r for r in rows if r['case']==c['id'] and r['arm']=='ordinary')['output_sha256'] for c in cases[1:]),
             'commercial_profit':None,'discovery_improvement':'NOT_ESTABLISHED','physical_validation':'NOT_ESTABLISHED',
             'limits':'Developer-authored adapters and frozen synthetic truths. Fresh instances of same output class. No independent external certification. Timing descriptive, not causal speed claim. Full economic costs unknown.'}
    save(out/'SUMMARY.json',summary);return summary

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args()
    r=run_demo(a.out);print(json.dumps({'summary':str(a.out/'SUMMARY.json'),'same_kernel_equal_outputs':r['same_kernel_equal_outputs']}))
if __name__=='__main__':main()
