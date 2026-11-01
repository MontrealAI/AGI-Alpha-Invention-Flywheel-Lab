"""Generated typed intake plans, executed services and retained constraints.

The search enumerates column-role assignments and checks structural invariants;
it never reads an expected answer or a supplied field-name mapping. Monetary
units are source obligations, not values the instrument may invent.
"""
import copy
from decimal import Decimal, InvalidOperation
import hashlib
import itertools
import json
from pathlib import Path
import time

SCHEMA = 'agi-alpha/adaptive012-services/v1'
SCOPE = 'SYNTHETIC_PUBLIC_WORKLOAD'
SOURCE_PATHS = ('connected_enterprise/packet_contract.py','connected_enterprise/receivables_packet.py','connected_enterprise/receivables_packet_verify.py', 'adaptive_enterprise/instruments.py', 'adaptive_enterprise/checkers.py',
                'adaptive_enterprise/strategies.py','adaptive_enterprise/bundles.py', 'enterprise/services.py', 'enterprise/checkers.py',
                'commercial/service.py', 'commercial/service_verifier.py')
CONSTRAINTS = ['preserve_source_rows', 'explicit_money_units', 'unique_record_identity', 'referential_customer_consistency']
BUNDLE_INDICES = (8,9,10,11,12,13,14,16)
ADMISSION_SCHEMA = 'agi-alpha/finite-service-admission048/v1'
PACKET_GEOMETRY_SCHEMA = 'agi-alpha/finite-service-admission048/v2'
_DEFAULT_PACKET_ROWS = object()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def cents(value, unit):
    if type(value) not in {int,str} or unit not in {'cents', 'USD'}:
        raise ValueError('EXPLICIT_EXACT_MONEY_REQUIRED')
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('EXACT_SOURCE_MONEY_REQUIRED')
    scaled = decimal * (100 if unit == 'USD' else 1)
    if not scaled.is_finite() or scaled != scaled.to_integral_value() or not 0 < scaled <= 10**14:
        raise ValueError('POSITIVE_INTEGER_CENTS_REQUIRED')
    return int(scaled)


def _raw(raw):
    from adaptive_enterprise.strategies import SERVICES
    fields = {'order_id', 'service_id', 'scope', 'currency', 'tables', 'units', 'source_order'}
    if not isinstance(raw, dict) or set(raw) != fields or raw['scope'] != SCOPE or raw['currency'] != 'USD' or raw['service_id'] not in SERVICES or not isinstance(raw['order_id'], str) or not raw['order_id']:
        raise ValueError('EXACT_AUTHORIZED_RAW_ORDER_REQUIRED')
    if not isinstance(raw['tables'], dict) or not isinstance(raw['units'], dict):
        raise ValueError('RAW_TABLES_AND_UNITS_REQUIRED')
    if raw['service_id'] == 'reconciliation':
        if set(raw['tables']) != {'invoices', 'payments'} or raw['source_order'] is not None:
            raise ValueError('RAW_RECONCILIATION_TABLES_REQUIRED')
        for table,rows in raw['tables'].items():
            if not isinstance(rows, list) or not 1 <= len(rows) <= 100 or any(not isinstance(row, dict) for row in rows):
                raise ValueError('BOUNDED_RAW_TABLE_REQUIRED')
            if any(set(row) != set(rows[0]) for row in rows):
                raise ValueError('CONSISTENT_EXPORT_COLUMNS_REQUIRED')
            if len(rows[0]) not in ({3} if table=='invoices' else {3,4}):
                raise ValueError('BOUNDED_EXPORT_COLUMNS_REQUIRED')
    elif raw['tables'] or raw['units'] or not isinstance(raw['source_order'], dict):
        raise ValueError('CANONICAL_SERVICE_SOURCE_REQUIRED')
    return raw


def _assignments(rows, payment=False):
    columns = sorted(rows[0])
    roles = ['id', 'customer', 'amount_cents']
    result = []
    for values in itertools.permutations(columns, len(roles)):
        base = dict(zip(roles, values))
        if payment:
            remaining = [x for x in columns if x not in values]
            result.extend([{**base, 'invoice_refs': ref} for ref in remaining] or [{**base, 'invoice_refs': None}])
        else:
            result.append(base)
    return result


def _normalize(raw, mapping, unit, meter=None):
    normalized = {'order_id': raw['order_id'], 'scope': SCOPE, 'currency': 'USD', 'require_complete': False}
    for table in ['invoices', 'payments']:
        rows = []
        m = mapping[table]
        for raw_row in raw['tables'][table]:
            if meter is not None:
                meter[0] += 1
            ident, customer = raw_row[m['id']], raw_row[m['customer']]
            if not isinstance(ident, str) or not ident or not isinstance(customer, str) or not customer:
                raise ValueError('TEXT_IDENTITY_AND_CUSTOMER_REQUIRED')
            row = {'id': ident, 'customer': customer, 'amount_cents': cents(raw_row[m['amount_cents']], unit[table])}
            if table == 'payments':
                value = raw_row[m['invoice_refs']] if m['invoice_refs'] is not None else []
                if isinstance(value, str):
                    value = value.split('|') if value else []
                if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
                    raise ValueError('EXPLICIT_REFERENCE_SEQUENCE_REQUIRED')
                row['invoice_refs'] = value
            rows.append(row)
        normalized[table] = rows
    from commercial.service import validate
    validate(normalized)
    return normalized


