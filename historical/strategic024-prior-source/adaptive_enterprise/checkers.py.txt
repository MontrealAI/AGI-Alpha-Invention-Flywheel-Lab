"""Independent checks of source adaptation, declared scope and useful outputs.

This checker imports neither the strategy constructor nor the intake producer.
Original service outputs are checked by the retained enterprise011 verifier.
Procedural separation shares the host and agent family; it is not certification.
"""
import copy
from decimal import Decimal, InvalidOperation
import hashlib
import itertools
import json

SCOPE = 'SYNTHETIC_PUBLIC_WORKLOAD'
SERVICES = ('reconciliation', 'kpi_variance', 'evidence_matrix')
RAW_FIELDS = {'order_id', 'service_id', 'scope', 'currency', 'tables', 'units', 'source_order'}
ARTIFACT_FIELDS = {'order_id', 'service_id', 'scope', 'currency', 'outcome_scope', 'method', 'plan', 'normalized_input', 'useful_outcome'}
PLAN_FIELDS = {'schema', 'service_id', 'status', 'mapping', 'units', 'constraints', 'search', 'failure'}
SEARCH_FIELDS = {'candidates_tested', 'candidate_count', 'operation_count', 'retained_constraints_used'}
READINESS_PROMISE = 'Intake readiness only; no completed reconciliation, KPI analysis or evidence response.'
REQUIRED_CONSTRAINTS = {'preserve_source_rows', 'explicit_money_units', 'unique_record_identity', 'referential_customer_consistency'}


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _safe_identity(value):
    try:
        return identity(value)
    except (TypeError, ValueError):
        return None


def _text(value):
    return isinstance(value, str) and 0 < len(value.strip()) <= 200


def _money(value, unit):
    if unit not in {'cents', 'USD'} or isinstance(value, bool) or type(value) not in {int, str}:
        raise ValueError('EXPLICIT_EXACT_MONETARY_UNITS_REQUIRED')
    try:
        converted = Decimal(str(value)) * (100 if unit == 'USD' else 1)
        if not converted.is_finite() or converted != converted.to_integral_value() or not 0 < converted <= 10**14:
            raise ValueError('POSITIVE_BOUNDED_INTEGER_CENTS_REQUIRED')
        return int(converted)
    except (InvalidOperation, OverflowError) as error:
        raise ValueError('EXACT_MONETARY_TEXT_REQUIRED') from error


def _references(value):
    refs = value if isinstance(value, list) else value.split('|') if isinstance(value, str) and value else [] if value == '' else None
    if refs is None or any(not _text(x) for x in refs) or len(refs) != len(set(refs)):
        raise ValueError('EXPLICIT_UNIQUE_INVOICE_REFERENCES_REQUIRED')
    return list(refs)


def _tables(raw):
    if not isinstance(raw['tables'], dict) or set(raw['tables']) != {'invoices', 'payments'} or not isinstance(raw['units'], dict) or set(raw['units']) != {'invoices', 'payments'}:
        raise ValueError('EXACT_RECONCILIATION_TABLES_AND_UNITS_REQUIRED')
    for table, required_columns in [('invoices', {3}), ('payments', {3, 4})]:
        rows = raw['tables'][table]
        units = raw['units'][table]
        if not isinstance(rows, list) or not 1 <= len(rows) <= 1000 or not isinstance(units, dict):
            raise ValueError('BOUNDED_REQUIRED_SOURCE_TABLE_MISSING')
        if not isinstance(rows[0], dict) or len(rows[0]) not in required_columns:
            raise ValueError('BOUNDED_SOURCE_COLUMNS_REQUIRED')
        columns = set(rows[0])
        if any(not _text(column) for column in columns) or any(not isinstance(row, dict) or set(row) != columns for row in rows):
            raise ValueError('CONSISTENT_SOURCE_COLUMNS_REQUIRED')
        if any(column not in columns or unit not in {'cents', 'USD'} for column, unit in units.items()):
            raise ValueError('SOURCE_UNIT_ANNOTATION_INVALID')
    return raw['tables']


