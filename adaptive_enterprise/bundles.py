"""Execute one complete operations bundle from three shared work identities.

Packaging adds orchestration and a joint acceptance contract, not three new
independent service jobs. The operating controller must consume these work keys
when the bundle is sold so the same packets cannot be sold individually again.
"""
import copy
import hashlib
import json

SCOPE = 'SYNTHETIC_PUBLIC_WORKLOAD'
SERVICE_ID = 'operations_bundle'
COMPONENT_SERVICES = {'reconciliation', 'kpi_variance', 'evidence_matrix'}
RAW_FIELDS = {'order_id', 'service_id', 'scope', 'currency', 'components', 'work_keys'}
ARTIFACT_FIELDS = {'order_id', 'service_id', 'scope', 'currency', 'outcome_scope', 'method', 'components', 'work_keys', 'promise'}
PROMISE = 'Three checked source-bound component outcomes; same component work cannot also be sold individually.'


def _identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _safe_identity(value):
    try:
        return _identity(value)
    except (ValueError, TypeError):
        return None


def _text(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= 200


def _validate_raw(raw):
    if not isinstance(raw, dict) or set(raw) != RAW_FIELDS or raw.get('service_id') != SERVICE_ID or raw.get('scope') != SCOPE or raw.get('currency') != 'USD' or not _text(raw.get('order_id')):
        raise ValueError('EXACT_AUTHORIZED_OPERATIONS_BUNDLE_REQUIRED')
    components = raw['components']
    if not isinstance(components, list) or len(components) != 3:
        raise ValueError('THREE_COMPONENT_OUTCOMES_REQUIRED')
    services, jobs = [], []
    for component in components:
        if not isinstance(component, dict) or set(component) != {'job_id', 'service_id', 'raw_order', 'artifact'} or component['service_id'] not in COMPONENT_SERVICES or not _text(component['job_id']):
            raise ValueError('EXACT_SCOPED_BUNDLE_COMPONENT_REQUIRED')
        source, artifact = component['raw_order'], component['artifact']
        if not isinstance(source, dict) or not isinstance(artifact, dict) or source.get('order_id') != component['job_id'] or artifact.get('order_id') != component['job_id'] or source.get('service_id') != component['service_id'] or artifact.get('service_id') != component['service_id']:
            raise ValueError('COMPONENT_SOURCE_IDENTITY_MISMATCH')
        if artifact.get('outcome_scope') != 'complete_outcome' or artifact.get('method') not in {'canonical', 'generated_schema'}:
            raise ValueError('FULL_BUNDLE_CANNOT_INCLUDE_STAGED_COMPONENT')
        services.append(component['service_id'])
        jobs.append(component['job_id'])
    if set(services) != COMPONENT_SERVICES or len(set(services)) != len(services) or len(set(jobs)) != len(jobs):
        raise ValueError('DISTINCT_SERVICE_AND_WORK_IDENTITIES_REQUIRED')
    if raw['work_keys'] != jobs or not isinstance(raw['work_keys'], list):
        raise ValueError('EXACT_SHARED_COMPONENT_WORK_KEYS_REQUIRED')
    return components


def build_bundle(raw_order):
    """Re-execute every component before publishing the combined packet."""
    components = _validate_raw(raw_order)
    from adaptive_enterprise.instruments import produce
    outputs = []
    for component in components:
        produced = produce(component['raw_order'], component['artifact']['method'])
        if _identity(produced) != _identity(component['artifact']):
            raise ValueError('COMPONENT_REEXECUTION_MISMATCH')
        outputs.append({'job_id': component['job_id'], 'artifact': produced})
    artifact = {'order_id': raw_order['order_id'], 'service_id': SERVICE_ID, 'scope': SCOPE, 'currency': 'USD',
                'outcome_scope': 'complete_outcome', 'method': 'operations_bundle', 'components': outputs,
                'work_keys': copy.deepcopy(raw_order['work_keys']), 'promise': PROMISE}
    checked = audit_bundle(raw_order, artifact)
    if checked['accepted'] is not True:
        raise ValueError('BUNDLE_INDEPENDENT_ACCEPTANCE_FAILED: ' + ';'.join(checked['errors']))
    return artifact


def audit_bundle(raw_order, artifact):
    """Independently check source identities and every retained sub-contract."""
    errors, checked_components = [], []
    try:
        source_components = _validate_raw(raw_order)
        if not isinstance(artifact, dict) or set(artifact) != ARTIFACT_FIELDS or artifact.get('order_id') != raw_order['order_id'] or artifact.get('service_id') != SERVICE_ID or artifact.get('scope') != SCOPE or artifact.get('currency') != 'USD' or artifact.get('outcome_scope') != 'complete_outcome' or artifact.get('method') != 'operations_bundle' or artifact.get('promise') != PROMISE or artifact.get('work_keys') != raw_order['work_keys']:
            raise ValueError('EXACT_COMPLETE_BUNDLE_ARTIFACT_REQUIRED')
        delivered = artifact['components']
        if not isinstance(delivered, list) or len(delivered) != 3:
            raise ValueError('COMPLETE_BUNDLE_COMPONENT_SCHEDULE_REQUIRED')
        from adaptive_enterprise.checkers import audit_delivery
        for source, output in zip(source_components, delivered):
            if not isinstance(output, dict) or set(output) != {'job_id', 'artifact'} or output['job_id'] != source['job_id'] or _identity(output['artifact']) != _identity(source['artifact']):
                raise ValueError('DELIVERED_COMPONENT_IDENTITY_OR_CONTENT_MISMATCH')
            checked = audit_delivery(source['service_id'], source['raw_order'], output['artifact'])
            checked_components.append({'job_id': source['job_id'], 'service_id': source['service_id'],
                                       'artifact_content_sha256': _identity(output['artifact']), 'accepted': checked['accepted']})
            if checked['accepted'] is not True:
                errors.extend(source['job_id'] + ': ' + error for error in checked['errors'])
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        errors.append('INVALID_OPERATIONS_BUNDLE: ' + str(error))
    return {'service_id': SERVICE_ID, 'order_id': raw_order.get('order_id') if isinstance(raw_order, dict) else None,
            'scope': SCOPE, 'accepted': not errors, 'errors': sorted(set(errors)),
            'input_content_sha256': _safe_identity(raw_order), 'artifact_content_sha256': _safe_identity(artifact),
            'component_acceptance': checked_components,
            'independence': 'Separate component and orchestration checker; shared host and agent family, not external certification.'}
