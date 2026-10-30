import argparse,contextlib,copy,hashlib,importlib,json,os,pathlib,sqlite3,sys,time
p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True);a=p.parse_args();root=pathlib.Path(a.root).resolve();out=pathlib.Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False);sys.path.insert(0,str(root))
C=importlib.import_module('inventions.lifetime007.compiler');E=importlib.import_module('inventions.lifetime007.execute')
ROLES=['acquire','prepare','durable','consume','release'];OPS={'sqlite':['sqlite_connect','sqlite_insert','sqlite_commit','sqlite_stream','sqlite_close'],'file':['file_open','file_write','file_fsync','file_stream','file_close']}
rows=[];executions=[];task_specs=[]
def check(name,condition,detail=None):rows.append({'id':name,'passed':bool(condition),'detail':detail})
def refused(name,fn):
 try:fn()
 except (ValueError,TypeError,KeyError):check(name,True);return
 except Exception as exc:check(name,False,type(exc).__name__+':'+str(exc));return
 check(name,False,'accepted unsupported input')
def spec(domain,index):
 ids=['consume-'+str(index),'release-'+str(index),'acquire-'+str(index),'prepare-'+str(index),'durable-'+str(index)];effects=[{'id':ident,'operation':op,'resource':'resource-µ-'+str(index)} for ident,op in zip(ids,OPS[domain])]
 effects=[effects[i] for i in [3,0,4,2,1]]
 blocks=[{'effects':[ids[3]],'separable':False},{'effects':[ids[2],ids[4]],'separable':True},{'effects':[ids[1]],'separable':False},{'effects':[ids[0]],'separable':False}]
 return {'schema':'agi-alpha/lifetime-spec007/v1','task_id':'protected-'+domain+'-'+str(index),'domain':domain,'effects':effects,'blocks':blocks,'obligations':{'durable_before_visible':True,'live_during_consumption':True,'close_on_exit':True}}
def role_ids(s):return {ROLES[OPS[s['domain']].index(e['operation'])]:e['id'] for e in s['effects']}
def strong_reference(domain,values,directory):
 directory.mkdir();path=directory/'reference';events=[]
 if domain=='sqlite':
  conn=sqlite3.connect(path)
  try:
   conn.execute('CREATE TABLE payload(seq INTEGER PRIMARY KEY,value TEXT)');conn.executemany('INSERT INTO payload(value) VALUES (?)',[(x,) for x in values]);conn.commit();events.append('durable');got=[x[0] for x in conn.execute('SELECT value FROM payload ORDER BY seq')];events.extend(['consume']*len(got))
  finally:conn.close();events.append('release')
 else:
  stream=path.open('w+b')
  try:
   for value in values:
    raw=value.encode();stream.write(len(raw).to_bytes(4,'big')+raw)
   stream.flush();os.fsync(stream.fileno());events.append('durable');stream.seek(0);got=[]
   while header:=stream.read(4):
    n=int.from_bytes(header,'big');got.append(stream.read(n).decode());events.append('consume')
  finally:stream.close();events.append('release')
 return {'output':got,'events':events}
def execute_observed(s,plan,values,fault,label):
 directory=out/label;directory.mkdir();held=[];fsync_calls=[]
 oldtemp=E.tempfile.TemporaryDirectory;oldconnect=sqlite3.connect;oldopen=pathlib.Path.open;oldfsync=os.fsync
 class AuditedConnection(sqlite3.Connection):
  close_count=0
  def close(self):self.close_count+=1;return super().close()
 def connect(*args,**kwargs):
  kwargs['factory']=AuditedConnection;c=oldconnect(*args,**kwargs);held.append(c);return c
 class AuditedFile:
  def __init__(self,stream):self.stream=stream;self.close_count=0
  def __getattr__(self,name):return getattr(self.stream,name)
  def close(self):self.close_count+=1;return self.stream.close()
 def openpath(path,*args,**kwargs):
  stream=oldopen(path,*args,**kwargs)
  if path==directory/'payload':stream=AuditedFile(stream);held.append(stream)
  return stream
 def fsync(fd):fsync_calls.append(fd);return oldfsync(fd)
 try:
  E.tempfile.TemporaryDirectory=lambda **kwargs:contextlib.nullcontext(str(directory));sqlite3.connect=connect;pathlib.Path.open=openpath;os.fsync=fsync
  result=E.execute(s,plan,values,fault=fault)
 finally:E.tempfile.TemporaryDirectory=oldtemp;sqlite3.connect=oldconnect;pathlib.Path.open=oldopen;os.fsync=oldfsync
 closed=[]
 for resource in held:
  if isinstance(resource,AuditedFile):closed.append(resource.stream.closed and resource.close_count==1)
  else:
   try:resource.execute('SELECT 1');closed.append(False);resource.close()
   except sqlite3.ProgrammingError:closed.append(resource.close_count==1)
 actual=None
 if s['domain']=='sqlite' and (directory/'payload').exists():
  conn=oldconnect(directory/'payload')
  try:actual=[r[0] for r in conn.execute('SELECT value FROM payload ORDER BY seq')]
  finally:conn.close()
 elif s['domain']=='file' and (directory/'payload').exists():
  raw=(directory/'payload').read_bytes();actual=[]
  while raw:
   n=int.from_bytes(raw[:4],'big');actual.append(raw[4:4+n].decode());raw=raw[4+n:]
 result['independent_observation']={'all_real_handles_closed_exactly_once':bool(held) and all(closed),'real_handles':len(held),'actual_persisted_values':actual,'real_fsync_calls':len(fsync_calls)}
 executions.append({'case':label,'spec':s,'fault':fault,'result':result});return result
