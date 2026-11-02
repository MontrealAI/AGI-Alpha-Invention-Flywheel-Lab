from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from adaptive_enterprise.instruments import prepare_services, load_jobs
from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.finance import JournalAccount, audit_journal, source_identity

SOURCE_COMMIT = '88ddcfa3745dd5ae3022b9224d151943c9489b10'
SCHEMA = 'agi-alpha/capability-transfer-cost-envelope/v1'
REGISTRATION = 'agi-alpha/capability-transfer-research-registration/v1'
PUBLIC = 'agi-alpha/capability-transfer-research-public/v1'
ROOT = Path(__file__).resolve().parents[2]
SELF = 'experiments/capability_transfer_20261102/economics.py'
MICRO = 1_000_000
CLAIMS = {'qualified_scientific_capability': False, 'scientific_verdict': 'NOT_EVALUATED_BY_ACCOUNTING',
          'revenue_or_sales': False, 'profitable_business': False, 'earned_funded_expansion': False,
          'conditional_cost_accounting': True, 'externally_secured_capital': False}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    path = Path(path)
    if path.exists() or path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('NEW_REGULAR_OUTPUT_REQUIRED')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(canonical(value) + b'\n')


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('EXACT_NONNEGATIVE_INTEGER_REQUIRED')
    return value


def validate_envelope(env):
    fields = {'schema', 'campaign_id', 'scope', 'clock_start_utc', 'observation_end_hour',
              'capital_levels_microUSD', 'working_reserve_microUSD', 'cost_items', 'unpriced_resources'}
    if not isinstance(env, dict) or set(env) != fields or env['schema'] != SCHEMA or env['scope'] != 'SIMULATED_COST_ONLY':
        raise ValueError('EXACT_COST_ONLY_ENVELOPE_REQUIRED')
    if not isinstance(env['campaign_id'], str) or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,79}', env['campaign_id']):
        raise ValueError('BOUNDED_CAMPAIGN_ID_REQUIRED')
    origin = datetime.fromisoformat(env['clock_start_utc'].replace('Z', '+00:00'))
    if origin.tzinfo is None or origin.utcoffset() != timedelta(0):
        raise ValueError('UTC_SIMULATED_CLOCK_ORIGIN_REQUIRED')
    horizon = integer(env['observation_end_hour'], 1)
    if horizon > 10**8:
        raise ValueError('FINITE_COMPUTABLE_CLOCK_REQUIRED')
    caps = env['capital_levels_microUSD']
    if not isinstance(caps, list) or not caps or len(caps) != len(set(caps)):
        raise ValueError('DISTINCT_REGISTERED_CAPITAL_CASES_REQUIRED')
    for value in caps:
        integer(value, 1)
    if not {100_000 * MICRO, 1_000_000_000 * MICRO} <= set(caps):
        raise ValueError('REQUIRED_100K_AND_1B_COMPARISONS_MISSING')
    working = integer(env['working_reserve_microUSD'])
    if working > min(caps):
        raise ValueError('WORKING_RESERVE_EXCEEDS_REGISTERED_OPENING')
    if not isinstance(env['cost_items'], list) or not env['cost_items']:
        raise ValueError('EXPLICIT_RESEARCH_COST_ITEMS_REQUIRED')
    ids, prior = set(), -1
    for item in env['cost_items']:
        if not isinstance(item, dict) or set(item) != {'id', 'category', 'amount_microUSD', 'at_hour', 'basis'}:
            raise ValueError('EXACT_RESEARCH_COST_ITEM_REQUIRED')
        if not isinstance(item['id'], str) or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,79}', item['id']) or item['id'] in ids:
            raise ValueError('UNIQUE_RESEARCH_COST_ID_REQUIRED')
        ids.add(item['id'])
        integer(item['amount_microUSD'], 1)
        hour = integer(item['at_hour'])
        if hour < prior or hour >= horizon:
            raise ValueError('ORDERED_COSTS_BEFORE_OBSERVATION_END_REQUIRED')
        prior = hour
        for field in ('category', 'basis'):
            if not isinstance(item[field], str) or not item[field].strip() or len(item[field]) > 1000:
                raise ValueError('EXPLICIT_MODELED_COST_BASIS_REQUIRED')
    if not isinstance(env['unpriced_resources'], list) or not env['unpriced_resources'] or any(not isinstance(x, str) or not x.strip() for x in env['unpriced_resources']):
        raise ValueError('UNMEASURED_ENGINEERING_RESOURCES_MUST_REMAIN_EXPLICIT')
    return env