def _normalize(raw, mapping, units):
    tables = _tables(raw)
    if not isinstance(mapping, dict) or set(mapping) != {'invoices', 'payments'} or not isinstance(units, dict) or set(units) != {'invoices', 'payments'}:
        raise ValueError('EXACT_MAPPING_AND_UNIT_SCHEMA_REQUIRED')
    normalized = {'order_id': raw['order_id'], 'scope': SCOPE, 'currency': 'USD', 'require_complete': False}
    for table in ['invoices', 'payments']:
        fields = {'id', 'customer', 'amount_cents'} | ({'invoice_refs'} if table == 'payments' else set())
        roles = mapping[table]
        if not isinstance(roles, dict) or set(roles) != fields:
            raise ValueError('EXACT_TYPED_FIELD_MAPPING_REQUIRED')
        columns = [value for value in roles.values() if value is not None]
        if any(not _text(column) for column in columns) or len(columns) != len(set(columns)) or set(columns) != set(tables[table][0]):
            raise ValueError('BIJECTIVE_SOURCE_COLUMN_MAPPING_REQUIRED')
        if table == 'invoices' and any(value is None for value in roles.values()) or table == 'payments' and any(roles[field] is None for field in ['id', 'customer', 'amount_cents']):
            raise ValueError('REQUIRED_MAPPING_FIELD_MISSING')
        if raw['units'][table].get(roles['amount_cents']) != units[table]:
            raise ValueError('MONEY_UNIT_NOT_SUPPORTED_BY_SOURCE')
        rows = []
        for source in tables[table]:
            row = {'id': source[roles['id']], 'customer': source[roles['customer']],
                   'amount_cents': _money(source[roles['amount_cents']], units[table])}
            if not _text(row['id']) or not _text(row['customer']):
                raise ValueError('SOURCE_IDENTITY_AND_CUSTOMER_TEXT_REQUIRED')
            if table == 'payments':
                row['invoice_refs'] = [] if roles['invoice_refs'] is None else _references(source[roles['invoice_refs']])
            rows.append(row)
        if len({row['id'] for row in rows}) != len(rows):
            raise ValueError('SOURCE_RECORD_IDENTITIES_NOT_UNIQUE')
        normalized[table] = rows
    invoices = {row['id']: row for row in normalized['invoices']}
    for row in normalized['payments']:
        if any(ref not in invoices or invoices[ref]['customer'] != row['customer'] for ref in row['invoice_refs']):
            raise ValueError('SOURCE_REFERENCE_OR_CUSTOMER_MISMATCH')
    return normalized


def _possible_mappings(raw):
    tables = _tables(raw)
    candidates = {}
    for table in ['invoices', 'payments']:
        columns = sorted(tables[table][0])
        fields = ['id', 'customer', 'amount_cents'] + (['invoice_refs'] if len(columns) == 4 else [])
        result = []
        for ordered in itertools.permutations(columns):
            roles = dict(zip(fields, ordered))
            if table == 'payments' and 'invoice_refs' not in roles:
                roles['invoice_refs'] = None
            amount_column = roles['amount_cents']
            if raw['units'][table].get(amount_column) not in {'cents', 'USD'}:
                continue
            result.append(roles)
        candidates[table] = result
    possible = []
    for invoice_map, payment_map in itertools.product(candidates['invoices'], candidates['payments']):
        mapping = {'invoices': invoice_map, 'payments': payment_map}
        units = {table: raw['units'][table][mapping[table]['amount_cents']] for table in ['invoices', 'payments']}
        try:
            normalized = _normalize(raw, mapping, units)
            possible.append((mapping, units, normalized))
        except (ValueError, TypeError, KeyError):
            continue
    return possible


def _validate_plan(raw, plan):
    if not isinstance(plan, dict) or set(plan) != PLAN_FIELDS or plan['schema'] != 'adaptive012/intake-plan/v1' or plan['service_id'] != raw['service_id'] or plan['status'] not in {'READY', 'BLOCKED'}:
        raise ValueError('EXACT_TYPED_PLAN_REQUIRED')
    if not isinstance(plan['constraints'], list) or len(plan['constraints']) > 100 or any(not _text(x) for x in plan['constraints']):
        raise ValueError('BOUNDED_PLAN_CONSTRAINTS_REQUIRED')
    if set(plan['constraints']) != REQUIRED_CONSTRAINTS or len(plan['constraints']) != len(REQUIRED_CONSTRAINTS):
        raise ValueError('SOURCE_CONSERVATION_CONSTRAINTS_REQUIRED')
    search = plan['search']
    if not isinstance(search, dict) or set(search) != SEARCH_FIELDS or any(type(search[key]) is not int or not 0 <= search[key] <= 10**8 for key in ['candidates_tested', 'candidate_count', 'operation_count']) or not isinstance(search['retained_constraints_used'], list) or any(not _text(x) for x in search['retained_constraints_used']):
        raise ValueError('EXACT_BOUNDED_SEARCH_RECEIPT_REQUIRED')
    if plan['status'] == 'READY' and plan['failure'] is not None or plan['status'] == 'BLOCKED' and not _text(plan['failure']):
        raise ValueError('PLAN_STATUS_AND_FAILURE_MISMATCH')


