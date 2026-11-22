from collections import Counter

def validate_request(r):
 if not isinstance(r,dict) or not isinstance(r.get('id'),str) or not r['id'] or len(r['id'])>120: raise ValueError('REQUEST_ID_REQUIRED')
 if r.get('family') not in {'reliable_readback','persistent_idempotency','both_capabilities','unobservable_nonidempotent','stale_readback','expiring_dedup'}: raise ValueError('DECLARED_INTERFACE_REQUIRED')
 if r.get('kind')=='preparation':
  if set(r)!={'id','kind','family','samples','components','quantity'}: raise ValueError('EXACT_PREPARATION_REQUEST')
  if any(type(r[k]) is not int or r[k]<=0 for k in ('samples','components','quantity')): raise ValueError('POSITIVE_EXACT_QUANTITIES')
  if r['samples']*r['components']>4096: raise ValueError('REGISTERED_LOCAL_EXPERIMENT_RESOURCE_BOUND')
 elif r.get('kind')=='characterization':
  if set(r)!={'id','kind','family','hidden_threshold','response_model'} or type(r['hidden_threshold']) is not int or not 1<=r['hidden_threshold']<=64: raise ValueError('EXACT_CHARACTERIZATION_REQUEST')
 else: raise ValueError('DECLARED_OUTCOME_REQUIRED')
 return r

def oracle(family,policy,trace,key,quantity,first_fault):
 counts=Counter();sent=0;actual=[];can_read=family in {'reliable_readback','both_capabilities','stale_readback'};persistent=family in {'persistent_idempotency','both_capabilities'}
 if policy not in {'retry_same_key','read_before_retry'}: return False
 expected=[('command',first_fault)]
 if first_fault!='ack':
  if policy=='retry_same_key': expected.append(('command','ack'))
  else:
   expected.append(('query',None))
   query_result='unsupported' if not can_read else (first_fault=='drop_after' and family!='stale_readback')
   if query_result is False: expected.append(('command','ack'))
   if query_result=='unsupported': return False
 if len(trace)!=len(expected) or len(trace)>3: return False
 for step,(action,fault) in zip(trace,expected):
  if step.get('action')!=action or step.get('key')!=key: return False
  if action=='command':
   if set(step)!={'action','key','quantity','fault','response'} or step['quantity']!=quantity or step['fault']!=fault: return False
   if step['response']!=('ok' if fault=='ack' else 'unknown'): return False
   if fault!='drop_before' and not (persistent and counts[key]): counts[key]+=1
  else:
   response='unsupported' if not can_read else bool(counts[key] and family!='stale_readback')
   if set(step)!={'action','key','response'} or step['response']!=response: return False
 return counts[key]==1

def robust_policy(family,policy):
 # Exhaustive algebraic contract check, separate from the producer simulator.
 if policy=='retry_same_key': return family in {'persistent_idempotency','both_capabilities'}
 if policy=='read_before_retry': return family in {'reliable_readback','both_capabilities'}
 return False

def verify(request,artifact):
 validate_request(request);errors=[]
 if not isinstance(artifact,dict) or artifact.get('id')!=request['id'] or artifact.get('kind')!=request['kind']: return {'accepted':False,'reason':'REQUEST_BINDING'}
 if artifact.get('status')!='delivered': return {'accepted':False,'reason':'NO_USEFUL_DELIVERY','refusal':artifact.get('status')=='refused'}
 policy=artifact.get('policy');family=request['family']
 if artifact.get('family')!=family or not robust_policy(family,policy): errors.append('RECOVERY_CONTRACT')
 rows=artifact.get('rows',[]);seen=set();faults=('ack','drop_before','drop_after')
 if request['kind']=='preparation':
  expected=[(f'{request["id"]}/sample{s}/component{c}',request['quantity']+c,faults[(s+c)%3]) for s in range(request['samples']) for c in range(request['components'])]
  if len(rows)!=len(expected): errors.append('COMPLETE_SAMPLE_COVERAGE')
  for row,(key,q,fault) in zip(rows,expected):
   if row.get('key')!=key or row.get('quantity')!=q or row.get('completed') is not True or key in seen or not oracle(family,policy,row.get('trace',[]),key,q,fault): errors.append('EXACTLY_ONCE_SAMPLE_OUTPUT')
   seen.add(key)
  expected_output={'sample_count':request['samples'],'component_count':request['components'],'quantities':{str(i):request['quantity']+i for i in range(request['components'])}}
  if artifact.get('output')!=expected_output: errors.append('PREPARATION_RESULT')
 else:
  if request['response_model']!='monotone_step': errors.append('UNSUPPORTED_RESPONSE_MODEL')
  lo,hi=0,64
  for i,row in enumerate(rows):
   key=f'{request["id"]}/probe{i}';q=(lo+hi)//2;truth=q>=request['hidden_threshold']
   if hi-lo<=1 or row.get('key')!=key or row.get('quantity')!=q or row.get('measurement') is not truth or row.get('completed') is not True or not oracle(family,policy,row.get('trace',[]),key,q,faults[i%3]): errors.append('CHARACTERIZATION_TRACE')
   if truth: hi=q
   else: lo=q
  if hi-lo!=1 or not lo<request['hidden_threshold']<=hi or artifact.get('output')!={'transition_bracket':[lo,hi],'width':1,'response_model':'monotone_step'}: errors.append('TRANSITION_BRACKET')
 return {'accepted':not errors,'errors':sorted(set(errors)),'checked_operations':len(rows),'scope':'FINITE_MODEL_ONLY','independence':'separate implementation on shared host, not external laboratory validation'}