def register(artifact, envelope, target):
    env = validate_envelope(strict_json(Path(envelope).read_bytes()))
    artifact = Path(artifact)
    if not artifact.is_file() or artifact.is_symlink():
        raise ValueError('REGULAR_RESEARCH_ARTIFACT_REQUIRED')
    reg = {'schema': REGISTRATION, 'registered_utc': datetime.now(timezone.utc).isoformat(),
           'source_commit': SOURCE_COMMIT, 'native_source': source_identity(ROOT),
           'economics_sha256': sha(ROOT / SELF), 'artifact_sha256': sha(artifact),
           'envelope_sha256': sha(envelope), 'envelope': env,
           'revenue_authorized': False, 'scientific_acceptance_claim': False,
           'accounting_policy': 'Expense each funded research item when paid. No revenue, debt, capitalization, depreciation or tax-benefit recognition.',
           'financing_policy': 'Each case is a separately seeded upfront-equity hypothesis. No cross-account transfers or follow-on financing.'}
    write_new(target, reg)
    return {'registration_path': str(target), 'registration_sha256': sha(target), 'artifact_sha256': reg['artifact_sha256']}


def validate_registration(reg, artifact, expected_sha256=None, raw=None):
    if expected_sha256 is not None and hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('REGISTERED_BYTES_CHANGED')
    if reg.get('schema') != REGISTRATION or reg.get('revenue_authorized') is not False or reg.get('scientific_acceptance_claim') is not False:
        raise ValueError('RESEARCH_ONLY_REGISTRATION_REQUIRED')
    validate_envelope(reg['envelope'])
    if reg['source_commit'] != SOURCE_COMMIT or reg['native_source'] != source_identity(ROOT) or reg['economics_sha256'] != sha(ROOT / SELF):
        raise ValueError('REGISTERED_EXECUTING_SOURCE_CHANGED')
    if sha(artifact) != reg['artifact_sha256']:
        raise ValueError('REGISTERED_RESEARCH_ARTIFACT_CHANGED')
    return reg


def rolling(record, env):
    end = env['observation_end_hour']
    start = max(0, end - 8760)
    profit = sum(a['after']['profit'] - a['before']['profit'] for a in record['ledger']['actions'] if start <= a['day'] < end)
    origin = datetime.fromisoformat(env['clock_start_utc'].replace('Z', '+00:00'))
    return {'start_hour_inclusive': start, 'end_hour_exclusive': end,
            'start_utc': (origin + timedelta(hours=start)).isoformat(),
            'end_utc': (origin + timedelta(hours=end)).isoformat(),
            'completed_365_day_window': end >= 8760, 'profit_microUSD': profit,
            'scope': 'Registered modeled research expenses only; no complete-business or commercial-profit claim.'}


