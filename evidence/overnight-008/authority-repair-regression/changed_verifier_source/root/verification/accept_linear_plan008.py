import argparse,hashlib,json,pathlib,sys
from fractions import Fraction
SCOPE='supplied-linear-ambiguity-plan-only'
SANDBOX_SHA256='103e2a8828a7aaf31faac475fb48ccbba1a685b4f64191dae4f6fbe8a9b6c7c8'
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def save(p,x):
 with pathlib.Path(p).open('x') as f: json.dump(x,f,indent=2,allow_nan=False);f.write('\n')
def rank(rows,n):
 a=[[Fraction(x) for x in row] for row in rows];r=0
 if any(len(row)!=n for row in a): raise ValueError('REFERENCE_ROW_WIDTH')
 for c in range(n):
  k=next((j for j in range(r,len(a)) if a[j][c]),None)
  if k is None: continue
  a[r],a[k]=a[k],a[r];z=a[r][c];a[r]=[x/z for x in a[r]]
  for j in range(r+1,len(a)):
   z=a[j][c];a[j]=[x-z*y for x,y in zip(a[j],a[r])]
  r+=1
  if r==len(a):break
 return r
def conventional(task):
 n=task['dimension'];rows=task['constraints'];r=rank(rows,n);selected=[];checks=0
 if r==n:return {'rank':r,'cost_units':0,'plan':[],'checks':0}
 for item in sorted(task['measurements'],key=lambda x:(x['cost_units'],x['id'])):
  if task['requires_absolute_calibration'] and not item['calibrated']:continue
  checks+=1;after=rank(rows+[x['row'] for x in selected]+[item['row']],n)
  if after>r:selected.append(item);r=after
  if r==n:break
 return {'rank':r,'cost_units':sum(x['cost_units'] for x in selected),'plan':[x['id'] for x in selected],'checks':checks}
