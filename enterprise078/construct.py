import copy
from .model import Instrument,execute,FAULTS
POLICIES=('retry_same_key','read_before_retry')

def observe(family):
 rows=[]
 for policy in POLICIES:
  for fault in FAULTS:
   device=Instrument(family)
   ok,trace=execute(device,policy,'disposable-calibration',4,fault)
   rows.append({'policy':policy,'fault':fault,'completed':ok,'reference_quantity':device.effects.get('disposable-calibration',0),'steps':len(trace),'trace':trace})
 return rows

def construct(observations,method='observation_selected_controller'):
 tested=[]
 for policy in POLICIES:
  rows=[r for r in observations if r['policy']==policy]
  accepted=len(rows)==3 and {r['fault'] for r in rows}==set(FAULTS) and all(r['completed'] and r['reference_quantity']==4 and r['steps']<=3 for r in rows)
  tested.append({'policy':policy,'accepted':accepted,'worst_steps':max((r['steps'] for r in rows),default=99)})
  if method=='ordinary_equal_content_controller' and accepted:
   return {'policy':policy,'selection_checks':len(tested),'tested':tested,'generated':'policy data from fixed known grammar'}
 valid=[r for r in tested if r['accepted']]
 chosen=min(valid,key=lambda r:(r['worst_steps'],POLICIES.index(r['policy'])))['policy'] if valid else None
 return {'policy':chosen,'selection_checks':len(tested),'tested':tested,'generated':'policy data from fixed known grammar'}

def learning_loop(family,method):
 obs=observe(family);candidate=construct(obs,method)
 hypotheses=['safe keyed retry','current-effect readback'];events=[{'stage':'observe','sandbox':'disposable simulated reference sample','observations':copy.deepcopy(obs)}]
 if candidate['policy'] is None:
  hypotheses.append('neither recovery interface is reliable')
  events.append({'stage':'expand_hypothesis_space','added':hypotheses[-1],'action':'stop; new authoritative observation or persistent dedup required'})
 else:
  events.append({'stage':'construct','program':candidate['policy']})
 events.append({'stage':'retain','retained':candidate['policy'] is not None,'applicability':'same explicit finite interface model; revalidate before each new family'})
 return candidate,events

def produce(request,method='ordinary_equal_content_controller',retained=None):
 family=request['family'];candidate,events=learning_loop(family,method)
 policy=candidate['policy']
 if retained is not None:
  if retained.get('family')!=family or retained.get('policy')!=policy: raise ValueError('INAPPLICABLE_RETAINED_EXECUTOR')
 if policy is None: return {'id':request['id'],'kind':request['kind'],'status':'refused','reason':'NO_ROBUST_POLICY_IN_REGISTERED_GRAMMAR','learning':events}
 device=Instrument(family);rows=[]
 if request['kind']=='preparation':
  for sample in range(request['samples']):
   for component in range(request['components']):
    key=f'{request["id"]}/sample{sample}/component{component}'
    fault=FAULTS[(sample+component)%3];quantity=request['quantity']+component
    ok,trace=execute(device,policy,key,quantity,fault)
    rows.append({'key':key,'quantity':quantity,'trace':trace,'completed':ok})
  output={'sample_count':request['samples'],'component_count':request['components'],'quantities':{str(i):request['quantity']+i for i in range(request['components'])}}
 else:
  if request.get('response_model')!='monotone_step': return {'id':request['id'],'kind':request['kind'],'status':'refused','reason':'UNSUPPORTED_RESPONSE_MODEL','learning':events}
  lo,hi=0,64;index=0
  while hi-lo>1:
   q=(lo+hi)//2;key=f'{request["id"]}/probe{index}';fault=FAULTS[index%3]
   ok,trace=execute(device,policy,key,q,fault)
   response=device.effects.get(key,0)>=request['hidden_threshold']
   rows.append({'key':key,'quantity':q,'trace':trace,'completed':ok,'measurement':response})
   if response: hi=q
   else: lo=q
   index+=1
  output={'transition_bracket':[lo,hi],'width':hi-lo,'response_model':'monotone_step'}
 return {'id':request['id'],'kind':request['kind'],'status':'delivered','policy':policy,'family':family,'rows':rows,'output':output,'selection':candidate,'learning':events,'scope':'MODEL_QUALIFIED_NO_PHYSICAL_ACTUATION'}
