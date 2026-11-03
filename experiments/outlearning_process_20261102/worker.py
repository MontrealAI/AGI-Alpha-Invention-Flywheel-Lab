"""Observation-only worker. Receives no seed, world label, true rates or evaluator."""
import hashlib,json,sys
from science import produce,construct_process

def emit(v):print(json.dumps(v,sort_keys=True,allow_nan=False),flush=True)
def receive():
    line=sys.stdin.readline()
    if not line:raise RuntimeError('CONTROLLER_CLOSED')
    return json.loads(line)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()

public=receive()
if set(public)!={'arm','retained','noise_bound','budget'}:raise ValueError('PUBLIC_METADATA_ONLY')
def observe(t,q):
    emit({'type':'query','time_s':t,'fraction_b':q})
    r=receive()
    if set(r)!={'observation'}:raise ValueError('OBSERVATION_ONLY')
    return r['observation']
k1=produce(observe,**public)
k1_hash=hashlib.sha256(canonical(k1)).hexdigest()
emit({'type':'frozen_k1','sha256':k1_hash,'artifact':k1})
ack=receive()
if ack!={'construct_k2_from':k1_hash}:raise ValueError('K1_BINDING')
k2=construct_process(k1);k2['inherited_k1_sha256']=k1_hash
emit({'type':'result','k1':k1,'k2':k2,'k1_sha256':k1_hash,
      'reference_module_loaded':any(x=='reference' or x.startswith('reference.') for x in sys.modules)})
