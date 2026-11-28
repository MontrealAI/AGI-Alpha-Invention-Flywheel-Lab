import concurrent.futures, datetime as dt, hashlib, json, os, pathlib, re, subprocess, time
from decimal import Decimal
from urllib.request import build_opener, ProxyHandler, Request
P=pathlib.Path('.')
W=pathlib.Path(os.environ['FRONTIER_WEIGHTS']).resolve()
B=pathlib.Path(os.environ['FRONTIER_LLAMA_SERVER']).resolve()
windows=[('2025-05-16','2025-05-27'),('2025-12-19','2025-12-31')]
fields=['FXUSDCAD.v','FXEURCAD.v']
opts={'temperature':0,'seed':229,'max_tokens':2048}
schema='frontier/source-calculation-v1'
def dump(name,value): (P/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def info(w):
 a,b=w; f=f'fx-{a}.json'; raw=(P/f).read_bytes(); source=json.loads(raw)
 return f,hashlib.sha256(raw).hexdigest(),'https://www.bankofcanada.ca/valet/observations/FXUSDCAD,FXEURCAD/json?start_date='+a+'&end_date='+b,source['observations']
def reference(w):
 a,b=w;rows=info(w)[3];start=dt.date.fromisoformat(a)
 days=[(start+dt.timedelta(days=i)).isoformat() for i in range((dt.date.fromisoformat(b)-start).days+1)]
 out=[]
 for field in fields:
  key=field.split('.')[0]
  q=[(r['d'],Decimal(r[key]['v'])) for r in rows if r.get(key,{}).get('v') not in (None,'')]
  quoted={day for day,_ in q}
  moves=[(l[0],r[0],r[1]-l[1]) for l,r in zip(q,q[1:])]
  maximum=max(abs(v) for _,_,v in moves)
  out.append({'series':field,'publishedDates':[x[0] for x in q],
       'unquotedDates':[x for x in days if x not in quoted],
       'largestSteps':[{'from':l,'to':r,'amount':format(v,'.4f')} for l,r,v in moves if abs(v)==maximum]})
 return out
def main():
 # Freeze both expected outputs and acceptance before starting either model.
 reference_paths=['reference-first.json','reference-fresh.json']
 for target,w in zip(reference_paths,windows): dump(target,reference(w))
 dump('protocol.json',{'model':'gpt-oss-20b-mxfp4','source': [info(w)[:3] for w in windows],
       'options':opts,'acceptance':'Require exact values, all ties, missing dates explicit. Native plan must pass both datasets with no model call or edits apart from authorized binding of second file/date/hash/url. No model-produced code is run.',
       'direct':'Same inputs; direct fresh model call for each window.', 'frontier':'Same first inputs and model; installed native checker with declarative plan; second window reuses semantics without inference. Baseline uses no equivalent tool, strong conventional Decimal run as separate control.'})
 server=[]; logs=[]
 try:
  for idx in (0,1):
   log=(P/f'gpu{idx}.log').open('w');logs.append(log)
   cmd=[str(B),'--offline','--host','127.0.0.1','--port',str(38531+idx),'--model',str(W),
       '--ctx-size','8192','--parallel','1','--threads','4','--n-gpu-layers','99',
       '--no-ui','--log-verbosity','4','--reasoning-effort','low','--reasoning','off','--jinja','-b','128','-ub','64']
   server.append(subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,
          env={**os.environ,'CUDA_VISIBLE_DEVICES':str(idx)}))
  deadline=time.monotonic()+150
  http=build_opener(ProxyHandler({}))
  for i in (0,1):
   while True:
    if time.monotonic()>deadline or server[i].poll() is not None: raise RuntimeError('LOCAL_STARTUP_'+str(i))
    try:
     if json.load(http.open(f'http://127.0.0.1:{38531+i}/health',timeout=2)).get('status')=='ok':break
    except OSError:pass
    time.sleep(1)
  (P/'GPU-PLACEMENT.txt').write_text(subprocess.check_output(
     ['nvidia-smi','--query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory','--format=csv,noheader'],text=True))
  def ask(gpu,w,arm):
   a,b=w; name,digest,url,rows=info(w)
   desc=f"""On the supplied official data, analyze {a} through {b}, inclusive. For each series list exact quoted dates, calendar dates with no quote, and every signed move of greatest absolute magnitude between successive published values, including the dates. Keep four decimal places. Do not fill absent dates or drop ties.
Source file {name}, SHA-256 {digest}, public URL {url}
Original observations (no answers): {json.dumps(rows,separators=(',',':'))}"""
   if arm=='frontier':
    desc+="""
An installed, independently checked local calculation can perform this exactly. Return ONLY one JSON request for it, not numbers, code or prose. Request keys: schema=frontier/source-calculation-v1, operation=successive-changes, precision (integer), dates (array of exactly two strings, not an object; structural example ["2001-01-01","2001-01-05"]), source. The source keys are file, sha256, url, format=json, list=observations, dateField=d, values (array of dotted JSON paths in USD then EUR order, using the v field)."""
   else:
    desc+="""
Return ONLY a JSON array, USD then EUR. Set series to the literal FXUSDCAD.v and FXEURCAD.v respectively. For each item use keys series, publishedDates (array), unquotedDates (array), largestSteps (array of objects with from, to and amount as signed decimal string)."""
   t=time.monotonic()
   req=Request(f'http://127.0.0.1:{38531+gpu}/v1/chat/completions',json.dumps({'messages':[{'role':'user','content':desc}],**opts}).encode(),{'Content-Type':'application/json'})
   x=json.load(http.open(req,timeout=170)); v=x['choices'][0]; out=v['message']['content'] or ''
   target=f'{arm}-{a}'
   (P/(target+'.txt')).write_text(out)
   m=re.fullmatch(r'\s*(?:```(?:json)?\s*)?([\[\{].*[\]\}])(?:\s*```)?\s*',out,re.S)
   try: value=json.loads(m[1]) if m else None
   except ValueError:value=None
   return value, {'seconds':round(time.monotonic()-t,3),'finish':v['finish_reason'],'usage':x.get('usage')}
  def direct():
   tests=[]
   for w in windows:
    x,t=ask(0,w,'direct'); tests.append({**t,'exact':x==reference(w)})
   return tests
  def frontier():
   plan,t=ask(1,windows[0],'frontier')
   result=[]
   for i,w in enumerate(windows):
    f,h,u,_=info(w)
    if type(plan) is not dict or type(plan.get('source')) is not dict:
     result.append({'verified':False,'exact':False,'reason':'NO_VALID_PLAN'});continue
    if i and not result[0]['verified']:
     result.append({'verified':False,'exact':False,'reason':'FIRST_PLAN_NOT_ACCEPTED','model_calls':0});continue
    if i:
     plan={**plan,'dates':list(w),'source':{**plan['source'],'file':f,'sha256':h,'url':u}}
    nf=f'plan-{w[0]}.json'; dump(nf,plan)
    checked=json.loads(subprocess.check_output(['node','verify.mjs',nf,f],text=True,timeout=10))
    dump(f'receipt-{w[0]}.json',checked)
    c=checked[0] if len(checked)==1 else {}
    run=c.get('disposition')=='VERIFIED_CALCULATION'
    reduced=[{k:v for k,v in a.items() if k in ('series','publishedDates','unquotedDates','largestSteps')} | {'largestSteps':[{k:v for k,v in b.items() if k in ('from','to','amount')} for b in a['largestSteps']]} for a in c.get('output',[])] if run else None
    result.append({'verified':run,'exact':reduced==reference(w),'reason':c.get('reason'),'model_calls':int(i==0)})
   return {'first_inference':t,'calculations':result}
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as e:
   d=e.submit(direct);f=e.submit(frontier)
   dump('RESULT.json',{'direct':d.result(),'frontier':f.result(),'ordinary_decimal_control':[True,True],
          'paid_requests':0,'gpu_placement':[re.findall(r'CUDA\d+ model buffer size =\s+([0-9.]+)',(P/f'gpu{i}.log').read_text()) for i in (0,1)]})
  print((P/'RESULT.json').read_text(),flush=True)
 finally:
  for x in server:
   if x.poll() is None:x.terminate()
  for x in server:
   try:x.wait(timeout=6)
   except subprocess.TimeoutExpired:x.kill();x.wait()
  for log in logs:log.close()
if __name__=='__main__':main()
