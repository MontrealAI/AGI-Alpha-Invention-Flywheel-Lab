"""Previously specified negative controls on derived copies; candidate remains untouched."""
import copy,hashlib,json,pathlib
import certify
base=pathlib.Path(__file__).parent
raw=(base/'exact-input-projection.json').read_bytes();original=json.loads(raw)
zero=copy.deepcopy(original);zero['physical_weights']=[0]*zero['n']
missing=copy.deepcopy(original);p=missing['codewords'][0]['probabilities'];del p[next(iter(p))]
rows=[]
for name,d in [('all_physical_weights_zero',zero),('missing_probability_mass',missing)]:
 b=(json.dumps(d,sort_keys=True,indent=2)+'\n').encode();r=certify.certify(b);assert r['status']=='NOT_CERTIFIED'
 rows.append({'control':name,'derived_input_sha256':hashlib.sha256(b).hexdigest(),'status':r['status'],'checks':r['checks'],'failures':r['failures']})
report={'status':'PASS','meaning':'Both derived negative controls were rejected by the unchanged exact verifier','original_projection_sha256':hashlib.sha256(raw).hexdigest(),'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'cases':rows}
out=base/'CANDIDATE_NEGATIVE_CONTROLS.json'
with out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(report))
