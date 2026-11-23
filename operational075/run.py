from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from . import broker, client, economics, source

PACKAGE = Path(__file__).resolve().parent
METHODS = ('retained', 'ordinary')
FROZEN_PACKAGE_FILES = (
    'BASELINE.md', 'CONTRACT.md', 'DEVELOPMENT.md', 'ECONOMIC_PROTOCOL.json',
    'INDEPENDENT_REVIEW.md', 'K1_FREEZE.json', 'K2_GENERATION.json',
    'K2_PROTOCOL.json', 'OPPORTUNITIES.md', 'RESERVATION.json', 'RETAINED.json',
    'RETAINED_POLICY.md', 'SOURCE_MANIFEST.json', 'broker.py', 'client.py',
    'economics.py', 'ordinary.py', 'retained.py', 'run.py', 'source.py', 'wave.py',
)


def expected_source_paths():
    return {'operational075/' + name for name in FROZEN_PACKAGE_FILES} | {
        'tests/test_operational075_broker.py', '.github/workflows/operational075.yml',
    }


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def read(path):
    path = Path(path)
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('OPERATIONAL075_REGULAR_RECORD_REQUIRED')
    return json.loads(path.read_text())


def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    data = encoded(value)
    if path.exists():
        if path.read_bytes() != data: raise ValueError('OPERATIONAL075_EXISTING_RESULT_CHANGED:' + path.name)
        return
    with path.open('xb') as f: f.write(data)


def check_source():
    frozen = read(PACKAGE / 'K2_SOURCE_FREEZE.json')
    if frozen['schema'] != 'operational075/k2-source-freeze/v1': raise ValueError('OPERATIONAL075_SOURCE_FREEZE_REQUIRED')
    if set(frozen['files']) != expected_source_paths(): raise ValueError('OPERATIONAL075_COMPLETE_SOURCE_INVENTORY_REQUIRED')
    expected_python = {name for name in FROZEN_PACKAGE_FILES if name.endswith('.py')}
    if {p.name for p in PACKAGE.glob('*.py')} != expected_python: raise ValueError('OPERATIONAL075_UNREGISTERED_PYTHON_SOURCE')
    for name, expected in frozen['files'].items():
        path = PACKAGE.parent / name
        if not path.is_file() or any(p.is_symlink() for p in (path,*path.parents)) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('OPERATIONAL075_FROZEN_SOURCE_CHANGED:' + name)
    k1 = read(PACKAGE / 'K1_FREEZE.json')
    for name, expected in k1['source_hashes'].items():
        if hashlib.sha256((PACKAGE.parent/name).read_bytes()).hexdigest() != expected: raise ValueError('OPERATIONAL075_K1_SOURCE_CHANGED')
    return {'accepted': True, 'frozen_source_sha256': hashlib.sha256((PACKAGE/'K2_SOURCE_FREEZE.json').read_bytes()).hexdigest(), 'source_files':len(frozen['files']), 'upstream_commit':source.manifest()['commit']}


def _travel_total(source_root, transcript):
    public, rows = broker._load_public(source_root), broker._load_confirmations(source_root)
    orders = {r['order_id']: r for r in rows}; total = 0
    for day in transcript['instances']:
        matrix = public[day['service_day_id']]['duration']
        for period in day['dispatch_rounds']:
            for route in period['routes']:
                previous = 0
                for ident in route:
                    current = orders[ident]['customer_id']; total += matrix[previous][current]; previous = current
                total += matrix[previous][0]
    return total


def _summary(source_root, output, identity, failures):
    k1 = read(output/'K1_CLIENT.json'); results={}; audits={}
    for method in METHODS:
        folder=output/method
        if (folder/'CLIENT_RESULT.json').exists():
            result=read(folder/'CLIENT_RESULT.json'); audit=broker.audit_episode(source_root,folder)
            if not audit['accepted']: raise ValueError('OPERATIONAL075_INDEPENDENT_CLIENT_REPLAY_REFUSED')
            total=_travel_total(source_root,read(folder/'TRANSCRIPT.json')) if result['upstream_client']['accepted'] else None
            results[method]={'accepted':result['upstream_client']['accepted'],'original_client':result['upstream_client'],'total_directed_driving_seconds':total,'mean_driving_seconds_fraction':None if total is None else {'numerator':total,'denominator':3},'raw_submissions':18,'resources':result['resources'],'resource_scope':'Worker startup and policy execution only; broker, original-client finalization and replay are excluded. Whole-study billing remains UNKNOWN.','feedback_before_final':False}
            audits[method]=audit
        else:
            results[method]={'accepted':False,'complete':False,'preserved_failure':failures.get(method),'raw_submissions':len(list(folder.glob('periods/*/SUBMISSION.json')))}
    both=all(results[m]['accepted'] for m in METHODS)
    difference=(results['retained']['total_directed_driving_seconds']-results['ordinary']['total_directed_driving_seconds']) if both else None
    facts={'qualified_artifact_acceptance':{'value':any(results[m]['accepted'] for m in METHODS),'independently_verified':True,'evidence_ref':'AUDITS.json and unchanged original-source client'},'qualified_public_benchmark_task_types':int(k1['accepted'])+int(any(results[m]['accepted'] for m in METHODS)),'actual_paying_contracts':0,'contract_count_scope':'One warehouse benchmark task plus one grocery benchmark task; alternative grocery policies are not extra buyers, orders or sales.','actual_model_and_host_billing':'UNKNOWN','whole_episode_complete_cost':'UNKNOWN','resources':{m:results[m].get('resources') for m in METHODS}}
    planning=economics.evaluate(facts)
    report={'schema':'operational075/executed-result/v1','source':identity,'K1':k1,'K2':results,'paired_total_driving_seconds_retained_minus_ordinary':difference,'independent_audits':audits,'economic_requirements':planning,'native_account_operated':False,'native_target_achieved':False,'actual_commercial_revenue_microUSD':0,'interpretation':'Exact original-client computational delivery comparison; no physical implementation, customer payment, novelty, expert superiority or causal discovery-method advantage is inferred.','next_decision':'Keep the accepted stronger complete method, or reject failed construction. Independently establish attainable commissioned demand, full cost, dated capacity and funding before treating the target thresholds as a business path.'}
    return report,audits,facts,planning


