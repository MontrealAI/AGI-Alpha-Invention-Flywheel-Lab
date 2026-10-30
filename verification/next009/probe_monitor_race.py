"""Independent deterministic race witness and narrow monitor repair regressions.

Transient filesystem fixtures live outside the outer supervisor's output tree:
otherwise the deliberately reproduced legacy race could abort this test runner.
The common campaign ledger charges the whole bounded outer execution. Inner
ledgers are explicit test fixtures, not additional campaign allocations.
"""
import argparse
import copy
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

OLD_SHA = '8a10193e2cc29ca277560c7b2153d616e8cb46e64fbc7f54c102518dc2b71cbd'
NEW_SHA = '606947bf8ba6812bf5accb437391b630e3ef3faa5804c3189b65771361c52a14'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def terminal_fixture():
    return {'state':'complete','reason':None,'wall_seconds':0.01,'waited_cpu_seconds':0.01,'output_bytes':0,
            'limits':{'wall_seconds':5,'cpu_seconds':5,'memory_bytes':134217728,'output_bytes':65536,'storage_bytes':131072}}


def disappearance(module, base, operation):
    base.mkdir();entry=base/'transaction.sqlite-journal';entry.write_bytes(b'journal'*32)
    original=Path.lstat;events=[]
    def scheduled_unlink(path,*args,**kwargs):
        if path==entry and not events:
            events.append({'entry_existed_immediately_before_unlink':entry.is_file(),'point':'immediately before real lstat after directory enumeration'})
            entry.unlink()
        return original(path,*args,**kwargs)
    try:
        with patch.object(Path,'lstat',scheduled_unlink):
            value=module._usage(base) if operation=='usage' else module._final_receipt(terminal_fixture(),base)
        result={'returned':value,'exception':None}
    except Exception as error:
        result={'exception':type(error).__name__,'message':str(error)}
    result.update({'operation':operation,'events':events,'entry_absent_after':not entry.exists()})
    return result


def error_propagation(module, base, exception, operation):
    base.mkdir();entry=base/'protected-file';entry.write_bytes(b'cannot-ignore-this-entry')
    original=Path.lstat;fired=[]
    def injected(path,*args,**kwargs):
        if path==entry:
            fired.append(True)
            raise exception('test-only injected filesystem error')
        return original(path,*args,**kwargs)
    try:
        with patch.object(Path,'lstat',injected):
            module._usage(base) if operation=='usage' else module._final_receipt(terminal_fixture(),base)
        return {'passed':False,'exception':None,'injection_fired':bool(fired)}
    except Exception as error:
        return {'passed':type(error) is exception and bool(fired),'exception':type(error).__name__,'injection_fired':bool(fired)}


def early_signal(root, source, temporary, output, signum, label, point):
    case=temporary/(label+'-'+point);case.mkdir();run=case/'run';worker=case/'worker-launched';ledger=case/'fixture-ledger.json'
    driver='''import importlib.util,os,signal,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('monitor_under_test',%r);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
output=Path(%r);fired=False
original_mkdir=Path.mkdir;original_write=module._write
def mkdir(path,*args,**kwargs):
 global fired
 result=original_mkdir(path,*args,**kwargs)
 if path==output and %r=='mkdir' and not fired:
  fired=True;os.kill(os.getpid(),%d)
 return result
def write(path,value):
 global fired
 if path.name=='PENDING.json' and %r=='pending_write' and not fired:
  fired=True;os.kill(os.getpid(),%d)
 return original_write(path,value)
Path.mkdir=mkdir;module._write=write
result=module.run([sys.executable,'-c',%r],output,Path(%r),%r,dict(wall_seconds=2,cpu_seconds=2,memory_bytes=134217728,output_bytes=65536,storage_bytes=131072))
assert fired
assert result['receipt']['state']=='interrupted',result
assert result['receipt']['descendant_survivors'] is False,result
assert not Path(%r).exists()
'''%(str(source),str(run),point,int(signum),point,int(signum),"from pathlib import Path;Path(%r).write_text('ran')"%str(worker),str(ledger),label+'-'+point,str(worker))
    artifact=output/('early-'+label+'-'+point);artifact.mkdir();script=artifact/'driver.py';script.write_text(driver)
    executed=subprocess.run([sys.executable,str(script)],capture_output=True,timeout=5)
    (artifact/'stdout.log').write_bytes(executed.stdout);(artifact/'stderr.log').write_bytes(executed.stderr)
    receipt_path=run/'RECEIPT.json';receipt=json.loads(receipt_path.read_bytes()) if receipt_path.exists() else None
    if receipt:save(artifact/'OBSERVED_RECEIPT.json',receipt)
    if ledger.exists():(artifact/'fixture-ledger.json').write_bytes(ledger.read_bytes())
    passed=executed.returncode==0 and receipt is not None and receipt['state']=='interrupted' and receipt['descendant_survivors'] is False and not worker.exists()
    return {'signal':label,'injection_point':point,'passed':passed,'driver_exit_code':executed.returncode,'worker_marker_absent':not worker.exists(),'receipt_wrapper_sha256':receipt.get('wrapper_sha256') if receipt else None}