def main():
 a=argparse.ArgumentParser();a.add_argument('--root',type=pathlib.Path,required=True);a.add_argument('--task',type=pathlib.Path,required=True);a.add_argument('--delivery',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True);v=a.parse_args()
 out=v.output.resolve();out.mkdir(parents=True,exist_ok=False);root=v.root.resolve();interpreter=root/'inventions/observability008/interpreter.py';sandbox=root/'flywheel/sandbox.py'
 srcsha=sha(__file__);artifact_sha=sha(v.delivery);task=json.loads(v.task.read_text());delivery=json.loads(v.delivery.read_text());checks={};errors=[];execution=None;reference=None
 try:
  checks['qualified_sandbox_unchanged']=sha(sandbox)==SANDBOX_SHA256
  checks['artifact_schema']=delivery['schema']=='agi-alpha/linear-ambiguity-delivery008/v1'
  checks['task_identity']=delivery['task_sha256']==sha(v.task)
  checks['interpreter_identity']=delivery['interpreter_sha256']==sha(interpreter)
  checks['linear_language']=task['language']=='linear-ambiguity-plan/v1'
  n=task['dimension'];checks['dimension']=type(n)is int and 1<=n<=48
  checks['typed_calibration']=type(task['requires_absolute_calibration'])is bool
  measurements=task['measurements'];ids=[x['id'] for x in measurements];checks['unique_measurement_ids']=len(ids)==len(set(ids))
  checks['typed_measurements']=all(type(x['calibrated'])is bool and type(x['cost_units'])is int and x['cost_units']>=0 for x in measurements)
  plan=delivery['plan'];checks['plan_identity']=type(plan)is list and all(type(x)is str for x in plan) and len(plan)==len(set(plan)) and set(plan)<=set(ids)
  if not all(checks.values()):raise ValueError('EARLY_IDENTITY_OR_SCHEMA_REFUSAL')
  selected=[next(x for x in measurements if x['id']==k) for k in plan]
  checks['calibration_obligation']=not task['requires_absolute_calibration'] or all(x['calibrated'] for x in selected)
  initial=rank(task['constraints'],n);final=rank(task['constraints']+[x['row'] for x in selected],n)
  checks['complete_supplied_linear_rank']=final==n and delivery['remaining_detected_ambiguity']==0
  cost=sum(x['cost_units'] for x in selected);checks['reported_cost']=type(delivery['cost_units'])is int and delivery['cost_units']==cost
  reference=conventional(task);checks['minimum_basis_cost']=reference['rank']==n and cost==reference['cost_units']
  checks['no_physical_or_commercial_upgrade']=delivery['physical_calibration_acquired']is False and delivery['commercial_cohort_admitted']is False and delivery['scientific_superiority_established']is False
  sys.path.insert(0,str(root));from flywheel.sandbox import run
  body={k:task[k] for k in ['language','dimension','constraints','measurements','requires_absolute_calibration','max_plans']};body.update(mode='execute',plan=plan)
  execution=run(interpreter,'interpret',body,delivery['interpreter_sha256'],{'wall_seconds':30,'cpu_seconds':20,'memory_bytes':268435456})
  result=execution.get('worker',{}).get('result',{})
  checks['actual_confined_execution']=execution['state']=='COMPLETE' and execution.get('worker',{}).get('confinement')=='linux-seccomp-default-deny' and result.get('status')=='DETECTED_LINEAR_AMBIGUITIES_REMOVED' and result.get('plan')==plan and result.get('cost_units')==cost and result.get('remaining_ambiguity')==0
 except Exception as e:errors.append(type(e).__name__+': '+str(e))
 report={'schema':'agi-alpha/independent-linear-plan-review008/v1','scope':SCOPE,'lane':'Independent fixed-artifact engineering review; DEVELOPMENT exposed, no statistical superiority claim or protected scientific confirmation','source_task_sha256':sha(v.task),'artifact_sha256':artifact_sha,'interpreter_sha256':delivery.get('interpreter_sha256'),'verifier_source_sha256':srcsha,'checks':checks,'errors':errors,'reference':reference,'execution':execution,'limits':['Source-derived constraints are supplied inputs; this review does not establish their scientific completeness.','calibrated:true means a conditional exact measurement specification; physical calibration and finite uncertainty are UNMEASURED_NOT_ENFORCED.','No global/practical identifiability, technical superiority, economic admission, funds or earned-funded successor claim.','Shared model/host/filesystem and libraries; separate role control is procedural, not external certification.']}
 save(out/'REVIEW.json',report)
 receipt={'schema':'agi-alpha/verifier-linear-plan-acceptance008/v1','scope':SCOPE,'accepted':all(checks.values()) and not errors,'artifact_sha256':artifact_sha,'interpreter_sha256':delivery.get('interpreter_sha256'),'verifier_source_sha256':srcsha,'task_sha256':sha(v.task),'review_sha256':sha(out/'REVIEW.json'),'scientific_superiority_established':False,'physical_calibration_acquired':False,'calibration_uncertainty_qualification':'UNMEASURED_NOT_ENFORCED','independence':'Procedural separate verifier; shared model, host, filesystem, Python and Linux/seccomp. No independent external certification.'}
 save(out/'ACCEPTANCE.json',receipt)
 authority={'schema':'agi-alpha/verifier-authority008/v1','owner':'separate verification role; builder must not edit this file or verifier source','scope':SCOPE,'verifier_source_sha256':srcsha,'verifier_source_path':'verification/accept_linear_plan008.py','accepted_artifacts':{artifact_sha:{'receipt_sha256':sha(out/'ACCEPTANCE.json'),'interpreter_sha256':delivery.get('interpreter_sha256'),'task_sha256':sha(v.task)}} if receipt['accepted'] else {},'trust':'Freeze this file hash in the consuming driver. Without a trusted frozen authority hash, receipt JSON is not authentication. This is procedural role separation, not adversarial-host cryptographic identity.'}
 save(out/'AUTHORITY.json',authority);print(json.dumps({'accepted':receipt['accepted'],'artifact_sha256':artifact_sha,'verifier_source_sha256':srcsha,'acceptance_sha256':sha(out/'ACCEPTANCE.json'),'authority_sha256':sha(out/'AUTHORITY.json'),'errors':errors}))
if __name__=='__main__':main()

# harmless tamper witness
