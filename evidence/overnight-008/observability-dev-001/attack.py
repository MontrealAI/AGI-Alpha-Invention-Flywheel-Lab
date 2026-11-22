import copy,hashlib,itertools,json,pathlib,random,sys,time
from fractions import Fraction
P=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(P.parents[1]/'lab'))
from flywheel.sandbox import run
S=P/'interpreter_snapshot.py.txt';H=hashlib.sha256(S.read_bytes()).hexdigest();records=[]
def invoke(name,p,expect=None):
 r=run(S,'interpret',p,H,{'cpu_seconds':2,'wall_seconds':5});v=r.get('worker',{}).get('result');ok=expect(r,v) if expect else None
 records.append({'name':name,'payload':p,'receipt':r,'test_passed':ok});return v

def base(n=2):
 return {'language':'linear-ambiguity-plan/v1','dimension':n,'constraints':[],'measurements':[{'id':f'm{i}','row':[int(j==i) for j in range(n)],'calibrated':True,'cost_units':i+1} for i in range(n)],'requires_absolute_calibration':True,'max_plans':2048}
def rank(rows,n):
 a=[[Fraction(x) for x in row] for row in rows];r=0
 for c in range(n):
  k=next((j for j in range(r,len(a)) if a[j][c]),None)
  if k is None: continue
  a[r],a[k]=a[k],a[r];z=a[r][c];a[r]=[x/z for x in a[r]]
  for j in range(r+1,len(a)):
   z=a[j][c];a[j]=[x-z*y for x,y in zip(a[j],a[r])]
  r+=1
  if r==len(a): break
 return r
def refs(p):
 n=p['dimension'];rows=p['constraints'];m=[x for x in p['measurements'] if not p['requires_absolute_calibration'] or x['calibrated']];sel=[];r=rank(rows,n)
 for x in sorted(m,key=lambda x:(x['cost_units'],x['id'])):
  after=rank(rows+[a['row'] for a in sel]+[x['row']],n)
  if after>r: sel.append(x);r=after
  if r==n: break
 full=rank(rows+[x['row'] for x in m],n)==n
 exact=None
 for mask in range(1<<len(m)):
  s=[m[i] for i in range(len(m)) if mask&(1<<i)]
  if rank(rows+[x['row'] for x in s],n)==n:
   key=(sum(x['cost_units'] for x in s),len(s))
   if exact is None or key<exact: exact=key
 return full,sum(x['cost_units'] for x in sel),r,exact

invoke('valid_rational',dict(base(),constraints=[['-1/-2','1/2']]),lambda r,v:r['state']=='COMPLETE' and v['remaining_ambiguity']==0)
for name,fn in [
 ('zero_denominator',lambda p:p['measurements'][0].update(row=['1/0',0])),
 ('bool_rational',lambda p:p['measurements'][0].update(row=[True,0])),
 ('float_rational',lambda p:p['measurements'][0].update(row=[1.0,0])),
 ('malformed_rational',lambda p:p['measurements'][0].update(row=['--1',0])),
 ('oversize_rational',lambda p:p['measurements'][0].update(row=[str(1<<129),0])),
 ('row_dimension',lambda p:p['measurements'][0].update(row=[1])),
 ('duplicate_ids',lambda p:p['measurements'][1].update(id='m0')),
 ('missing_calibration',lambda p:p.pop('requires_absolute_calibration')),
 ('calibration_not_bool',lambda p:p.update(requires_absolute_calibration=1)),
 ('negative_cost',lambda p:p['measurements'][0].update(cost_units=-1)),
 ('bool_cost',lambda p:p['measurements'][0].update(cost_units=True)),
 ('zero_dimension',lambda p:p.update(dimension=0)),
 ('bool_dimension',lambda p:p.update(dimension=True)),
 ('excess_dimension',lambda p:p.update(dimension=49)),
 ('unknown_mode',lambda p:p.update(mode='magic')),
 ('duplicate_execute_plan',lambda p:p.update(mode='execute',plan=['m0','m0'])),
 ('unknown_execute_plan',lambda p:p.update(mode='execute',plan=['missing'])),
 ('zero_search_cap',lambda p:p.update(max_plans=0)),
 ('excess_search_cap',lambda p:p.update(max_plans=2049)),
 ('unknown_measurement_field',lambda p:p['measurements'][0].update(extra=True))]:
 p=base();fn(p);invoke(name,p,lambda r,v:r['state']=='FAILED')
