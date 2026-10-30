"""Registered eight-business expansion addendum over unchanged source002."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import importlib
import json
import multiprocessing
import os
import signal
import datetime
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

BASE=Path(__file__).resolve().parents[1]
REGISTRATION=BASE/'campaign/connected-014/EXPANSION_ADDENDUM.json'
if not REGISTRATION.is_file():REGISTRATION=Path(__file__).resolve().with_name('EXPANSION_ADDENDUM.json')
EXPECTED_SOURCE='3d985299bf6cfaf546b712ebd9e878e875aaf730ffdb32023637aafc5504a38d'
EXPECTED_COMMIT='ffc1f2e14e88e11f75d5087ab0f7c4e60512431e'


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp');temporary.write_bytes(canonical(value)+b'\n');temporary.replace(path)


def business(source):
    source=Path(source).resolve();sys.path.insert(0,str(source))
    runner=importlib.import_module('connected_enterprise.runner')
    if Path(runner.__file__).resolve()!=source/'connected_enterprise/runner.py':raise ValueError('IMMUTABLE_BUSINESS_IMPORT_REQUIRED')
    return runner


def registration(path=REGISTRATION):
    record=json.loads(Path(path).read_text())
    if record['business_source_sha256']!=EXPECTED_SOURCE or record['business_source_commit']!=EXPECTED_COMMIT:raise ValueError('REGISTERED_BUSINESS_SOURCE_CHANGED')
    p=record['protocol']
    if p['central_seeds']!=list(range(2610301801,2610301805)) or p['arms']!=['baseline','growth'] or p['cases']!=['central'] or p['service_cohort_seed']!=14033026 or p['workers']!=4 or p['adverse_seeds'] or p['channel_control_seeds']:raise ValueError('REGISTERED_SMALL_ADDENDUM_CHANGED')
    if p['candidate_arm']!='growth' or p['control_arm']!='baseline' or record['config']['horizon_days']!=70 or record['config']['customer_pool']!=36 or record['config']['opening']!=5000_000_000:raise ValueError('REGISTERED_EQUAL_CAPITAL_COMPARISON_CHANGED')
    return record


def freeze(output,source,publication_commit):
    output=Path(output).resolve();source=Path(source).resolve()
    if output.exists() or any(p.is_symlink() for p in [output,*output.parents]):raise ValueError('NEW_NORMALIZED_OUTPUT_REQUIRED')
    if not isinstance(publication_commit,str) or len(publication_commit)!=40 or any(c not in '0123456789abcdef' for c in publication_commit):raise ValueError('PUBLISHED_HARNESS_COMMIT_REQUIRED_BEFORE_FRESH_EXECUTION')
    reg=registration();runner=business(source);identity=runner.identity(source)
    if identity['sha256']!=EXPECTED_SOURCE or len(identity['files'])!=116:raise ValueError('EXACT_116_FILE_SOURCE002_REQUIRED')
    if reg['config']!=runner.config_for('central'):raise ValueError('UNCHANGED_CENTRAL_BUSINESS_TERMS_REQUIRED')
    output.mkdir(parents=True)
    for name in identity['files']:
        target=output/'source'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,target)
    harness=output/'harness';harness.mkdir();shutil.copyfile(__file__,harness/'run_connected014_expansion.py');shutil.copyfile(REGISTRATION,harness/'EXPANSION_ADDENDUM.json')
    f={'schema':'agi-alpha/connected014-expansion-freeze/v1','source':identity,'protocol':reg['protocol'],'configs':{'central':reg['config']},'git_commit':EXPECTED_COMMIT,'registered_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'harness':{'script_sha256':sha(__file__),'registration_sha256':sha(REGISTRATION),'publication_commit':publication_commit,'business_source_commit':EXPECTED_COMMIT,'evaluation_source_separate_from_business_source':True}}
    f['sha256']=digest(f);write(output/'FROZEN.json',f);return f


def read_freeze(output):
    output=Path(output).resolve();f=json.loads((output/'FROZEN.json').read_text());expected=f.pop('sha256')
    if digest(f)!=expected:raise ValueError('EXPANSION_FREEZE_CHANGED')
    reg=registration(output/'harness/EXPANSION_ADDENDUM.json')
    if f['protocol']!=reg['protocol'] or f['configs']!={'central':reg['config']} or f['harness']['registration_sha256']!=sha(output/'harness/EXPANSION_ADDENDUM.json') or f['harness']['script_sha256']!=sha(output/'harness/run_connected014_expansion.py') or sha(__file__)!=f['harness']['script_sha256']:raise ValueError('REGISTERED_EVALUATION_HARNESS_CHANGED')
    runner=business(output/'source')
    if runner.identity(output/'source')!=f['source'] or f['source']['sha256']!=EXPECTED_SOURCE:raise ValueError('UNCHANGED_SOURCE002_REQUIRED')
    f['sha256']=expected;return f,runner


def task(payload):
    source,manifest,output,f,entry=payload
    return business(source)._task((source,manifest,output,f,entry))


def worker(output):
    output=Path(output).resolve();f,runner=read_freeze(output)
    from adaptive_enterprise.instruments import prepare_services
    from enterprise.runner import RunLock
    with RunLock(output):
        manifest_path=output/'SERVICES.json'
        if manifest_path.exists():manifest=json.loads(manifest_path.read_text())
        else:manifest=prepare_services(output/'source','service-inputs',cohort_seed=f['protocol']['service_cohort_seed']);write(manifest_path,manifest)
        payloads=[(str(output/'source'),manifest,str(output),f,t) for t in runner.tasks(f['protocol'])];items=[]
        with ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn')) as pool:
            for item in pool.map(task,payloads):
                items.append(item);write(output/'PROGRESS.json',{'completed':len(items),'total':8,'last_task':item['task']['id']})
        results=[json.loads((output/'worlds'/i['task']['id']/'RESULT.json').read_text()) for i in items]
        report=runner._summary(f,items,results);report['evaluation_harness']=f['harness'];write(output/'REPORT.json',report)
        write(output/'COMPLETE.json',{'source_sha256':EXPECTED_SOURCE,'report_sha256':digest(report),'worlds':len(items),'evaluation_harness':f['harness']});return report


def audit_output(output):
    output=Path(output).resolve();f,runner=read_freeze(output);manifest=json.loads((output/'SERVICES.json').read_text());stored=json.loads((output/'REPORT.json').read_text())
    from connected_enterprise.verify import audit
    from connected_enterprise.scale import analyze
    from adaptive_enterprise.runner import _validate_manifest_origin
    cohort=_validate_manifest_origin({'protocol':{'service_cohort_seed':f['protocol']['service_cohort_seed']}},manifest,output/'source')
    tasks=runner.tasks(f['protocol']);indices=stored['worlds_index'];items=[];results=[]
    if len(tasks)!=8 or len(indices)!=8:raise ValueError('ALL_EIGHT_REGISTERED_BUSINESSES_REQUIRED')
    for entry,index in zip(tasks,indices):
        directory=output/'worlds'/entry['id'];r=json.loads((directory/'RESULT.json').read_text())
        if any(r[k]!=entry[k] for k in ['seed','case','arm']) or r['config']!=f['configs']['central'] or r['source']!=f['source'] or not r['complete'] or index['task']!=entry or index['result_sha256']!=digest(r):raise ValueError('FROZEN_BUSINESS_TASK_OR_RESULT_CHANGED')
        checked=audit(output/'source',manifest,r);growth=analyze(r)
        if checked!=json.loads((directory/'AUDIT.json').read_text()) or growth!=json.loads((directory/'GROWTH.json').read_text()):raise ValueError('INDEPENDENT_OPERATING_OR_GROWTH_RECEIPT_CHANGED')
        results.append(r);items.append({'task':entry,'result':runner.brief(r),'result_sha256':digest(r),'audit':checked,'growth':growth,'cpu_seconds':index['cpu_seconds']})
    expected=runner._summary(f,items,results);expected['evaluation_harness']=f['harness']
    if stored!=expected:raise ValueError('EXPANSION_REPORT_NOT_INDEPENDENTLY_REDERIVED')
    complete={'source_sha256':EXPECTED_SOURCE,'report_sha256':digest(expected),'worlds':8,'evaluation_harness':f['harness']}
    if complete!=json.loads((output/'COMPLETE.json').read_text()):raise ValueError('EXPANSION_COMPLETION_RECEIPT_CHANGED')
    receipt={'schema':'agi-alpha/connected014-expansion-package-audit/v1','source_sha256':EXPECTED_SOURCE,'worlds':8,'accepted':all(i['audit']['accepted'] for i in items),'scope':'NATIVE_FINANCE_AND_OPERATING_SEMANTICS_WITH_ARTIFACT_REEXECUTION_AND_REPORT_REDERIVATION','service_cohort':cohort,'evaluation_harness':f['harness'],'simulation_keys_required':False};write(output/'PACKAGE_AUDIT.json',receipt);return receipt


def package(output,archive):
    output=Path(output).resolve();archive=Path(archive).resolve();checked=audit_output(output)
    if not checked['accepted'] or archive.exists() or output in archive.parents:raise ValueError('NEW_OUTSIDE_ARCHIVE_AND_ACCEPTED_AUDIT_REQUIRED')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(output.rglob('*')):
            if not p.is_file() or p.is_symlink() or '.sqlite' in p.name or p.name.endswith('.adaptive-simulation-key') or '__pycache__' in p.parts or p.name in {'WORKER.lock','RUN.lock'}:continue
            z.write(p,p.relative_to(output).as_posix())
    return {'bytes':archive.stat().st_size,'sha256':sha(archive),'worlds':8,'scope':'KEY_FREE_AUDIT_AND_FRESH_REPRODUCTION_NOT_ACCOUNT_TAKEOVER'}


def watched_call(arguments,output,command):
    resource_path=output/'HARNESS_RESOURCE.json'
    prior=json.loads(resource_path.read_text()) if resource_path.exists() else {'cpu_seconds':0.,'wall_seconds':0.}
    reg=registration(output/'harness/EXPANSION_ADDENDUM.json')
    cutoff=datetime.datetime.fromisoformat(reg['bounds']['absolute_closeout_utc']).timestamp()
    wall_remaining=min(reg['bounds']['wall_minutes']*60-prior['wall_seconds'],cutoff-time.time())
    cpu_remaining=reg['bounds']['cpu_seconds']-prior['cpu_seconds']
    if wall_remaining<=0 or cpu_remaining<=0:raise ValueError('REGISTERED_ADDENDUM_RESOURCE_BOUNDARY')
    start=time.monotonic();process=subprocess.Popen(arguments,cwd=output/'source',start_new_session=True);maximum_cpu=0.;reason=None
    ticks=os.sysconf('SC_CLK_TCK')
    while process.poll() is None:
        cpu=0.
        for directory in Path('/proc').iterdir():
            if not directory.name.isdigit():continue
            try:
                fields=(directory/'stat').read_text().rsplit(')',1)[1].split()
                if int(fields[2])==process.pid:cpu+=sum(int(fields[i]) for i in [11,12,13,14])/ticks
            except (OSError,ValueError,IndexError):continue
        maximum_cpu=max(maximum_cpu,cpu)
        if time.monotonic()-start>=wall_remaining:reason='REGISTERED_WALL_OR_ABSOLUTE_CUTOFF'
        if maximum_cpu>=cpu_remaining:reason='REGISTERED_CPU_LIMIT'
        if reason:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=2)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
            break
        time.sleep(.2)
    observed={'cpu_seconds':prior['cpu_seconds']+maximum_cpu,'wall_seconds':prior['wall_seconds']+time.monotonic()-start,'scope':'Aggregate observed live process-group CPU plus reaped-child CPU; sampling may omit final sub-second work. Host/model billing unavailable.','last_command':command,'last_exit_code':process.returncode}
    write(resource_path,observed)
    if reason:
        write(output/'INTERRUPTION.json',{'schema':'agi-alpha/connected014-expansion-interruption/v1','reason':reason,'source_sha256':EXPECTED_SOURCE,'resource':observed,'completed_result_files':len(list((output/'worlds').glob('*/RESULT.json'))),'full_confirmation_complete':False})
        return 124
    return process.returncode


def main():
    parser=argparse.ArgumentParser();subs=parser.add_subparsers(dest='command',required=True)
    for name in ['run','resume','audit','package','_worker','_audit']:
        sub=subs.add_parser(name);sub.add_argument('--output',required=True)
        if name=='run':sub.add_argument('--source',required=True);sub.add_argument('--publication-commit',required=True)
        if name=='package':sub.add_argument('--archive',required=True)
    args=parser.parse_args();raw_output=Path(args.output).expanduser()
    if any(p.is_symlink() for p in [raw_output,*raw_output.parents]):raise ValueError('OUTPUT_SYMLINK_REFUSED')
    output=raw_output.resolve()
    if args.command=='run':freeze(output,args.source,args.publication_commit)
    if args.command in {'run','resume','audit'}:
        frozen_script=output/'harness/run_connected014_expansion.py';command='_audit' if args.command=='audit' else '_worker'
        return watched_call([sys.executable,str(frozen_script),command,'--output',str(output)],output,args.command)
    if args.command=='_worker':print(json.dumps(worker(output),sort_keys=True));return 0
    if args.command=='_audit':print(json.dumps(audit_output(output),sort_keys=True));return 0
    if args.command=='package':print(json.dumps(package(output,args.archive),sort_keys=True));return 0
    return 1

if __name__=='__main__':raise SystemExit(main())
