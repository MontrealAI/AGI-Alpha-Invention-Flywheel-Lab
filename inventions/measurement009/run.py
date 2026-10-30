import argparse
import hashlib
import itertools
import json
from fractions import Fraction
from pathlib import Path
import time
from .model import canonical, digest, simulate
from .compiler import compile_plan, diagnose, synthesize_operator, uncalibrated_witness, evaluate_expression, ObservationInterpreter

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')

def observations(corpus, plan, source, outages=(), phase=0):
    i = corpus['sources'].index(source)
    trace, refs = {}, {}
    epsilon = Fraction(plan['noise_bound_pp'])
    for k, sensor in enumerate(corpus['nodes']):
        if sensor not in plan['sensors'] or sensor in outages:
            continue
        bias = Fraction(37*(k+1), 3)
        ref_error = epsilon if (k+phase)%2 else -epsilon
        refs[sensor] = str(bias+ref_error)
        trace[sensor] = [str(Fraction(str(row[k]))+bias+(epsilon if (t+k+phase)%2 else -epsilon)) for t,row in enumerate(corpus['signal'][i])]
    return {'trace': trace, 'reference': refs, 'outages': list(outages), 'known_zero_valid': True, 'offset_constant': True,
        'simulation': 'Deterministic authored boundary-noise probes; not protected confirmation or physical acquisition.'}

def boundary_regressions():
    corpus = {'schema': 'agi-alpha/measurement-corpus009/v1', 'network': 'unit-boundary', 'nodes': ['a','b'],
        'sources': ['left','right'], 'times_seconds': [0,1], 'units': 'source_contribution_percentage_points',
        'network_sha256': 'authored-regression-not-EPA', 'signal': [[[0,0],[0,0]],[[3,3],[3,3]]]}
    corrected = compile_plan(corpus, max_sensor_erasures=0)
    naive = compile_plan(corpus, max_sensor_erasures=0, operator='naive-offset-free')
    results = {'reference_error_counted': corrected['status']=='INFEASIBLE' and naive['status']=='CONSTRUCTED_MODEL_PLAN',
        'no_reference_is_missing_primitive': synthesize_operator(('read',))['status']=='MISSING_PRIMITIVE',
        'time_difference_does_not_preserve_absolute_source_response': synthesize_operator(('read','previous_read'))['status']=='MISSING_PRIMITIVE'}
    try:
        evaluate_expression({'op':'eval','code':'anything'}, {}, 'a', 0)
    except ValueError:
        results['unqualified_ast_rejected'] = True
    else:
        results['unqualified_ast_rejected'] = False
    if not all(results.values()):
        raise AssertionError(results)
    return {'schema':'agi-alpha/measurement009/engineering-regressions-v1','checks':results,
        'scope':'Small authored arithmetic/representation witnesses, not selected service cohort.'}

def execute(network, out):
    model = simulate(network, out/'model')
    corpus = model
    plans = {}
    for name, algorithm, operator in [('no_reference','milp','uncalibrated-time-trace'),
            ('generated','milp','known-zero-reference'),('ordinary_greedy','greedy','known-zero-reference'),
            ('ordinary_exact','exhaustive' if len(corpus['nodes'])<=16 else 'milp','known-zero-reference')]:
        plans[name] = compile_plan(corpus, algorithm=algorithm, operator=operator)
        write(out/(name+'_plan.json'), plans[name])
    witness = uncalibrated_witness(corpus)
    write(out/'uncalibrated_two_truth_witness.json', witness)
    generated = plans['generated']; replay=[]
    if generated['status']=='CONSTRUCTED_MODEL_PLAN':
        interpreter=ObservationInterpreter(corpus,generated)
        for source in corpus['sources']:
            for lost in [(), *[(sensor,) for sensor in generated['sensors']]]:
                record = observations(corpus,generated,source,lost)
                result = interpreter.diagnose(record)
                replay.append({'source':source,'outages':list(lost),'status':result['status'],'returned_sources':result['sources'],
                    'observation_sha256':digest(record)})
                if result['status']!='UNIQUE' or result['sources']!=[source]:
                    raise AssertionError(replay[-1])
        first = observations(corpus,generated,corpus['sources'][0])
        write(out/'example_observations.json', first)
        write(out/'example_diagnosis.json', diagnose(corpus,generated,first))
        for flag in ('known_zero_valid','offset_constant'):
            bad = dict(first);bad[flag]=False
            result=diagnose(corpus,generated,bad)
            if result['status']!='ASSUMPTIONS_UNQUALIFIED':
                raise AssertionError(flag)
            replay.append({'negative_control':flag,'status':result['status']})
    write(out/'development_replay.json', {'schema':'agi-alpha/measurement009/development-replay-v1','cases':replay,
        'scope':'Builder-visible engineering replay with deterministic boundary noises; not protected confirmation.'})
    summary={'network':network,'sources':len(corpus['sources']),'sensors':len(corpus['nodes']),
        'corpus_sha256':digest(corpus),'all_sensor_uncalibrated_obstruction':witness['status'],
        'plans':{name:{'status':p['status'],'sensors':p['sensors'],'solver':p['solver'],'construction_cost':p['construction_cost']} for name,p in plans.items()},
        'technical_scope':'Constructed missing calibrated-reference operator in authored finite model. A physical zero reference and offset stability are added information, not obtained evidence.',
        'novelty':'NOT_ESTABLISHED; strong ordinary exact/MILP receives identical calibration information.',
        'commerce':'Not measured by this program; no orders, production acquisition or earned funds.'}
    write(out/'RESULT.json',summary)
    return summary

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--networks',nargs='+',choices=['Net1','Net3'],default=['Net1'])
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=False)
    start,own=time.monotonic(),time.process_time()
    write(out/'engineering_regressions.json',boundary_regressions())
    results=[]
    for network in args.networks:
        target=out/network;target.mkdir();results.append(execute(network,target))
    manifest={'schema':'agi-alpha/measurement009/construction-receipt-v1','results':results,
        'wall_seconds':time.monotonic()-start,'process_cpu_seconds':time.process_time()-own,
        'complete_monetary_cost':None,'model_calls':'No model-provider calls made by this program. Source construction occurred in hosted agent session; token billing unavailable.',
        'files':{str(p.relative_to(out)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file()}}
    write(out/'MANIFEST.json',manifest)
    print(json.dumps({'results':results,'wall_seconds':manifest['wall_seconds'],'process_cpu_seconds':manifest['process_cpu_seconds']}))

if __name__=='__main__':
    main()
