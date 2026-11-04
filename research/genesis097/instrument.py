"""Conventional rational interval reconstruction in an editable instrument."""
from fractions import Fraction as Q
import math

def finite(x):
 return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)
def rational(x):
 if not finite(x):raise ValueError('finite scalar required')
 return Q(str(x))
def outward(q,up):
 f=float(q)
 if not math.isfinite(f):raise ValueError('output overflow')
 if (up and Q(f)<q) or (not up and Q(f)>q):f=math.nextafter(f,math.inf if up else -math.inf)
 if not math.isfinite(f):raise ValueError('output overflow')
 return f
def encode(s):return {k:None if b is None else [outward(b[0],False),outward(b[1],True)] for k,b in s.items()}
def classify(interval,threshold):
 if interval is None:return 'ambiguous'
 lo,hi=interval
 if lo>threshold or hi < -threshold:return 'changed'
 if lo>=-threshold and hi<=threshold:return 'unchanged'
 return 'ambiguous'

def session(s):
 e,ie=map(rational,(s['voltage_error'],s['current_error']));gl,gh=map(rational,s['gain_range']);fl,fh=map(rational,s['sense_fraction_range'])
 if e<0 or ie<0 or not 0<gl<=gh or not 0<fl<=fh<=1:raise ValueError('invalid calibration')
 records=[{k:rational(row[k]) for k in ('current','v2','v4')} for row in s['records']]
 if not records or len(records)%2:raise ValueError('incomplete reversal')
 slopes={k:[] for k in ('v2','v4')}
 for j in range(0,len(records),2):
  a,b=records[j:j+2]
  if a['current']<b['current']:a,b=b,a
  if not a['current']>0>b['current']:raise ValueError('not a reversal')
  di=a['current']-b['current']
  if di<=2*ie:raise ValueError('unsafe current interval')
  for key in slopes:
   dv=a[key]-b[key];corners=[v/i for v in (dv-2*e,dv+2*e) for i in (di-2*ie,di+2*ie)]
   slopes[key].append((max(Q(0),min(corners))/gh,max(corners)/gl))
 # Eliminate one stable offset from all pairs, allowing bounded current errors.
 for key in slopes:
  low,high=Q(0),None
  for a in records:
   for b in records:
    coefficient=a['current']-b['current']+2*ie;rhs=a[key]-b[key]-2*e
    if coefficient>0:low=max(low,rhs/coefficient)
    elif coefficient<0:high=rhs/coefficient if high is None else min(high,rhs/coefficient)
    elif rhs>0:raise ValueError('inconsistent common offset')
  if high is None or low>high or high<0:raise ValueError('inconsistent common offset')
  slopes[key].append((max(Q(0),low)/gh,high/gl))
 def intersect(v):
  lo=max(x[0] for x in v);hi=min(x[1] for x in v)
  if lo>hi or hi<0:raise ValueError('inconsistent channel')
  return (max(Q(0),lo),hi)
 total=intersect(slopes['v2']);sense=intersect(slopes['v4'])
 bulk=(sense[0]/fh,sense[1]/fl);contact=(max(Q(0),total[0]-bulk[1]),total[1]-bulk[0])
 if contact[1]<contact[0]:raise ValueError('nonpassive contact')
 return {'bulk':bulk,'contact':contact}

def analyze(obs):
 obs=obs if isinstance(obs,dict) else {};empty={'bulk':None,'contact':None};sessions={}
 for phase in ('baseline','after'):
  try:sessions[phase]=session(obs.get(phase,{}));encode(sessions[phase])
  except (KeyError,TypeError,ValueError,OverflowError,ZeroDivisionError):sessions[phase]=empty.copy()
 diff={}
 for key in empty:
  a,b=sessions['baseline'][key],sessions['after'][key]
  diff[key]=(b[0]-a[1],b[1]-a[0]) if a is not None and b is not None else None
 try:encoded=encode(diff)
 except (ValueError,OverflowError):encoded=empty.copy()
 return {'baseline':encode(sessions['baseline']),'after':encode(sessions['after']),
  'difference':encoded,'classifications':{'sample':classify(encoded['bulk'],.5),'contact':classify(encoded['contact'],.25)}}

def compile_design(spec):
 maximum=spec['maximum_current_A'];power=spec['maximum_specimen_power_W'];r=spec['maximum_bulk_ohm']
 if not all(finite(x) and x>0 for x in (maximum,power,r)):raise ValueError('invalid numerical design limits')
 choices=[i for i in spec['current_menu_A'] if finite(i) and i>0 and i<=maximum and i*i*r<=power]
 if not choices:raise ValueError('no permitted measurement current')
 i=max(choices)
 return {'schema':'genesis097-editable-design/v1','method':'Kelvin current reversal',
  'currents_A':[i,-i,.5*i,-.5*i,.25*i,-.25*i],
  'outputs':['bulk resistance interval','aggregate contact resistance interval','change or abstention'],
  'physical_execution_authorized':False,'physical_calibration_verified':False,
  'basis':'Conventional method; no enabling superiority claimed','specification':spec}
