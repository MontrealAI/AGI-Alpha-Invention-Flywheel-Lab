"""Executed fixed-capability service packets with source-bound acceptance.

No model API is called. These deterministic tools run on synthetic inputs. Agent
construction effort and unavailable host billing require disclosed cost envelopes.
"""
import hashlib
import json
import time
from pathlib import Path

SCHEMA = 'agi-alpha/enterprise011-services/v1'
SCOPE = 'SYNTHETIC_PUBLIC_WORKLOAD'
SERVICE_IDS = ('reconciliation', 'kpi_variance', 'evidence_matrix')
SOURCE_PATHS = ('enterprise/services.py', 'enterprise/checkers.py', 'commercial/service.py',
                'commercial/service_verifier.py', 'commercial/ledger.py')


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(canonical(value))
    return sha(path.read_bytes())


def _bound(root, relative, expected):
    if not isinstance(relative, str) or not isinstance(expected, str) or len(expected) != 64:
        raise ValueError('SOURCE_IDENTITY_REQUIRED')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('RELATIVE_SOURCE_REQUIRED')
    full = Path(root) / path
    if full.is_symlink() or any(parent.is_symlink() for parent in full.parents):
        raise ValueError('SYMLINK_REFUSED')
    raw = full.read_bytes()
    if len(raw) > 2_000_000 or sha(raw) != expected:
        raise ValueError('SOURCE_OR_ARTIFACT_CHANGED')
    return raw


def _read(root, relative, expected):
    from commercial.ledger import strict_json
    return strict_json(_bound(root, relative, expected))


def produce(service_id, order):
    if service_id not in SERVICE_IDS or not isinstance(order, dict) or order.get('scope') != SCOPE or order.get('currency') != 'USD':
        raise ValueError('SUPPORTED_SYNTHETIC_USD_SERVICE_REQUIRED')
    if service_id == 'reconciliation':
        from commercial.service import reconcile
        return reconcile(order)
    if service_id == 'kpi_variance':
        rows = []
        for row in order['metrics']:
            if type(row['prior_cents']) is not int or type(row['current_cents']) is not int:
                raise ValueError('INTEGER_CENTS_REQUIRED')
            delta = row['current_cents'] - row['prior_cents']
            rows.append({**row, 'delta_cents': delta,
                         'direction': {True: 'UP', False: 'DOWN'}[delta > 0] if delta else 'UNCHANGED',
                         'change_ratio': [delta, row['prior_cents']] if row['prior_cents'] else None})
        rows.sort(key=lambda row: row['metric'])
        return {'order_id': order['order_id'], 'scope': SCOPE, 'currency': 'USD', 'rows': rows,
                'totals': {key: sum(row[key] for row in rows) for key in ['prior_cents', 'current_cents', 'delta_cents']}}
    rows = []
    for requirement in order['requirements']:
        citations = [{'source_id': source['id'], 'value': source['value']} for source in order['sources'] if source['key'] == requirement['key']]
        citations.sort(key=lambda row: row['source_id'])
        values = sorted(set(row['value'] for row in citations))
        rows.append({'requirement_id': requirement['id'], 'key': requirement['key'],
                     'status': 'MISSING' if not values else 'CONFLICT' if len(values) > 1 else 'SUPPORTED',
                     'value': values[0] if len(values) == 1 else None, 'citations': citations})
    rows.sort(key=lambda row: row['requirement_id'])
    return {'order_id': order['order_id'], 'scope': SCOPE, 'currency': 'USD', 'rows': rows,
            'limitations': 'Source-bound documentation only; missing or conflicting facts are not inferred.'}