def run(artifact, registration, registration_sha256, output):
    raw = Path(registration).read_bytes()
    reg = validate_registration(strict_json(raw), artifact, registration_sha256, raw)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise ValueError('NEW_INDEPENDENT_RESEARCH_OUTPUT_REQUIRED')
    output.mkdir(parents=True)
    env = reg['envelope']
    prefix = '_native_cost_fixtures/' + digest(reg)
    manifest_path = ROOT / prefix / 'MANIFEST.json'
    cpu, wall = time.process_time(), time.monotonic()
    manifest = prepare_services(ROOT, prefix, cohort_seed=0)
    manifest['native_engine'] = 'exact-prospective-v2'
    atomic_bytes(manifest_path, canonical(manifest) + b'\n')
    load_jobs(ROOT, manifest)
    cases = []
    for capital in env['capital_levels_microUSD']:
        case_id = 'equity-' + str(capital)
        decisions = []
        with JournalAccount(ROOT, manifest, output / 'private' / case_id / 'account.sqlite',
                            opening=capital, working=env['working_reserve_microUSD'], contract=env['campaign_id'] + '-' + case_id) as account:
            for item in env['cost_items']:
                before = account.snapshot()
                work = {'registration_sha256': registration_sha256, 'artifact_sha256': reg['artifact_sha256'],
                        'economics_sha256': reg['economics_sha256'], 'item': item, 'scope': 'COSTED_RESEARCH_ONLY_NO_SERVICE_SALE'}
                receipt = account.spend(item['id'], 'research', item['amount_microUSD'], item['at_hour'], work, 0, allow_seed=True)
                decisions.append({'item_id': item['id'], 'amount_microUSD': item['amount_microUSD'],
                                  'at_hour': item['at_hour'], 'funded': receipt is not None,
                                  'before_state_digest': before['state_digest'], 'receipt': receipt})
                if receipt is None:
                    if account.snapshot() != before:
                        raise ValueError('REFUSAL_MUTATED_NATIVE_ACCOUNT')
                    break
            account.advance_financial(env['observation_end_hour'])
            record = account.export()
            audit = audit_journal(record, root=ROOT, manifest=manifest)
        incurred = sum(x['amount_microUSD'] for x in decisions if x['funded'])
        summary = record['snapshot']['summary']
        if summary['revenue'] != 0 or summary['profit'] != -incurred or summary['cash'] != capital - incurred:
            raise ValueError('RESEARCH_NATIVE_ACCOUNT_RECONCILIATION_FAILED')
        cases.append({'case_id': case_id, 'opening_equity_microUSD': capital,
                      'decisions': decisions, 'registered_cost_microUSD': sum(x['amount_microUSD'] for x in env['cost_items']),
                      'incurred_cost_microUSD': incurred, 'funding_refused': any(not x['funded'] for x in decisions),
                      'snapshot': summary, 'rolling365': rolling(record, env), 'record': record, 'native_audit': audit})
    fixture_paths = {str(Path(prefix) / 'MANIFEST.json')}
    for job in manifest['jobs']:
        fixture_paths.update(job[field] for field in ('input', 'artifact', 'receipt'))
    public = {'schema': PUBLIC, 'registration': reg, 'registration_sha256': registration_sha256,
              'registration_raw': raw.decode(), 'manifest': manifest,
              'fixtures': {p: (ROOT / p).read_text() for p in sorted(fixture_paths)}, 'cases': cases,
              'execution_resources': {'process_cpu_seconds': time.process_time() - cpu,
                                      'wall_seconds': time.monotonic() - wall,
                                      'scope': 'This accounting-stage process only; excludes scientific construction and included assistant work.',
                                      'actual_model_tokens': None, 'actual_inference_cost_usd': None,
                                      'unpriced_resources': env['unpriced_resources']},
              'claims': dict(CLAIMS),
              'fixture_scope': 'Canonical synthetic acceptance fixtures initialize the native account only; no fixture is sold or counted as scientific output.'}
    write_new(output / 'PUBLIC.json', public)
    verdict = audit_public(artifact, output / 'PUBLIC.json', registration_sha256)
    write_new(output / 'PUBLIC_AUDIT.json', verdict)
    return {'public_path': str(output / 'PUBLIC.json'), 'public_sha256': sha(output / 'PUBLIC.json'),
            'audit_path': str(output / 'PUBLIC_AUDIT.json'), 'cases': [{k: v for k, v in c.items() if k not in {'record', 'native_audit', 'decisions'}} for c in cases]}


