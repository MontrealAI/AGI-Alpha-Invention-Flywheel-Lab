"""Independent nodal Kirchhoff generator; no estimator imports."""
import numpy as np

def voltages(bulk,contact,fraction,current):
 # Drive terminal, left surface, left sense, right sense, right surface, ground.
 resistors=[contact*.4,bulk*(1-fraction)/2,bulk*fraction,bulk*(1-fraction)/2,contact*.6]
 y=np.zeros((5,5));rhs=np.zeros(5);rhs[0]=current
 for k,r in enumerate(resistors):
  g=1/r;y[k,k]+=g
  if k<4:y[k+1,k+1]+=g;y[k,k+1]-=g;y[k+1,k]-=g
 v=np.linalg.solve(y,rhs)
 return float(v[0]),float(v[2]-v[3]),float(np.max(np.abs(y@v-rhs)))

def make_case(truth,family,rep,seed,currents):
 rng=np.random.default_rng(seed);r=float(rng.uniform(10,30));c=float(rng.uniform(2,8))
 dr=float(rng.uniform(3,5)) if truth in ('sample','both') else 0.
 dc=float(rng.uniform(1,2)) if truth in ('contact','both') else 0.
 if rep%2:dr=-dr;dc=-dc*.5
 real={'baseline':{'bulk':r,'contact':c},'after':{'bulk':r+dr,'contact':c+dc}}
 obs={};max_residual=0.;admitted=True
 for label,state in real.items():
  f=float(rng.uniform(.4999,.5001));g=float(rng.uniform(.9998,1.0002));e=2e-7;ie=1e-9
  fr=[.4998,.5002];gr=[.9995,1.0005]
  if family=='geometry' and rep>=8:fr=[.35,.65];admitted=False
  if family=='channels' and 4<=rep<8:e=.003;admitted=False
  offset2=float(rng.uniform(-.002,.002));offset4=float(rng.uniform(-.002,.002))
  rows=[]
  for i in currents:
   it=i+float(rng.uniform(-ie,ie));v2,v4,residual=voltages(state['bulk'],state['contact'],f,it);max_residual=max(max_residual,residual)
   # Time-varying error is covered by the declared bound, not inferred from truth.
   rows.append({'current':i,'v2':g*v2+offset2+float(rng.uniform(-e,e)),
    'v4':None if family=='channels' and rep<4 else g*v4+offset4+float(rng.uniform(-e,e))})
  if family=='channels' and rep<4:admitted=False
  obs[label]={'records':rows,'voltage_error':e,'current_error':ie,'gain_range':gr,'sense_fraction_range':fr}
 return {'id':f'{truth}-{family}-{rep}','truth_class':truth,'family':family,'replicate':rep,
  'observation':obs,'truth':real,'identifiable_envelope':admitted,'kcl_residual':max_residual}