def synthetic_order(service_id, index):
    if service_id not in SERVICE_IDS or type(index) is not int or index < 0:
        raise ValueError('SERVICE_AND_NONNEGATIVE_INDEX_REQUIRED')
    order = {'order_id': f'{service_id}-{index:03d}', 'scope': SCOPE, 'currency': 'USD'}
    if service_id == 'reconciliation':
        invoices, payments = [], []
        for row in range(12):
            amount = (index + 1) * 107 + (row + 1) * 923
            invoices.append({'id': f'I{row:02d}', 'customer': f'C{row % 3}', 'amount_cents': amount})
            if row != 11:
                payments.append({'id': f'P{row:02d}', 'customer': f'C{row % 3}', 'amount_cents': amount, 'invoice_refs': [f'I{row:02d}']})
        return {**order, 'require_complete': False, 'invoices': invoices, 'payments': payments}
    if service_id == 'kpi_variance':
        return {**order, 'metrics': [{'metric': f'metric-{row:02d}', 'prior_cents': 0 if row == 0 else (index + 1) * 1000 + row * 73,
                                   'current_cents': (index + 1) * 1000 + row * 73 + (row % 3 - 1) * 29} for row in range(10)]}
    return {**order,
            'sources': [{'id': f'S{row:02d}', 'key': f'capability-{row:02d}', 'value': f'Bounded synthetic feature {index}-{row}'} for row in range(6)] +
                       [{'id': 'S99', 'key': 'capability-04', 'value': 'Conflicting source; escalate rather than invent'}],
            'requirements': [{'id': f'R{row:02d}', 'key': f'capability-{row:02d}'} for row in range(8)]}


def prepare_services(root, output_relative):
    root = Path(root).absolute()
    target = Path(output_relative)
    if target.is_absolute() or '..' in target.parts:
        raise ValueError('RELATIVE_OUTPUT_REQUIRED')
    output = root / target
    if output.exists():
        raise FileExistsError('SERVICE_EVIDENCE_OVERWRITE_REFUSED')
    if output.is_symlink() or any(parent.is_symlink() for parent in output.parents):
        raise ValueError('SYMLINK_REFUSED')
    from enterprise.checkers import audit_delivery
    started = time.process_time()
    source_hashes = {path: sha((root / path).read_bytes()) for path in SOURCE_PATHS}
    jobs = []
    for service_id in SERVICE_IDS:
        for index in range(32):
            order = synthetic_order(service_id, index)
            artifact = produce(service_id, order)
            acceptance = audit_delivery(service_id, order, artifact)
            job_id = order['order_id']
            base = target / job_id
            input_path, artifact_path, receipt_path = [str(base / name) for name in ['input.json', 'artifact.json', 'acceptance.json']]
            input_hash = _write(root / input_path, order)
            artifact_hash = _write(root / artifact_path, artifact)
            receipt = {**acceptance, 'input_sha256': input_hash, 'artifact_sha256': artifact_hash,
                       'checker_source_sha256': source_hashes['enterprise/checkers.py'],
                       'execution': 'Actual deterministic tool execution on synthetic authorized inputs; no model inference call.'}
            receipt_hash = _write(root / receipt_path, receipt)
            jobs.append({'id': job_id, 'service_id': service_id, 'accepted': acceptance['accepted'],
                         'input': input_path, 'input_sha256': input_hash, 'artifact': artifact_path,
                         'artifact_sha256': artifact_hash, 'receipt': receipt_path, 'receipt_sha256': receipt_hash})
    attempts = []
    for service_id in SERVICE_IDS:
        order = synthetic_order(service_id, 99)
        artifact = produce(service_id, order)
        if service_id == 'reconciliation':
            artifact['totals']['matched_invoice_cents'] += 1
        elif service_id == 'kpi_variance':
            artifact['rows'][0]['delta_cents'] += 1
        else:
            artifact['rows'][0]['value'] = 'Unsupported credential claim'
        acceptance = audit_delivery(service_id, order, artifact)
        base = target / ('rejected-' + service_id)
        record = {'id': 'rejected-' + service_id, 'service_id': service_id, 'accepted': acceptance['accepted'], 'reason': 'Deliberate adversarial artifact corruption; retained and charged by the shared setup envelope.'}
        for field, name, value in [('input', 'input.json', order), ('artifact', 'artifact.json', artifact), ('receipt', 'acceptance.json', acceptance)]:
            record[field] = str(base / name)
            record[field + '_sha256'] = _write(root / record[field], value)
        attempts.append(record)
    manifest = {'schema': SCHEMA, 'scope': SCOPE, 'currency': 'USD', 'source_hashes': source_hashes,
                'jobs': jobs, 'attempts': attempts,
                'resource_receipt': {'process_cpu_seconds': time.process_time() - started,
                    'model_calls': 0, 'model_billing': 'UNAVAILABLE; no inference performed by these deterministic executors',
                    'human_runtime_review_hours': 0, 'construction_cost': 'Disclosed campaign setup envelope; host model/token billing unavailable'},
                'acceptance_contracts': {
                    'reconciliation': 'Exact safe matching, invoice/payment row partition, integer-cents conservation, exception schedule; ambiguous/unmatched items disclosed.',
                    'kpi_variance': 'All source metrics exactly once; exact prior/current/delta cents, sign, zero-base ratio and totals; no inferred forecast.',
                    'evidence_matrix': 'All requirements exactly once; verbatim supplied facts with source IDs; missing and contradictory evidence surfaced; no unsupported claims.'}}
    _write(output / 'MANIFEST.json', manifest)
    load_jobs(root, manifest)
    return manifest