def infer_plan(raw, retained=None, *, mode='generated'):
    _raw(raw)
    if mode not in {'generated', 'retained', 'ordinary_reuse', 'conventional'}:
        raise ValueError('DECLARED_PLAN_COMPARATOR_REQUIRED')
    if retained is not None and (not isinstance(retained, dict) or retained.get('schema') != 'adaptive012/retained-constraints/v1' or retained.get('constraints') != CONSTRAINTS):
        raise ValueError('TYPED_RETAINED_CONSTRAINTS_REQUIRED')
    used = list(retained['constraints']) if retained is not None else []
    plan = {'schema': 'adaptive012/intake-plan/v1', 'service_id': raw['service_id'], 'status': 'READY',
            'mapping': None, 'units': {}, 'constraints': list(CONSTRAINTS),
            'search': {'candidates_tested': 0, 'candidate_count': 0, 'operation_count': 0, 'retained_constraints_used': used}, 'failure': None}
    if raw['service_id'] != 'reconciliation':
        return plan
    possibilities = {}
    early = mode in {'retained', 'ordinary_reuse', 'conventional'}
    for table in ['invoices', 'payments']:
        possible = _assignments(raw['tables'][table], table == 'payments')
        plan['search']['candidate_count'] += len(possible)
        if early:
            units = raw['units'].get(table, {})
            filtered=[]
            for m in possible:
                if units.get(m['amount_cents']) not in {'USD','cents'}:
                    continue
                plan['search']['operation_count']+=len(raw['tables'][table])
                if len({str(row.get(m['id'])) for row in raw['tables'][table]})==len(raw['tables'][table]):
                    filtered.append(m)
            possible=filtered
        possibilities[table] = possible
    valid = []
    for inv, pay in itertools.product(possibilities['invoices'], possibilities['payments']):
        plan['search']['candidates_tested'] += 1
        mapping = {'invoices': inv, 'payments': pay}
        units = {table: raw['units'].get(table, {}).get(mapping[table]['amount_cents']) for table in mapping}
        meter=[0]
        try:
            _normalize(raw, mapping, units,meter)
        except (ValueError, KeyError, TypeError, InvalidOperation):
            plan['search']['operation_count']+=meter[0]
            continue
        plan['search']['operation_count']+=meter[0]
        valid.append((mapping, units))
        if len(valid) > 1:
            break
    if len(valid) == 1:
        plan['mapping'], plan['units'] = valid[0]
    else:
        plan.update(status='BLOCKED', failure='AMBIGUOUS_MAPPING' if len(valid) > 1 else 'MISSING_TYPED_MAPPING_OR_FACTS')
    return plan


def retain_failure(raw, failure):
    _raw(raw)
    from adaptive_enterprise.strategies import _adjudicate
    if not isinstance(failure,dict) or failure.get('schema')!='adaptive012/adjudicated-criticism/v1' or failure.get('raw_order')!=raw:
        raise ValueError('VERIFIED_FAILURE_RECEIPT_REQUIRED')
    expected=_adjudicate(failure.get('rejected_offer'),raw,failure.get('rejected_artifact'))
    if failure!=expected:
        raise ValueError('RETAINED_FAILURE_EVIDENCE_MISMATCH')
    return {'schema': 'adaptive012/retained-constraints/v1', 'constraints': list(CONSTRAINTS),
            'source_order_sha256': digest(raw), 'failure_sha256': digest(failure),
            'applicability': 'Typed invoice/payment export adaptation; no inferred missing facts or units.',
            'origin': 'Developer-authored invariant extraction from independently rejected work; not autonomous discovery.'}


def execute_plan(raw, plan):
    _raw(raw)
    if plan.get('status') != 'READY' or plan.get('service_id') != raw['service_id']:
        raise ValueError('PRODUCTION_READY_PLAN_REQUIRED')
    if raw['service_id'] != 'reconciliation':
        result = copy.deepcopy(raw['source_order'])
        result['order_id'] = raw['order_id']
        return result
    return _normalize(raw, plan['mapping'], plan['units'])


def compare_methods(raw, memory):
    """Matched source/tool comparisons; equal-content ordinary reuse may tie."""
    from adaptive_enterprise.checkers import audit_delivery
    from enterprise.services import produce as inherited_produce
    results={}
    for mode in ['generated','retained','ordinary_reuse','conventional']:
        start=time.process_time()
        plan=infer_plan(raw,memory if mode in {'retained','ordinary_reuse'} else None,mode=mode)
        normalized=execute_plan(raw,plan) if plan['status']=='READY' else None
        method='generated_schema' if normalized is not None else 'staged_readiness'
        useful=inherited_produce(raw['service_id'],normalized) if normalized is not None else {'order_id':raw['order_id'],'source_rows':{table:len(rows) for table,rows in raw['tables'].items()},'missing_or_ambiguous':[plan['failure']],'production_ready':False,'promised_outcome':'Intake readiness only; no completed reconciliation, KPI analysis or evidence response.','source_sha256':digest(raw)}
        artifact={'order_id':raw['order_id'],'service_id':raw['service_id'],'scope':SCOPE,'currency':'USD','outcome_scope':'complete_outcome' if normalized is not None else 'intake_readiness','method':method,'plan':plan,'normalized_input':normalized,'useful_outcome':useful}
        checked=audit_delivery(raw['service_id'],raw,artifact)
        results[mode]={'accepted':checked['accepted'],'plan':plan,'useful_outcome_sha256':digest(useful),'process_cpu_seconds':time.process_time()-start,'mapping_stage_row_visits':plan['search']['operation_count']}
    return {'source_sha256':digest(raw),'methods':results,'metric_scope':'Counted row visits in mapping and early pruning only; not human hours, inference billing or complete service cost. CPU measured independently.',
            'conclusion':'Retained constraints and equal-content ordinary reuse share the same information; no superiority is inferred from a tie. Strong conventional typed pruning remains available.'}


