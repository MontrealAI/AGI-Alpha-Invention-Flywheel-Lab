"""Summarize the completed condition-specific scientific construction tests."""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from native_experiment import run
from science_substrate import canonical, read_json
from substrate_study import ARMS, evaluate, projection


def emit(path, data):
    path.write_bytes(canonical(data)+b'\n')


def measurement(raw):
    accepted = raw['outcomes'].get('ACCEPT',0)
    return {'accepted':accepted, 'by_cause':raw['outcomes'], 'source_accepted':raw['source_accepted'],
            'source_denominators':raw['source_denominators'], 'unsupported_decisions':raw['unsupported_decisions'],
            'unsupported_within':raw['unsupported_within'], 'worker_ns':sum(row['work_ns'] for row in raw['records'])}


def summary(run_state):
    events = run_state.get('events',[])
    return {'status':run_state['status'], 'attempts':len(events),
            'input_reported':sum(event.get('usage',{}).get('input_tokens') or 0 for event in events),
            'output_reported':sum(event.get('usage',{}).get('output_tokens') or 0 for event in events),
            'charged_output':run_state.get('spent_output',0),
            'reported_calls':sum(bool(event.get('usage')) for event in events),
            'wall_ns':sum(event.get('wall_ns',0) for event in events)}


def evaluated(path, candidate, arm):
    from contextlib import redirect_stdout
    from io import StringIO
    stdout = StringIO()
    with redirect_stdout(stdout):
        evaluate(SimpleNamespace(candidate=path, confirmation=candidate, arm=arm))
    return json.loads(stdout.getvalue())


def named_use(run_state, example):
    if run_state['status']!='SEALED':
        return {'status':'NO_CANDIDATE'}
    source = run_state['result']['source']
    current = run(source, projection(example['input'],'typed'))
    changed = run(source, projection(example['input'],'direct'))
    return {'status':'REQUIRED_FOR_CORRECT_OUTPUT' if current.get('result')==example['expected']
            and changed.get('result')!=example['expected'] else 'USE_NOT_SHOWN',
            'scope':'one submitted candidate on a development case; equal-content encoding withdrawal',
            'named':current,'positional':changed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runtime',type=Path,help='directory with frozen constructor and evaluator files')
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    registry, output = args.runtime, args.output
    confirmation = registry/'evaluation/CONFIRMATION.json'
    development = registry/'constructor/DEVELOPMENT.json'
    evidence = {}
    results = {}
    winners = {}
    for model, prefix in (('qwen3-8b-q4-k-m',''), ('qwen3-4b-instruct-2507-q4_k_m','model4-')):
        arms = {}
        for arm in ARMS:
            path = registry/(prefix+arm+'.json')
            if not path.is_file() or path.stat().st_size==0:
                continue
            run_state = read_json(path)
            if run_state['status']=='RUNNING':
                continue
            held, dev = evaluated(path,confirmation,arm), evaluated(path,development,arm)
            entry = {'run':run_state,'confirmation':held,'development':dev}
            arms[arm] = {**summary(run_state), 'development':measurement(dev),'confirmation':measurement(held)}
            if arm=='typed':
                arms[arm]['named_use'] = named_use(run_state,read_json(development)[0])
            evidence[model+'/'+arm] = entry
        results[model] = arms
        # A baseline that could not complete construction cannot establish a causal effect.
        paired = set(arms)==set(ARMS) and all(v['status']=='SEALED' for v in arms.values())
        typed = arms.get('typed',{}).get('confirmation',{})
        winners[model] = None if not paired else (
            arms['typed']['named_use']['status']=='REQUIRED_FOR_CORRECT_OUTPUT'
            and typed['source_accepted']['archive']>0 and all(
                typed['accepted']>=arms[arm]['confirmation']['accepted']+2
                and typed['unsupported_decisions']<=arms[arm]['confirmation']['unsupported_decisions']
                for arm in ('direct','harness')))
    manual = registry/'constructor/manual-candidate.json'
    manual_results = {'development':evaluated(manual,development,'direct'),
                      'confirmation':evaluated(manual,confirmation,'direct')}
    evidence['operator-assisted'] = manual_results
    output.mkdir(parents=True,exist_ok=True)
    emit(output/'model-evidence.json',evidence)
    emit(output/'RESULTS.json',{'schema':'frontier/substrate-results-v1',
          'scoped_reference':{'accepted':28,'paper':12,'archive':12,'boundary fixture':4,
                              'all_source_row_horizons_agree':2792},
          'operator_assisted':{name:measurement(values) for name,values in manual_results.items()},
          'matched_runs':results,'material_gain':winners,
          'known_configuration':{'runtime':'llama.cpp b12242 from original included CPU runtime','context':8192,
               'qwen3-8b-q4-k-m':{'threads':8,'digest':'d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785'},
               'qwen3-4b-instruct-2507-q4_k_m':{'threads':4,
                    'digest':'2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e'},
               'gpu_layers':0,'external_api_requests':0,'paid_inference_charge':0},
          'unknown_costs':['human labor','energy consumption','ownership and maintenance','commercial value','realized revenue']})


if __name__=='__main__':
    main()