def _validate_manifest(root, manifest):
    if not isinstance(manifest, dict) or manifest.get('schema') != SCHEMA or manifest.get('scope') != SCOPE or manifest.get('currency') != 'USD':
        raise ValueError('ENTERPRISE_SERVICE_SCOPE_REQUIRED')
    if set(manifest) != {'schema', 'scope', 'currency', 'source_hashes', 'jobs', 'attempts', 'resource_receipt', 'acceptance_contracts'}:
        raise ValueError('EXACT_SERVICE_MANIFEST_SCHEMA_REQUIRED')
    if set(manifest.get('source_hashes', {})) != set(SOURCE_PATHS):
        raise ValueError('EXACT_SOURCE_CLOSURE_REQUIRED')
    for path, expected in manifest['source_hashes'].items():
        _bound(root, path, expected)
        if sha((Path(__file__).resolve().parents[1] / path).read_bytes()) != expected:
            raise ValueError('EXECUTING_SOURCE_IDENTITY_MISMATCH')
    if not isinstance(manifest.get('jobs'), list) or not 1 <= len(manifest['jobs']) <= 1000:
        raise ValueError('BOUNDED_SERVICE_COHORT_REQUIRED')


def check_job(root, manifest, job, artifact=None):
    _validate_manifest(root, manifest)
    from enterprise.checkers import audit_delivery
    fields = {'id', 'service_id', 'accepted', 'input', 'input_sha256', 'artifact', 'artifact_sha256', 'receipt', 'receipt_sha256'}
    if not isinstance(job, dict) or set(job) != fields or not isinstance(job['id'], str) or job['service_id'] not in SERVICE_IDS or type(job['accepted']) is not bool:
        raise ValueError('EXACT_SERVICE_JOB_SCHEMA_REQUIRED')
    order = _read(root, job['input'], job['input_sha256'])
    current = _read(root, job['artifact'], job['artifact_sha256'])
    receipt = _read(root, job['receipt'], job['receipt_sha256'])
    if order.get('order_id') != job['id'] or receipt.get('input_sha256') != job['input_sha256'] or receipt.get('artifact_sha256') != job['artifact_sha256'] or receipt.get('checker_source_sha256') != manifest['source_hashes']['enterprise/checkers.py']:
        raise ValueError('SCOPED_ACCEPTANCE_BINDING_REQUIRED')
    fresh = audit_delivery(job['service_id'], order, current if artifact is None else artifact)
    if set(receipt) != set(fresh) | {'input_sha256', 'artifact_sha256', 'checker_source_sha256', 'execution'} or receipt.get('execution') != 'Actual deterministic tool execution on synthetic authorized inputs; no model inference call.':
        raise ValueError('EXACT_ACCEPTANCE_RECEIPT_REQUIRED')
    if any(receipt.get(key) != value for key, value in fresh.items()) or receipt.get('accepted') is not job['accepted']:
        raise ValueError('INDEPENDENT_ACCEPTANCE_MISMATCH')
    if artifact is not None and canonical(artifact) != canonical(current):
        raise ValueError('DELIVERED_ARTIFACT_CHANGED')
    return {'job': job, 'artifact': current, 'receipt': receipt}


