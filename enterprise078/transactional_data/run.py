import argparse,hashlib,json,os,resource,shutil,sqlite3,subprocess,sys,time
from pathlib import Path
from . import operator
from .acceptance import inspect,verify

def save(p,value): p.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fixture(n):return [{'id':f'event-{i:08d}','account':f'group-{i%31:02d}','quantity':(i*17)%103-51} for i in range(n)]
def crash(action,db,events,mode,expected):
 input_path=db.with_suffix('.input.json');save(input_path,events)
 r=subprocess.run([sys.executable,'-m','enterprise078.transactional_data.operator',action,'--database',str(db),'--input',str(input_path),'--crash',mode],capture_output=True,text=True)
 if r.returncode!=expected:raise ValueError('EXPECTED_CRASH_NOT_OBSERVED:'+r.stderr)
 return r.returncode

def run_case(out,case):
 folder=out/case['id'];folder.mkdir();db=folder/'delivery.sqlite';csv_path=folder/'derived.csv';events=fixture(case['events']);facts={}
 t=time.perf_counter()
 if case['id'] in ('lost_reply','largest_gateway'):
  facts['exit_code']=crash('ingest',db,events,'after_commit',72)
  facts['accepted_before_retry']=verify(db,events,projection=False)['accepted']
  if not facts['accepted_before_retry']:raise ValueError('COMMIT_NOT_DURABLE_BEFORE_RETRY')
  operator.ingest(db,events)
 elif case['id']=='mid_batch_crash':
  operator.ingest(db,[]);facts['exit_code']=crash('ingest',db,events,'before_commit',71)
  facts['rollback_preserved']=inspect(db)['events']==[]
  if not facts['rollback_preserved']:raise ValueError('PARTIAL_COMMIT')
  operator.ingest(db,events)
 elif case['id']=='reordered_duplicate':operator.ingest(db,list(reversed(events))+events[::3])
 elif case['id'] in ('conflicting_duplicate','invalid_event'):
  operator.ingest(db,events);before=inspect(db)
  bad=[dict(events[0],quantity=events[0]['quantity']+1)] if case['id']=='conflicting_duplicate' else [{'account':'x','quantity':3}]
  try:operator.ingest(db,bad)
  except ValueError as e:facts['refused']=str(e)
  else:raise ValueError('INVALID_INTERVENTION_ACCEPTED')
  facts['prior_state_preserved']=inspect(db)==before
  if not facts['prior_state_preserved']:raise ValueError('REFUSAL_CHANGED_STATE')
 elif case['id']=='derived_restart':
  old=events[:128];operator.ingest(db,old);operator.project(db);before=inspect(db)['totals'];operator.ingest(db,events[128:])
  facts['stale_projection_refused']=not verify(db,events)['accepted']
  facts['exit_code']=crash('project',db,events,'projection',73)
  facts['prior_projection_preserved']=inspect(db)['totals']==before
  if not facts['stale_projection_refused'] or not facts['prior_projection_preserved']:raise ValueError('PROJECTION_ATOMICITY')
 else:operator.ingest(db,events)
 k1=verify(db,events,projection=False)
 operator.project(db);operator.export_csv(db,csv_path);k2=verify(db,events,csv_path=csv_path)
 if not k1['accepted'] or not k2['accepted']:raise ValueError('DELIVERY_REFUSED:'+case['id'])
 bad=folder/'mutation.sqlite';shutil.copy2(db,bad);c=sqlite3.connect(bad)
 c.execute('UPDATE totals SET units=units+1 WHERE account=(SELECT MIN(account) FROM totals)');c.commit();c.close()
 mutation_rejected=not verify(bad,events)['accepted'];bad.unlink()
 if not mutation_rejected:raise ValueError('CORRUPT_DERIVED_OUTPUT_ACCEPTED')
 facts['mutated_projection_rejected']=mutation_rejected
 return {'case':case['id'],'k1':k1,'k2':k2,'faults':facts,'wall_seconds':time.perf_counter()-t,'database_bytes':db.stat().st_size,'database_sha256':sha(db),'csv_bytes':csv_path.stat().st_size,'csv_sha256':sha(csv_path),'accepted':True}


def run(out):
 out=Path(out).resolve()
 if out.exists():raise ValueError('NEW_EXPERIMENT_DIRECTORY_REQUIRED')
 out.mkdir(parents=True);root=Path(__file__).resolve().parent
 protocol=json.loads((root/'PROTOCOL.json').read_text())
 source={p.name:sha(p) for p in sorted(root.iterdir()) if p.suffix in ('.py','.json')}
 save(out/'SOURCE.json',{'files':source,'head':subprocess.check_output(['git','-C',str(root.parents[1]),'rev-parse','HEAD'],text=True).strip(),'python':sys.version,'sqlite':sqlite3.sqlite_version,'preregistered_at':'c58b4cc3a8abf65b3945d09d98a2e10c88cf9791'})
 start=time.perf_counter();cpu=time.process_time();child_start=resource.getrusage(resource.RUSAGE_CHILDREN)
 results=[]
 for case in protocol['cases']:
  try: result=run_case(out,case)
  except Exception as error: result={'case':case['id'],'accepted':False,'error':type(error).__name__+': '+str(error)}
  results.append(result);save(out/'RESULTS.partial.json',results)
 child_end=resource.getrusage(resource.RUSAGE_CHILDREN)
 result={'accepted':len(results)==8 and all(r['accepted'] for r in results),'cases':results,'cpu_seconds':time.process_time()-cpu+(child_end.ru_utime+child_end.ru_stime-child_start.ru_utime-child_start.ru_stime),'wall_seconds':time.perf_counter()-start,'actual_generated_database_count':len(list(out.glob('*/delivery.sqlite'))),'largest_actual_event_count':max((r.get('k1',{}).get('unique_events',0) for r in results),default=0),'native_profit':None,'original_account_mutated':False,'actual_customers':0,'commercial_status':'UNEXECUTED_NO_ORIGINAL_AUTHORITY','whole_construction_and_inference_cost':'UNKNOWN_NOT_ZERO','discovery_advantage':'NOT_CLAIMED_ORDINARY_SQLITE_REUSED','scope':'actual local crash/restart and file outputs; synthetic data and developer-authored contracts'}
 save(out/'RESULTS.json',result);return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 result=run(a.output);print('TRANSACTIONAL_RESULT='+json.dumps(result,sort_keys=True));print('TRANSACTIONAL_SOURCE='+(a.output/'SOURCE.json').read_text().replace('\n',''));raise SystemExit(0 if result['accepted'] else 1)
