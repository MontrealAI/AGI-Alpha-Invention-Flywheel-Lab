"""Execute the prospectively frozen successor; orchestration is not its candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from inventions.measurement009 import model, numeric_edition
from research.next009 import successor

def run(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    start, cpu = time.monotonic(), time.process_time()
    freeze_path = root/'verification/next009/SUCCESSOR_FREEZE.json'
    raw = freeze_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != '18fcf172156ea18ccb5c343844e160779884b3d44f8a04cfd1dae7ce7b99cb30':
        raise ValueError('PUBLIC_SUCCESSOR_FREEZE_CHANGED')
    for name, expected in json.loads(raw)['files'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != expected:
            raise ValueError('FROZEN_SOURCE_CHANGED:'+name)
    network = root/'inventions/measurement009/inputs/Net2.inp'
    model.simulate('Net2',output/'raw',model_path=network,
                   expected_blob='6645947b161a90a18f312539d4ff5ac3aee12c4a')
    original = (output/'raw/corpus.json').read_bytes()
    derived, receipt = numeric_edition.adapt_corpus(original)
    edition = output/'numeric'; edition.mkdir()
    (edition/'raw_corpus.json').write_bytes(original)
    numeric_edition.save(edition/'corpus.json',derived)
    numeric_edition.save(edition/'NUMERIC_RECEIPT.json',receipt)
    successor.run(argparse.Namespace(root=str(root),output=str(output/'plans'),
        corpus=str(edition/'corpus.json'),
        primary_plan=str(root/'evidence/next009/construction/networks-v2/artifacts/Net1/generated_plan.json'),
        primary_receipt=str(root/'evidence/next009/verification/primary-confirmation/artifacts/ACCEPTANCE.json'),
        verifier_source=str(root/'verification/next009/verify.py'),
        primary_protocol=str(root/'verification/next009/protocol.json'),
        parent_freeze=str(root/'research/next009/PARENT_FREEZE.json')))
    report = {'schema':'agi-alpha/successor009-execution/v1',
        'public_freeze_commit':'31c05cb2f698f7e5b9159774482e8a9e5278beac',
        'freeze_sha256':hashlib.sha256(raw).hexdigest(),
        'whole_wall_seconds':time.monotonic()-start,
        'whole_process_cpu_seconds':time.process_time()-cpu,
        'funding':'explicit research allocation; qualified earned funds zero',
        'complete_monetary_cost':None,
        'scope':'Builder construction only; independent verification separately required.'}
    (output/'EXECUTION.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',default='.')
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(run(args.root,args.output)))