def apply_source_extension(raw, supplied_facts):
    """Admit genuinely new simulated-customer facts; never infer absent units."""
    _raw(raw)
    if not isinstance(supplied_facts,dict) or set(supplied_facts)!={'source_id','origin','units','prior_source_sha256'} or supplied_facts['origin']!='SIMULATED_CUSTOMER_SUPPLIED' or supplied_facts['prior_source_sha256']!=digest(raw) or not isinstance(supplied_facts['source_id'],str) or not supplied_facts['source_id']:
        raise ValueError('NEW_SOURCE_EVENT_WITH_PROVENANCE_REQUIRED')
    if raw['service_id']!='reconciliation' or not isinstance(supplied_facts['units'],dict) or set(supplied_facts['units'])!={'invoices','payments'}:
        raise ValueError('SCOPED_NEW_UNIT_EVIDENCE_REQUIRED')
    result=copy.deepcopy(raw)
    for table,new_units in supplied_facts['units'].items():
        if not isinstance(new_units,dict) or any(key not in raw['tables'][table][0] or value not in {'cents','USD'} for key,value in new_units.items()):
            raise ValueError('SOURCE_UNIT_EVIDENCE_REQUIRED')
        if any(key in result['units'].get(table,{}) and result['units'][table][key]!=value for key,value in new_units.items()):
            raise ValueError('CONFLICTING_SOURCE_FACT_REQUIRES_ADJUDICATION')
        result['units'].setdefault(table,{}).update(new_units)
    return result,{'source_id':supplied_facts['source_id'],'origin':supplied_facts['origin'],'prior_source_sha256':digest(raw),'new_source_sha256':digest(result),'scope':'New facts supplied by the simulation environment; readiness sale alone did not manufacture them.'}


def produce(raw, method='generated_schema', retained=None, mode=None):
    if isinstance(raw,dict) and raw.get('service_id')=='receivables_packet':
        if method!='receivables_packet':raise ValueError('QUALIFIED_PACKET_METHOD_REQUIRED')
        from connected_enterprise.receivables_packet import produce as packet_produce
        return packet_produce(raw)
    if isinstance(raw,dict) and raw.get('service_id')=='operations_bundle':
        if method!='operations_bundle':
            raise ValueError('QUALIFIED_BUNDLE_PRODUCTION_METHOD_REQUIRED')
        from adaptive_enterprise.bundles import build_bundle
        return build_bundle(raw)
    from enterprise.services import produce as inherited_produce
    _raw(raw)
    plan = infer_plan(raw, retained, mode=mode or ('retained' if retained is not None else 'generated'))
    if method == 'canonical' and raw['service_id'] == 'reconciliation':
        canonical_mapping = {'invoices': {'id': 'id', 'customer': 'customer', 'amount_cents': 'amount_cents'},
                             'payments': {'id': 'id', 'customer': 'customer', 'amount_cents': 'amount_cents', 'invoice_refs': 'invoice_refs'}}
        if plan['mapping'] != canonical_mapping:
            raise ValueError('CANONICAL_METHOD_REQUIRES_CANONICAL_SOURCE_SCHEMA')
    scope = 'intake_readiness' if method == 'staged_readiness' else 'complete_outcome'
    normalized = None
    if scope == 'complete_outcome':
        normalized = execute_plan(raw, plan)
        useful = inherited_produce(raw['service_id'], normalized)
    else:
        if plan['status'] == 'READY':
            raise ValueError('STAGED_METHOD_REQUIRES_REAL_UNRESOLVED_INTAKE_OBSTACLE')
        useful = {'order_id': raw['order_id'], 'source_rows': {table: len(rows) for table, rows in raw['tables'].items()},
                  'missing_or_ambiguous': [plan['failure']], 'production_ready': False,
                  'promised_outcome': 'Intake readiness only; no completed reconciliation, KPI analysis or evidence response.', 'source_sha256': digest(raw)}
    return {'order_id': raw['order_id'], 'service_id': raw['service_id'], 'scope': SCOPE, 'currency': 'USD',
            'outcome_scope': scope, 'method': method, 'plan': plan, 'normalized_input': normalized, 'useful_outcome': useful}


def synthetic_raw(service_id, index, cohort_seed=0):
    from enterprise.services import synthetic_order
    if type(cohort_seed) is not int or not 0<=cohort_seed<=10**15:
        raise ValueError('BOUNDED_COHORT_GENERATION_SEED_REQUIRED')
    token=digest(['adaptive012-fresh-source',cohort_seed,service_id,index])[:10]
    offset=0 if cohort_seed==0 else int(token,16)%1_000_000
    source = synthetic_order(service_id, index + 1000 + offset)
    ident = 'adaptive012-' + service_id + '-' + (token+'-' if cohort_seed else '') + str(index).zfill(3)
    raw = {'order_id': ident, 'service_id': service_id, 'scope': SCOPE, 'currency': 'USD', 'tables': {}, 'units': {}, 'source_order': None}
    if service_id != 'reconciliation':
        raw['source_order'] = source
        return raw
    if cohort_seed:
        for table in ['invoices','payments']:
            for row in source[table]:
                row['id']=token+'-'+row['id']
                row['customer']=token+'-'+row['customer']
                if table=='payments':
                    row['invoice_refs']=[token+'-'+ref for ref in row['invoice_refs']]
    for table in ['invoices', 'payments']:
        suffix='_'+token if cohort_seed else ''
        renamed = {'id': f'field_{index}{suffix}_a', 'customer': f'field_{index}{suffix}_b', 'amount_cents': f'field_{index}{suffix}_c', 'invoice_refs': f'field_{index}{suffix}_d'}
        if index < 8:
            renamed = {k: k for k in renamed}
        unit = 'cents' if index<8 else ('USD' if index % 2 else 'cents')
        raw['units'][table] = {renamed['amount_cents']: unit} if index<8 or index % 8 != 7 else {}
        raw['tables'][table] = [{renamed[key]: (format(Decimal(value)/100, '.2f') if key == 'amount_cents' and unit == 'USD' else value) for key, value in row.items()} for row in source[table]]
    return raw


