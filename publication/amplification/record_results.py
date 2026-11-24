"""Score committed cases after closing the constructor workspaces."""

from hashlib import sha256
import json
from pathlib import Path
import os
import platform
import re
from statistics import median
import sys
from time import perf_counter_ns

from amplify import assess, canonical, counts, read, selected
from calibration_environment import exact, validate
from reproduce_amplification import native_controls
from route_environment import conventional, independent, verify


def attempts(record):
    summary = []
    for attempt in record['attempts']:
        events=[]
        for event in attempt['request']['events']:
            retained={key:value for key,value in event.items() if key!='candidate'}
            if retained.get('draft')==attempt['candidate']:
                retained.pop('draft',None)
            events.append(retained)
        summary.append({'number':attempt['number'],'scores':attempt['scores'],
            'diagnostics':attempt['diagnostics'],'candidate':attempt['candidate'],
            'development':attempt['development'],'events':events})
    return summary


def verify_arms(paths, plan_path, held):
    plan_digest=sha256(plan_path.read_bytes()).hexdigest()
    arms={}
    for path in sorted(paths):
        record, artifact_digest=read(path)
        if record['binding']['registration']!=plan_digest or record['state']=='RUNNING':
            raise ValueError('UNSEALED_CONSTRUCTOR')
        model=record['binding']['model']
        mode=record['binding']['arm']
        key=f'{model}/{mode}'
        winner=selected(record)
        candidate=winner['candidate'] if winner else None
        results=assess(candidate['source'],held) if candidate else []
        artifact=sha256(canonical(candidate['source']).encode()).hexdigest() if candidate else None
        arms[key]={'accepted':counts(results)['accepted'],'results':results,'checkpoint_sha256':artifact_digest,
            'candidate':candidate,'source_sha256':artifact,'selected':winner['number'] if winner else None,
            'attempts':attempts(record),'binding':record['binding'],'state':record['state'],
            'selected_instrument_used':bool(winner and winner['diagnostics'] and winner['diagnostics']['used']),
            'wrong_positive_witness':sum(not row['accepted'] and isinstance(row.get('result'),dict)
                and bool(row['result'].get('witnesses')) for row in results)}
    return arms


def material(arms, plan):
    winners=[]
    for model in plan['comparisons']:
        experiment=arms.get(f'{model}/amplified')
        direct=arms.get(f'{model}/direct')
        harness=arms.get(f'{model}/harness')
        if (experiment and experiment['selected_instrument_used'] and direct and harness
                and experiment['accepted']>=max(direct['accepted'],harness['accepted'])+2
                and experiment['wrong_positive_witness']<=min(direct['wrong_positive_witness'],harness['wrong_positive_witness'])):
            winners.append(model)
    return winners


def workload(held):
    selected_case=next(row for row in held if row['id']=='deployment-05')
    trial=selected_case['input']
    receipt={'case':selected_case['id'],'exact':verify(held),'trial':selected_case['expected'],'execution':{}}
    for name, function in (('sqlite',conventional),('feasible-load-search',independent)):
        latency=[]
        for _ in range(31):
            start=perf_counter_ns()
            result=function(trial)
            latency.append(perf_counter_ns()-start)
            if result!=receipt['trial']:
                raise ValueError('WORKLOAD_OUTPUT')
        receipt['execution'][name]={'repeat':len(latency),'min_ns':min(latency),'median_ns':median(latency),'max_ns':max(latency)}
    return {**receipt,'accepted':len(receipt['exact']),'cases':len(held)}


def transport(*logs):
    observations=[]
    for path in logs:
        if path.is_file():
            text=path.read_text()
            observations.extend((float(ms),int(count),float(rate)) for ms,count,rate in re.findall(
                r'\bI slot print_timing: .*?\|\s+eval time\s+=\s*([\d.]+) ms\s*/\s*(\d+) tokens .*?([\d.]+) tokens per second\)',text))
    return {'completed_server_samples':len(observations),
            'median_output_tokens_per_second':median(speed for _,_,speed in observations) if observations else None,
            'server_generation_tokens':sum(tokens for _,tokens,_ in observations),
            'server_generation_ms':round(sum(ms for ms,_,_ in observations),3)}


