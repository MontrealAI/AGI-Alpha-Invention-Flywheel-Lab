import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import zipfile

PART_DIRECTORIES = ('enterprise011-parts', 'adaptive012-parts', 'connected014-confirmation002-parts',
                    'connected014-expansion-parts', 'connected014-incomplete001-parts',
                    'connected014-development-parts', 'completion015-parts')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _contract_shape_issues(account, jobs):
    issues = []
    valid_id = lambda value: isinstance(value, str) and bool(value.strip()) and len(value) <= 160
    for ident, proof in account.get('action_proofs', {}).items():
        seen = set()
        for option in proof['body']['plan'].get('selected_options', []):
            if (not isinstance(option, dict) or not {'id', 'kind', 'execution'} <= set(option)
                    or not valid_id(option.get('id')) or not valid_id(option.get('kind'))
                    or not isinstance(option.get('execution'), dict)):
                issues.append({'plan_id': ident, 'reason': 'selected_shape'})
                continue
            if option['id'] in seen:
                issues.append({'plan_id': ident, 'reason': 'duplicate_id'})
            seen.add(option['id'])
            if option['kind'] == 'delivery':
                execution = option['execution']
                fields = {'job_id', 'customer_id', 'payment_bps', 'payment_fixed_microUSD', 'onboarding_microUSD'}
                if not fields <= set(execution):
                    issues.append({'plan_id': ident, 'reason': 'delivery_fields'})
                    continue
                if (not valid_id(execution['job_id']) or not valid_id(execution['customer_id'])
                        or type(execution['payment_bps']) is not int or not 0 <= execution['payment_bps'] <= 10_000
                        or any(type(execution[key]) is not int or not 0 <= execution[key] <= 10**12
                               for key in ('payment_fixed_microUSD', 'onboarding_microUSD'))):
                    issues.append({'plan_id': ident, 'reason': 'delivery_types'})
                if execution['job_id'] not in jobs:
                    issues.append({'plan_id': ident, 'reason': 'unknown_job'})
    return issues


def inspect(result, name, jobs=None):
    account = result.get('owned_account')
    row = {'world': name, 'affected_account_schema': bool(account), 'affected_account_reservations': 0,
           'explicit_upfront_zero_later': 0, 'omitted_upfront_finishes': [],
           'upfront_aggregate_mismatches': [], 'proofs_without_native_reservation': []}
    if not account:
        return row
    actions, proofs = account['ledger']['actions'], account.get('action_proofs', {})
    finishes = {event['args']['id']: event for event in actions if event['op'] == 'finish'}
    resolutions = account.get('obligation_resolutions', {})
    shapes = {'newly_required_zero_later_contracts': 0, 'zero_cost_selected_contracts': 0,
              'unsupported_top_only_positive_contracts': 0, 'all_required_finish_missing_receipts': [],
              'newly_required_finish_missing_receipts': []}
    native = {event['args']['id'] for event in actions if event['op'] == 'reserve'}
    row['affected_account_reservations'] = len(native)
    row['proofs_without_native_reservation'] = [ident for ident in proofs if ident not in native]
    for ident, proof in proofs.items():
        plan = proof['body']['plan']
        options = plan.get('selected_options', [])
        upfront = sum(option['upfront_cost'] for option in options) if options else plan.get('upfront_cost', 0)
        later = max(plan.get('worst_later_reserve', 0), sum(max(option['later_liabilities'].values()) for option in options))
        required = bool(options) or plan.get('upfront_cost', 0) > 0 or later > 0
        if required and later == 0:
            shapes['newly_required_zero_later_contracts'] += 1
        if options and plan.get('upfront_cost', 0) == 0 and upfront == 0 and later == 0:
            shapes['zero_cost_selected_contracts'] += 1
        if not options and (plan.get('upfront_cost', 0) > 0 or later > 0):
            shapes['unsupported_top_only_positive_contracts'] += 1
        if required and ident in finishes and not isinstance(resolutions.get(ident), dict):
            shapes['all_required_finish_missing_receipts'].append(ident)
            if later == 0:
                shapes['newly_required_finish_missing_receipts'].append(ident)
        if options and 'upfront_cost' in plan and plan['upfront_cost'] != upfront:
            row['upfront_aggregate_mismatches'].append(ident)
        if options and upfront > 0 and later == 0:
            row['explicit_upfront_zero_later'] += 1
            row['omitted_upfront_finishes'].extend({'plan_id': ident, 'expected_upfront_microUSD': upfront,
                'actual_microUSD': event['args']['amount']} for event in actions
                if event['op'] == 'finish' and event['args']['id'] == ident and event['args']['amount'] < upfront)
    row['complete_predicate_shapes'] = shapes
    if jobs is not None:
        row['contract_shape_issues'] = _contract_shape_issues(account, jobs)
    return row