def sqlite_churn(module, temporary, output):
    run=temporary/'sqlite-monitor-run';ledger=temporary/'sqlite-fixture-ledger.json'
    worker='''import json,sqlite3,time
from pathlib import Path
root=Path(%r);db=root/'active.sqlite';connection=sqlite3.connect(db)
mode=connection.execute('PRAGMA journal_mode=DELETE').fetchone()[0]
connection.execute('CREATE TABLE values_table(id INTEGER PRIMARY KEY,value BLOB)')
connection.execute('INSERT INTO values_table VALUES(1,zeroblob(4096))');connection.commit()
present=absent=0
for index in range(300):
 connection.execute('BEGIN IMMEDIATE');connection.execute('UPDATE values_table SET value=randomblob(4096) WHERE id=1')
 present+=int(Path(str(db)+'-journal').is_file())
 connection.commit();absent+=int(not Path(str(db)+'-journal').exists())
 if index%%10==0:time.sleep(.004)
connection.close()
(root/'CHURN.json').write_text(json.dumps({'sqlite_version':sqlite3.sqlite_version,'journal_mode':mode,'transactions':300,'journal_observed_before_commit':present,'journal_absent_after_commit':absent,'database_bytes':db.stat().st_size}))
'''%str(run)
    (output/'sqlite-worker.py').write_text(worker)
    result=module.run([sys.executable,'-c',worker],run,ledger,'sqlite-journal-churn',dict(wall_seconds=5,cpu_seconds=5,memory_bytes=134217728,output_bytes=131072,storage_bytes=262144),cwd=str(temporary))
    receipt=result['receipt'];churn=json.loads((run/'CHURN.json').read_bytes()) if (run/'CHURN.json').exists() else None
    save(output/'SQLITE_MONITOR_RECEIPT.json',receipt);save(output/'SQLITE_CHURN_OBSERVATIONS.json',churn)
    (output/'sqlite-fixture-ledger.json').write_bytes(ledger.read_bytes())
    for name in ['stdout.log','stderr.log']:(output/('sqlite-'+name)).write_bytes((run/name).read_bytes())
    passed=receipt['state']=='complete' and receipt['descendant_survivors'] is False and churn is not None and churn['journal_mode']=='delete' and churn['journal_observed_before_commit']==300 and churn['journal_absent_after_commit']==300
    return {'passed':passed,'receipt_state':receipt['state'],'descendant_survivors':receipt['descendant_survivors'],'wrapper_sha256':receipt['wrapper_sha256'],'observed_churn':churn}