def _write(root, path, value):
    full = root / path
    full.parent.mkdir(parents=True, exist_ok=True)
    with full.open('xb') as stream:
        stream.write(canonical(value))
    return hashlib.sha256(full.read_bytes()).hexdigest()


def _read(root, path, expected):
    from commercial.ledger import read_bound
    return read_bound(root, path, expected)


def _finite_windows(count, window):
    if type(count) is not int or count < 1 or type(window) is not int or window < 1:
        raise ValueError('FINITE_POSITIVE_ADMISSION_AND_WINDOW_REQUIRED')
    for start in range(0, count, window):
        yield start, min(window, count-start)


def _packet_geometry(packet_count, rows):
    if (type(packet_count) is not int or packet_count < 1 or type(rows) is not list
            or len(rows) != packet_count or any(type(n) is not int or not 4 <= n <= 1000 for n in rows)):
        raise ValueError('EXACT_BOUNDED_PACKET_ROW_VECTOR_REQUIRED')
    return list(rows)


def _packet_inventory(packet_count, rows):
    return {'jobs': packet_count, 'rows_by_job': list(rows),
            'scope': 'Explicit finite coherent entity/period inventory, not sales or market size.'}


def _admission_record(manifest, primitive_count, packet_count, packet_rows, window, *, packet_rows_by_job=None):
    from adaptive_enterprise.strategies import PRIMITIVE_SERVICES
    if type(primitive_count) is not int or primitive_count < 32 or type(packet_count) is not int or packet_count < 0:
        raise ValueError('FINITE_DECLARED_SERVICE_COUNTS_REQUIRED')
    if packet_rows_by_job is not None:
        _packet_geometry(packet_count, packet_rows_by_job)
        if packet_rows is not None:
            raise ValueError('SCALAR_AND_VECTOR_PACKET_GEOMETRY_CONFLICT')
    elif (packet_count == 0 and packet_rows is not None or packet_count > 0 and
            (type(packet_rows) is not int or not 4 <= packet_rows <= 1000)):
        raise ValueError('BOUNDED_PACKET_ROWS_REQUIRED')
    seed_hash = manifest['cohort_provenance'].get('cohort_seed_sha256')
    if type(seed_hash) is not str or len(seed_hash) != 64 or any(c not in '0123456789abcdef' for c in seed_hash):
        raise ValueError('EXACT_GENERATION_SEED_COMMITMENT_REQUIRED')
    total = len(PRIMITIVE_SERVICES)*primitive_count+len(BUNDLE_INDICES)+packet_count
    if len(manifest['jobs']) != total:
        raise ValueError('FINITE_ADMISSION_COUNT_MISMATCH')
    chunks = []
    for start, count in _finite_windows(total, window):
        chunks.append({'start': start, 'count': count, 'jobs_sha256': digest(manifest['jobs'][start:start+count])})
    result = {'schema': ADMISSION_SCHEMA, 'primitive_jobs_per_service': primitive_count,
            'primitive_services': list(PRIMITIVE_SERVICES), 'bundle_indices': list(BUNDLE_INDICES),
            'packet_jobs': packet_count, 'packet_rows_per_kind': packet_rows,
            'chunk_size': window, 'total_jobs': total, 'chunks': chunks,
            'source_sha256': digest(manifest['source_hashes']),
            'cohort_seed_sha256': manifest['cohort_provenance']['cohort_seed_sha256']}
    if packet_rows_by_job is not None:
        result['schema'] = PACKET_GEOMETRY_SCHEMA
        del result['packet_rows_per_kind']
        result['packet_rows_by_job'] = list(packet_rows_by_job)
    return result


def _seal_admission(manifest, primitive_count, packet_count, packet_rows, window, *, packet_rows_by_job=None):
    manifest['cohort_provenance']['finite_admission'] = _admission_record(
        manifest, primitive_count, packet_count, packet_rows, window, packet_rows_by_job=packet_rows_by_job)


