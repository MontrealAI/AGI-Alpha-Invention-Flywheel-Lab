"""Turn an actual retrieved negative constraint into a scoped reference experiment."""
import argparse, hashlib, json, time
from pathlib import Path
from flywheel import retention
from inventions.consequential009.reference_extension import run as reference_run

ROOT = Path(__file__).resolve().parents[1]

def run(memory, expected_record, protocol, output):
    start, cpu = time.monotonic(), time.process_time()
    target = {'schema_version': 1, 'conditions': {'model_family': 'passive-RCL-one-port',
        'observable': 'coherent-normalized-admittance', 'sensor_gain': 'unbounded'}}
    retrieved = retention.retrieve(Path(memory), target, ROOT)
    relevant = [x for x in retrieved['failures'] if x['id'] == expected_record]
    if retrieved['records'] or not relevant: raise ValueError('VERIFIED_RETRIEVED_NEGATIVE_CONSTRAINT_REQUIRED')
    if not any(f['conditions'].get('sensor_gain') == 'unbounded' for x in relevant for f in x['counterexamples']):
        raise ValueError('MISSING_TYPED_GAIN_COUNTEREXAMPLE')
    p = json.loads(Path(protocol).read_text())
    if p['retained_constraint']['kind'] != 'unbounded_sensor_gain_confounding':
        raise ValueError('CONSTRAINT_TO_EXPERIMENT_TYPE_MISMATCH')
    output = Path(output); output.mkdir(parents=True, exist_ok=False)
    report = reference_run(output / 'artifacts', protocol)
    result = {'schema': 'agi-alpha/consequential009-negative-memory-adaptation/v1',
        'retrieved': retrieved, 'record_sha256': expected_record,
        'reference_protocol_sha256': hashlib.sha256(Path(protocol).read_bytes()).hexdigest(),
        'reference_artifact_sha256': hashlib.sha256((output / 'artifacts/REPORT.json').read_bytes()).hexdigest(),
        'executed_path': ['flywheel.retention.retrieve', 'typed gain-counterexample admission',
                          'fixed reference-normalization constructor', 'new RLC experiment'],
        'source_of_rule': 'Developer supplied known switched-reference normalization; retrieved defect gates the experiment. This does not invent or autonomously discover the physical law.',
        'counterfactual': 'Equal-content ordinary reuse can supply the same defect and known reference rule; no superiority is claimed.',
        'funding': 'Original campaign allocation; qualified earned funds zero; conditional commercial reservation remains unspent.',
        'cpu_seconds': time.process_time() - cpu, 'wall_seconds': time.monotonic() - start,
        'complete_monetary_cost': None, 'report_scope': report['conditional_scope']}
    with (output / 'ADAPTATION.json').open('x') as stream: json.dump(result, stream, indent=2, allow_nan=False); stream.write('\n')
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--memory', type=Path, required=True)
    parser.add_argument('--expected-record-sha256', required=True)
    parser.add_argument('--protocol', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.memory, args.expected_record_sha256, args.protocol, args.output)
    print(json.dumps({'record_sha256': result['record_sha256'], 'reference_artifact_sha256': result['reference_artifact_sha256']}))