values=['protected ω 89413','', 'é'*128,'tail\x00value'];faults=[None,'commit','consume','interrupt','mid_consume','mid_interrupt']
for index,domain in enumerate(['sqlite','file']):
 s=spec(domain,index);task_specs.append(s);roles=role_ids(s);expected=[roles[x] for x in ROLES];plan=C.construct(s)
 check(domain+'-mapping',plan['mapping']['roles']==roles);check(domain+'-constructed',plan['status']=='CONSTRUCTED' and plan['order']==expected and len(plan['split_blocks'])==1)
 check(domain+'-reset-infeasible',C.construct(s,allow_factorization=False)['status']=='INFEASIBLE_IN_GRAMMAR')
 reference=strong_reference(domain,values,out/(domain+'-strong-reference'));check(domain+'-competent-complete-reference',reference['output']==values and reference['events'][0]=='durable' and reference['events'][-1]=='release')
 for fault in faults:
  label=domain+'-'+str(fault);r=execute_observed(s,plan,values,fault,label);events=[x['event'] for x in r['trace']];want=values if fault is None else values[:1] if fault.startswith('mid_') else []
  check(label+'-output',r['output']==want);check(label+'-actual-close',r['closed'] and r['independent_observation']['all_real_handles_closed_exactly_once'] and events.count('release')==1)
  check(label+'-temporal-contract',all(x.get('live') and x.get('durable') for x in r['trace'] if x['event']=='consume') and ('visible' not in events or events.index('durable')<events.index('visible')<events.index('release')))
  check(label+'-error',r['error'] is None if fault is None else r['error'] is not None)
  if fault is None:check(label+'-real-persistence',r['independent_observation']['actual_persisted_values']==values and (domain!='file' or r['independent_observation']['real_fsync_calls']==1))
 nonsep=copy.deepcopy(s);nonsep['task_id']+='-atomic';nonsep['blocks'][1]['separable']=False
 check(domain+'-nonseparable-refusal',C.construct(nonsep)['status']=='INFEASIBLE_IN_GRAMMAR')
 forged=copy.deepcopy(plan);forged['spec_sha256']='0'*64;refused(domain+'-stale-plan',lambda:C.validate_plan(s,forged))
 forged2=copy.deepcopy(plan);forged2['order'][-1],forged2['order'][-2]=forged2['order'][-2],forged2['order'][-1];refused(domain+'-release-before-consume',lambda:C.validate_plan(s,forged2))
 forged3=copy.deepcopy(plan);forged3['split_blocks']*=2;refused(domain+'-duplicate-factorization',lambda:C.validate_plan(s,forged3))
 bad=copy.deepcopy(s);bad['effects'][0]['operation']='file_stream' if domain=='sqlite' else 'sqlite_stream';refused(domain+'-misleading-domain',lambda:C.construct(bad))
 bad=copy.deepcopy(s);bad['obligations']['durable_before_visible']=False;refused(domain+'-weakened-obligation',lambda:C.construct(bad))
 bad=copy.deepcopy(s);bad['effects'][0]['operation']='sqlite_shell';refused(domain+'-unknown-semantics',lambda:C.construct(bad))
 bad=copy.deepcopy(s);bad['effects'][0]['resource']='unrelated';refused(domain+'-resource-mismatch',lambda:C.construct(bad))
 for label,badvalues in [('empty',[]),('oversized',['x'*257]),('count',['x']*65),('wrongtype',[1])]:refused(domain+'-input-'+label,lambda:E.execute(s,plan,badvalues))
 refused(domain+'-unknown-fault',lambda:E.execute(s,plan,values,fault='invented-fault'))
source,target=task_specs;sourceplan=C.construct(source);operator=sourceplan['generated_operator'];mapped=C.remap_operator(operator,source,target);reused=C.construct_from_operator(target,mapped);fresh=C.construct(target)
check('cross-domain-retrieval-remap-construction',reused['order']==fresh['order'] and reused['search_attempts']==0)
r=execute_observed(target,reused,values,None,'retained-cross-domain');check('cross-domain-actual-execution',r['output']==values and r['independent_observation']['all_real_handles_closed_exactly_once'])
ordinary=copy.deepcopy(mapped);ordinaryplan=C.construct_from_operator(target,ordinary);check('equivalent-content-ordinary-tie',ordinaryplan==reused)
badoperator=copy.deepcopy(operator);badoperator['precedence'][0].reverse();refused('corrupted-source-operator',lambda:C.remap_operator(badoperator,source,target))
badtarget=copy.deepcopy(target);badtarget['blocks'][1]['separable']=False;refused('nonseparable-failed-transfer',lambda:C.remap_operator(operator,source,badtarget))
badoperator=copy.deepcopy(mapped);badoperator['precedence']=[['unrecognized','edge']];refused('unsupported-invariant',lambda:C.construct_from_operator(target,badoperator))
report={'schema':'agi-alpha/temporal-verifier-cases007/v1','accepted':all(x['passed'] for x in rows),'checks':rows,'checks_passed':sum(x['passed'] for x in rows),'checks_total':len(rows),'executions':executions,'case_source_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'task_identity_sha256':hashlib.sha256(json.dumps(task_specs,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest(),'scope':'Fixed-cohort descriptive checks of supplied effect grammar, actual SQLite/file operations and injected exceptions. No actual process cancellation, hardware power-loss guarantee, mathematical novelty, discovery-policy advantage or strongest-conventional superiority.'}
(out/'REPORT.json').write_text(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'accepted':report['accepted'],'checks_passed':report['checks_passed'],'checks_total':report['checks_total']}));sys.exit(0 if report['accepted'] else 1)