def summarize(rows):
    return {'worlds_inspected': len(rows), 'account_worlds': sum(row['affected_account_schema'] for row in rows),
            'affected_account_reservations': sum(row['affected_account_reservations'] for row in rows),
            **{key: sum(row[key] if isinstance(row[key], int) else len(row[key]) for row in rows)
               for key in ('explicit_upfront_zero_later', 'omitted_upfront_finishes', 'upfront_aggregate_mismatches')},
            'orphan_proofs': sum(len(row['proofs_without_native_reservation']) for row in rows),
            'malformed_contract_count': sum(len(row.get('contract_shape_issues', [])) for row in rows),
            'complete_predicate_summary': {key: sum(value if isinstance(value, int) else len(value)
                for row in rows for value in [row.get('complete_predicate_shapes', {}).get(key, 0)])
                for key in ('newly_required_zero_later_contracts', 'zero_cost_selected_contracts',
                            'unsupported_top_only_positive_contracts', 'all_required_finish_missing_receipts',
                            'newly_required_finish_missing_receipts')}, 'worlds': rows}


def scan(root, fresh):
    archives = []
    for directory in PART_DIRECTORIES:
        folder = root / 'artifacts' / directory
        index = json.loads((folder / 'INDEX.json').read_bytes())
        chunks = []
        for part in index['parts']:
            raw = (folder / part['path']).read_bytes()
            if sha(raw) != part['sha256'] or len(raw) != part['bytes']:
                raise ValueError('PART_IDENTITY:' + directory + ':' + part['path'])
            chunks.append(raw)
        data = b''.join(chunks)
        if sha(data) != index['archive_sha256']:
            raise ValueError('ARCHIVE_IDENTITY:' + directory)
        rows = []
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            manifests = {}
            for name in archive.namelist():
                if name.endswith('SERVICES.json'):
                    raw = archive.read(name)
                    manifest = json.loads(raw)
                    authority = sha(json.dumps(manifest, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())
                    manifests[authority] = {'path': name, 'file_sha256': sha(raw),
                                            'jobs': {job['id'] for job in manifest['jobs'] if job.get('accepted') is True}}
            bindings = {}
            for name in archive.namelist():
                eligible = (name.startswith('worlds/') or '/worlds/' in name) and (
                    name.endswith('/RESULT.json') or name.endswith('.json.gz') or
                    (name.startswith('worlds/') and name.count('/') == 1 and name.endswith('.json')))
                if not eligible:
                    continue
                raw = archive.read(name)
                result = json.loads(gzip.decompress(raw) if name.endswith('.gz') else raw)
                if isinstance(result, dict) and ('owned_account' in result or 'ledger' in result):
                    account = result.get('owned_account')
                    if account:
                        authority = account['ledger']['config']['manifest_sha256']
                        manifest = manifests[authority]
                        row = inspect(result, name, manifest['jobs'])
                        row['contract_shape_manifest_sha256'] = authority
                        bindings[authority] = {'path': manifest['path'], 'file_sha256': manifest['file_sha256'],
                                               'admitted_job_ids': len(manifest['jobs'])}
                    else:
                        row = inspect(result, name)
                    rows.append(row)
        archives.append({'archive': directory, 'archive_sha256': sha(data),
                         'parts_verified': len(chunks), 'contract_shape_manifest_bindings': bindings, **summarize(rows)})
    if fresh is not None:
        manifest = json.loads((fresh / 'SERVICES.json').read_bytes())
        jobs = {job['id'] for job in manifest['jobs'] if job.get('accepted') is True}
        rows = [inspect(json.loads(path.read_bytes()), str(path.relative_to(fresh)), jobs)
                for path in sorted((fresh / 'worlds').glob('*/RESULT.json'))]
        archives.append({'scope': 'Original local completed businesses; original resource failure preserved', **summarize(rows)})
    return {'schema': 'agi-alpha/completion015-p1-p2-historical-impact/v1',
            'scope': 'Read-only authentic archive inspection. Counts apply only to the affected owned_account schema. '
                     'Generic enterprise011 ledgers predate this facade. Repeated worlds are not pooled businesses. '
                     'No business reexecution or original-account mutation; incomplete/development outcomes retain their scope.',
            'archives': archives}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--fresh-original', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = scan(args.root, args.fresh_original)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