def _validate_admission(manifest):
    from adaptive_enterprise.strategies import PRIMITIVE_SERVICES
    admission = manifest['cohort_provenance'].get('finite_admission')
    if admission is None:
        if len(manifest['jobs']) > 1000:
            raise ValueError('FINITE_SOURCE_BOUND_ADMISSION_REQUIRED')
        return
    if not isinstance(admission, dict):
        raise ValueError('FINITE_SOURCE_BOUND_ADMISSION_REQUIRED')
    vector = None
    if admission.get('schema') == PACKET_GEOMETRY_SCHEMA:
        vector = _packet_geometry(admission.get('packet_jobs'), admission.get('packet_rows_by_job'))
        if 'packet_rows_per_kind' in admission:
            raise ValueError('SCALAR_AND_VECTOR_PACKET_GEOMETRY_CONFLICT')
        if manifest['cohort_provenance'].get('packet_inventory') != _packet_inventory(admission['packet_jobs'], vector):
            raise ValueError('PACKET_INVENTORY_GEOMETRY_MISMATCH')
    elif admission.get('schema') != ADMISSION_SCHEMA:
        raise ValueError('FINITE_ADMISSION_SCHEMA_REQUIRED')
    expected = _admission_record(manifest, admission.get('primitive_jobs_per_service'),
        admission.get('packet_jobs'), admission.get('packet_rows_per_kind'), admission.get('chunk_size'),
        packet_rows_by_job=vector)
    if canonical(admission) != canonical(expected):
        raise ValueError('FINITE_ADMISSION_BINDING_MISMATCH')
    primitive_count = admission['primitive_jobs_per_service']
    for index, job in enumerate(manifest['jobs']):
        service = (PRIMITIVE_SERVICES[index//primitive_count] if index < len(PRIMITIVE_SERVICES)*primitive_count
                   else 'operations_bundle' if index < len(PRIMITIVE_SERVICES)*primitive_count+len(BUNDLE_INDICES)
                   else 'receivables_packet')
        if not isinstance(job, dict) or job.get('service_id') != service:
            raise ValueError('FINITE_ADMISSION_SERVICE_ORDER_MISMATCH')


def audit_admission(root, manifest, *, cohort_seed):
    """Reconstruct declared origins without exposing a generation seed to policy."""
    from adaptive_enterprise.strategies import PRIMITIVE_SERVICES
    from connected_enterprise.packet_contract import synthetic_input
    _validate_manifest(root, manifest)
    admission = manifest['cohort_provenance'].get('finite_admission')
    if (type(cohort_seed) is not int or not 0 <= cohort_seed <= 10**15 or admission is None
            or admission['cohort_seed_sha256'] != digest(cohort_seed)):
        raise ValueError('DECLARED_GENERATION_ORIGIN_REQUIRED')
    offset = 0
    for service in PRIMITIVE_SERVICES:
        for start, count in _finite_windows(admission['primitive_jobs_per_service'], admission['chunk_size']):
            for index in range(start, start+count):
                job = manifest['jobs'][offset]
                expected = synthetic_raw(service, index, cohort_seed)
                if canonical(_read(root, job['input'], job['input_sha256'])) != canonical(expected):
                    raise ValueError('ADMITTED_GENERATION_ORIGIN_MISMATCH')
                offset += 1
    for index in range(len(BUNDLE_INDICES)):
        job = manifest['jobs'][offset]
        ident = 'adaptive012-operations_bundle-'+(digest(cohort_seed)[:10]+'-' if cohort_seed else '')+str(index).zfill(3)
        raw = _read(root, job['input'], job['input_sha256'])
        wanted = [manifest['jobs'][i*admission['primitive_jobs_per_service']+BUNDLE_INDICES[index]]['id']
                  for i in range(len(PRIMITIVE_SERVICES))]
        if job['id'] != ident or raw.get('work_keys') != wanted:
            raise ValueError('ADMITTED_BUNDLE_ORIGIN_MISMATCH')
        offset += 1
    for start, count in _finite_windows(admission['packet_jobs'], admission['chunk_size']) if admission['packet_jobs'] else ():
        for index in range(start, start+count):
            job = manifest['jobs'][offset]
            rows = (admission['packet_rows_by_job'][index] if admission['schema'] == PACKET_GEOMETRY_SCHEMA
                    else admission['packet_rows_per_kind'])
            expected = synthetic_input(index=index, cohort_seed=cohort_seed, rows=rows)
            if canonical(_read(root, job['input'], job['input_sha256'])) != canonical(expected):
                raise ValueError('ADMITTED_PACKET_ORIGIN_MISMATCH')
            offset += 1
    checked = load_jobs(root, manifest)
    return {'schema': admission['schema'], 'accepted': True, 'total_jobs': offset,
            'accepted_jobs': len(checked), 'chunks': len(admission['chunks']),
            'admission_sha256': digest(admission), 'manifest_sha256': digest(manifest),
            'scope': 'Exact synthetic origin and independent complete-artifact checks; no demand, capacity or financial authority.'}


def prepare_services(root, relative, cohort_seed=0, *, jobs_per_service=32, chunk_size=64):
    if type(jobs_per_service) is not int or jobs_per_service<32:
        raise ValueError("FINITE_ADMITTED_INVENTORY_REQUIRED")
    if type(chunk_size) is not int or chunk_size < 1:
        raise ValueError('FINITE_POSITIVE_ADMISSION_AND_WINDOW_REQUIRED')
    if type(cohort_seed) is not int or not 0 <= cohort_seed <= 10**15:
        raise ValueError('BOUNDED_COHORT_GENERATION_SEED_REQUIRED')
    from adaptive_enterprise.checkers import audit_delivery
    from adaptive_enterprise.strategies import PRIMITIVE_SERVICES
    root, target = Path(root).absolute(), Path(relative)
    if target.is_absolute() or '..' in target.parts or (root/target).exists() or any(p.is_symlink() for p in (root/target).parents):
        raise ValueError('NEW_RELATIVE_SERVICE_OUTPUT_REQUIRED')
    source_hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in SOURCE_PATHS}
    jobs = []
    start = time.process_time()
    for service_id in PRIMITIVE_SERVICES:
        for start_index, count in _finite_windows(jobs_per_service, chunk_size):
            for index in range(start_index, start_index+count):
                raw = synthetic_raw(service_id, index,cohort_seed)
                plan = infer_plan(raw)
                method = 'staged_readiness' if plan['status'] != 'READY' else ('canonical' if service_id!='reconciliation' or index<8 else 'generated_schema')
                artifact = produce(raw, method)
                checked = audit_delivery(service_id, raw, artifact)
                base = target / raw['order_id']
                job = {'id': raw['order_id'], 'service_id': service_id, 'accepted': checked['accepted'],'work_keys':[raw['order_id']]}
                for field, name, value in [('input','input.json',raw), ('artifact','artifact.json',artifact)]:
                    job[field] = str(base/name)
                    job[field+'_sha256'] = _write(root, job[field], value)
                receipt = {**checked, 'input_sha256':job['input_sha256'], 'artifact_sha256':job['artifact_sha256'],
                           'checker_source_sha256':source_hashes['adaptive_enterprise/checkers.py']}
                job['receipt'] = str(base/'acceptance.json')
                job['receipt_sha256'] = _write(root, job['receipt'], receipt)
                jobs.append(job)
    component_jobs=jobs[:]
    for bundle_index,index in enumerate(BUNDLE_INDICES):
        components=[]
        for service_id in PRIMITIVE_SERVICES:
            job=[j for j in component_jobs if j['service_id']==service_id][index]
            components.append({'job_id':job['id'],'service_id':service_id,
                               'raw_order':_read(root,job['input'],job['input_sha256']),
                               'artifact':_read(root,job['artifact'],job['artifact_sha256'])})
        ident='adaptive012-operations_bundle-'+(digest(cohort_seed)[:10]+'-' if cohort_seed else '')+str(bundle_index).zfill(3)
        work_keys=[c['job_id'] for c in components]
        raw={'order_id':ident,'service_id':'operations_bundle','scope':SCOPE,'currency':'USD','components':components,'work_keys':work_keys}
        artifact=produce(raw,'operations_bundle');checked=audit_delivery('operations_bundle',raw,artifact)
        base=target/ident
        job={'id':ident,'service_id':'operations_bundle','accepted':checked['accepted'],'work_keys':work_keys}
        for field,name,value in [('input','input.json',raw),('artifact','artifact.json',artifact)]:
            job[field]=str(base/name);job[field+'_sha256']=_write(root,job[field],value)
        receipt={**checked,'input_sha256':job['input_sha256'],'artifact_sha256':job['artifact_sha256'],'checker_source_sha256':source_hashes['adaptive_enterprise/checkers.py']}
        job['receipt']=str(base/'acceptance.json');job['receipt_sha256']=_write(root,job['receipt'],receipt);jobs.append(job)
    manifest = {'schema': SCHEMA, 'scope': SCOPE, 'currency':'USD', 'account_namespace':'adaptive012',
                'source_hashes':source_hashes,'jobs':jobs,'attempts':[],
                'cohort_provenance':{'generator':'adaptive_enterprise.instruments.synthetic_raw','cohort_seed_sha256':digest(cohort_seed),'scope':'Deterministic synthetic sources; seed0 is exposed development. Fresh registered seeds change amounts, identities, evidence and aliased headers; no hidden seed is given to seller policy.'},
                'resource_receipt':{'process_cpu_seconds':time.process_time()-start,'model_calls':0,'billing':'UNAVAILABLE; deterministic executors and authored setup envelope'}}
    if jobs_per_service!=32:
        manifest['cohort_provenance']['jobs_per_service']=jobs_per_service
        manifest['cohort_provenance']['inventory_scope']='Equal predeclared finite synthetic workload inventory, not market size or free business capacity. Actual enterprise delivery costs remain native prepaid contracts.'
    _seal_admission(manifest, jobs_per_service, 0, None, chunk_size)
    _write(root,str(target/'MANIFEST.json'),manifest)
    load_jobs(root,manifest)
    return manifest


