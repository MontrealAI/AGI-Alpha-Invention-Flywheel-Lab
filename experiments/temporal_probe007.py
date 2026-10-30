import argparse,asyncio,hashlib,importlib.metadata,inspect,json,platform,sqlite3,time
from pathlib import Path
from fastapi import Depends,FastAPI
from starlette.responses import StreamingResponse

def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v): p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def setup(p):
 c=sqlite3.connect(p);c.execute('PRAGMA foreign_keys=ON');c.executescript('CREATE TABLE parent(id INTEGER PRIMARY KEY); CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED); INSERT INTO parent VALUES(1);');c.commit();c.close()
async def run_case(arm,fail,path):
 setup(path);events=[];app=FastAPI();t=time.perf_counter()
 def note(kind,**x): events.append({'event':kind,'elapsed_seconds':time.perf_counter()-t,**x})
 async def resource():
  conn=sqlite3.connect(path);conn.execute('PRAGMA foreign_keys=ON');note('open')
  try:
   yield conn
   if arm!='split': note('commit_attempt');conn.commit();note('commit_success')
  finally:
   if conn.in_transaction: conn.rollback();note('rollback')
   conn.close();note('close')
 async def endpoint(conn=Depends(resource,scope='function' if arm=='function' else 'request')):
  conn.execute('INSERT INTO child VALUES(7,?)',(2 if fail else 1,));note('insert')
  if arm=='split': note('commit_attempt');conn.commit();note('commit_success')
  async def stream():
   note('stream_read_attempt');rows=conn.execute('SELECT id FROM child ORDER BY id').fetchall();note('stream_read_success',rows=rows)
   for row in rows: yield f'{row[0]}\n'.encode()
   note('stream_complete')
  return StreamingResponse(stream(),media_type='text/plain')
 app.add_api_route('/export',endpoint,methods=['GET'])
 async def receive(): return {'type':'http.request','body':b'','more_body':False}
 async def send(message):
  if message['type']=='http.response.start':
   check=sqlite3.connect(path);n=check.execute('SELECT COUNT(*) FROM child').fetchone()[0];check.close();note('response_start',status=message['status'],externally_visible_rows=n)
  elif message['type']=='http.response.body': note('response_body',body=message.get('body',b'').decode(),more_body=message.get('more_body',False))
 scope={'type':'http','asgi':{'version':'3.0','spec_version':'2.4'},'http_version':'1.1','method':'GET','scheme':'http','path':'/export','raw_path':b'/export','query_string':b'','root_path':'','headers':[],'client':('127.0.0.1',12345),'server':('localhost',80)}
 error=None
 try: await asyncio.wait_for(app(scope,receive,send),timeout=5)
 except Exception as exc: error={'type':type(exc).__name__,'message':str(exc)};note('exception',**error)
 c=sqlite3.connect(path);persisted=c.execute('SELECT id,parent_id FROM child').fetchall();c.close()
 kinds=[e['event'] for e in events];starts=[e for e in events if e['event']=='response_start'];success=any(e['status']==200 for e in starts)
 commit_before_success=not success or ('commit_success'in kinds and kinds.index('commit_success')<kinds.index('response_start'))
 live_stream=not success or ('stream_read_success'in kinds and kinds.index('stream_complete')<kinds.index('close'))
 no_false_success=not(fail and success)
 delivered=fail and not success and not persisted or not fail and success and error is None and persisted==[(7,1)] and live_stream
 return {'arm':arm,'commit_failure':fail,'events':events,'exception':error,'persisted_rows':persisted,'commit_before_success':commit_before_success,'live_resource_through_stream':live_stream,'no_success_after_failed_commit':no_false_success,'delivery_contract_pass':bool(delivered and commit_before_success and no_false_success)}
async def main(out):
 out.mkdir(parents=True,exist_ok=False)
 files={}
 for name in ['fastapi.routing','fastapi.dependencies.utils','fastapi.params','starlette.responses']:
  module=__import__(name,fromlist=['_']);p=inspect.getfile(module);files[name]={'path':p,'sha256':digest(p)}
 env={'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'packages':{x:importlib.metadata.version(x) for x in ['fastapi','starlette','pydantic','anyio']},'source_files':files,'probe_sha256':digest(__file__),'authorship':'Source-derived reproduction authored by development agent; not an upstream application or an observed customer deployment.','sources':['https://fastapi.tiangolo.com/advanced/advanced-dependencies/','https://github.com/fastapi/fastapi/discussions/14151']}
 write(out/'environment.json',env);results=[]
 for arm in ['request','function','split']:
  for fail in [False,True]:
   r=await run_case(arm,fail,out/f'{arm}-{int(fail)}.sqlite3');results.append(r);print(json.dumps({k:r[k] for k in ['arm','commit_failure','delivery_contract_pass','commit_before_success','live_resource_through_stream','no_success_after_failed_commit']}),flush=True)
 write(out/'results.json',results)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();asyncio.run(main(a.output))
