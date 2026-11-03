from __future__ import annotations
import argparse
import copy
import fcntl
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys
import time
from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.finance import SOURCE_PATHS
from . import baseline, constructor, economics, native, service, worlds
from .verify import verify

ARMS = ('retained', 'ordinary')
PROTOCOL_PATHS = ('outlearning073/PREREGISTRATION.json', 'outlearning073/ECONOMIC_PLAN.json', 'outlearning073/requests.json', 'outlearning073/K1_GENERATION.json', 'outlearning073/CONSTRUCTOR.md', 'outlearning073/BASELINE.md', 'outlearning073/CONTRACT.md', 'tests/test_outlearning073_runner.py')


def expected_source_paths():
    return sorted(set(service.SOURCES) | set(SOURCE_PATHS) | set(PROTOCOL_PATHS))


def _plain_path(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)): raise ValueError('OUTLEARNING073_SYMLINK_PATH_REFUSED')
    return path


def _read(path):
    path = _plain_path(path)
    if path.is_symlink() or not path.is_file(): raise ValueError('OUTLEARNING073_REGULAR_JSON_REQUIRED:' + path.name)
    return strict_json(path.read_bytes())


def _write(path, value):
    path = _plain_path(path); path.parent.mkdir(parents=True, exist_ok=True)
    atomic_bytes(path, canonical(value))


