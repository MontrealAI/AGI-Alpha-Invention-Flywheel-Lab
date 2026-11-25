from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys


root = Path(__file__).resolve().parent
working = root / 'quote-manufacturing'


def read(path):
    try:
        return json.loads(path.read_bytes())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


driver = read(working / 'RESULT.json')
first = read(root / 'QUOTE-FIRST-REQUEST.json')
lease = read(root / 'QUOTE-LEASE-CHECKPOINT.json')
arm = next(iter(driver.get('arms', [])), {})
checkpoint_filename = next((working / 'private-projects').glob('wf_*/state.json'), None)
checkpoint = read(checkpoint_filename).get('state', {}) if checkpoint_filename else {}
journal = arm.get('events', checkpoint.get('events', []))
clock = Counter(e['kind'] for e in journal)
checks = arm.get('verification', checkpoint.get('verification', {})).get('checks', [])
external = driver.get('outside_execution', [])
boundaries = driver.get('numerical_boundary', [])
runtime_log = working / 'runtime.log'
telemetry = json.loads(subprocess.check_output([sys.executable, '-B', str(root / 'aggregate-runtime-timings.py'),
                                               str(runtime_log)])) if runtime_log.is_file() else None
observations = [{'prompt_sha256': value.get('prompt_sha256'),
                 'schema_sha256': value.get('request_schema_sha256'),
                 'wall_seconds': value.get('wall_seconds'), 'error_code': value.get('error_code'),
                 'response_usage': value.get('response', {}).get('usage')}
                for value in arm.get('observations', [])]

state = 'RUNNING' if not lease else 'PREEMPTED' if lease.get('production_preemption') else driver.get('status', 'FAIL')
record = {
    'scope': 'Original quote 006 manufacturing arm on a separate Linux host',
    'historical_hosted_verdict': 'FAIL',
    'historical_hosted_source': '504a4c86dae6568e7b50eb09f371c515e5398063',
    'historical_product_tree': driver.get('product_tree_sha'),
    'local_first_request': first,
    'original_pinned_model_sha256': driver.get('model_download', {}).get('sha256'),
    'runtime_binary_sha256': driver.get('runtime_binary_sha256'),
    'protocol_sha256': driver.get('protocol_sha256'),
    'driver_source_unchanged': driver.get('source_unchanged'),
    'local_completion': state,
    'manufacturing_state': arm.get('status', checkpoint.get('status')),
    'model_requests': arm.get('model_calls', checkpoint.get('model_calls')),
    'model_completions': clock['model_completed'],
    'tool_actions': arm.get('actions', checkpoint.get('actions')),
    'quote_artifact_sha256': arm.get('artifact_hashes', checkpoint.get('artifacts', {})).get('quote.json', {}).get('sha256'),
    'frozen_checks': {'cases': len(checks), 'passed': sum(row['passed'] for row in checks)},
    'portable_checks': {'cases': len(external), 'passed': sum(row['passed'] for row in external)},
    'portable_boundary': {'cases': len(boundaries), 'refused': sum(row['refused'] for row in boundaries)},
    'request_observations': observations,
    'local_runtime_aggregate': telemetry,
    'lease': lease,
    'registered_other_inference_arms': 'Outside this replay',
    'raw_prompts_and_cases_exported': False,
}
if state == 'PASS':
    assert first['matches_historical_request'] and first['configured_transport_timeout_seconds'] == 600
    assert record['model_completions'] > 0 and arm['status'] == 'complete' and driver['source_unchanged']
    assert checks and external and boundaries and all(row['passed'] for row in checks + external)
    assert all(row['refused'] for row in boundaries)

label = 'QUOTE-MANUFACTURING-CHECKPOINT.json' if state == 'RUNNING' else 'QUOTE-MANUFACTURING-LOCAL.json'
raw = (json.dumps(record, sort_keys=True, indent=2) + '\n').encode()
(root / label).write_bytes(raw)
print(label, hashlib.sha256(raw).hexdigest())
print(json.dumps({key: record[key] for key in ('local_completion', 'manufacturing_state', 'model_requests',
                  'model_completions', 'tool_actions', 'frozen_checks', 'portable_checks', 'portable_boundary',
                  'request_observations')}, sort_keys=True))