def inference_costs(*batches):
    result={}
    for label,events in batches:
        result[label]={'attempts':len(events),'observed_request_wall_ns':sum(e.get('wall_ns',0) for e in events),
            'reported_input_tokens':sum((e.get('usage') or {}).get('input_tokens') or 0 for e in events),
            'reported_output_tokens':sum((e.get('usage') or {}).get('output_tokens') or 0 for e in events),
            'interrupted_output_reserved':sum(e.get('reserved_output',0) for e in events if e['status']=='INTERRUPTED'),
            'unreported_or_refused':sum(not e.get('usage') for e in events),'paid_inference_usd':0}
    return result


def arm_calls(arms):
    return [event for arm in arms.values() for attempt in arm['attempts'] for event in attempt['events']]


def collect(root):
    primary=root/'registered-v1'
    plan,_=read(primary/'registration.json')
    cases,_=read(primary/'confirmation.json')
    base=verify_arms((root/'matrix').glob('model*/amplification-status.json'),primary/'registration.json',cases)
    further=root/'continuation'
    revised=verify_arms(further.glob('endpoint-*/amplification-status.json'),primary/'registration.json',cases)
    calibration=root/'calibration-v1'
    fresh,_=read(calibration/'confirmation.json')
    for case in fresh:
        if exact(case['input'])!=case['expected'] or not validate(case['input'],case['expected']):
            raise ValueError('CALIBRATION_CONTROLS')
    transfer=verify_arms(further.glob('calibration-*/amplification-status.json'),calibration/'registration.json',fresh)
    registration=root/'registered-v1'/'registration.json'
    generated={'discovery':read(root/'discovery-executed.json')[0],
        'first_diagnostic':read(root/'matrix/design/run.json')[0],
        'first_instrument':read(root/'matrix/design/instrument.json')[0],
        'refinement':read(further/'refinement/run.json')[0],
        'interruption':read(further/'interruption.json')[0]}
    for name,path in (('revised_instrument',further/'refinement/instrument.json'),
                      ('transfer_instrument',further/'transfer-instrument.json')):
        if path.is_file():
            generated[name]=read(path)[0]
    firing={
        'matched':{'context':4096,'threads':8,'config_hashes':{idx:sha256((root/f'model{idx}-matched.json').read_bytes()).hexdigest() for idx in (4,8)}},
        'revision':{'context':8192,'threads':8,'config_hash':sha256((further/'config.json').read_bytes()).hexdigest()},
        'llama_cpp_build':12242,'gpu_layers':0,
        'observed_host':{'machine':platform.machine(),'kernel':platform.release(),'available_cpus':os.cpu_count(),
                         'memory_total_kib':int(Path('/proc/meminfo').read_text().splitlines()[0].split()[1]),
                         'cpu_model':next(line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                                          if line.startswith('model name'))},
        'weights_bytes':{'4B':(root.parent/'model.gguf').stat().st_size,
                         '8B':(root.parent/'inventor'/'qwen3-8b.gguf').stat().st_size},
        'throughput': {'8B/8192-discovery':transport(root/'discovery-server.log'),
                       '8B/4096':transport(root/'matrix8.log'),
                       '4B/4096':transport(root/'matrix4.log',root/'matrix4-resume.log'),
                       '4B/8192':transport(root/'continuation-server.log')},
    }
    return {'schema':'frontier/amplification-comparison-v1','registration_sha256':sha256(registration.read_bytes()).hexdigest(),
        'models':firing,'generated':generated,'held_cases':len(cases),'arms':base,
        'revised_arms':revised,'conventional':workload(cases),
        'same_model_amplification':{'4096':material(base,plan),'8192':material(revised,plan)},
        'transfer':{'scope':'Public measured calibration blocks. Instrument transfer is experimental.',
                    'held_cases':len(fresh),'control':len(fresh),'arms':transfer},
        'resumed_queues': [read(path)[0] for path in sorted((root/'matrix').glob('model*-comparison.json'))],
        'cost_ledger':inference_costs(('discovery',generated['discovery']['events']),
            ('design',generated['first_diagnostic']['events']),('matched',arm_calls(base)),
            ('refinement',generated['refinement']['events']),('revised',arm_calls(revised)),('fresh',arm_calls(transfer))),
        'ownership':{'accepted_local_assets':['route_environment.py','calibration_environment.py'],
            'operational_failover':'ABSTAIN','specialist_training':'ABSTAIN','candidate_promotion':'NONE',
            'real_member_trial':'ABSENT','paid_inference_usd':0,'realized_revenue_usd':None,
            'not_measured':['human effort','energy','infrastructure rates','repeated maintenance','full customer economics']},
        'native_boundaries':native_controls()}


if __name__=='__main__':
    print(json.dumps(collect(Path(sys.argv[1])),ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False))