def check_source(root):
    root = _plain_path(root).resolve(); path = root / 'outlearning073/FROZEN_SOURCE.json'; frozen = _read(path)
    if set(frozen) != {'schema','source_hashes','preregistration_sha256'} or frozen['schema'] != 'outlearning073/frozen-source/v1': raise ValueError('OUTLEARNING073_EXACT_FROZEN_SOURCE_REQUIRED')
    hashes = frozen['source_hashes']
    if not set(expected_source_paths()) <= set(hashes) or 'outlearning073/FROZEN_SOURCE.json' in hashes: raise ValueError('OUTLEARNING073_COMPLETE_STATIC_SOURCE_REQUIRED')
    executing = Path(__file__).resolve().parents[1]
    for name, expected in hashes.items():
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or str(rel) != name: raise ValueError('OUTLEARNING073_SAFE_SOURCE_PATH_REQUIRED')
        for base in (root, executing):
            target = _plain_path(base / name)
            if target.is_symlink() or not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != expected: raise ValueError('OUTLEARNING073_FROZEN_SOURCE_CHANGED:' + name)
    protocol = hashlib.sha256((root / 'outlearning073/PREREGISTRATION.json').read_bytes()).hexdigest()
    if frozen['preregistration_sha256'] != protocol: raise ValueError('OUTLEARNING073_PREREGISTRATION_CHANGED')
    if _read(root / 'outlearning073/ECONOMIC_PLAN.json') != economics.ECONOMIC_PLAN: raise ValueError('OUTLEARNING073_ECONOMIC_PLAN_CODE_MISMATCH')
    if _read(root / 'outlearning073/requests.json') != [worlds.development_requests()[0],worlds.confirmation_requests()[0]]: raise ValueError('OUTLEARNING073_PREDETERMINED_NATIVE_REQUESTS_CHANGED')
    return {'accepted':True,'source_hashes_sha256':digest(hashes),'source_files':len(hashes),'preregistration_sha256':protocol,'frozen_source_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def _cases():
    return [{'id':digest({'request':request,'arm':arm})[:24],'request':request,'arm':arm} for request in worlds.development_requests()+worlds.confirmation_requests() for arm in ARMS]


def _compact(verdict):
    keys = ('accepted','decision','scope','request_sha256','artifact_sha256','fault_schedules','accepted_schedules','maximum_operation_units','maximum_avoidable_loss_units','output_ok')
    result = {key:verdict[key] for key in keys if key in verdict}
    result['operation_unit_sum_across_fault_schedules'] = sum(row['cost_units'] for row in verdict.get('results',[]))
    result['rejected_schedules'] = [row for row in verdict.get('results',[]) if not row['accepted']]
    return result


def _build(request, arm, source):
    session = worlds.make_session(request); content = constructor.retained_content()
    routine = constructor.build if arm == 'retained' else baseline.build
    wall,cpu = time.perf_counter(),time.process_time()
    artifact,trace = routine(session,copy.deepcopy(content))
    return {'schema':'outlearning073/constructed-case/v1','request':copy.deepcopy(request),'arm':arm,'source':source,'retained_content_sha256':digest(content),'routine':'outlearning073.'+('constructor' if arm=='retained' else 'baseline')+':build','artifact':artifact,'construction_trace':trace,'probes':copy.deepcopy(session.probes),'diagnostic_units':session.units_spent,'construction_wall_seconds':time.perf_counter()-wall,'construction_process_cpu_seconds':time.process_time()-cpu}


def _check_case(record, case, source, *, semantic=True):
    if record.get('schema') != 'outlearning073/constructed-case/v1' or record['request'] != case['request'] or record['arm'] != case['arm'] or record['source'] != source or record['retained_content_sha256'] != digest(constructor.retained_content()): raise ValueError('OUTLEARNING073_CASE_IDENTITY_CHANGED')
    if record['verification'] != _compact(verify(case['request'],record['artifact'])): raise ValueError('OUTLEARNING073_ACCEPTANCE_REPLAY_CHANGED')
    if record['diagnostic_units'] != sum(probe['result']['cost_units'] for probe in record['probes']): raise ValueError('OUTLEARNING073_DIAGNOSTIC_COST_CHANGED')
    _check_timings(record)
    if semantic: _semantic_check(record,source)
    return record


def _semantic_check(record, source):
    _check_timings(record)
    reproduced = _build(record['request'],record['arm'],source)
    for key in ('schema','source','artifact','construction_trace','probes','diagnostic_units','routine','retained_content_sha256'):
        if record.get(key) != reproduced[key]: raise ValueError('OUTLEARNING073_CONSTRUCTION_REPLAY_CHANGED:'+key)
    return reproduced['diagnostic_units']


def _check_timings(record):
    for key in ('construction_wall_seconds','construction_process_cpu_seconds','verification_wall_seconds','verification_process_cpu_seconds'):
        if key in record and (type(record[key]) not in (int,float) or not math.isfinite(record[key]) or record[key]<0): raise ValueError('OUTLEARNING073_FINITE_NONNEGATIVE_RESOURCE_TIMING_REQUIRED')


def _audit_native_result(root, manifest, account, result, case):
    audit = native.audit_export(account,root=root,manifest=manifest)
    if not audit.get('accepted') or result['snapshot']['summary']!=audit['summary'] or result['record_sha256']!=digest(account) or result['scenario']!=case['scenario'] or result['opening_microUSD']!=case['opening_microUSD'] or result['plan_sha256']!=digest(economics.ECONOMIC_PLAN): raise ValueError('OUTLEARNING073_NATIVE_SUMMARY_CLAIM_CHANGED')
    actions = account['ledger']['actions']
    offers = {a['args']['id']:a['args'] for a in actions if a['op']=='offer'}
    released = {a['args']['id'] for a in actions if a['op']=='event' and a['args'].get('action')=='release'}
    prepares = {a['args']['id']:a['args']['artifact_sha256'] for a in actions if a['op']=='event' and a['args'].get('action')=='prepare'}
    public_orders = result.get('orders',[])
    if len({r['order_id'] for r in public_orders})!=len(public_orders) or {r['order_id'] for r in public_orders}!=set(offers): raise ValueError('OUTLEARNING073_PUBLIC_ORDER_COVERAGE_CHANGED')
    for row in public_orders:
        order_id = row['order_id']
        if row['job_id']!=offers[order_id]['job_id'] or row['acceptance']['accepted']!=(order_id in prepares) or order_id in prepares and row['artifact_sha256']!=prepares[order_id]: raise ValueError('OUTLEARNING073_PUBLIC_ORDER_ARTIFACT_CHANGED')
    pre_names = {'research_construction','adaptation_construction','inference_envelope','failed_attempts_corrections','acquisition_onboarding'}
    expenses = 0; seen = set(); fee = economics.ECONOMIC_PLAN['modeled_payment_fee_microUSD_per_order']
    for row in result['costs']:
        stage = row['stage']
        if stage not in ('K1','K2') or stage in seen: raise ValueError('OUTLEARNING073_EXACT_COST_STAGE_REQUIRED')
        seen.add(stage)
        if 'sunk_research_microUSD' in row:
            expected = economics.ECONOMIC_PLAN['sunk_research_USD_before_entry_decision']*1_000_000
            if case['scenario']['enter'] or stage!='K1' or row!={'stage':'K1','sunk_research_microUSD':expected,'total_microUSD':expected}: raise ValueError('OUTLEARNING073_SUNK_COST_CLAIM_CHANGED')
            expenses += expected
            continue
        costs = {name:amount*1_000_000*case['scenario']['resource_multiplier'] for name,amount in economics.ECONOMIC_PLAN[stage]['costs_USD'].items()}
        before = {name:amount for name,amount in costs.items() if name in pre_names}
        categories = row['categories_microUSD']
        if categories not in (costs,before) or row['total_microUSD']!=sum(categories.values()): raise ValueError('OUTLEARNING073_COST_CATEGORIES_CHANGED')
        order_id = stage+'-order'; expected_fee = fee if order_id in offers else 0
        margin = economics.ECONOMIC_PLAN[stage]['price_microUSD']-sum(costs.values())-fee
        tax = max(margin,0)*economics.ECONOMIC_PLAN['tax_numerator']//economics.ECONOMIC_PLAN['tax_denominator'] if order_id in released else 0
        if row.get('payment_fee_microUSD',0)!=expected_fee or row.get('tax_microUSD',0)!=tax: raise ValueError('OUTLEARNING073_PAYMENT_FEE_OR_TAX_CHANGED')
        expenses += row['total_microUSD']+expected_fee+tax
    if not seen or expenses!=audit['summary']['expenses']: raise ValueError('OUTLEARNING073_COMPLETE_EXPENSE_CLAIM_CHANGED')
    reconciliation = result['expense_reconciliation']
    if reconciliation.get('expected_microUSD')!=expenses or reconciliation.get('native_microUSD')!=expenses or reconciliation.get('equal') is not True: raise ValueError('OUTLEARNING073_EXPENSE_RECONCILIATION_CHANGED')
    verdict = 'CONDITIONAL_COMPLETE_COST_SIM_PROFIT' if audit['summary']['profit']>0 and {'K1-order','K2-order'}<=released else 'NO_CONNECTED_COMMERCIAL_SUCCESS'
    if result['commercial_verdict']!=verdict: raise ValueError('OUTLEARNING073_COMMERCIAL_VERDICT_CHANGED')
    return audit


def _one_case(output, case, source):
    folder = _plain_path(output / 'technical' / case['id']); result = folder / 'CASE.json'; built = folder / 'BUILT.json'
    if result.exists(): return _check_case(_read(result),case,source)
    if folder.exists():
        if not built.is_file(): raise ValueError('OUTLEARNING073_INTERRUPTED_CONSTRUCTION_PRESERVED_NO_RETRY:'+case['id'])
        record = _read(built)
        if record['request'] != case['request'] or record['arm'] != case['arm'] or record['source'] != source: raise ValueError('OUTLEARNING073_INTERRUPTED_CASE_CHANGED')
    else:
        folder.mkdir(parents=True); _write(folder/'STARTED.json',{'case':case,'source':source})
        try:
            record = _build(case['request'],case['arm'],source); _write(built,record)
        except Exception as error:
            _write(folder/'ERROR.json',{'error_type':type(error).__name__,'error':str(error)[:500],'source':source}); raise
    wall,cpu = time.perf_counter(),time.process_time()
    record['verification'] = _compact(verify(case['request'],record['artifact']))
    record.update(verification_wall_seconds=time.perf_counter()-wall,verification_process_cpu_seconds=time.process_time()-cpu)
    _write(result,record)
    return _check_case(record,case,source,semantic=False)


def _technical(records):
    result = {'scope':'Exact finite authored grid; no IID confidence interval or market probability.','arms':{},'families':[]}
    def summarize(rows):
        return {'tasks':len(rows),'accepted':sum(r['verification']['accepted'] for r in rows),'refused':sum(r['verification'].get('decision')=='REFUSE' for r in rows),'rejected':sum(r['verification'].get('decision')=='REJECT' for r in rows),'diagnostic_units':sum(r['diagnostic_units'] for r in rows),'sum_maximum_executor_units':sum(r['verification']['maximum_operation_units'] for r in rows),'maximum_avoidable_loss_units':max((r['verification']['maximum_avoidable_loss_units'] for r in rows),default=0),'construction_wall_seconds':sum(r['construction_wall_seconds'] for r in rows),'construction_process_cpu_seconds':sum(r['construction_process_cpu_seconds'] for r in rows)}
    for stage in ('K1','K2'):
        result['arms'][stage] = {arm:summarize([r for r in records if r['request']['stage']==stage and r['arm']==arm]) for arm in ARMS}
    for family in range(8):
        result['families'].append({'semantic_family_index':family,'arms':{arm:summarize([r for r in records if r['request']['stage']=='K2' and (r['request']['seed']-100)%8==family and r['arm']==arm]) for arm in ARMS}})
    result['paired_accepted_K2_difference_retained_minus_ordinary'] = result['arms']['K2']['retained']['accepted']-result['arms']['K2']['ordinary']['accepted']
    result['economic_material_effect'] = 'Requires incremental modeled collected surplus after complete first-use/reuse costs, separately from technical counts.'
    return result


def _native(root, output, source):
    requests = _read(root/'outlearning073/requests.json'); context = {}
    def manifest_factory(case):
        context['case'] = case
        return service.prepare_manifest(root,[{'id':r['id'],'delivery_path':'outlearning073/deliveries/'+case+'/'+r['id']+'.json'} for r in requests])
    def produce(request):
        folder = _plain_path(output/'native'/'constructions'/context['case']/digest(request)[:24])
        if folder.exists(): raise ValueError('OUTLEARNING073_NATIVE_PRODUCTION_MUST_NOT_REUSE_PREBUILT_ARTIFACT')
        folder.mkdir(parents=True); _write(folder/'STARTED.json',{'request':request,'source':source,'scope':'Called by economics only after canonical paid production reservation.'})
        record = _build(request,'retained',source); _write(folder/'BUILT.json',record)
        return record['artifact']
    return economics.run_all(root,output/'native',manifest_factory,produce)


def _output(value, root):
    if not Path(value).is_absolute(): raise ValueError('OUTLEARNING073_ABSOLUTE_OUTPUT_REQUIRED')
    path = _plain_path(value)
    if not path.is_absolute() or path.is_symlink(): raise ValueError('OUTLEARNING073_ABSOLUTE_OUTPUT_REQUIRED')
    path = path.resolve()
    if path==root or root in path.parents: raise ValueError('OUTLEARNING073_PRIVATE_OUTPUT_MUST_BE_OUTSIDE_PUBLIC_SOURCE')
    return path


def execute(root, output):
    root = _plain_path(root).resolve(); source = check_source(root); output = _output(output,root); output.mkdir(parents=True,exist_ok=True)
    with _plain_path(output/'.run.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        expected = {'schema':'outlearning073/task-queue/v1','source':source,'cases':_cases(),'retained_content_sha256':digest(constructor.retained_content())}
        path = output/'QUEUE.json'
        if path.exists():
            queue = _read(path)
            if any(queue.get(k)!=v for k,v in expected.items()): raise ValueError('OUTLEARNING073_QUEUE_SOURCE_CHANGED')
        else:
            if any(p.name!='.run.lock' for p in output.iterdir()): raise ValueError('OUTLEARNING073_NONEMPTY_OUTPUT_WITHOUT_QUEUE')
            queue = dict(expected,completed={}); _write(path,queue)
        records = []
        for case in expected['cases']:
            record = _one_case(output,case,source); identity = digest(record)
            if case['id'] in queue['completed'] and queue['completed'][case['id']]!=identity: raise ValueError('OUTLEARNING073_COMPLETED_TRIAL_CHANGED')
            queue['completed'][case['id']] = identity; _write(path,queue); records.append(record)
        technical = _technical(records); _write(output/'TECHNICAL_SUMMARY.json',technical)
        economic = _native(root,output,source); check_source(root)
        summary = {'schema':'outlearning073/executed-summary/v1','source':source,'technical':technical,'native':economic,'actual_model_and_host_billing':'UNKNOWN','confirmation_scope':'Frozen deterministic reuse of an actual included-agent K1 construction; no unattended model-call integration.','milestone_USD3B_achieved':False}
        _write(output/'SUMMARY.json',summary); queue['summary_sha256'] = digest(summary); _write(path,queue)
        return summary


def replay(root, output):
    root = _plain_path(root).resolve(); source = check_source(root); output = _output(output,root); queue = _read(output/'QUEUE.json')
    if queue['source']!=source or queue['cases']!=_cases(): raise ValueError('OUTLEARNING073_REPLAY_QUEUE_CHANGED')
    records = []; replay_diagnostic_units = 0
    for case in queue['cases']:
        record = _check_case(_read(output/'technical'/case['id']/'CASE.json'),case,source)
        if queue['completed'].get(case['id'])!=digest(record): raise ValueError('OUTLEARNING073_REPLAY_INCOMPLETE_OR_CHANGED_CASE')
        replay_diagnostic_units += record['diagnostic_units']
        records.append(record)
    technical = _technical(records)
    if _read(output/'TECHNICAL_SUMMARY.json')!=technical: raise ValueError('OUTLEARNING073_TECHNICAL_SUMMARY_CHANGED')
    native_queue = _read(output/'native'/'QUEUE.json')
    expected_cases = [{'directory':s['id'],'scenario':s,'opening_microUSD':economics.ECONOMIC_PLAN['opening_microUSD']} for s in economics.ECONOMIC_PLAN['scenarios']]
    expected_cases += [{'directory':name,'scenario':economics.ECONOMIC_PLAN['scenarios'][0],'opening_microUSD':economics.ECONOMIC_PLAN[key]} for name,key in [('positive-1000-underfunded','underfunded_opening_microUSD'),('positive-100k-reference','reference_opening_microUSD')]]
    if native_queue['plan_sha256']!=digest(economics.ECONOMIC_PLAN) or native_queue['source_hashes']!=service._source_hashes(root) or native_queue['cases']!=expected_cases: raise ValueError('OUTLEARNING073_NATIVE_QUEUE_CHANGED')
    audits = []; economic_results = []; requests = _read(root/'outlearning073/requests.json')
    for case in native_queue['cases']:
        folder = output/'native'/case['directory']; manifest,account,result = (_read(folder/name) for name in ('MANIFEST.json','ACCOUNT_PUBLIC.json','RESULT.json'))
        if native_queue['completed'].get(case['directory'])!=digest(result) or result['record_sha256']!=digest(account): raise ValueError('OUTLEARNING073_NATIVE_RESULT_CHANGED')
        if result['case_id']!=case['directory']: raise ValueError('OUTLEARNING073_NATIVE_CASE_ID_CHANGED')
        expected_manifest = service.prepare_manifest(root,[{'id':r['id'],'delivery_path':'outlearning073/deliveries/'+case['directory']+'/'+r['id']+'.json'} for r in requests])
        if manifest!=expected_manifest: raise ValueError('OUTLEARNING073_NATIVE_MANIFEST_CHANGED')
        audit = _audit_native_result(root,manifest,account,result,case)
        audits.append({'case':case['directory'],'record_sha256':digest(account),'audit':audit})
        economic_results.append(result)
        for row in result['orders']:
            request = next(r for r in requests if r['id']==row['job_id'])
            built = _read(output/'native'/'constructions'/case['directory']/digest(request)[:24]/'BUILT.json')
            if built['request']!=request or built['arm']!='retained': raise ValueError('OUTLEARNING073_FUNDED_CONSTRUCTION_IDENTITY_CHANGED')
            replay_diagnostic_units += _semantic_check(built,source)
            if digest(built['artifact'])!=row['artifact_sha256']: raise ValueError('OUTLEARNING073_FUNDED_CONSTRUCTION_ARTIFACT_CHANGED')
            if service.verify_delivery(root,manifest,row['job_id'],built['artifact'])!=row['acceptance']: raise ValueError('OUTLEARNING073_NATIVE_ACCEPTANCE_RECEIPT_CHANGED')
    compact_native = {'schema':'outlearning073/native-economic-summary/v1','plan_sha256':digest(economics.ECONOMIC_PLAN),'scope':economics.ECONOMIC_PLAN['scope'],'cases':[{k:row[k] for k in ['case_id','scenario','opening_microUSD','snapshot','commercial_verdict','record_sha256']} for row in economic_results]}
    if _read(output/'native'/'SUMMARY.json')!=compact_native: raise ValueError('OUTLEARNING073_NATIVE_COMPACT_SUMMARY_CHANGED')
    summary = _read(output/'SUMMARY.json')
    if queue.get('summary_sha256')!=digest(summary) or summary['technical']!=technical or summary['native']!=_read(output/'native'/'SUMMARY.json') or summary['source']!=source: raise ValueError('OUTLEARNING073_EXECUTED_SUMMARY_CHANGED')
    receipt = {'schema':'outlearning073/independent-replay/v1','accepted':True,'source':source,'technical_cases_recomputed':len(records),'native_accounts_publicly_replayed':len(audits),'native_audits':audits,'reproduction_diagnostic_units':replay_diagnostic_units,'summary_sha256':digest(summary),'scope':'Key-free constructor/probe, artifact and public account replay; diagnostic reproduction resources are separate from original scored cases. Private authority never opened; no trades constructed.'}
    _write(output/'REPLAY.json',receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('command',choices=('check-source','execute','replay')); parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); parser.add_argument('--output',type=Path); args = parser.parse_args()
    try:
        if args.command=='check-source': result = check_source(args.root)
        else:
            if args.output is None: raise ValueError('OUTLEARNING073_OUTPUT_REQUIRED')
            result = execute(args.root,args.output) if args.command=='execute' else replay(args.root,args.output)
        print(json.dumps(result,sort_keys=True,allow_nan=False))
    except (ValueError,OSError,KeyError,TypeError) as error:
        print(json.dumps({'accepted':False,'error_type':type(error).__name__,'error':str(error)[:500]},sort_keys=True),file=sys.stderr); raise SystemExit(1)


if __name__ == '__main__': main()