def execute_job(root, job):
    """Re-execute a scoped order at commitment time and compare its saved output."""
    started = time.process_time()
    order = _read(root, job['input'], job['input_sha256'])
    saved = _read(root, job['artifact'], job['artifact_sha256'])
    receipt = _read(root, job['receipt'], job['receipt_sha256'])
    if job.get('accepted') is not True or order.get('order_id') != job.get('id') or receipt.get('input_sha256') != job['input_sha256'] or receipt.get('artifact_sha256') != job['artifact_sha256']:
        raise ValueError('SCOPED_EXECUTION_BINDING_REQUIRED')
    if sha((Path(root) / 'enterprise/checkers.py').read_bytes()) != receipt.get('checker_source_sha256'):
        raise ValueError('CHECKER_SOURCE_CHANGED')
    artifact = produce(job['service_id'], order)
    from enterprise.checkers import audit_delivery
    fresh = audit_delivery(job['service_id'], order, artifact)
    if canonical(artifact) != canonical(saved) or any(receipt.get(key) != value for key, value in fresh.items()) or not fresh['accepted']:
        raise ValueError('COMMITTED_SERVICE_REEXECUTION_FAILED')
    return {**fresh, 'reexecuted': True, 'process_cpu_seconds': time.process_time() - started,
            'model_calls': 0, 'artifact_sha256': job['artifact_sha256']}


def load_jobs(root, manifest):
    _validate_manifest(root, manifest)
    result, seen = {}, set()
    for job in manifest['jobs']:
        if not isinstance(job, dict) or not isinstance(job.get('id'), str) or job['id'] in seen:
            raise ValueError('UNIQUE_JOB_ID_REQUIRED')
        seen.add(job['id'])
        checked = check_job(root, manifest, job)
        if job['accepted']:
            result[job['id']] = checked
    if not isinstance(manifest.get('attempts'), list) or len(manifest['attempts']) > 1000:
        raise ValueError('BOUNDED_ATTEMPTS_REQUIRED')
    from enterprise.checkers import audit_delivery
    for attempt in manifest['attempts']:
        fields = {'id', 'service_id', 'accepted', 'reason', 'input', 'input_sha256', 'artifact', 'artifact_sha256', 'receipt', 'receipt_sha256'}
        if not isinstance(attempt, dict) or set(attempt) != fields or not isinstance(attempt.get('id'), str) or not attempt['id'] or attempt.get('accepted') is not False or attempt.get('service_id') not in SERVICE_IDS or attempt.get('id') in seen:
            raise ValueError('REJECTED_ATTEMPT_REQUIRED')
        seen.add(attempt['id'])
        values = {field: _read(root, attempt[field], attempt[field + '_sha256']) for field in ['input', 'artifact', 'receipt']}
        fresh = audit_delivery(attempt['service_id'], values['input'], values['artifact'])
        if fresh != values['receipt'] or fresh['accepted']:
            raise ValueError('REJECTED_ATTEMPT_AUDIT_MISMATCH')
    if not result:
        raise ValueError('NO_ACCEPTED_SERVICE_ARTIFACTS')
    return result
