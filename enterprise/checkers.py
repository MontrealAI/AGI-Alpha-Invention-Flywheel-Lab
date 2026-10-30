"""Independent acceptance contracts for three bounded synthetic services.

The producer is not imported. The reconciliation verifier is inherited; the two
new contracts derive arithmetic and provenance independently on the shared host.
"""
import hashlib
import json

SCOPE = 'SYNTHETIC_PUBLIC_WORKLOAD'
SERVICES = ('reconciliation', 'kpi_variance', 'evidence_matrix')


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _safe_identity(value):
    try:
        return identity(value)
    except (TypeError, ValueError):
        return None


def _text(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= 200


def audit_delivery(service_id, order, artifact):
    errors = []
    try:
        if service_id not in SERVICES or not isinstance(order, dict) or not isinstance(artifact, dict):
            raise ValueError('service, order and artifact required')
        if order.get('scope') != SCOPE or order.get('currency') != 'USD' or not _text(order.get('order_id')):
            raise ValueError('explicit synthetic USD order identity required')
        if service_id == 'reconciliation':
            if set(order) != {'order_id', 'scope', 'currency', 'require_complete', 'invoices', 'payments'} or set(artifact) != {'order_id', 'scope', 'currency', 'matches', 'unmatched_invoices', 'unmatched_payments', 'exceptions', 'totals', 'accepted'}:
                raise ValueError('exact reconciliation input and output schema required')
            from commercial.service_verifier import audit_delivery as inherited_audit
            result = inherited_audit(order, artifact)
            errors.extend(result['errors'])
        elif service_id == 'kpi_variance':
            if set(order) != {'order_id', 'scope', 'currency', 'metrics'}:
                raise ValueError('exact KPI input schema required')
            source = order['metrics']
            if not isinstance(source, list) or not 1 <= len(source) <= 1000:
                raise ValueError('bounded metric table required')
            names = set()
            expected_rows = []
            for metric in source:
                if not isinstance(metric, dict) or set(metric) != {'metric', 'prior_cents', 'current_cents'}:
                    raise ValueError('metric schema required')
                if not _text(metric['metric']) or metric['metric'] in names:
                    raise ValueError('unique metric names required')
                names.add(metric['metric'])
                if any(type(metric[k]) is not int or not 0 <= metric[k] <= 10**14 for k in ['prior_cents', 'current_cents']):
                    raise ValueError('bounded nonnegative integer cents required')
                prior, current = metric['prior_cents'], metric['current_cents']
                change = current - prior
                expected_rows.append({'metric': metric['metric'], 'prior_cents': prior,
                                      'current_cents': current, 'delta_cents': change,
                                      'direction': 'UP' if change > 0 else 'DOWN' if change < 0 else 'UNCHANGED',
                                      'change_ratio': None if prior == 0 else [change, prior]})
            expected_rows.sort(key=lambda row: row['metric'])
            expected = {'order_id': order['order_id'], 'scope': SCOPE, 'currency': 'USD',
                        'rows': expected_rows, 'totals': {
                            'prior_cents': sum(row['prior_cents'] for row in source),
                            'current_cents': sum(row['current_cents'] for row in source),
                            'delta_cents': sum(row['current_cents'] - row['prior_cents'] for row in source)}}
            if identity(artifact) != identity(expected):
                errors.append('KPI_ARITHMETIC_OR_COMPLETENESS')
        else:
            if set(order) != {'order_id', 'scope', 'currency', 'sources', 'requirements'}:
                raise ValueError('exact evidence input schema required')
            sources, requirements = order['sources'], order['requirements']
            if not isinstance(sources, list) or not 1 <= len(sources) <= 1000 or not isinstance(requirements, list) or not 1 <= len(requirements) <= 1000:
                raise ValueError('bounded sources and requirements required')
            ids, facts = set(), {}
            for source in sources:
                if not isinstance(source, dict) or set(source) != {'id', 'key', 'value'} or any(not _text(source[k]) for k in source):
                    raise ValueError('source fact schema required')
                if source['id'] in ids:
                    raise ValueError('unique source identifiers required')
                ids.add(source['id'])
                facts.setdefault(source['key'], []).append(source)
            seen, expected_rows = set(), []
            for requirement in requirements:
                if not isinstance(requirement, dict) or set(requirement) != {'id', 'key'} or not _text(requirement['id']) or not _text(requirement['key']) or requirement['id'] in seen:
                    raise ValueError('unique scoped requirements required')
                seen.add(requirement['id'])
                citations = sorted(facts.get(requirement['key'], []), key=lambda row: row['id'])
                values = {row['value'] for row in citations}
                expected_rows.append({'requirement_id': requirement['id'], 'key': requirement['key'],
                                      'status': 'MISSING' if not citations else 'SUPPORTED' if len(values) == 1 else 'CONFLICT',
                                      'value': next(iter(values)) if len(values) == 1 else None,
                                      'citations': [{'source_id': row['id'], 'value': row['value']} for row in citations]})
            expected_rows.sort(key=lambda row: row['requirement_id'])
            expected = {'order_id': order['order_id'], 'scope': SCOPE, 'currency': 'USD',
                        'rows': expected_rows, 'limitations': 'Source-bound documentation only; missing or conflicting facts are not inferred.'}
            if identity(artifact) != identity(expected):
                errors.append('EVIDENCE_PROVENANCE_OR_COMPLETENESS')
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        errors.append('INVALID_INPUT_OR_ARTIFACT: ' + str(exc))
    return {'service_id': service_id, 'order_id': order.get('order_id') if isinstance(order, dict) else None,
            'scope': SCOPE, 'accepted': not errors, 'errors': sorted(set(errors)),
            'input_content_sha256': _safe_identity(order), 'artifact_content_sha256': _safe_identity(artifact),
            'independence': 'Separate checker implementation, same agent family and host; not external certification.'}