def check_job(root, manifest, job, artifact=None):
    _validate_manifest(root, manifest)
    checked = _check_job(root, manifest, job, artifact)
    _validate_manifest(root, manifest)
    return checked


def _check_job(root, manifest, job, artifact=None):
    from adaptive_enterprise.checkers import audit_delivery
    raw = _read(root,job['input'],job['input_sha256'])
    current = _read(root,job['artifact'],job['artifact_sha256'])
    receipt = _read(root,job['receipt'],job['receipt_sha256'])
    checked = audit_delivery(job['service_id'],raw,current if artifact is None else artifact)
    expected_work=current['work_keys'] if job['service_id'] in {'operations_bundle','receivables_packet'} else [job['id']]
    if job['service_id']=='receivables_packet':
        from connected_enterprise.packet_contract import work_contract
        if expected_work!=work_contract(raw)['work_keys']:raise ValueError('PACKET_WORK_NOT_BOUND_TO_SOURCE')
    if job.get('work_keys')!=expected_work or len(expected_work)!=len(set(expected_work)):
        raise ValueError('EXACT_SHARED_WORK_IDENTITIES_REQUIRED')
    if job['service_id']=='operations_bundle':
        for component in raw['components']:
            original=next((item for item in manifest['jobs'] if item['id']==component['job_id'] and item['service_id']==component['service_id']),None)
            if original is None or original.get('work_keys')!=[component['job_id']] or canonical(_read(root,original['input'],original['input_sha256']))!=canonical(component['raw_order']) or canonical(_read(root,original['artifact'],original['artifact_sha256']))!=canonical(component['artifact']):
                raise ValueError('BUNDLE_MUST_REUSE_EXACT_ADMITTED_COMPONENT_WORK')
    if raw['order_id']!=job['id'] or receipt.get('input_sha256')!=job['input_sha256'] or receipt.get('artifact_sha256')!=job['artifact_sha256'] or receipt.get('checker_source_sha256')!=manifest['source_hashes']['adaptive_enterprise/checkers.py'] or any(receipt.get(k)!=v for k,v in checked.items()) or checked['accepted'] is not job['accepted']:
        raise ValueError('ADAPTIVE_SERVICE_ACCEPTANCE_IDENTITY_MISMATCH')
    if artifact is not None and canonical(artifact)!=canonical(current):
        raise ValueError('ADAPTIVE_DELIVERED_ARTIFACT_CHANGED')
    return {'job':job,'artifact':current,'receipt':receipt}


