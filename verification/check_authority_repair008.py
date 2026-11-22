import copy,hashlib,json,pathlib,runpy,shutil,sys,time
P=pathlib.Path(__file__).resolve().parent;ROOT=P.parent/'lab';OUT=P/'authority-repair-regression';OUT.mkdir(exist_ok=False);sys.path.insert(0,str(ROOT));driver=ROOT/'experiments/observability008.py';snapshot=OUT/'driver_snapshot.py.txt';snapshot.write_bytes(driver.read_bytes());h=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
previous=ROOT/'evidence/overnight-008/observability-development-r2/artifacts';acceptance=ROOT/'evidence/overnight-008/observability-accepted-r2/ACCEPTANCE.json';fresh=ROOT/'research/observability008/crauste/model_constraints.json';old=ROOT/'evidence/overnight-008/observability-development-r1/artifacts';records=[]
for name,expected in [('forged_receipt','RECEIPT_NOT_AUTHORIZED_FOR_ARTIFACT'),('changed_receipt_bytes','RECEIPT_NOT_AUTHORIZED_FOR_ARTIFACT'),('changed_authority_bytes','PINNED_VERIFIER_AUTHORITY_REQUIRED'),('changed_verifier_source','VERIFIER_SOURCE_IDENTITY'),('changed_interpreter_source','AUTHORITY_SOURCE_OR_TASK_MISMATCH'),('old_artifact_new_receipt','RECEIPT_NOT_AUTHORIZED_FOR_ARTIFACT'),('valid_frozen_receipt',None)]:
 case=OUT/name;copyroot=case/'root';case.mkdir();
 for rel in ['inventions/observability008/interpreter.py','verification/observability008_AUTHORITY.json','verification/accept_linear_plan008.py']:
  p=copyroot/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,p)
 accepted=json.loads(acceptance.read_text());receipt=case/'ACCEPTANCE.json';receipt.write_bytes(acceptance.read_bytes());prev=previous
 if name=='forged_receipt':
  accepted={k:accepted[k] for k in ['accepted','artifact_sha256','interpreter_sha256','scope']};receipt.write_text(json.dumps(accepted)+'\n')
 if name=='changed_receipt_bytes':accepted['unreviewed_annotation']='caller supplied';receipt.write_text(json.dumps(accepted,indent=2)+'\n')
 if name=='changed_authority_bytes':
  p=copyroot/'verification/observability008_AUTHORITY.json';x=json.loads(p.read_text());x['owner']='caller';p.write_text(json.dumps(x,indent=2)+'\n')
 if name=='changed_verifier_source':
  p=copyroot/'verification/accept_linear_plan008.py';p.write_bytes(p.read_bytes()+b'\n# harmless tamper witness\n')
 if name=='changed_interpreter_source':
  p=copyroot/'inventions/observability008/interpreter.py';p.write_bytes(p.read_bytes()+b'\n# harmless tamper witness\n')
 if name=='old_artifact_new_receipt':prev=old
 namespace=runpy.run_path(str(snapshot),run_name='verifier_reviews_frozen_driver');fn=namespace['retain_and_use'];fn.__globals__['ROOT']=copyroot;start=time.monotonic();error=None
 try:fn(prev,receipt,fresh,case/'run')
 except Exception as e:error=type(e).__name__+': '+str(e)
 memories=list((case/'run/memory').glob('*.json')) if (case/'run/memory').exists() else []
 passed=(error is not None and expected in error and not memories) if expected else (error is None and len(memories)==1)
 records.append({'name':name,'expected_error':expected,'observed_error':error,'memory_records':len(memories),'passed':passed,'wall_seconds':time.monotonic()-start,'receipt_sha256':h(receipt)})
x={'schema':'agi-alpha-authority-repair-development-regression/v1','lane':'EXPOSED DEVELOPMENT ONLY; negative cases are deliberate isolated copies, not legitimate retained verification','driver_sha256':h(snapshot),'verifier_source_sha256':h(ROOT/'verification/accept_linear_plan008.py'),'authority_sha256':h(ROOT/'verification/observability008_AUTHORITY.json'),'accepted_receipt_sha256':h(acceptance),'records':records,'passed':all(x['passed'] for x in records),'protection_scope':'Runtime rejects unlisted/mutated receipt/source/authority under the frozen driver. Shared writable host and builder control of future source remain procedural trust boundaries; no external certification.'}
(OUT/'REPORT.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(x))