def audit_public(artifact, public_path, expected_registration_sha256):
    public = strict_json(Path(public_path).read_bytes())
    if public.get('schema') != PUBLIC:
        raise ValueError('PUBLIC_RESEARCH_SCHEMA_REQUIRED')
    if public.get('claims') != CLAIMS:
        raise ValueError('COST_ACCOUNTING_CANNOT_CERTIFY_SCIENCE_OR_COMMERCE')
    if public.get('registration_sha256') != expected_registration_sha256:
        raise ValueError('INDEPENDENT_REGISTRATION_COMMITMENT_CHANGED')
    raw = public['registration_raw'].encode()
    reg = validate_registration(public['registration'], artifact, public['registration_sha256'], raw)
    if strict_json(raw) != reg:
        raise ValueError('PUBLIC_REGISTRATION_CONTENT_CHANGED')
    prefix = '_native_cost_fixtures/' + digest(reg) + '/'
    manifest = public['manifest']
    expected_paths = {prefix + 'MANIFEST.json'}
    for job in manifest['jobs']:
        expected_paths.update(job[field] for field in ('input', 'artifact', 'receipt'))
    if set(public['fixtures']) != expected_paths:
        raise ValueError('EXACT_PUBLIC_FIXTURE_CLOSURE_REQUIRED')
    for name, text in public['fixtures'].items():
        relative = Path(name)
        if not name.startswith(prefix) or relative.is_absolute() or '..' in relative.parts or relative.suffix != '.json':
            raise ValueError('SAFE_RESEARCH_FIXTURE_NAMESPACE_REQUIRED')
        path = ROOT / relative
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError('REGULAR_PUBLIC_FIXTURE_REQUIRED')
        data = text.encode()
        if path.exists():
            if path.read_bytes() != data:
                raise ValueError('EXISTING_FIXTURE_IDENTITY_CHANGED')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(data)
    if strict_json((ROOT / prefix / 'MANIFEST.json').read_bytes()) != manifest:
        raise ValueError('MANIFEST_BYTES_CHANGED')
    env = reg['envelope']
    resources = public['execution_resources']
    if (resources.get('actual_model_tokens') is not None or resources.get('actual_inference_cost_usd') is not None or
            resources.get('unpriced_resources') != env['unpriced_resources']):
        raise ValueError('UNMEASURED_ENGINEERING_COSTS_CANNOT_BECOME_ZERO')
    if [c['opening_equity_microUSD'] for c in public['cases']] != env['capital_levels_microUSD']:
        raise ValueError('CAPITAL_CASES_CHANGED_OR_POOLED')
    audits = []
    for case in public['cases']:
        if case['case_id'] != 'equity-' + str(case['opening_equity_microUSD']):
            raise ValueError('EXPLICIT_INDEPENDENT_CAPITAL_CASE_ID_REQUIRED')
        record = case['record']
        audit = audit_journal(record, root=ROOT, manifest=manifest)
        decisions, incurred = [], 0
        for item in env['cost_items']:
            funded = case['opening_equity_microUSD'] - incurred - env['working_reserve_microUSD'] >= item['amount_microUSD']
            decisions.append((item['id'], item['amount_microUSD'], item['at_hour'], funded))
            if not funded:
                break
            incurred += item['amount_microUSD']
        if [(d['item_id'], d['amount_microUSD'], d['at_hour'], d['funded']) for d in case['decisions']] != decisions:
            raise ValueError('RESEARCH_FUNDING_DECISION_CHANGED')
        if (case['funding_refused'] != any(not d[3] for d in decisions) or
                case['registered_cost_microUSD'] != sum(i['amount_microUSD'] for i in env['cost_items'])):
            raise ValueError('RESEARCH_COST_OR_REFUSAL_REPORT_CHANGED')
        journal = record['connected_journal']['entries']
        items = [i for i, d in zip(env['cost_items'], decisions) if d[3]]
        if len(journal) != len(items) or any(a['op'] != 'cost' for a in record['ledger']['actions']):
            raise ValueError('UNREGISTERED_REVENUE_OR_FINANCE_ACTION')
        for entry, item in zip(journal, items):
            req = entry['request']
            expected_work = {'registration_sha256': public['registration_sha256'], 'artifact_sha256': reg['artifact_sha256'],
                             'economics_sha256': reg['economics_sha256'], 'item': item, 'scope': 'COSTED_RESEARCH_ONLY_NO_SERVICE_SALE'}
            if req != {'operation': 'spend', 'id': item['id'], 'kind': 'research', 'amount': item['amount_microUSD'],
                       'day': item['at_hour'], 'work': expected_work, 'expected_net': 0, 'allow_seed': True} or entry['funding'] != 'SEED':
                raise ValueError('REGISTERED_RESEARCH_COMMITMENT_CHANGED')
        summary = record['snapshot']['summary']
        if (record['ledger']['config']['opening'] != case['opening_equity_microUSD'] or
                record['ledger']['config']['working'] != env['working_reserve_microUSD'] or
                record['ledger']['config']['contract'] != env['campaign_id'] + '-' + case['case_id'] or
                summary != case['snapshot'] or summary['profit'] != -incurred or summary['revenue'] != 0 or
                summary['cash'] != case['opening_equity_microUSD'] - incurred or case['incurred_cost_microUSD'] != incurred or
                case['rolling365'] != rolling(record, env)):
            raise ValueError('RESEARCH_REPORT_RECONCILIATION_FAILED')
        audits.append({'case_id': case['case_id'], 'accepted': True, 'native_audit': audit,
                       'incurred_cost_microUSD': incurred, 'trailing365_profit_microUSD': case['rolling365']['profit_microUSD']})
    return {'accepted': True, 'scope': 'Independent native replay plus registered cost reconciliation; no scientific, market or complete-business qualification.',
            'public_sha256': sha(public_path), 'cases': audits}


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('register')
    p.add_argument('--artifact', required=True, type=Path)
    p.add_argument('--envelope', required=True, type=Path)
    p.add_argument('--registration', required=True, type=Path)
    p = commands.add_parser('run')
    p.add_argument('--artifact', required=True, type=Path)
    p.add_argument('--registration', required=True, type=Path)
    p.add_argument('--registration-sha256', required=True)
    p.add_argument('--output', required=True, type=Path)
    p = commands.add_parser('audit')
    p.add_argument('--artifact', required=True, type=Path)
    p.add_argument('--public', required=True, type=Path)
    p.add_argument('--registration-sha256', required=True)
    args = parser.parse_args()
    if args.command == 'register':
        result = register(args.artifact, args.envelope, args.registration)
    elif args.command == 'run':
        result = run(args.artifact, args.registration, args.registration_sha256, args.output)
    else:
        result = audit_public(args.artifact, args.public, args.registration_sha256)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
