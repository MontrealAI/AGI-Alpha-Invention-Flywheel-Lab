"""Independent source-binding audit of saved delivered scopes, not physical truth."""
import argparse,json,time
from pathlib import Path
from producer import verify_sources,digest
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
contract=json.loads((a.evidence/'commission.json').read_text());outputs={q:json.loads((a.evidence/(q+'.json')).read_text()) for q in contract['request']['queries']}
t=time.perf_counter();cpu=time.process_time();counts=verify_sources(contract,outputs,a.source)
report={'passed':True,'counts':counts,'wall_seconds':time.perf_counter()-t,'cpu_seconds':time.process_time()-cpu,'fresh_model_calls':0,'source_images_redecoded':0,'scope':'metadata source binding and delivered content integrity; no independent physical-truth certification','producer_code_matches':contract.get('producer_sha256')==digest((Path(__file__).parent/'producer.py').read_bytes())}
(a.evidence/'independent_binding_audit.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