def _readiness(raw, plan):
    if raw['service_id'] != 'reconciliation' or raw['source_order'] is not None:
        raise ValueError('STAGED_SCOPE_REQUIRES_REAL_RECONCILIATION_INTAKE_BLOCKER')
    try:
        possible = _possible_mappings(raw) if raw['service_id'] == 'reconciliation' else []
    except (ValueError, TypeError, KeyError):
        possible = []
    if len(possible) == 1:
        raise ValueError('FABRICATED_INTAKE_BLOCKER')
    if plan['status'] != 'BLOCKED' or plan['mapping'] is not None:
        raise ValueError('STAGED_SCOPE_REQUIRES_REAL_INTAKE_BLOCKER')
    expected_failure = 'AMBIGUOUS_MAPPING' if len(possible) > 1 else 'MISSING_TYPED_MAPPING_OR_FACTS'
    if plan['failure'] != expected_failure or plan['units'] != {}:
        raise ValueError('BLOCKER_EVIDENCE_MISMATCH')
    tables = raw['tables']
    if not isinstance(tables, dict) or any(not isinstance(rows, list) for rows in tables.values()):
        raise ValueError('SOURCE_ROW_SCHEDULE_REQUIRED')
    return {'order_id': raw['order_id'], 'source_rows': {table: len(rows) for table, rows in tables.items()},
            'missing_or_ambiguous': [plan['failure']], 'production_ready': False,
            'promised_outcome': READINESS_PROMISE, 'source_sha256': identity(raw)}


def audit_delivery(service_id, raw_order, artifact):
    if service_id=='operations_bundle':
        from adaptive_enterprise.bundles import audit_bundle
        return audit_bundle(raw_order,artifact)
    errors = []
    try:
        raw = raw_order
        if service_id not in SERVICES or not isinstance(raw, dict) or set(raw) != RAW_FIELDS or raw.get('service_id') != service_id or raw.get('scope') != SCOPE or raw.get('currency') != 'USD' or not _text(raw.get('order_id')):
            raise ValueError('EXACT_AUTHORIZED_RAW_ORDER_REQUIRED')
        if not isinstance(artifact, dict) or set(artifact) != ARTIFACT_FIELDS or artifact['order_id'] != raw['order_id'] or artifact['service_id'] != service_id or artifact['scope'] != SCOPE or artifact['currency'] != 'USD' or artifact['method'] not in {'canonical', 'generated_schema', 'staged_readiness'}:
            raise ValueError('EXACT_SCOPED_ARTIFACT_REQUIRED')
        if (artifact['method'] == 'staged_readiness') != (artifact['outcome_scope'] == 'intake_readiness'):
            raise ValueError('METHOD_AND_PROMISED_SCOPE_MISMATCH')
        plan = artifact['plan']
        _validate_plan(raw, plan)
        if artifact['outcome_scope'] == 'intake_readiness':
            if artifact['normalized_input'] is not None or artifact['useful_outcome'] != _readiness(raw, plan):
                raise ValueError('READINESS_SCOPE_OR_SOURCE_EVIDENCE_MISMATCH')
        elif artifact['outcome_scope'] == 'complete_outcome':
            if plan['status'] != 'READY':
                raise ValueError('COMPLETE_OUTCOME_REQUIRES_READY_PLAN')
            if service_id == 'reconciliation':
                if raw['source_order'] is not None:
                    raise ValueError('RAW_RECONCILIATION_MUST_NOT_CONTAIN_NORMALIZED_ORACLE')
                normalized = _normalize(raw, plan['mapping'], plan['units'])
                possible = _possible_mappings(raw)
                if len(possible) != 1:
                    raise ValueError('UNIQUE_SOURCE_SUPPORTED_MAPPING_REQUIRED')
                if artifact['method'] == 'canonical' and plan['mapping'] != {'invoices': {'id': 'id', 'customer': 'customer', 'amount_cents': 'amount_cents'}, 'payments': {'id': 'id', 'customer': 'customer', 'amount_cents': 'amount_cents', 'invoice_refs': 'invoice_refs'}}:
                    raise ValueError('CANONICAL_METHOD_CANNOT_CLAIM_GENERATED_ADAPTATION')
            else:
                if raw['tables'] != {} or raw['units'] != {} or not isinstance(raw['source_order'], dict) or plan['mapping'] is not None or plan['units'] != {}:
                    raise ValueError('EXACT_IDENTITY_ADAPTER_REQUIRED')
                normalized = copy.deepcopy(raw['source_order'])
                normalized['order_id'] = raw['order_id']
            if identity(normalized) != identity(artifact['normalized_input']):
                raise ValueError('NORMALIZED_SOURCE_CONSERVATION_MISMATCH')
            from enterprise.checkers import audit_delivery as inherited_check
            checked = inherited_check(service_id, normalized, artifact['useful_outcome'])
            errors.extend(checked['errors'])
        else:
            raise ValueError('EXPLICIT_COMPLETE_OR_STAGED_OUTCOME_SCOPE_REQUIRED')
    except (ValueError, TypeError, KeyError, OverflowError) as error:
        errors.append('INVALID_ADAPTIVE_DELIVERY: ' + str(error))
    return {'service_id': service_id, 'order_id': raw_order.get('order_id') if isinstance(raw_order, dict) else None,
            'scope': SCOPE, 'accepted': not errors, 'errors': sorted(set(errors)),
            'input_content_sha256': _safe_identity(raw_order), 'artifact_content_sha256': _safe_identity(artifact),
            'independence': 'Independent source-adaptation and outcome checker; shared agent family and host, not external certification.'}
