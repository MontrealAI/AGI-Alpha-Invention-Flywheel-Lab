"""Lossless projection of declared mathematical fields; preserve frozen source and every rejection."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parent
LAB=R.parent/'lab'
freeze_path=LAB/'campaign/cycle-004/CANDIDATE_FREEZE.json'
raw_freeze=freeze_path.read_bytes();f=json.loads(raw_freeze)
checks={}
for name,expected in f['source_sha256'].items():
 actual=hashlib.sha256((LAB/name).read_bytes()).hexdigest()
 checks[name]=dict(expected_sha256=expected,actual_sha256=actual,matched=actual==expected)
assert all(v['matched'] for v in checks.values())
p=LAB/f['candidate'];raw=p.read_bytes();d=json.loads(raw)
required=['n','physical_weights','global_phase_exponent','logical_order','codewords']
assert all(k in d for k in required)
projection={k:d[k] for k in required}
out=R/'exact-input-projection.json'
with out.open('x') as h:h.write(json.dumps(projection,indent=2)+'\n')
receipt=dict(candidate_freeze_sha256=hashlib.sha256(raw_freeze).hexdigest(),frozen_candidate_sha256=hashlib.sha256(raw).hexdigest(),
 projection_path=str(out),projection_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
 adaptation='Copy exactly the five declared mathematical fields, preserving all values and codewords; ignore provenance/claim metadata as authority',
 ignored_metadata_keys=[k for k in d if k not in required],all_frozen_source_identities=checks)
with (R/'INPUT_ADAPTER_RECEIPT.json').open('x') as h:json.dump(receipt,h,indent=2);h.write('\n')
print(json.dumps(receipt,indent=2))
