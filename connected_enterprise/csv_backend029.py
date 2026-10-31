"""Qualified CSV production backend; its caller owns native prepayment and choice.

This module performs no financial mutation. Execution is permitted by the native
execute_funded caller only after its positive production contract is verified.
Search uses an existing finite operator catalogue, never effect-label authority.
"""
import hashlib
import json
from pathlib import Path
import tempfile
import time

from commercial.ledger import digest, read_bound
from adaptive_enterprise.instruments import (_validate_manifest, check_job,
                                              _semantics, operation_count)
from adaptive_enterprise.strategies import validate_offer
from adaptive_enterprise.checkers import audit_delivery
from mechanism_harness import core, operating027, study027
from .funded_csv_adapter028 import binding, ARMS, FEES
from . import native_csv_manifest028 as seam

SPEC = 'campaign/mechanism-harness-027/EXISTING_OPERATIONS.json'
PLAN = 'campaign/mechanism-harness-027/PLAN.json'
SELF = 'connected_enterprise/csv_backend029.py'


def extra_cost(arm):
    if arm not in ARMS:
        raise ValueError('DECLARED_CSV_BACKEND_ARM_REQUIRED')
    return FEES[arm] + 50000


def eligible(offer, mode):
    return (mode in ('conventional', 'generated')
            and offer.get('service_id') == 'reconciliation'
            and offer.get('method') in ('canonical', 'generated_schema')
            and offer.get('scope') == 'complete_outcome')


def _inputs(root):
    root = Path(root).resolve()
    executing = Path(__file__).resolve().parents[1]
    source = binding(root)
    for name in (SELF, SPEC, PLAN):
        p, actual = root/name, executing/name
        if (not p.is_file() or not actual.is_file()
                or any(x.is_symlink() for x in (p, *p.parents))
                or p.read_bytes() != actual.read_bytes()):
            raise ValueError('CSV_BACKEND_EXECUTING_SOURCE_CHANGED:' + name)
        source['files'][name] = hashlib.sha256(p.read_bytes()).hexdigest()
    source['sha256'] = digest(source['files'])
    spec = json.loads((root/SPEC).read_text())
    plan = json.loads((root/PLAN).read_text())
    return source, spec, plan


def contract(root, arm):
    source, spec, plan = _inputs(root)
    return {'schema': 'csv-backend029/v1', 'arm': arm, 'source': source,
            'spec_sha256': digest(spec), 'plan_sha256': digest(plan),
            'extra_cost_microUSD': extra_cost(arm)}


def validate_contract(root, backend):
    if not isinstance(backend, dict) or backend != contract(root, backend.get('arm')):
        raise ValueError('EXACT_SOURCE_BOUND_CSV_BACKEND_REQUIRED')
    return backend


def execute_service(root, manifest, offer, job_id, mode, backend):
    """Execute current public CSV service after caller's native funding check.

    Native semantics and manifest identity are checked independently of the CSV
    executor. Whole-invocation timing includes adaptation and extra verification,
    but is process CPU, not child-inclusive accounting or measured monetary bills.
    """
    cpu, wall = time.process_time_ns(), time.monotonic_ns()
    validate_contract(root, backend)
    if not eligible(offer, mode):
        raise ValueError('CSV_BACKEND_NOT_ELIGIBLE_FOR_NATIVE_OFFER')
    validate_offer(offer)
    _validate_manifest(root, manifest)
    job = next((j for j in manifest['jobs'] if j['id'] == job_id), None)
    if job is None or job['service_id'] != offer['service_id']:
        raise ValueError('SCOPED_CSV_OFFER_JOB_REQUIRED')
    saved = check_job(root, manifest, job)['artifact']
    raw = read_bound(root, job['input'], job['input_sha256'])
    source, spec, plan = _inputs(root)
    try:
        if saved['method'] != offer['method'] or saved['outcome_scope'] != offer['scope']:
            raise ValueError('OFFER_DOES_NOT_MATCH_ADMITTED_PRODUCTION_CONTRACT')
        operating027._validate_plan(spec, plan)
        selected = core.compose(spec) if backend['arm'] == 'replanned' else plan
        operating027._validate_plan(spec, selected)
        with tempfile.TemporaryDirectory(prefix='native-csv029-') as temporary:
            base = Path(temporary)
            prepared = seam.prepare(root, manifest, job_id, base/'inputs', mode)
            output = base/'output'
            if backend['arm'] == 'direct':
                producer = study027._direct(prepared['paths'], output)
                check = operating027._audit_outputs(prepared['paths'], output)
                if check != producer['checker']:
                    raise ValueError('CSV_DIRECT_CURRENT_CHECK_CHANGED')
            else:
                operating027.execute(spec, selected, prepared['paths'], output,
                    execution_mode='inherited_existing_plan' if backend['arm'] == 'inherited' else 'composed')
                check = operating027.verify(spec, selected, prepared['paths'], output)
            qualification = seam.qualify(root, manifest, job_id, prepared, output)
            report = json.loads((output/'production/reconciliation.json').read_text())
            artifact = {'order_id': raw['order_id'], 'service_id': 'reconciliation',
                        'scope': raw['scope'], 'currency': raw['currency'],
                        'outcome_scope': 'complete_outcome', 'method': offer['method'],
                        'plan': prepared['plan'], 'normalized_input': prepared['normalized'],
                        'useful_outcome': report}
            native_check = audit_delivery('reconciliation', raw, artifact)
            if (not check['accepted'] or not native_check['accepted']
                    or digest(_semantics(artifact)) != digest(_semantics(saved))):
                raise ValueError('CSV_CURRENT_PRODUCTION_NOT_NATIVE_EQUIVALENT')
            result = {**native_check, 'artifact_sha256': job['artifact_sha256'],
                      'actual_execution_artifact_sha256': digest(artifact), 'artifact': artifact,
                      'native_delivered_artifact_sha256': job['artifact_sha256'],
                      'useful_outcome_sha256': digest(_semantics(artifact)),
                      'outcome_scope': artifact['outcome_scope'], 'work_keys': job['work_keys'],
                      'operation_count': operation_count(artifact), 'model_calls': 0,
                      'execution_binding': 'Native delivers its admitted artifact; the selected CSV backend freshly produces independently checked equivalent normalized input and useful outcome.',
                      'native_manifest_qualification': qualification}
    except (ValueError, KeyError, TypeError, OSError) as error:
        detail = type(error).__name__ + ': ' + str(error)
        refusal = seam.verify_refusal(root, manifest, job_id, detail)
        result = {'accepted': False, 'service_id': offer['service_id'],
                  'order_id': raw['order_id'], 'errors': [detail],
                  'outcome_scope': offer['scope'], 'operation_count': 0, 'model_calls': 0,
                  'independent_refusal': refusal}
    if _inputs(root)[0] != source:
        raise ValueError('CSV_BACKEND_SOURCE_CHANGED_DURING_EXECUTION')
    result.update(backend=backend, current_proof=None, authority=[],
                  process_cpu_seconds=(time.process_time_ns()-cpu)/1e9,
                  whole_invocation_wall_seconds=(time.monotonic_ns()-wall)/1e9)
    return result
