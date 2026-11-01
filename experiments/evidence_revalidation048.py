"""Finite dependency-carrying evidence experiment; no account or trade authority."""
from __future__ import annotations
import argparse
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'evidence-revalidation048/v1'
ARMS = ('full_recompute', 'ordinary_reuse', 'retained_method')
SOURCE_PATHS = ('experiments/evidence_revalidation048.py', 'tests/test_evidence_revalidation048.py')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _contract(contract, sources):
    if type(contract) is not dict or set(contract) != {'sources', 'claims'} or sorted(contract['sources']) != sorted(sources) or len(set(contract['sources'])) != len(sources):
        raise ValueError('EXACT_DECLARED_SOURCE_SET_REQUIRED')
    claims = contract['claims']
    if type(claims) is not list or not claims:
        raise ValueError('CLAIMS_REQUIRED')
    seen = set()
    for claim in claims:
        if type(claim) is not dict or set(claim) != {'id', 'kind', 'source', 'column'} or type(claim['id']) is not str or claim['id'] in seen or not claim['id']:
            raise ValueError('CLAIM_CONTRACT')
        if claim['kind'] not in {'integer_sum', 'unique_key'} or claim['source'] not in sources or type(claim['column']) is not str:
            raise ValueError('UNSUPPORTED_OR_UNDECLARED_INPUT')
        seen.add(claim['id'])
    if {c['source'] for c in claims} != set(sources):
        raise ValueError('UNACCOUNTED_SOURCE')
    if any(type(value) is not str for value in sources.values()):
        raise ValueError('TEXT_SOURCES_REQUIRED')
    return claims


def construct(contract, sources):
    claims = _contract(contract, sources)
    return {'schema': SCHEMA, 'contract_sha256': digest(contract),
            'instrument_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'dependencies': {c['id']: [c['source']] for c in claims},
            'applicability': ['Exact declared source set', 'Only two supported total CSV functions',
                              'Trusted previous artifact hash supplied out of band', 'Independent full current-input audit remains required'],
            'authority': []}


def _evaluate(claim, text):
    reader = csv.DictReader(io.StringIO(text), strict=True)
    if reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames) or claim['column'] not in reader.fieldnames:
        raise ValueError('CSV_HEADER')
    values = []
    for row in reader:
        if None in row or any(v is None for v in row.values()):
            raise ValueError('CSV_ROW_SHAPE')
        values.append(row[claim['column']])
    if claim['kind'] == 'integer_sum':
        if any(not value or str(int(value)) != value for value in values):
            raise ValueError('CANONICAL_INTEGER_REQUIRED')
        result = sum(map(int, values))
    else:
        result = len(values) == len(set(values)) and all(values)
        result = bool(result)
    return result, len(values)


def produce(contract, sources, plan, previous=None, previous_sha256=None):
    claims = _contract(contract, sources)
    if plan != construct(contract, sources):
        raise ValueError('PLAN_CHANGED_OR_INCOMPLETE')
    if previous is not None and (previous_sha256 is None or digest(previous) != previous_sha256):
        raise ValueError('TRUSTED_PREVIOUS_IDENTITY_REQUIRED')
    rows, evaluated, reused, values = 0, [], [], {}
    for claim in claims:
        key = claim['id']
        input_hash = digest([claim, sources[claim['source']]])
        prior = previous.get('claims', {}).get(key) if previous is not None else None
        if previous is not None and (previous.get('plan_sha256') != digest(plan) or previous.get('contract_sha256') != digest(contract)):
            raise ValueError('PREVIOUS_SCOPE_CHANGED')
        if prior is not None and prior.get('input_sha256') == input_hash:
            value = copy.deepcopy(prior['value'])
            reused.append(key)
        else:
            value, visits = _evaluate(claim, sources[claim['source']])
            rows += visits
            evaluated.append(key)
        values[key] = {'input_sha256': input_hash, 'value': value}
    return {'schema': SCHEMA, 'contract_sha256': digest(contract), 'plan_sha256': digest(plan),
            'sources_sha256': digest(sources), 'claims': values, 'evaluated': evaluated,
            'reused': reused, 'producer_row_visits': rows, 'authority': []}