p=base();p['measurements'][0]['calibrated']=False
invoke('unknown_gain_refusal',p,lambda r,v:r['state']=='COMPLETE' and v['status']=='INSUFFICIENT_MEASUREMENTS' and v['remaining_ambiguity']==1 and v['refused'][0]['id']=='m0')
p['mode']='execute';p['plan']=['m0'];invoke('unknown_gain_cannot_execute',p,lambda r,v:r['state']=='FAILED')
p=base(3);p['max_plans']=1;invoke('search_limit_honest',p,lambda r,v:r['state']=='COMPLETE' and v['status']=='SEARCH_LIMIT')
p=base(1);p.update(constraints=[[1]],max_plans=1)
p['mode']='construct';invoke('already_full_construct',p,lambda r,v:r['state']=='COMPLETE' and v['remaining_ambiguity']==0)
p['mode']='ordinary';invoke('already_full_ordinary_limit',p,lambda r,v:r['state']=='COMPLETE' and v['status']=='SEARCH_LIMIT')
p=base(1);p.update(requires_global_identifiability=True);invoke('unknown_top_level_obligation_is_ignored',p,lambda r,v:r['state']=='COMPLETE' and v['status']=='DETECTED_LINEAR_AMBIGUITIES_REMOVED')
random.seed(20261030008)
for k in range(32):
 n=random.randint(1,6);m=random.randint(1,8);p=base(n);p['constraints']=[[random.randint(-2,2) for _ in range(n)] for _ in range(random.randint(0,n))];p['measurements']=[{'id':f'm{i:02}','row':[f'{random.randint(-2,2)}/{random.randint(1,3)}' for _ in range(n)],'calibrated':bool(random.randrange(4)),'cost_units':random.randint(0,12)} for i in range(m)]
 full,cost,r,exact=refs(p)
 invoke(f'fraction_reference_{k:02}',p,lambda rc,v,full=full,cost=cost,r=r,exact=exact:rc['state']=='COMPLETE' and v['remaining_ambiguity']==p['dimension']-r and (v['cost_units']==exact[0] if full else v['status']=='INSUFFICIENT_MEASUREMENTS'))
 p['mode']='ordinary';invoke(f'exhaustive_reference_{k:02}',p,lambda rc,v,full=full,exact=exact:rc['state']=='COMPLETE' and (v['cost_units']==exact[0] and v['remaining_ambiguity']==0 if full else v['status']=='INSUFFICIENT_MEASUREMENTS'))

fixture=P/'initialization_attack.py.txt';fixture.write_text("open('/etc/passwd').read()\ndef interpret(p): return True\n")
r=run(fixture,'interpret',{},hashlib.sha256(fixture.read_bytes()).hexdigest());records.append({'name':'initialization_read_confined','receipt':r,'test_passed':r['state']=='FAILED' and 'PermissionError' in r['stderr']})
try: run(fixture,'interpret',{},H)
except ValueError as e: records.append({'name':'tampered_source_refuses','error':str(e),'test_passed':'SOURCE_IDENTITY_MISMATCH' in str(e)})
else: records.append({'name':'tampered_source_refuses','test_passed':False})
x={'schema':'agi-alpha-observability-development-attacks/v1','candidate_snapshot_sha256':H,'lane':'EXPOSED_DEVELOPMENT_ONLY','test_count':len(records),'passed':sum(x['test_passed'] is True for x in records),'records':records,'scope':'Adversarial source/input/rational/rank/cost checks. Equal full rows and costs in all reference methods. No real calibration, global identifiability, physical feasibility, population significance, commercial or successor claim.'}
(P/'ATTACK_REPORT.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({'test_count':x['test_count'],'passed':x['passed'],'failed':[r['name'] for r in records if r['test_passed'] is not True],'candidate_sha256':H}))
