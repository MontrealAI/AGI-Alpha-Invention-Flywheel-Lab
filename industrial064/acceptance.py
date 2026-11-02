"""Independently execute pinned source client rules on exact fresh artifact."""
import hashlib,json,subprocess,sys,tempfile
from fractions import Fraction
from pathlib import Path

def verify(root,request,artifact):
    root=Path(root)
    raw=(root/request['input_path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=request['input_sha256']: raise ValueError('REQUEST_INPUT_CHANGED')
    with tempfile.TemporaryDirectory(prefix='industrial064-check-') as td:
        path=Path(td)/'artifact.json'; path.write_text(json.dumps(artifact))
        script='''import json,sys
from fractions import Fraction
sys.path.insert(0,sys.argv[1])
import _network_engine as c
from _network_delivery import delivery_distance
D=json.load(open(sys.argv[2])); A=json.load(open(sys.argv[3])); x,e=c.parse_solution(A,D)
e+=c.check_structure(x,D);e+=c.check_balance(x,D)
m=c.evaluate(x,D); covered,total=c.service_coverage(x,D)
r=sum(q for (k,p,n),q in x.customer_service.items() if delivery_distance(D,n,k)*1.10<=D['service_distance_km'])
f=Fraction(str(D['service_coverage_floor']))
if covered*f.denominator<f.numerator*total:e.append(['NOMINAL_COVERAGE','failed'])
if r*f.denominator<f.numerator*total:e.append(['ROBUST_COVERAGE','failed'])
if m['total_cost']>float(sys.argv[4]):e.append(['BUDGET','failed'])
print(json.dumps({'accepted':not e,'errors':e,'metrics':m,'robust_covered':r,'total_pieces':total}))
'''
        p=subprocess.run([sys.executable,'-c',script,str(root/'industrial062/inputs/15_network_direct'),str(root/request['input_path']),str(path),str(request['cost_ceiling_yuan'])],capture_output=True,text=True,timeout=30)
        if p.returncode: raise ValueError('INDEPENDENT_CLIENT_FAILED:'+p.stderr[-1000:])
        return json.loads(p.stdout)