def audit(contract, sources, plan, artifact):
    """Full current-input reconstruction; never calls producer evaluation or trusts reuse."""
    claims = _contract(contract, sources)
    if plan != construct(contract, sources):
        raise ValueError('AUDIT_PLAN_INVALID')
    if artifact.get('schema') != SCHEMA or artifact.get('contract_sha256') != digest(contract) or artifact.get('plan_sha256') != digest(plan) or artifact.get('sources_sha256') != digest(sources) or artifact.get('authority') != []:
        raise ValueError('AUDIT_BINDING_INVALID')
    expected, rows = {}, 0
    for claim in claims:
        table = list(csv.reader(io.StringIO(sources[claim['source']]), strict=True))
        if not table or len(set(table[0])) != len(table[0]) or claim['column'] not in table[0]:
            raise ValueError('AUDIT_CSV_HEADER')
        column = table[0].index(claim['column'])
        if any(len(row) != len(table[0]) for row in table[1:]):
            raise ValueError('AUDIT_CSV_ROW')
        values = [row[column] for row in table[1:]]
        rows += len(values)
        if claim['kind'] == 'integer_sum':
            if any(str(int(value)) != value for value in values):
                raise ValueError('AUDIT_INTEGER')
            value = sum(int(item) for item in values)
        else:
            value = bool(all(values) and len(set(values)) == len(values))
        expected[claim['id']] = {'input_sha256': digest([claim, sources[claim['source']]]), 'value': value}
    if artifact.get('claims') != expected:
        raise ValueError('AUDIT_CLAIM_MISMATCH')
    return {'accepted': True, 'full_row_visits': rows, 'artifact_sha256': digest(artifact), 'authority': []}


def cases():
    result = []
    for domain, column, kind, original, replacement in (
        ('distribution_manifest', 'bytes', 'integer_sum', 'name,bytes\na.py,41\nb.py,59\n', 'name,bytes\na.py,41\nb.py,71\n'),
        ('manufacturing_sample', 'serial', 'unique_key', 'serial,status\nA,pass\nB,pass\n', 'serial,status\nA,pass\nA,fail\n'),
        ('measurement_batch', 'reading', 'integer_sum', 'sensor,reading\nA,-7\nB,11\n', 'sensor,reading\nA,-7\nB,-11\n')):
        sources = {'changing.csv': original, 'stable.csv': 'id,n\nx,17\ny,23\n'}
        contract = {'sources': sorted(sources), 'claims': [
            {'id': domain, 'kind': kind, 'source': 'changing.csv', 'column': column},
            {'id': 'stable_total', 'kind': 'integer_sum', 'source': 'stable.csv', 'column': 'n'},
            {'id': 'stable_identity', 'kind': 'unique_key', 'source': 'stable.csv', 'column': 'id'}]}
        for change in ('localized', 'all_changed'):
            current = dict(sources, **{'changing.csv': replacement})
            if change == 'all_changed':
                current['stable.csv'] = 'id,n\nz,31\nz,37\n'
            result.append({'id': domain + ':' + change, 'contract': contract, 'before': sources, 'after': current})
    return result


def protocol():
    return {'schema': SCHEMA, 'evidence_role': 'developer_authored_finite_engineering_comparison',
            'arms': list(ARMS), 'cases_sha256': digest(cases()), 'case_ids': [c['id'] for c in cases()],
            'primary_metric': 'independently accepted successor artifacts; no retained-method advantage if ordinary reuse ties',
            'secondary_metric': 'CSV row visits including acquisition, production and full current-input audit',
            'stopping_rule': 'One fixed execution of every arm on all six cases; no seed search, replacement or favorable retry',
            'cost_scope': {'acquisition': 'Recompute and audit predecessor once, fully charged to each reuse arm; no amortization',
                           'adaptation': 'Exact plan/content hash validation each arm', 'verification': 'Full current-input audit each arm',
                           'host_model_engineering_usd': None, 'profit_usd': None},
            'claims_excluded': ['autonomous discovery', 'retained-method superiority', 'commercial profit', 'physical validation'], 'authority': []}


def binding():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCE_PATHS}


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def register(output):
    output.mkdir(parents=True, exist_ok=False)
    value = {'protocol': protocol(), 'source': binding(), 'cases': cases()}
    write(output / 'PREREGISTRATION.json', value)
    return value