def execute(source_root, output):
    output=Path(output).absolute(); source_root=Path(source_root).absolute(); identity=check_source();source.verify_source(source_root)
    if PACKAGE.parent==output or PACKAGE.parent in output.parents: raise ValueError('OPERATIONAL075_PRIVATE_EXECUTION_OUTSIDE_SOURCE_REQUIRED')
    output.mkdir(parents=True,exist_ok=True)
    if not read(output/'K1_CLIENT.json')['accepted']: raise ValueError('OPERATIONAL075_ACCEPTED_K1_REQUIRED')
    if hashlib.sha256((output/'K1.json').read_bytes()).hexdigest()!=read(PACKAGE/'K2_PROTOCOL.json')['K1']['raw_artifact_sha256']:raise ValueError('OPERATIONAL075_K1_ARTIFACT_CHANGED')
    checked=client.verify_wave(source_root,source.source_path(source_root,source.WAVE_INPUT),output/'K1.json')
    if checked!=read(output/'K1_CLIENT.json'):raise ValueError('OPERATIONAL075_K1_ORIGINAL_CLIENT_CHANGED')
    write(output/'REGISTRATION.json',{'source':identity,'methods':METHODS,'rounds_per_method':18,'source_manifest_sha256':hashlib.sha256((PACKAGE/'SOURCE_MANIFEST.json').read_bytes()).hexdigest()})
    failures={}
    for method in METHODS:
        try: broker.run_episode(source_root,'operational075.'+method,output/method)
        except (ValueError,OSError,KeyError,TypeError) as exc:
            failures[method]={'type':type(exc).__name__,'message':str(exc)[:1800]}
            write(output/(method+'_FAILURE.json'),failures[method])
    check_source(); report,audits,facts,planning=_summary(source_root,output,identity,failures)
    for name,value in [('AUDITS.json',audits),('PUBLIC_FACTS.json',facts),('ECONOMIC_REQUIREMENTS.json',planning),('SUMMARY.json',report)]:write(output/name,value)
    return report


def audit(source_root, output):
    output=Path(output).absolute();identity=check_source();report=read(output/'SUMMARY.json')
    if report['source']!=identity:raise ValueError('OPERATIONAL075_REPORT_SOURCE_CHANGED')
    failures={m:read(output/(m+'_FAILURE.json')) for m in METHODS if (output/(m+'_FAILURE.json')).exists()}
    rebuilt,audits,facts,planning=_summary(source_root,output,identity,failures)
    if rebuilt!=report or facts!=read(output/'PUBLIC_FACTS.json') or planning!=read(output/'ECONOMIC_REQUIREMENTS.json') or audits!=read(output/'AUDITS.json'):
        raise ValueError('OPERATIONAL075_PUBLIC_REPORT_REPLAY_CHANGED')
    checked=client.verify_wave(source_root,source.source_path(source_root,source.WAVE_INPUT),output/'K1.json')
    if checked!=report['K1']:raise ValueError('OPERATIONAL075_K1_REPLAY_CHANGED')
    return {'accepted':True,'source':identity,'K1_original_client_accepted':checked['accepted'],'methods_replayed':len(audits),'original_K2_submissions_replayed':sum(v['original_submissions_replayed'] for v in audits.values()),'native_target_achieved':False,'scope':'Original-client and frozen immutable output replay, without rerunning or tuning policies.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=('check-source','execute','audit'));p.add_argument('--source',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    if a.command=='check-source': result=check_source()
    else:
        if a.source is None or a.output is None:p.error('--source and --output required')
        result=execute(a.source,a.output) if a.command=='execute' else audit(a.source,a.output)
    print(json.dumps(result,sort_keys=True,allow_nan=False))


if __name__=='__main__':main()
