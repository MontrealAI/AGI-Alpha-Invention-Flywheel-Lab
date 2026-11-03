"""Reproduce compact request inputs from checksum-verified Apache-2.0 OR-License.

Changes: baseline JSON reserialized; demand105 increases each customer-product
quantity by 5%, rounded upward, and recomputes total pieces. This is an authored
sensitivity, not an observed second manufacturer. No answers are constructed.
"""
import copy,hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=root/'industrial062/inputs/15_network_direct/01.json'
if hashlib.sha256(source.read_bytes()).hexdigest()!='de44431d708f695b3825efc5e372f7c15243313819a9fb42aabf73c0204be0f2':raise ValueError('PINNED_SOURCE_DIFFERS')
d=json.loads(source.read_text());out=root/'industrial064/inputs';out.mkdir(exist_ok=True)
for name in ['baseline','demand105']:
 x=copy.deepcopy(d)
 if name=='demand105':
  for c in x['customers'].values():
   for k,v in c['demand'].items():c['demand'][k]=(v*105+99)//100
  x['totals']['demand_pieces']=sum(sum(c['demand'].values()) for c in x['customers'].values())
 raw=(json.dumps(x,sort_keys=True)+'\n').encode();target=out/(name+'.json')
 expected=next(q['input_sha256'] for q in json.loads((root/'industrial064/registration.json').read_text())['requests'] if q['id']==name)
 if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('REGISTERED_INPUT_DIFFERS')
 if target.exists() and target.read_bytes()!=raw:raise ValueError('EXISTING_INPUT_DIFFERS')
 target.write_bytes(raw)
print('Both registered request inputs reproduced; no plan or account created.')
