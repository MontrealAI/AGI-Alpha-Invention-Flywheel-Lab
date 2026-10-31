"""Public single-business operator over the canonical connected engine."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import shutil

from commercial.ledger import canonical, digest, strict_json
from commercial.persistence import atomic_bytes
from .transition_evidence import business_evidence

SCHEMA = 'agi-alpha/connected-single-business-operator/v1'


def _read(path):
    path = Path(path).absolute()
    if not path.is_file() or any(p.is_symlink() for p in [path, *path.parents]) or path.stat().st_size > 64_000_000:
        raise ValueError('REGULAR_BOUNDED_CONNECTED_OPERATOR_FILE_REQUIRED')
    return strict_json(path.read_bytes())


def _write(path, value):
    atomic_bytes(Path(path), canonical(value) + b'\n')


def is_connected(output):
    return (Path(output) / 'OPERATOR.json').is_file()


def _copy_source(root, target):
    from .runner import identity
    root, target = Path(root).absolute(), Path(target).absolute()
    source = identity(root)
    if target.exists():
        if identity(target) != source:
            raise ValueError('EXISTING_CONNECTED_OPERATOR_SOURCE_CHANGED')
        return source
    target.mkdir(parents=True)
    for name in source['files']:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, destination)
    if identity(target) != source:
        raise ValueError('FROZEN_CONNECTED_OPERATOR_SOURCE_CHANGED')
    return source


def _copy_inputs(root, target, manifest):
    def values(value):
        if isinstance(value, dict):
            for item in value.values():
                yield from values(item)
        elif isinstance(value, list):
            for item in value:
                yield from values(item)
        elif isinstance(value, str):
            yield value
    for name in set(values(manifest)):
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or len(name) > 1000:
            continue
        source = Path(root) / relative
        if not source.is_file():
            continue
        if any(p.is_symlink() for p in [source, *source.parents]):
            raise ValueError('OPERATING_SERVICE_INPUT_SYMLINK_REFUSED')
        destination = Path(target) / relative
        if destination.exists() and destination.read_bytes() != source.read_bytes():
            raise ValueError('OPERATING_INPUT_COLLIDES_WITH_TARGET_SOURCE')
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copyfile(source, destination)
    from commercial.ledger import load_jobs
    load_jobs(target, manifest)


def register(root, config, output, *, seed, arm, cohort_seed=None):
    from .engine import validate_config
    from adaptive_enterprise.instruments import prepare_services
    output = Path(output).absolute(); config = validate_config(config)
    if output.exists() or any(p.is_symlink() for p in [output, *output.parents]):
        raise FileExistsError('NEW_CONNECTED_BUSINESS_OUTPUT_REQUIRED')
    if type(seed) is not int or seed < 0 or arm not in {'baseline', 'channel', 'growth', 'competitive_growth'}:
        raise ValueError('REGISTERED_CONNECTED_SEED_AND_ARM_REQUIRED')
    output.mkdir(parents=True)
    source = _copy_source(root, output / 'source')
    manifest = prepare_services(output / 'source', 'service-inputs', cohort_seed=seed if cohort_seed is None else cohort_seed)
    _write(output / 'SERVICES.json', manifest)
    descriptor = {'schema': SCHEMA, 'source_dir': 'source', 'source': source, 'business_dir': 'business',
                  'config': config, 'seed': seed, 'arm': arm, 'manifest_sha256': digest(manifest),
                  'upgrade_request': None, 'scope': 'CONDITIONAL_SYNTHETIC_CONNECTED_BUSINESS'}
    descriptor['sha256'] = digest(descriptor)
    _write(output / 'OPERATOR.json', descriptor)
    return descriptor


def read_operator(output):
    from .runner import identity
    from .engine import validate_config
    output = Path(output).absolute(); d = _read(output / 'OPERATOR.json')
    fields = {'schema', 'source_dir', 'source', 'business_dir', 'config', 'seed', 'arm', 'manifest_sha256', 'upgrade_request', 'scope', 'sha256'}
    if (set(d) != fields or d['schema'] != SCHEMA or digest({k: v for k, v in d.items() if k != 'sha256'}) != d['sha256']
            or not (d['source_dir'] in {'source', 'source-022'} or isinstance(d['source_dir'], str) and d['source_dir'].startswith('source-') and len(d['source_dir']) == 71 and all(c in '0123456789abcdef' for c in d['source_dir'][7:])) or d['business_dir'] not in {'business', '.'}
            or validate_config(d['config']) != d['config'] or identity(output / d['source_dir']) != d['source']):
        raise ValueError('REGISTERED_CONNECTED_OPERATOR_OR_SOURCE_CHANGED')
    manifest = _read(output / 'SERVICES.json')
    if digest(manifest) != d['manifest_sha256']:
        raise ValueError('CONNECTED_OPERATOR_SERVICE_MANIFEST_CHANGED')
    return d, manifest


def prepare_upgrade(root, historical_root, manifest_path, output, *, policy, expected_checkpoint_sha256, ident):
    from .migration import validate_policy
    output = Path(output).absolute(); historical_root = Path(historical_root).absolute()
    manifest = _read(manifest_path); checkpoint = _read(output / 'STATE.json')
    policy = validate_policy(policy)
    request = {'historical_root': str(historical_root), 'policy': policy,
               'expected_checkpoint_sha256': expected_checkpoint_sha256, 'id': ident}
    previous = None
    if (output / 'OPERATOR.json').exists():
        d, existing = read_operator(output)
        if existing != manifest or d['business_dir'] != '.':
            raise ValueError('OPERATING_UPGRADE_OPERATOR_RETRY_CHANGED')
        if d['upgrade_request'] == request:
            from .runner import identity
            if d['source'] != identity(root):
                raise ValueError('OPERATING_UPGRADE_RETRY_TARGET_CHANGED')
            return d
        previous = d
    if digest(checkpoint) != expected_checkpoint_sha256:
        raise ValueError('STALE_OPERATING_UPGRADE_CHECKPOINT')
    # Authenticate and measure the new representation before descriptor/source
    # mutation. The owner subprocess keeps the existing key private.
    from .upgrades import authorize_upgrade, validate_ticket
    from .runner import identity
    state=checkpoint['body']['state'];cfg=state['config']
    origin=state.get('origin_source',state['source'])
    contract='connected014/'+digest({'config':cfg,'seed':state['seed'],'arm':state['arm'],'source':origin,'manifest':manifest})
    day=max(state['last_time'],state['current']['event']['time'] if state['current'] else state['last_time'])
    operating={'schema':'agi-alpha/connected-operating-transition/v1','prior_checkpoint':checkpoint,
               'from_runtime':state['source'],'to_runtime':identity(root),'policy':policy}
    prepared=authorize_upgrade(historical_root=historical_root,target_root=root,manifest=manifest,
        path=output/'account.sqlite',opening=cfg['opening'],working=cfg['working'],contract=contract,
        expected_state_digest=None,ident=ident,day=day,operating=operating,evidence_dir=output/'transition-evidence')
    with business_evidence(output):validate_ticket(prepared,root=root,path=output/'account.sqlite')
    state = checkpoint['body']['state']
    from .runner import identity
    source_dir = 'source-022' if previous is None else 'source-' + identity(root)['sha256']
    source = _copy_source(root, output / source_dir)
    _copy_inputs(historical_root, output / source_dir, manifest)
    _write(output / 'SERVICES.json', manifest)
    descriptor = {'schema': SCHEMA, 'source_dir': source_dir, 'source': source, 'business_dir': '.',
                  'config': state['config'], 'seed': state['seed'], 'arm': state['arm'],
                  'manifest_sha256': digest(manifest), 'upgrade_request': request,
                  'scope': 'CONDITIONAL_SYNTHETIC_CONNECTED_BUSINESS'}
    descriptor['sha256'] = digest(descriptor)
    if previous is not None:
        from .migration import _preserve
        _preserve(output / 'OPERATOR_HISTORY' / (previous['sha256'] + '.json'), previous)
    _write(output / 'OPERATOR.json', descriptor)
    return descriptor


def upgrade(output, *, failpoint=None):
    from .migration import upgrade_world
    d, manifest = read_operator(output); output = Path(output).absolute(); request = d['upgrade_request']
    if request is None:
        raise ValueError('EXPLICIT_CONNECTED_OPERATING_UPGRADE_REQUIRED')
    return upgrade_world(output / d['source_dir'], request['historical_root'], manifest, output / d['business_dir'],
                         policy=request['policy'], expected_checkpoint_sha256=request['expected_checkpoint_sha256'],
                         ident=request['id'], failpoint=failpoint)


def operate(output, *, max_events=None):
    from .engine import run_world
    d, manifest = read_operator(output); output = Path(output).absolute()
    business = output / d['business_dir']
    if d['upgrade_request'] is not None and not (business / 'MIGRATION_INTENT.json').exists():
        raise ValueError('EXPLICIT_OPERATING_UPGRADE_NOT_COMMITTED')
    return run_world(output / d['source_dir'], manifest, d['config'], d['seed'], d['arm'], business,
                     source=d['source'], stop_after_events=max_events)


def audit(output):
    from .verify import audit as independent_audit
    d, manifest = read_operator(output); output = Path(output).absolute()
    result = _read(output / d['business_dir'] / 'RESULT.json')
    if any(result[k] != d[k] for k in ['config', 'seed', 'arm', 'source']):
        raise ValueError('CONNECTED_OPERATOR_RESULT_AUTHORITY_CHANGED')
    with business_evidence(output/d['business_dir']):
        checked = independent_audit(output / d['source_dir'], manifest, result)
    _write(output / 'OPERATOR_AUDIT.json', checked)
    return checked


def scoreboard(output):
    checked = audit(output); d, manifest = read_operator(output)
    result = _read(Path(output) / d['business_dir'] / 'RESULT.json')
    tape = result['owned_account']['ledger']; actions = tape['actions']; lineage = []
    for order in result['orders']:
        funding = order['funding_receipt']
        if funding['funding'] != 'EARNED':
            continue
        reserve = next(e for e in actions if e['op'] == 'reserve' and e['args']['id'] == funding['plan_id'])
        releases = [e for e in actions if e['op'] == 'mature' and e['seq'] < reserve['seq']]
        settled = order['outcome'] == 'SETTLED'; margin = order['price'] - order['complete_cost']
        lineage.append({'order_id': order['id'], 'reservation_sequence': reserve['seq'],
                        'audited_available_before': reserve['before']['available'],
                        'audited_unrestricted_earned_before': reserve['before']['unrestrictedEarned'],
                        'reserved_microUSD': reserve['args']['amount'], 'prior_matured_order_ids': [e['args']['id'] for e in releases],
                        'settled': settled, 'direct_complete_cost_margin_microUSD': margin,
                        'scope': 'Fungible audited earned cash; shared setup, maintenance, acquisition and taxes remain in enterprise profit.'})
    score = {'schema': 'agi-alpha/connected-operating-scoreboard/v1', 'accepted_audit': checked['accepted'],
             'source_sha256': result['source']['sha256'], 'complete': result['complete'],
             'summary': result['summary'], 'paid_jobs': result['paid_jobs'], 'accepted_jobs': result['accepted_jobs'],
             'profitable_earned_continuations': result['profitable_earned_continuations'],
             'profitable_settlements_funded_after_maturity': sum(bool(r['prior_matured_order_ids']) and r['settled'] and r['direct_complete_cost_margin_microUSD'] > 0 for r in lineage),
             'maturities': sum(e['op'] == 'mature' for e in actions), 'funding_lineage': lineage,
             'operating_source_transitions': len(result.get('operating_upgrades', [])),
             'scope': 'BOUNDED_AUTHORED_SYNTHETIC_COMMERCE_NOT_ANNUAL_OR_EXTERNAL_PROFIT',
             'actual_host_billing': None, 'actual_frontier_model_billing': None, 'actual_profit': None}
    _write(Path(output) / 'SCOREBOARD.json', score)
    return score
