"""Frozen phase-two diagnostic driver; labels never enter worker requests."""
import time
run_start = time.perf_counter()
import os, sys, argparse, json, hashlib, subprocess, resource
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS'] = '1'; os.environ['OMP_NUM_THREADS'] = '1'
if hasattr(os, 'sched_getaffinity'):
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
p = argparse.ArgumentParser()
p.add_argument('--pristine-extension-dir', required=True)
p.add_argument('--modified-extension-dir', required=True)
p.add_argument('--helper-dir', required=True)
p.add_argument('--deps', required=True)
p.add_argument('--circuit', required=True)
p.add_argument('--output', required=True)
p.add_argument('--competence-anchor', action='store_true')
a = p.parse_args()
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(a.deps).resolve()))
import_start = time.perf_counter()
import stim, numpy as np
from diagnostic_common import Fallback, mask
imports_seconds = time.perf_counter()-import_start
prep_start = time.perf_counter()
circuit = stim.Circuit.from_file(a.circuit)
dem = circuit.detector_error_model(decompose_errors=False)
fallback = Fallback(dem)
# Select and retain only twenty registered shots in RAM. No syndrome archive.
cases = []
sampler = circuit.compile_detector_sampler(seed=2026110102)
for index in range(9):
    detectors, observables = sampler.sample(1, separate_observables=True)
    if index in (0, 1, 2, 8):
        cases.append({'group': 'development', 'seed': 2026110102, 'shot': index,
                      'detectors': detectors[0].nonzero()[0].tolist(),
                      'truth': mask(observables[0].nonzero()[0])})
sampler = circuit.compile_detector_sampler(seed=2026110201)
for index in range(16):
    detectors, observables = sampler.sample(1, separate_observables=True)
    cases.append({'group': 'fresh', 'seed': 2026110201, 'shot': index,
                  'detectors': detectors[0].nonzero()[0].tolist(),
                  'truth': mask(observables[0].nonzero()[0])})
for case in cases:
    case['fallback'] = fallback.solve(mask(case['detectors']))
