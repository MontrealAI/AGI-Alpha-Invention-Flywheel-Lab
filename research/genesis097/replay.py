"""Explicit obstacle reopening; no automatic tool progress or data invention."""
import hashlib,json,copy
from .instrument import analyze

def digest(obs):return hashlib.sha256(json.dumps(obs,sort_keys=True,allow_nan=False).encode()).hexdigest()
def replay_missing_sense(previous,current):
 def present(obs):return all(r.get('v4') is not None for s in ('baseline','after') for r in obs[s]['records'])
 if present(previous):return {'reopened':False,'reason':'prior obstacle not missing sense data'}
 # Replay may fill missing sense entries, not replace the task or other data.
 try:
  restored=copy.deepcopy(current)
  for phase in ('baseline','after'):
   if len(previous[phase]['records'])!=len(current[phase]['records']):raise ValueError('record count')
   for old,new in zip(previous[phase]['records'],restored[phase]['records']):
    if old.get('v4') is None:
     if 'v4' in old:new['v4']=None
     else:new.pop('v4',None)
  if restored!=previous:raise ValueError('context changed')
 except (KeyError,TypeError,ValueError):
  return {'reopened':False,'reason':'changed task context is not replay of this obstacle'}
 if not present(current):return {'reopened':False,'reason':'required observation still missing; a new solver does not supply information'}
 return {'reopened':True,'reason':'newly supplied sense observations; calibration still required',
  'previous_sha256':digest(previous),'current_sha256':digest(current),'prediction':analyze(current),
  'physical_capability_change_verified':False}
