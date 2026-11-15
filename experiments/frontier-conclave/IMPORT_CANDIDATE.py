"""Convert manual Pro response to native HARNESS formula spec, without executing code."""
import sys,json
from pathlib import Path
from vendor.instruments import strict_portable_json
r=strict_portable_json(Path(sys.argv[1]).read_text())
if set(r)!={'inputs','bindings','outputs','summary'}:raise ValueError('Unexpected response shape')
if not isinstance(r['inputs'],list) or len(set(r['inputs']))!=len(r['inputs']):raise ValueError('Inputs must be distinct names')
s={'inputs':r['inputs']}
for group in ['bindings','outputs']:
 if not isinstance(r[group],dict) or not all(isinstance(v,str) and 0<len(v)<=1024 for v in r[group].values()):raise ValueError('Bounded formula strings required')
 s[group]={k:{'formula':v} for k,v in r[group].items()}
if not s['outputs']:raise ValueError('Outputs required')
print(json.dumps(s,indent=2))
