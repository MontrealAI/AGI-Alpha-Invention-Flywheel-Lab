import argparse,copy,hashlib,json,shutil,tempfile,zipfile
from pathlib import Path

ORIGINAL={'favorable','central','weak_demand','adverse','high_cost','uncollected','illiquid','underfunded','reference_100k','no_deployment','provider_failure','direct_K2'}

def read(p): return json.loads(Path(p).read_text())
def digest(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def review(out,revision='original'):
 out=Path(out);expected=ORIGINAL if revision=='original' else {'central','illiquid','provider_failure'} if revision=='v2' else {'gateway'}
 present={p.name for p in (out/'public').iterdir() if p.is_dir()}
 if present!=expected: raise ValueError('EXACT_REGISTERED_ACCOUNT_COVERAGE')
 summary=read(out/'SUMMARY.json');source=read(out/'SOURCE.json')
 if digest(source['files'])!=source['sha256'] or summary['source_sha256']!=source['sha256']: raise ValueError('SOURCE_AND_SUMMARY_BINDING')
 for n,h in source['files'].items():
  if Path(n).is_absolute() or '..' in Path(n).parts or hashlib.sha256((out/'source'/n).read_bytes()).hexdigest()!=h: raise ValueError('FROZEN_SOURCE_BYTES')
 results=[];seen=set()
 for name in sorted(expected):
  base=out/'public'/name;r=read(base/'result.json');m=read(base/'manifest.json');a=read(base/'account.json');s=a['ledger']['summary'];config=a['ledger']['config']
  opening=(100000 if name=='reference_100k' else 8000 if name=='underfunded' else 25000)*1000000
  if r['region']!=name or r['opening_microUSD']!=opening or config['opening']!=opening or config['contract']!='enterprise078-'+name or r['contract']!=config['contract']: raise ValueError('REGISTERED_IDENTITY_OR_CAPITAL')
  if r['manifest_sha256']!=digest(m) or r['export_sha256']!=digest(a) or digest(a) in seen: raise ValueError('UNIQUE_BOUND_NATIVE_EVIDENCE')
  seen.add(digest(a))
  expected_jobs=['gateway-K1'] if name=='gateway' else ['native-K2'] if name=='direct_K2' else ['native-K1','native-K1-repeat','native-K2']
  if [x['id'] for x in m['jobs']]!=expected_jobs or any(x['delivery_path']!=f'enterprise078/deliveries/{name}/{x["id"]}.json' for x in m['jobs']): raise ValueError('REGISTERED_DELIVERY_NAMESPACE')
  for j in m['jobs']:
   for n,h in m['source_hashes'].items():
    if source['files'].get(n)!=h: raise ValueError('NATIVE_SOURCE_DIFFERS_FROM_REGISTERED_EXECUTION')
  if r['summary']!=s or s['profit']!=s['revenue']+s['recoveryIncome']-s['expenses']: raise ValueError('PROFIT_RECONCILIATION')
  last=0;window=0
  for event in a['ledger']['actions']:
   delta=event['after']['profit']-last
   if 0<=event['day']<8760: window+=delta
   last=event['after']['profit']
  if window!=r['final365_microUSD'] or r['window_hours']!=[0,8760]: raise ValueError('COMPLETE_COMMON_FINAL365_WINDOW')
  if s['cash']!=opening+s['collections']+s['recoveryIncome']-s['expensePaid']: raise ValueError('CASH_RECONCILIATION')
  rows=[x for x in summary['accounts'] if x['region']==name]
  if len(rows)!=1 or rows[0]['profit_microUSD']!=s['profit'] or rows[0]['accepted']!=sum(bool(x.get('accepted')) for x in r['attempts']): raise ValueError('SUMMARY_ACCOUNT_COVERAGE')
  if r['K1_K2_chain'] and r['K1_K2_chain']['funding']:
   c=r['K1_K2_chain'];entry=c['funding'];before=c['before']['summary']
   if entry['funding']!='EARNED' or min(before['available'],before['unrestrictedEarned'])<entry['amount']: raise ValueError('EARNED_SUCCESSOR_FUNDING')
  if revision=='v2' and name=='illiquid':
   if r['K1_K2_chain']['funding'] is not None or r['attempts'][-1].get('decision')!='DEFER_WHOLE_DELIVERY_LIQUIDITY' or s['profit']<=0: raise ValueError('POSITIVE_PROFIT_LIQUIDITY_REGRESSION')
   if any(e['request'].get('id')=='K2-construction' for e in a['connected_journal']['entries']): raise ValueError('DEFER_MUST_NOT_SPEND')
  results.append({'region':name,'profit_microUSD':s['profit'],'window_hours':[0,8760],'actions':len(a['ledger']['actions']),'accepted_outputs':sum(bool(x.get('accepted')) for x in r['attempts'])})
 if len(summary['accounts'])!=len(expected): raise ValueError('EXACT_SUMMARY_COVERAGE')
 if revision=='original':
  tech=read(out/'technical.json')
  if len(tech)!=84 or len({(r['request_id'],r['method']) for r in tech})!=84: raise ValueError('EXACT_TECHNICAL_DENOMINATOR')
 return {'accepted':True,'revision':revision,'results':results,'source_sha256':source['sha256'],'scope':'independent coverage/arithmetic/binding review; native semantic audit separate; no ownership-HMAC authentication'}

def challenges(out):
 out=Path(out);results=[]
 cases=['missing_case','capital_substitution','wrong_contract','duplicate_evidence','false_summary','changed_profit']
 for case in cases:
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'evidence';shutil.copytree(out/'public',p/'public');shutil.copy2(out/'SUMMARY.json',p/'SUMMARY.json');shutil.copy2(out/'SOURCE.json',p/'SOURCE.json');shutil.copytree(out/'source',p/'source',ignore=shutil.ignore_patterns('__pycache__'))
   q=p/'public'/'central'/'result.json';r=read(q)
   if case=='missing_case': shutil.rmtree(p/'public'/'weak_demand')
   elif case=='capital_substitution': r['opening_microUSD']=100000000000
   elif case=='wrong_contract': r['contract']='enterprise078-adverse'
   elif case=='duplicate_evidence': shutil.copy2(p/'public'/'favorable'/'account.json',p/'public'/'central'/'account.json')
   elif case=='changed_profit': r['summary']['profit']+=1
   else:
    s=read(p/'SUMMARY.json');s['accounts'][0]['profit_microUSD']+=1;(p/'SUMMARY.json').write_text(json.dumps(s))
   q.write_text(json.dumps(r))
   try: review(p)
   except ValueError as e: results.append({'case':case,'rejected':True,'reason':str(e)})
   else: results.append({'case':case,'rejected':False})
 return {'all_rejected':all(x['rejected'] for x in results),'cases':results}

def unpack(archive,source,destination):
 archive,source,destination=Path(archive),Path(source),Path(destination)
 if destination.exists(): raise ValueError('NEW_EXTRACTION_REQUIRED')
 destination.mkdir(parents=True)
 with zipfile.ZipFile(archive) as z:
  for i in z.infolist():
   p=Path(i.filename)
   if p.is_absolute() or '..' in p.parts or 'private' in p.parts or (i.external_attr>>16)&0o170000==0o120000: raise ValueError('PUBLIC_REGULAR_ARCHIVE_REQUIRED')
  z.extractall(destination)
 for n,h in read(destination/'SOURCE.json')['files'].items():
  p=source/n;raw=p.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=h: raise ValueError('EXACT_REPLAY_SOURCE_REQUIRED:'+n)
  q=destination/'source'/n;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(raw)
 return destination

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('output',type=Path);p.add_argument('--revision',default='original',choices=['original','v2','gateway']);p.add_argument('--challenges',action='store_true');a=p.parse_args()
 print(json.dumps(challenges(a.output) if a.challenges else review(a.output,a.revision),sort_keys=True))
