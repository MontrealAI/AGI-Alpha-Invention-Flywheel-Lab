"""Independent acceptance checks; does not import forward solver or estimator."""
import json,math
from fractions import Fraction
ARMS=('genesis_composition','conventional_kelvin','independent_direct_agent')
def interval(value):
 if value is None:return None
 if not isinstance(value,list) or len(value)!=2 or not all(isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x) for x in value) or value[0]>value[1]:raise AssertionError('invalid interval')
 return value

def check_prediction(case,p):
 count=0
 for phase in ('baseline','after'):
  if set(p[phase])!={'bulk','contact'}:raise AssertionError('interval schema')
  for quantity in ('bulk','contact'):
   bound=interval(p[phase][quantity])
   if bound is not None:
    actual=case['truth'][phase][quantity]
    if not bound[0]-1e-8<=actual<=bound[1]+1e-8:raise AssertionError('truth outside interval')
    count+=1
 complete=True
 if set(p['difference'])!={'bulk','contact'} or set(p['classifications'])!={'sample','contact'}:raise AssertionError('output schema')
 for quantity,label,threshold in [('bulk','sample',.5),('contact','contact',.25)]:
  change=Fraction(str(case['truth']['after'][quantity]))-Fraction(str(case['truth']['baseline'][quantity]))
  expected='changed' if abs(change)>Fraction(str(threshold)) else 'unchanged'
  claim=p['classifications'][label];bound=interval(p['difference'][quantity]);a=p['baseline'][quantity];b=p['after'][quantity]
  if a is None or b is None:
   if bound is not None:raise AssertionError('difference without session bounds')
  elif bound is None:raise AssertionError('missing difference')
  else:
   if abs(bound[0]-(b[0]-a[1]))>1e-8 or abs(bound[1]-(b[1]-a[0]))>1e-8:raise AssertionError('difference not rederived')
  derived='ambiguous'
  if bound is not None:
   if not bound[0]-1e-8<=change<=bound[1]+1e-8:raise AssertionError('difference not conservative')
   if bound[0]>threshold or bound[1]<-threshold:derived='changed'
   elif bound[0]>=-threshold and bound[1]<=threshold:derived='unchanged'
  if claim!=derived:raise AssertionError('classification not interval-derived')
  if claim!='ambiguous' and claim!=expected:raise AssertionError('false confident change claim')
  complete &= claim==expected;count+=1
 return {'checks':count,'complete_correct':bool(complete),'abstained':any(x=='ambiguous' for x in p['classifications'].values())}

def check_result(result):
 if result['arms']!=list(ARMS):raise AssertionError('exact registered arms required')
 rows=result['rows'];expected={(t,f,r,a) for t in ('none','contact','sample','both') for f in ('noise','geometry','channels') for r in range(12) for a in ARMS}
 keys={(r['case']['truth_class'],r['case']['family'],r['case']['replicate'],r['arm']) for r in rows}
 if keys!=expected or len(rows)!=432:raise AssertionError('incomplete or duplicated keyspace')
 sums={a:{'rows':0,'checks':0,'admitted':0,'admitted_complete':0,'all_complete':0,'abstentions':0} for a in ARMS};cases={}
 for row in rows:
  c=row['case'];key=(c['truth_class'],c['family'],c['replicate']);encoded=json.dumps(c,sort_keys=True,allow_nan=False)
  if key in cases and encoded!=cases[key]:raise AssertionError('unmatched arm inputs')
  cases[key]=encoded
  admitted=c['family']=='noise' or (c['family']=='geometry' and c['replicate']<8) or (c['family']=='channels' and c['replicate']>=8)
  if c['identifiable_envelope']!=admitted:raise AssertionError('registered subset changed')
  v=check_prediction(c,row['prediction']);s=sums[row['arm']];s['rows']+=1;s['checks']+=v['checks'];s['all_complete']+=v['complete_correct'];s['abstentions']+=v['abstained']
  if admitted:s['admitted']+=1;s['admitted_complete']+=v['complete_correct']
  if not math.isfinite(c['kcl_residual']) or c['kcl_residual']<0 or c['kcl_residual']>1e-12:raise AssertionError('forward Kirchhoff residual')
 for s in sums.values():
  if s['admitted']!=96 or s['admitted_complete']<.9*96:raise AssertionError('registered completion threshold failed')
 return sums