def main(root, output):
    output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    old_path=root/'experiments/resource006_v3.py';new_path=root/'research/next009/resource_monitor009.py';old_raw=old_path.read_bytes();new_raw=new_path.read_bytes()
    if sha(old_raw)!=OLD_SHA or sha(new_raw)!=NEW_SHA:raise ValueError('MONITOR_SOURCE_NOT_THE_REVIEWED_EDITION')
    (output/'original_resource006_v3.py').write_bytes(old_raw);(output/'repaired_resource_monitor009.py').write_bytes(new_raw)
    old=load_module(old_path,'original_monitor009_test');new=load_module(new_path,'repaired_monitor009_test');checks=[]
    with tempfile.TemporaryDirectory(prefix='next009-independent-monitor-') as name:
        temporary=Path(name)
        for operation in ['usage','final_receipt']:
            original=disappearance(old,temporary/('old-'+operation),operation);repaired=disappearance(new,temporary/('new-'+operation),operation)
            passed=original.get('exception')=='FileNotFoundError' and repaired.get('exception') is None and len(original['events'])==len(repaired['events'])==1 and original['entry_absent_after'] and repaired['entry_absent_after']
            if operation=='usage':passed=passed and repaired['returned']==0
            else:passed=passed and repaired['returned']['state']=='complete' and repaired['returned']['output_bytes']>0
            checks.append({'case':'same_actual_unlink_before_lstat_'+operation,'passed':passed,'original':original,'repaired':repaired})
        files=temporary/'regular-and-symlink';files.mkdir();(files/'nested').mkdir();(files/'a').write_bytes(b'abcde');(files/'nested/b').write_bytes(b'1234567');(files/'empty').touch()
        outside=temporary/'external-target';outside.write_bytes(b'x'*100000);(files/'outside-link').symlink_to(outside);(files/'dangling-link').symlink_to('missing-target')
        expected=12+(files/'outside-link').lstat().st_size+(files/'dangling-link').lstat().st_size;observed=new._usage(files)
        checks.append({'case':'regular_nested_empty_and_symlink_entries','passed':observed==expected,'observed_bytes':observed,'expected_bytes':expected,'external_target_bytes_not_followed':100000})
        for error in [PermissionError,OSError]:
            for operation in ['usage','final_receipt']:
                checks.append({'case':error.__name__+'_propagates_'+operation,**error_propagation(new,temporary/(error.__name__+'-'+operation),error,operation),'scope':'Injected exception at lstat tests propagation; not a claim of an observed OS permission denial.'})
        for kind in ['aggregate','individual']:
            files=temporary/('bound-'+kind);files.mkdir();(files/'large').write_bytes(b'x'*13000);receipt=terminal_fixture()
            receipt['limits']['storage_bytes']=10000 if kind=='aggregate' else 50000;receipt['limits']['output_bytes']=20000 if kind=='aggregate' else 5000
            result=new._final_receipt(receipt,files);reason='final-aggregate-output-storage-limit' if kind=='aggregate' else 'final-output-file-limit'
            checks.append({'case':kind+'_limit_still_enforced','passed':result['state']=='overrun' and result['reason']==reason,'result':result})
        checks.append({'case':'actual_sqlite_delete_journal_churn',**sqlite_churn(new,temporary,output)})
        for signum,label in [(signal.SIGINT,'SIGINT'),(signal.SIGTERM,'SIGTERM')]:
            for point in ['mkdir','pending_write']:
                checks.append({'case':'early_'+label+'_'+point,**early_signal(root,new_path,temporary,output,signum,label,point)})
    unchanged=old_path.read_bytes()==old_raw and new_path.read_bytes()==new_raw
    report={'schema':'agi-alpha/next009-independent-monitor-race-repair/v1','passed':all(c['passed'] for c in checks) and unchanged,'original_source_sha256':OLD_SHA,'repaired_source_sha256':NEW_SHA,'verifier_source_sha256':sha(Path(__file__).read_bytes()),'checks':checks,'source_unchanged_during_checks':unchanged,'wall_seconds':time.monotonic()-started,'scope':'Deterministic real-file unlink at the reproduced stat boundary in both original and repaired live source; direct helper checks plus real SQLite transactions and actual early kernel signals. Shared infrastructure; no outside certification.','resource_scope':'All work charged by one outer common-ledger reservation. Inner ledgers are small test fixtures only. Transient fixtures outside the outer monitored output prevent the intentionally reproduced legacy race from aborting the test runner. SQLite worker itself uses unchanged limits (5 CPU/wall seconds,128MiB memory,256KiB total output); other fixture payloads total under1MiB. Fixture logs, receipts, sources and schedules are retained.','historical_failure_status':'Actual public-clean-r1 failure and immediate descendant_survivors=True remain unchanged. Later scoped process inspection is separate. These tests do not repair or overturn the older frozen cycle001 SIGINT failure.'}
    save(output/'REPORT.json',report);print(json.dumps({'passed':report['passed'],'checks':len(checks),'original':OLD_SHA,'repaired':NEW_SHA,'wall_seconds':report['wall_seconds']}));return 0 if report['passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();raise SystemExit(main(args.root.resolve(),args.output.resolve()))