prep_seconds = time.perf_counter()-prep_start
extension_provenance = {}
for name, directory in [('pristine',a.pristine_extension_dir),('modified',a.modified_extension_dir)]:
    extension_provenance[name] = [{'path':str(f.resolve()),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
                                  for f in Path(directory).resolve().glob('tesseract_decoder*.so')]
variants = ['A', 'B', 'C']
records = []; witnesses = []; stop_reason = None; anchor_records = []

def run_one(case, variant):
    remaining = 900 - (time.perf_counter()-run_start)
    if remaining <= 0:
        return None
    extension = a.modified_extension_dir if variant == 'C' else a.pristine_extension_dir
    command = [sys.executable, str(HERE/'matched_worker.py'), '--variant', variant,
               '--extension-dir', extension, '--helper-dir', a.helper_dir,
               '--deps', a.deps, '--circuit', a.circuit]
    started = time.perf_counter(); response = None
    timeout = min(45.0, remaining)
    try:
        process = subprocess.run(command, input=json.dumps({'detectors': case['detectors']}),
                                 capture_output=True, text=True, timeout=timeout, env=os.environ)
        lines = [line for line in process.stdout.splitlines() if line.strip()]
        if lines:
            response = json.loads(lines[-1])
        if response is None:
            response = {'status': 'error', 'error': 'Worker returned no JSON',
                        'returncode': process.returncode, 'stderr': process.stderr[-1000:]}
        elif process.returncode and response.get('status') == 'complete':
            response = {'status': 'error', 'error': 'Nonzero worker exit after result',
                        'returncode': process.returncode}
    except subprocess.TimeoutExpired:
        response = {'status': 'timeout', 'timeout_seconds': timeout}
    except Exception as exc:
        response = {'status': 'error', 'error': type(exc).__name__+': '+str(exc)}
    response['subprocess_seconds'] = time.perf_counter()-started
    if response['status'] != 'complete':
        response.update({'fallback': True,
                         'minimum_prediction': case['fallback']['logical'],
                         'mass_prediction': case['fallback']['logical'],
                         'candidate_count': 1, 'classes': 1})
    # True observable is consulted only here, after all decoder/fallback decisions.
    response['minimum_failure'] = response['minimum_prediction'] != case['truth']
    response['mass_failure'] = response['mass_prediction'] != case['truth']
    response['case_group'] = case['group']; response['case_shot'] = case['shot']
    response['variant'] = variant
    if variant == 'C' and response.get('classes', 0) > 1 and len(witnesses) < 8:
        witnesses.append({'group': case['group'], 'shot': case['shot'], 'seed': case['seed'],
                          'detectors': case['detectors'], 'truth_for_scoring_only': case['truth'],
                          'minimum_prediction': response['minimum_prediction'],
                          'mass_prediction': response['mass_prediction'],
                          'candidates': response.get('candidates', [])})
    # Drop full configurations after optional compact witness capture.
    response.pop('candidates', None)
    return response

def summarize(items, planned):
    values = [x for x in items if x['status'] == 'complete']
    result = {'planned_calls': planned, 'attempted': len(items),
              'never_run': planned-len(items), 'complete': len(values),
              'timeouts': sum(x['status']=='timeout' for x in items),
              'errors': sum(x['status']=='error' for x in items),
              'fallback_calls': sum(x.get('fallback', False) for x in items),
              'search_failure_calls': sum(x.get('fallback', False) for x in values),
              'minimum_failures_including_fallback': sum(x['minimum_failure'] for x in items),
              'mass_failures_including_fallback': sum(x['mass_failure'] for x in items),
              'decision_disagreements': sum(x['minimum_prediction']!=x['mass_prediction'] for x in items),
              'mass_only_wins': sum(x['minimum_failure'] and not x['mass_failure'] for x in items),
              'mass_only_losses': sum(x['mass_failure'] and not x['minimum_failure'] for x in items),
              'multilogical_pools': sum(x.get('classes',1)>1 for x in values),
              'max_candidate_count': max((x.get('candidate_count',0) for x in values), default=0),
              'candidate_count_sum': sum(x.get('candidate_count',0) for x in values),
              'low_confidence_calls': sum(x.get('low_confidence',False) for x in values),
              'invalid_candidates': sum(x.get('invalid_candidates',0) for x in values),
              'actual_configs': [json.loads(v) for v in sorted({json.dumps(x['actual_config'],sort_keys=True) for x in values})],
              'rejected_completed_shots': 0}
    for key in ['subprocess_seconds','worker_seconds','import_seconds','prep_seconds',
                'decode_seconds','validation_fallback_reduction_seconds','maxrss_kib',
                'first_goal_cost','final_min_cost','first_goal_seconds','final_collection_seconds',
                'cost_improvement_after_first']:
        series = [x[key] for x in items if key in x and x[key] is not None]
        result[key] = {'sum': sum(series), 'median': float(np.median(series)),
                       'max': max(series), 'count': len(series)} if series else None
    result['search_work'] = {}
    for key in ['pushed','popped','expanded','max_queue','max_arena','raw_goals','duplicate_goals']:
        series = [x['work'][key] for x in values if x.get('work') is not None]
        result['search_work'][key] = {'sum': sum(series), 'max': max(series)} if series else 'unknown'
    result['class_count_histogram'] = {}
    for x in values:
        key=str(x.get('classes',1))
        result['class_count_histogram'][key]=result['class_count_histogram'].get(key,0)+1
    result['stop_reasons'] = {}
    for x in values:
        reason = x['work']['stop_reason'] if x.get('work') else 'legacy_first_goal_or_failure'
        result['stop_reasons'][reason] = result['stop_reasons'].get(reason,0)+1
    return result

def save():
    output = {'protocol': 'phase2 frozen candidate-generation diagnostic, not confirmation',
              'protocol_sha256': hashlib.sha256((HERE/'FROZEN_PROTOCOL.md').read_bytes()).hexdigest(),
              'circuit_sha256': hashlib.sha256(Path(a.circuit).read_bytes()).hexdigest(),
              'dem_sha256': hashlib.sha256(str(dem).encode()).hexdigest(),
              'extension_provenance':extension_provenance,
              'registered_cases': {'development_seed':2026110102,'development_indices':[0,1,2,8],
                                   'fresh_seed':2026110201,'fresh_shots':16,'sample_batch':1},
              'settings': {'order':0,'beam':5,'pqlimit':200000,'list_goal_cap':64,
                           'whole_worker_timeout_seconds':45,'total_seconds_cap':900,
                           'address_space_bytes':2*1024**3,'variant_order':['A','B','C']},
              'driver_import_seconds':imports_seconds,'driver_prep_seconds':prep_seconds,
              'elapsed_seconds':time.perf_counter()-run_start,'stop_reason':stop_reason,
              'variants': {v:summarize([x for x in records if x['variant']==v],20) for v in variants},
              'competence_anchor':summarize(anchor_records,4) if a.competence_anchor else 'not_requested',
              'compact_witnesses':witnesses,
              'errors':[{'variant':x['variant'],'group':x['case_group'],'shot':x['case_shot'],
                         'error':x.get('error')} for x in records+anchor_records if x['status']=='error'],
              'limitations':['Finite-pool mass, not entire logical coset',
                             'Baseline push/pop counts unknown without separate telemetry replay',
                             'Equal push ceiling is not equal actual work',
                             'Shared CPU and twenty shots do not establish tail-latency superiority',
                             'Whole-worker timeout includes import/preparation and is not intrinsic decode time',
                             'No hardware validation or profit evidence']}
    Path(a.output).write_text(json.dumps(output,indent=2))

for case in cases:
    for variant in variants:
        result = run_one(case,variant)
        if result is None:
            stop_reason='total_time_cap';break
        records.append(result)
        print(json.dumps({k:result.get(k) for k in ['variant','case_group','case_shot','status',
                       'fallback','candidate_count','classes','subprocess_seconds']}),flush=True)
        if result['status']=='error':
            stop_reason='correctness_or_worker_error';break
        save()
    if stop_reason:break
if not stop_reason and a.competence_anchor:
    for case in cases[:4]:
        # Optional competence anchor never displaces registered main diagnostic calls.
        if 900-(time.perf_counter()-run_start)<45:
            break
        result=run_one(case,'anchor')
        if result is None:break
        anchor_records.append(result)
        if result['status']=='error':
            stop_reason='competence_anchor_worker_error';break
if not stop_reason:
    multilogical=sum(x.get('classes',1)>1 for x in records if x['variant']=='C')
    list_calls=[x for x in records if x['variant']=='C']
    majority_fallback=sum(x.get('fallback',False) for x in list_calls)>len(list_calls)/2
    if majority_fallback:stop_reason='finished_majority_list_fallback_stop_branch'
    else:stop_reason='finished_with_multilogical_pool' if multilogical else 'finished_no_competing_classes_stop_branch'
save()