def run(output):
    frozen = json.loads((output / 'PREREGISTRATION.json').read_text())
    if frozen != {'protocol': protocol(), 'source': binding(), 'cases': cases()}:
        raise ValueError('FROZEN_SOURCE_OR_PROTOCOL_CHANGED')
    if (output / 'RESULT.json').exists():
        raise ValueError('FIXED_EXECUTION_ALREADY_COMPLETE')
    started, cpu, rows = time.monotonic(), time.process_time(), []
    for case in frozen['cases']:
        for arm in ARMS:
            plan = construct(case['contract'], case['before'])
            acquisition = 0
            previous = None
            if arm != 'full_recompute':
                previous = produce(case['contract'], case['before'], plan)
                checked = audit(case['contract'], case['before'], plan, previous)
                acquisition = previous['producer_row_visits'] + checked['full_row_visits']
            artifact = produce(case['contract'], case['after'], copy.deepcopy(plan), previous,
                               digest(previous) if previous is not None else None)
            checked = audit(case['contract'], case['after'], plan, artifact)
            rows.append({'case': case['id'], 'arm': arm, 'artifact': artifact, 'audit': checked,
                         'acquisition_row_visits': acquisition,
                         'complete_lifecycle_row_visits': acquisition + artifact['producer_row_visits'] + checked['full_row_visits']})
    result = {'schema': SCHEMA, 'preregistration_sha256': digest(frozen), 'rows': rows,
              'accepted': all(r['audit']['accepted'] for r in rows),
              'retained_method_advantage': False, 'actual_profit_usd': None,
              'conclusion': 'Equal-content ordinary reuse and retained method tie exactly. Full recomputation uses fewer lifecycle row visits on these one-successor cases. Selective producer work is not total verification savings.',
              'wall_seconds': time.monotonic() - started, 'process_cpu_seconds': time.process_time() - cpu, 'authority': []}
    write(output / 'RESULT.json', result)
    return result


def verify(output):
    frozen = json.loads((output / 'PREREGISTRATION.json').read_text())
    if frozen != {'protocol': protocol(), 'source': binding(), 'cases': cases()}:
        raise ValueError('FROZEN_SOURCE_OR_PROTOCOL_CHANGED')
    result = json.loads((output / 'RESULT.json').read_text())
    if result.get('preregistration_sha256') != digest(frozen):
        raise ValueError('RESULT_PREREGISTRATION_CHANGED')
    indexed = {(c['id'], arm): c for c in frozen['cases'] for arm in ARMS}
    seen = set()
    for row in result['rows']:
        key = row['case'], row['arm']
        if key not in indexed or key in seen:
            raise ValueError('COVERAGE_OR_DUPLICATE_ROW')
        seen.add(key)
        case = indexed[key]
        plan = construct(case['contract'], case['after'])
        if audit(case['contract'], case['after'], plan, row['artifact']) != row['audit']:
            raise ValueError('RECORDED_AUDIT_CHANGED')
        prior = produce(case['contract'], case['before'], plan) if key[1] != 'full_recompute' else None
        acquisition = 0 if prior is None else prior['producer_row_visits'] + audit(case['contract'], case['before'], plan, prior)['full_row_visits']
        expected = produce(case['contract'], case['after'], plan, prior, digest(prior) if prior is not None else None)
        if row['artifact'] != expected or row['acquisition_row_visits'] != acquisition or row['complete_lifecycle_row_visits'] != acquisition + expected['producer_row_visits'] + row['audit']['full_row_visits']:
            raise ValueError('COST_OR_EXECUTION_CHANGED')
    if seen != set(indexed) or result.get('retained_method_advantage') is not False or result.get('actual_profit_usd') is not None or result.get('accepted') is not True or result.get('authority') != []:
        raise ValueError('RESULT_COVERAGE_OR_CLAIMS')
    return {'accepted': True, 'checked_rows': len(seen), 'result_sha256': digest(result), 'authority': []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('register', 'run', 'verify'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = {'register': register, 'run': run, 'verify': verify}[args.command](args.output.resolve())
    print(json.dumps({'command': args.command, 'accepted': value.get('accepted'), 'output': str(args.output)}, sort_keys=True))


if __name__ == '__main__':
    main()