def _validate_manifest(root,manifest):
    if not isinstance(manifest,dict) or manifest.get('schema')!=SCHEMA or manifest.get('scope')!=SCOPE or manifest.get('currency')!='USD' or manifest.get('account_namespace')!='adaptive012':
        raise ValueError('ADAPTIVE_SERVICE_SCOPE_REQUIRED')
    if set(manifest)-{'native_engine'}!={'schema','scope','currency','account_namespace','source_hashes','jobs','attempts','cohort_provenance','resource_receipt'} or manifest['attempts']!=[]:
        raise ValueError('EXACT_ADAPTIVE_MANIFEST_REQUIRED')
    if 'native_engine' in manifest and manifest['native_engine'] not in {'legacy-permanent-v1','prospective-v1','exact-permanent-v2','exact-prospective-v2'}:
        raise ValueError('DECLARED_NATIVE_ENGINE_REQUIRED')
    if set(manifest.get('source_hashes',{}))!=set(SOURCE_PATHS) or not isinstance(manifest.get('jobs'),list) or not manifest['jobs'] or not isinstance(manifest.get('cohort_provenance'),dict):
        raise ValueError('ADAPTIVE_BOUNDED_SOURCE_AND_COHORT_REQUIRED')
    _validate_admission(manifest)
    for name,expected in manifest['source_hashes'].items():
        source=Path(root)/name
        if source.is_symlink() or any(p.is_symlink() for p in source.parents) or hashlib.sha256(source.read_bytes()).hexdigest()!=expected or hashlib.sha256((Path(__file__).resolve().parents[1]/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('ADAPTIVE_EXECUTING_SOURCE_CHANGED')


def iter_checked_job_chunks(root, manifest):
    _validate_manifest(root,manifest)
    admission = manifest['cohort_provenance'].get('finite_admission')
    window = admission['chunk_size'] if admission else 64
    seen=set()
    for start, count in _finite_windows(len(manifest['jobs']), window):
        checked_chunk=[]
        for job in manifest['jobs'][start:start+count]:
            fields={'id','service_id','accepted','work_keys','input','input_sha256','artifact','artifact_sha256','receipt','receipt_sha256'}
            if not isinstance(job,dict) or set(job)!=fields or not isinstance(job.get('id'),str) or not job['id'] or job['id'] in seen or type(job['accepted']) is not bool:
                raise ValueError('UNIQUE_ADAPTIVE_JOB_REQUIRED')
            seen.add(job['id'])
            checked=_check_job(root,manifest,job)
            checked_chunk.append(checked)
        yield checked_chunk
    _validate_manifest(root, manifest)


def load_jobs(root,manifest):
    jobs={}
    for chunk in iter_checked_job_chunks(root, manifest):
        for checked in chunk:
            if checked['job']['accepted']:
                jobs[checked['job']['id']]=checked
    if not jobs:
        raise ValueError('NO_ACCEPTED_ADAPTIVE_ARTIFACTS')
    return jobs


def execute_job(root,job):
    from adaptive_enterprise.checkers import audit_delivery
    start=time.process_time()
    raw=_read(root,job['input'],job['input_sha256'])
    saved=_read(root,job['artifact'],job['artifact_sha256'])
    receipt=_read(root,job['receipt'],job['receipt_sha256'])
    if job.get('accepted') is not True or raw.get('order_id')!=job.get('id') or receipt.get('input_sha256')!=job['input_sha256'] or receipt.get('artifact_sha256')!=job['artifact_sha256'] or receipt.get('checker_source_sha256')!=hashlib.sha256((Path(root)/'adaptive_enterprise/checkers.py').read_bytes()).hexdigest():
        raise ValueError('ADAPTIVE_EXECUTION_IDENTITY_MISMATCH')
    artifact=produce(raw,saved['method'])
    checked=audit_delivery(job['service_id'],raw,artifact)
    if not checked['accepted'] or canonical(artifact)!=canonical(saved) or any(receipt.get(k)!=v for k,v in checked.items()):
        raise ValueError('ADAPTIVE_REEXECUTION_FAILED')
    return {**checked,'artifact_sha256':job['artifact_sha256'],'reexecuted':True,
            'process_cpu_seconds':time.process_time()-start,'operation_count':operation_count(artifact),'model_calls':0}


def operation_count(artifact):
    if artifact.get('service_id')=='receivables_packet':return artifact['work_observation']['instrumented_source_row_visits']
    if artifact.get('service_id')=='operations_bundle':
        return sum(operation_count(c['artifact']) for c in artifact['components'])
    return artifact['plan']['search']['operation_count']


def _semantics(artifact):
    if artifact.get('service_id')=='receivables_packet':return artifact
    if artifact.get('service_id')=='operations_bundle':
        return {'work_keys':artifact['work_keys'],'components':[{'job_id':c['job_id'],'semantics':_semantics(c['artifact'])} for c in artifact['components']],'promise':artifact['promise']}
    return {'normalized_input':artifact['normalized_input'],'useful_outcome':artifact['useful_outcome']}


def execute_offer(root,manifest,offer,job_id,context=None):
    from adaptive_enterprise.strategies import validate_offer
    from adaptive_enterprise.checkers import audit_delivery
    validate_offer(offer)
    _validate_manifest(root,manifest)
    job=next((job for job in manifest['jobs'] if job['id']==job_id),None)
    if job is None or offer['service_id']!=job['service_id']:
        raise ValueError('SCOPED_OFFER_JOB_REQUIRED')
    saved=check_job(root,manifest,job)['artifact'];raw=_read(root,job['input'],job['input_sha256'])
    start=time.process_time()
    try:
        if offer['method']!=saved['method'] or offer['scope']!=saved['outcome_scope']:
            raise ValueError('OFFER_DOES_NOT_MATCH_ADMITTED_PRODUCTION_CONTRACT')
        artifact=produce(raw,offer['method'],(context or {}).get('retained'),mode=(context or {}).get('mode'))
        checked=audit_delivery(offer['service_id'],raw,artifact)
        if artifact['outcome_scope']!=offer['scope']:
            raise ValueError('OFFER_SCOPE_CHANGED')
        if digest(_semantics(artifact))!=digest(_semantics(saved)):
            raise ValueError('ACTUAL_PRODUCTION_DIFFERS_FROM_NATIVE_DELIVERY_OUTCOME')
        return {**checked,'artifact_sha256':job['artifact_sha256'],'actual_execution_artifact_sha256':digest(artifact),'artifact':artifact,'outcome_scope':artifact['outcome_scope'],
                'native_delivered_artifact_sha256':job['artifact_sha256'],'useful_outcome_sha256':digest(_semantics(artifact)),
                'execution_binding':'Native delivers the saved accepted artifact; current production rechecks identical normalized input and useful outcome. Search trace and measured work may differ under retained constraints; byte identity is not claimed.',
                'operation_count':operation_count(artifact),**({'work_count_scope':artifact['work_observation']['scope']} if artifact.get('service_id')=='receivables_packet' else {}),'work_keys':job['work_keys'],'process_cpu_seconds':time.process_time()-start,'model_calls':0}
    except (ValueError,KeyError,TypeError) as exc:
        return {'accepted':False,'service_id':offer['service_id'],'order_id':raw['order_id'],'errors':[str(exc)],
                'outcome_scope':offer['scope'],'operation_count':0,'process_cpu_seconds':time.process_time()-start,'model_calls':0}


def prepare_complete_offer_services(root, relative, *, cohort_seed=0, jobs_per_service=32, packet_jobs=8, packet_rows=_DEFAULT_PACKET_ROWS, chunk_size=64, packet_rows_by_job=None):
    """Explicit opt-in finite primitive plus coherent-packet admission; not demand."""
    if packet_rows_by_job is not None:
        packet_rows_by_job = _packet_geometry(packet_jobs, packet_rows_by_job)
        if packet_rows is not _DEFAULT_PACKET_ROWS:
            raise ValueError('SCALAR_AND_VECTOR_PACKET_GEOMETRY_CONFLICT')
        packet_rows = None
    else:
        packet_rows = 40 if packet_rows is _DEFAULT_PACKET_ROWS else packet_rows
        if type(packet_jobs) is not int or packet_jobs<1 or type(packet_rows) is not int or not 4<=packet_rows<=1000:
            raise ValueError('BOUNDED_PACKET_INVENTORY_REQUIRED')
    from connected_enterprise.packet_contract import synthetic_input,work_contract
    from adaptive_enterprise.checkers import audit_delivery
    root=Path(root);start=time.process_time()
    manifest=prepare_services(root,relative,cohort_seed=cohort_seed,jobs_per_service=jobs_per_service,chunk_size=chunk_size)
    for start_index, count in _finite_windows(packet_jobs, chunk_size):
        for index in range(start_index, start_index+count):
            rows = packet_rows_by_job[index] if packet_rows_by_job is not None else packet_rows
            raw=synthetic_input(index=index,cohort_seed=cohort_seed,rows=rows)
            artifact=produce(raw,'receivables_packet');checked=audit_delivery('receivables_packet',raw,artifact)
            if not checked['accepted']:raise ValueError('PACKET_ADMISSION_REJECTED')
            base=Path(relative)/raw['order_id']
            job={'id':raw['order_id'],'service_id':'receivables_packet','accepted':True,'work_keys':work_contract(raw)['work_keys']}
            for field,name,value in [('input','input.json',raw),('artifact','artifact.json',artifact)]:
                job[field]=str(base/name);job[field+'_sha256']=_write(root,job[field],value)
            receipt={**checked,'input_sha256':job['input_sha256'],'artifact_sha256':job['artifact_sha256'],'checker_source_sha256':manifest['source_hashes']['adaptive_enterprise/checkers.py']}
            job['receipt']=str(base/'acceptance.json');job['receipt_sha256']=_write(root,job['receipt'],receipt)
            manifest['jobs'].append(job)
    manifest['cohort_provenance']['packet_inventory']={'jobs':packet_jobs,'rows_per_kind':packet_rows,'scope':'Explicit finite coherent entity/period inventory, not sales or market size.'}
    if packet_rows_by_job is not None:
        manifest['cohort_provenance']['packet_inventory'] = _packet_inventory(packet_jobs, packet_rows_by_job)
    manifest['resource_receipt']['process_cpu_seconds']=time.process_time()-start
    _seal_admission(manifest, jobs_per_service, packet_jobs, packet_rows, chunk_size, packet_rows_by_job=packet_rows_by_job)
    from commercial.persistence import atomic_bytes
    atomic_bytes(root/relative/'MANIFEST.json',canonical(manifest)+b'\n');load_jobs(root,manifest)
    return manifest
