"""Source-bound native delivery of verified local numerical workload programs.

Prices, independently specified buyer budgets and commercial costs are explicit
simulation assumptions. This module constructs real numerical result artifacts;
it calls no model API and makes no real sale. ``units`` denotes a homogeneous
cohort buying identical accepted packages. Per-buyer prices, budgets, costs and
contingent exposure are multiplied exactly; cohorts still need cash-feasible scheduling.
"""
from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from commercial.ledger import amount, canonical, digest, read_bound, strict_json
from commercial.terms_exact_v2 import prospective_terms

SCHEMA = 'omega-savings/native-services/v1'
SCOPE = 'HYPOTHETICAL_SIMULATION_ACTUAL_NUMERICAL_DELIVERY'
SOURCE_PATHS = ('omega_savings/__init__.py', 'omega_savings/kernel.py',
                'omega_savings/verify.py', 'omega_savings/interval.py', 'omega_savings/interval.c',
                'omega_savings/world.py', 'omega_savings/service.py')
NATIVE_FEE = 200_000  # Contingent reversal exposure, not an ordinary release expense.
CONTRACT_FIELDS = {'id', 'request', 'price_microUSD', 'budget_microUSD', 'costs_microUSD'}
OPTIONAL_FIELDS = {'units', 'method', 'claim_window_hours', 'residual_bps',
                   'collection_delay_hours', 'deadline_hours', 'minimum_saved_bps'}


def _ident(value):
    if not isinstance(value, str) or not value or len(value) > 80 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.' for c in value):
        raise ValueError('BOUNDED_SAFE_SAVINGS_IDENTIFIER_REQUIRED')
    return value


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError('EXPLICIT_NONNEGATIVE_INTEGER_REQUIRED:' + name)
    return value


def _relative(value):
    if not isinstance(value, str):
        raise ValueError('RELATIVE_SAVINGS_PATH_REQUIRED')
    path = Path(value)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('RELATIVE_SAVINGS_PATH_REQUIRED')
    return path


def _path(root, relative):
    result = Path(root).absolute() / _relative(relative)
    if result.is_symlink() or any(p.is_symlink() for p in result.parents):
        raise ValueError('SAVINGS_SYMLINK_REFUSED')
    return result


def _write(path, value):
    raw = canonical(value) + b'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('IMMUTABLE_SAVINGS_ARTIFACT_CHANGED')
    else:
        with path.open('xb') as stream:
            stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def validate_contract(contract):
    if (not isinstance(contract, dict) or not CONTRACT_FIELDS <= set(contract)
            or set(contract) - CONTRACT_FIELDS - OPTIONAL_FIELDS):
        raise ValueError('EXACT_SAVINGS_CONTRACT_REQUIRED')
    clean = copy.deepcopy(contract)
    _ident(clean['id'])
    amount(clean['price_microUSD'], positive=True)
    amount(clean['budget_microUSD'])
    if clean['price_microUSD'] < NATIVE_FEE:
        raise ValueError('SAVINGS_PRICE_BELOW_NATIVE_FEE')
    if not isinstance(clean['request'], dict):
        raise ValueError('EXPLICIT_NUMERICAL_REQUEST_REQUIRED')
    if not isinstance(clean['costs_microUSD'], dict) or not clean['costs_microUSD']:
        raise ValueError('EXPLICIT_COMPLETE_SAVINGS_COSTS_REQUIRED')
    for name, value in clean['costs_microUSD'].items():
        _ident(name)
        amount(value)
    clean.setdefault('units', 1)
    clean.setdefault('method', 'adaptive')
    clean.setdefault('claim_window_hours', 720)
    clean.setdefault('residual_bps', 100)
    clean.setdefault('collection_delay_hours', 0)
    clean.setdefault('minimum_saved_bps', 0)
    clean.setdefault('deadline_hours', max(24, clean['collection_delay_hours'] + 1))
    _integer(clean['units'], 'units', 1)
    _ident(clean['method'])
    for name in ('claim_window_hours', 'deadline_hours'):
        _integer(clean[name], name, 1)
    for name in ('residual_bps', 'collection_delay_hours', 'minimum_saved_bps'):
        _integer(clean[name], name)
    if (clean['residual_bps'] > 10000 or clean['minimum_saved_bps'] > 10000 or clean['collection_delay_hours'] > clean['deadline_hours']
            or clean['deadline_hours'] >= clean['collection_delay_hours'] + clean['claim_window_hours']):
        raise ValueError('SAVINGS_COLLECTION_DEADLINE_OR_RESIDUAL_INVALID')
    canonical(clean)  # Reject nonfinite JSON, including request values.
    return clean


def totals(contract):
    c = validate_contract(contract)
    units = c['units']
    return {'units': units, 'price_microUSD': units * c['price_microUSD'],
            'buyer_budget_microUSD': units * c['budget_microUSD'],
            'service_cost_microUSD': units * sum(c['costs_microUSD'].values()),
            'exposure_microUSD': units * (c['price_microUSD'] + NATIVE_FEE),
            # Per-constituent rounding is required for exact aggregate parity.
            'residual_microUSD': units * (c['price_microUSD'] * c['residual_bps'] // 10000)}


def prepare_manifest(root, relative_dir, contracts=None, *, rule=None):
    root = Path(root).absolute()
    relative = _relative(str(relative_dir))
    target = _path(root, str(relative))
    if target.exists():
        raise FileExistsError('FRESH_SAVINGS_MANIFEST_DIRECTORY_REQUIRED')
    if (contracts is None) == (rule is None):
        raise ValueError('EXACTLY_ONE_CATALOG_OR_PROCEDURAL_RULE_REQUIRED')
    if rule is not None and not isinstance(rule, dict):
        raise ValueError('EXPLICIT_PROCEDURAL_RULE_REQUIRED')
    if contracts is not None and (not isinstance(contracts, list) or not contracts):
        raise ValueError('DECLARED_SAVINGS_CONTRACT_CATALOG_REQUIRED')
    clean = [validate_contract(c) for c in contracts] if contracts is not None else []
    if len({c['id'] for c in clean}) != len(clean):
        raise ValueError('UNIQUE_SAVINGS_CONTRACT_IDS_REQUIRED')
    source_hashes = {p: hashlib.sha256(_path(root, p).read_bytes()).hexdigest() for p in SOURCE_PATHS}
    manifest = {'schema': SCHEMA, 'scope': SCOPE, 'account_namespace': 'adaptive012',
                'native_engine': 'exact-prospective-v2', 'source_hashes': source_hashes,
                'cost_basis': 'EXPLICIT_MODELED_PER_BUYER_CASH_COSTS_NOT_MEASURED_MARKET_COSTS',
                'cohort_semantics': 'Identical request, price, budget, costs, delivery and terms per constituent; exact integer multiplication; no demand forecast',
                'jobs': []}
    if rule is not None:
        manifest.pop('jobs')
        manifest.update(rule=copy.deepcopy(rule), output_dir=str(relative))
        canonical(manifest)
    target.mkdir(parents=True)
    for contract in clean:
        relative_input = str(relative / (contract['id'] + '.contract.json'))
        input_hash = _write(_path(root, relative_input), contract)
        job = {'id': contract['id'], 'input': relative_input, 'input_sha256': input_hash,
               'output': str(relative / (contract['id'] + '.delivery.json')),
               'artifact_sha256': digest({'contract_sha256': input_hash, 'schema': SCHEMA}),
               'receipt_sha256': digest({'contract_sha256': input_hash,
                                         'source_sha256': digest(source_hashes)})}
        manifest['jobs'].append(job)
    _write(target / 'MANIFEST.json', manifest)
    load_contracts(root, manifest)
    return manifest


def load_contracts(root, manifest):
    expected = {'schema', 'scope', 'account_namespace', 'native_engine', 'source_hashes',
                'cost_basis', 'cohort_semantics', 'jobs'}
    procedural = isinstance(manifest, dict) and 'rule' in manifest
    if procedural:
        expected = (expected - {'jobs'}) | {'rule', 'output_dir'}
    if (not isinstance(manifest, dict) or set(manifest) != expected
            or manifest.get('schema') != SCHEMA or manifest.get('scope') != SCOPE
            or manifest.get('account_namespace') != 'adaptive012'
            or manifest.get('native_engine') != 'exact-prospective-v2'):
        raise ValueError('EXACT_SAVINGS_MANIFEST_REQUIRED')
    if set(manifest['source_hashes']) != set(SOURCE_PATHS):
        raise ValueError('COMPLETE_SAVINGS_SOURCE_CLOSURE_REQUIRED')
    executing_root = Path(__file__).resolve().parents[1]
    for relative, expected_hash in manifest['source_hashes'].items():
        if (hashlib.sha256(_path(root, relative).read_bytes()).hexdigest() != expected_hash
                or hashlib.sha256(_path(executing_root, relative).read_bytes()).hexdigest() != expected_hash):
            raise ValueError('SAVINGS_EXECUTING_OR_FROZEN_SOURCE_CHANGED')
    if procedural:
        if not isinstance(manifest['rule'], dict):
            raise ValueError('EXPLICIT_PROCEDURAL_RULE_REQUIRED')
        _path(root, manifest['output_dir'])
        return ProceduralContracts(root, manifest)
    if not isinstance(manifest['jobs'], list) or not manifest['jobs']:
        raise ValueError('SAVINGS_JOB_CATALOG_REQUIRED')
    result = {}
    for job in manifest['jobs']:
        if (not isinstance(job, dict) or set(job) != {'id', 'input', 'input_sha256', 'output', 'artifact_sha256', 'receipt_sha256'}
                or job['id'] in result):
            raise ValueError('EXACT_UNIQUE_SAVINGS_JOB_REQUIRED')
        contract = validate_contract(read_bound(root, job['input'], job['input_sha256']))
        _path(root, job['output'])
        if (contract['id'] != job['id']
                or job['artifact_sha256'] != digest({'contract_sha256': job['input_sha256'], 'schema': SCHEMA})
                or job['receipt_sha256'] != digest({'contract_sha256': job['input_sha256'], 'source_sha256': digest(manifest['source_hashes'])})):
            raise ValueError('SAVINGS_REQUEST_OR_CHECKER_BINDING_CHANGED')
        result[job['id']] = {'job': copy.deepcopy(job),
                             'artifact': {'unproduced_contract': job['input_sha256']},
                             'receipt': {'accepted': False}}
    return result


@lru_cache(maxsize=128)
def _generated_contract(source_identity, rule_json, job_id):
    # Bounded memoization is an execution optimization, not a demand limit.
    from omega_savings.world import contract_for as generate_contract
    return validate_contract(generate_contract(strict_json(rule_json), job_id))


class ProceduralContracts:
    """Source-bound lazy lookup, with no finite customer catalogue or mutation.

    Equality compares the complete generator contract, not the currently visited
    keys. The native account only needs keyed lookup, membership and equality.
    Enumerating an unbounded procedural domain is deliberately unsupported.
    """
    def __init__(self, root, manifest):
        self.root = Path(root).absolute()
        self.manifest = copy.deepcopy(manifest)
        self.identity = digest(manifest)

    def _contract(self, job_id):
        _ident(job_id)
        contract = copy.deepcopy(_generated_contract(digest(self.manifest['source_hashes']), canonical(self.manifest['rule']), job_id))
        if contract['id'] != job_id:
            raise ValueError('PROCEDURAL_SAVINGS_JOB_ID_CHANGED')
        return contract

    def __getitem__(self, job_id):
        contract = self._contract(job_id)
        contract_hash = hashlib.sha256(canonical(contract) + b'\n').hexdigest()
        job = {'id': job_id,
               'input': str(Path(self.manifest['output_dir']) / (job_id + '.contract.json')),
               'input_sha256': contract_hash,
               'output': str(Path(self.manifest['output_dir']) / (job_id + '.delivery.json')),
               'artifact_sha256': digest({'contract_sha256': contract_hash, 'schema': SCHEMA}),
               'receipt_sha256': digest({'contract_sha256': contract_hash,
                                         'source_sha256': digest(self.manifest['source_hashes'])})}
        return {'job': job, 'artifact': {'unproduced_contract': contract_hash},
                'receipt': {'accepted': False}}

    def __contains__(self, job_id):
        try:
            self._contract(job_id)
            return True
        except (ValueError, KeyError, TypeError):
            return False

    def get(self, job_id, default=None):
        return self[job_id] if job_id in self else default

    def __eq__(self, other):
        return isinstance(other, ProceduralContracts) and self.root == other.root and self.identity == other.identity

    def __ne__(self, other):
        return not self == other


def contract_for(root, manifest, job_id):
    jobs = load_contracts(root, manifest)
    job = jobs[job_id]['job']
    contract = jobs._contract(job_id) if isinstance(jobs, ProceduralContracts) else validate_contract(read_bound(root, job['input'], job['input_sha256']))
    if isinstance(jobs, ProceduralContracts) and _path(root, job['input']).exists():
        # Purchased generated inputs are public evidence too; materialization
        # cannot drift while a cached generator continues to return old content.
        raw = _path(root, job['input']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != job['input_sha256']:
            raise ValueError('PROCEDURAL_SAVINGS_INPUT_CHANGED')
    return job, contract


def produce(root, manifest, job_id, result=None):
    """Persist actual workload output, preserving exact existing recovery bytes."""
    job, contract = contract_for(root, manifest, job_id)
    path = _path(root, job['output'])
    if path.exists() and result is None:
        return delivery(root, manifest, job_id)
    if result is None:
        from omega_savings.kernel import solve
        result = solve(contract['request'], method=contract['method'])
    # Materialize only purchased input contracts, for compact independent replay.
    _write(_path(root, job['input']), contract)
    artifact = {'schema': 'omega-savings/delivery/v1', 'scope': SCOPE,
                'contract_sha256': job['input_sha256'],
                'source_sha256': digest(manifest['source_hashes']),
                'method': contract['method'], 'units': contract['units'],
                'result': copy.deepcopy(result)}
    _write(path, artifact)
    return artifact


def delivery(root, manifest, job_id):
    job, _ = contract_for(root, manifest, job_id)
    return strict_json(_path(root, job['output']).read_bytes())


@lru_cache(maxsize=128)
def _accepted_semantics(source_identity, request_bytes, result_bytes, method, minimum_saved_bps):
    """Cache only independently checked semantics after fresh byte rebinding.

    Both producer and checker source identities are part of the key. The cache
    limit bounds execution memory, not the number of buyers or jobs allowed.
    Result data never become authority merely because a request was seen before.
    """
    from omega_savings.kernel import construct
    from omega_savings.verify import verify
    request, result = strict_json(request_bytes), strict_json(result_bytes)
    try:
        expected = construct(request, policy=method)
        plan = result['plan']
        # Count and recipe claims are separate from mathematical acceptance.
        # A correct answer with a fabricated cheap recipe cannot be sold as the
        # declared program. Timing fields remain measured, not deterministic.
        keys = set(expected) - {'constructor_wall_seconds'}
        if (not isinstance(plan, dict) or set(plan) != set(expected)
                or any(canonical(plan.get(k)) != canonical(expected[k]) for k in keys)
                or canonical(result.get('count_model')) != canonical(expected['count_model'])
                or result.get('program_sha256') != expected['program_sha256']
                or result.get('request_sha256') != expected['request_sha256']):
            return False
        counts = expected['count_model']
        baseline = counts['direct_complete_proxy_units']
        saved = baseline - counts['candidate_complete_proxy_units']
        if saved * 10000 < minimum_saved_bps * baseline:
            return False
        return verify(request, result).get('accepted') is True
    except (ValueError, TypeError, KeyError, IndexError, OverflowError):
        return False


def check_delivery(root, manifest, job_id, artifact):
    """Rebind all bytes and source, then independently check math and recipe."""
    job, contract = contract_for(root, manifest, job_id)
    metadata_ok = (isinstance(artifact, dict)
        and set(artifact) == {'schema', 'scope', 'contract_sha256', 'source_sha256', 'method', 'units', 'result'}
        and artifact.get('schema') == 'omega-savings/delivery/v1'
        and artifact.get('scope') == SCOPE
        and artifact.get('contract_sha256') == job['input_sha256']
        and artifact.get('source_sha256') == digest(manifest['source_hashes'])
        and artifact.get('method') == contract['method']
        and artifact.get('units') == contract['units']
        and canonical(artifact) == canonical(delivery(root, manifest, job_id)))
    accepted = metadata_ok and _accepted_semantics(digest(manifest['source_hashes']),
        canonical(contract['request']), canonical(artifact['result']), contract['method'],
        contract['minimum_saved_bps'])
    return {'accepted': bool(accepted), 'decisive': True, 'scope': 'SIMULATED',
            'authority': job['receipt_sha256']}


def cost_rows(job, order_id, contract):
    """Each cost is paid once per native order; no implicit payroll or API call."""
    c = validate_contract(contract)
    # One atomic, fully prepaid invoice preserves exact itemized economics while
    # avoiding ten redundant journal mutations for one complete delivery.
    # The immutable contract remains the authoritative category breakdown.
    return [('savings:' + order_id + ':complete_delivery',
             c['units'] * sum(c['costs_microUSD'].values()))]


def terms_for(manifest, order_id, contract, hour):
    c = validate_contract(contract)
    t = totals(c)
    _integer(hour, 'hour')
    return prospective_terms(order_id, t['price_microUSD'], hour + c['collection_delay_hours'] + c['claim_window_hours'],
        hour + c['collection_delay_hours'], exposure=t['exposure_microUSD'], residual=t['residual_microUSD'],
        counterparty_obligations='Modeled buyers pay only for independently accepted numerical output; all declared delivery costs prepaid; residual claims remain seller obligations; no enforceability asserted')


def require_costs(root, manifest, actions, order):
    job_id = json.loads(order['task'])['job_id']
    job, contract = contract_for(root, manifest, job_id)
    t = totals(contract)
    paid = {a['args']['id']: a['args']['amount'] for a in actions if a['op'] == 'cost'
            and a['after']['expensePaid'] - a['before']['expensePaid'] == a['args']['amount']}
    if int(order['price']) != t['price_microUSD']:
        raise ValueError('SAVINGS_CONTRACT_PRICE_CHANGED')
    if any(paid.get(ident) != value for ident, value in cost_rows(job, order['id'], contract)):
        raise ValueError('SAVINGS_FULLY_PAID_COSTS_REQUIRED')
    offers = [a for a in actions if a['op'] == 'offer' and a['args']['id'] == order['id']]
    if len(offers) != 1:
        raise ValueError('ONE_NATIVE_SAVINGS_OFFER_REQUIRED')
    offer = offers[0]
    wallets = [a for a in actions if a['op'] == 'wallet' and a['args']['buyer'] == order['buyer']]
    if len(wallets) != 1 or wallets[0]['args']['amount'] != t['buyer_budget_microUSD']:
        raise ValueError('INDEPENDENT_PREDECLARED_BUYER_BUDGET_REQUIRED')
    expected = terms_for(manifest, order['id'], contract, offer['day'])
    terms = [a['args']['terms'] for a in actions if a['op'] == 'register_terms'
             and a['args']['id'] == offer['args'].get('terms_id')]
    if (terms != [expected] or offer['args']['deadline'] != offer['day'] + contract['deadline_hours']):
        raise ValueError('EXACT_PRECOMMITTED_SAVINGS_TERMS_REQUIRED')


def rebind_prepared(root, manifest, actions, jobs, *, _verified_prefix=0, _byte_bindings=None):
    """Rebind preparations, retaining a private already-verified prefix proof.

    Only the native replay session supplies ``_verified_prefix``, after matching
    the complete prior action bytes, owner, source, manifest and account. Public
    replay uses zero and independently checks every preparation. For a matched
    prefix, immutable private bindings retain the actual raw input/output hashes
    only after full semantic qualification. Read and hash every file again; no
    mtime, size, caller-supplied head or stored public receipt substitutes for its
    current bytes. Missing bindings and public replay perform full qualification.
    The map grows with already-verified history, without limiting market size.
    """
    if type(_verified_prefix) is not int or not 0 <= _verified_prefix <= len(actions):
        raise ValueError('EXACT_PRIVATE_VERIFIED_PREFIX_REQUIRED')
    if _byte_bindings is not None and not isinstance(_byte_bindings, dict):
        raise ValueError('PRIVATE_PREPARED_BYTE_BINDINGS_REQUIRED')
    current_jobs = load_contracts(root, manifest)
    if current_jobs != jobs:
        raise ValueError('SAVINGS_PREPARED_JOB_AUTHORITY_CHANGED')
    offers = {a['args']['id']: a['args']['job_id'] for a in actions if a['op'] == 'offer'}
    rebound = {}
    for index, action in enumerate(actions):
        if action['op'] == 'event' and action['args']['action'] == 'prepare':
            job_id = offers[action['args']['id']]
            if isinstance(current_jobs, ProceduralContracts):
                _ident(job_id)
                base = Path(manifest['output_dir']) / job_id
                input_path = str(base) + '.contract.json'
                output_path = str(base) + '.delivery.json'
            else:
                job = current_jobs[job_id]['job']
                input_path, output_path = job['input'], job['output']
            authority = (job_id, input_path, output_path, action['args']['artifact_sha256'])
            prior = (_byte_bindings or {}).get(index) if index < _verified_prefix else None
            input_raw = _path(root, input_path).read_bytes()
            artifact_raw = _path(root, output_path).read_bytes()
            input_sha = hashlib.sha256(input_raw).hexdigest()
            raw_output_sha = hashlib.sha256(artifact_raw).hexdigest()
            if prior is not None:
                if (not isinstance(prior, tuple) or len(prior) != 6
                        or prior[:4] != authority or prior[4:] != (input_sha, raw_output_sha)):
                    raise ValueError('SAVINGS_PREPARED_BYTES_OR_ACCEPTANCE_CHANGED')
                rebound[index] = prior
                continue
            artifact = strict_json(artifact_raw)
            if (digest(artifact) != action['args']['artifact_sha256']
                    or input_sha != artifact.get('contract_sha256')
                    or not check_delivery(root, manifest, job_id, artifact)['accepted']
                    or _path(root, output_path).read_bytes() != artifact_raw
                    or _path(root, input_path).read_bytes() != input_raw):
                raise ValueError('SAVINGS_PREPARED_BYTES_OR_ACCEPTANCE_CHANGED')
            # Only fully qualified, byte-stable evidence may enter the private
            # cache. Tuples prevent accidental mutation of binding fields.
            rebound[index] = authority + (input_sha, raw_output_sha)
    return rebound


def fulfill(account, root, manifest, job_id, *, order_id, buyer, hour, consent=True, result=None):
    """Cash-feasible native order with exact recovery; delay scheduling stays explicit.

    This convenience entry point performs a complete order, including declared
    clearing delay. A runner interleaving other orders during that delay should
    use the same exported primitives and native events instead.
    """
    if type(consent) is not bool:
        raise ValueError('EXPLICIT_SIMULATED_BUYER_CONSENT_REQUIRED')
    job, contract = contract_for(root, manifest, job_id)
    t = totals(contract)
    if not consent or contract['budget_microUSD'] < contract['price_microUSD']:
        return {'status': 'declined', 'collected_microUSD': 0}
    prior = account.export()['ledger']['actions']
    order_exists = any(a['op'] == 'offer' and a['args']['id'] == order_id for a in prior)
    if not order_exists:
        already_paid = {a['args']['id']: a['args']['amount'] for a in prior if a['op'] == 'cost'
                        and a['after']['expensePaid'] - a['before']['expensePaid'] == a['args']['amount']}
        remaining = sum(value for ident, value in cost_rows(job, order_id, contract) if ident not in already_paid)
        required = remaining + t['exposure_microUSD']
        if account.snapshot()['summary']['available'] < required:
            return {'status': 'deferred_liquidity', 'collected_microUSD': 0,
                    'required_microUSD': required}
    for ident, value in cost_rows(job, order_id, contract):
        account.cost(ident, value, hour)
    wallet_exists = any(a['op'] == 'wallet' and a['args']['buyer'] == buyer for a in prior)
    if not wallet_exists:
        account.execute('wallet', {'buyer': buyer, 'amount': t['buyer_budget_microUSD']}, hour)
    account.execute('register_terms', {'id': order_id + ':terms', 'terms': terms_for(manifest, order_id, contract, hour)}, hour)
    account.execute('offer', {'id': order_id, 'buyer': buyer, 'price': t['price_microUSD'],
                            'job_id': job_id, 'deadline': hour + contract['deadline_hours'],
                            'terms_id': order_id + ':terms'}, hour)
    def event(action, at=hour, **extra):
        return account.execute('event', {'id': order_id, 'action': action,
                               'event_id': order_id + ':' + action, **extra}, at)
    event('consent'); event('fund')
    artifact = produce(root, manifest, job_id, result=result)
    if not check_delivery(root, manifest, job_id, artifact)['accepted']:
        event('refund')
        return {'status': 'refunded', 'collected_microUSD': 0, 'artifact_sha256': digest(artifact)}
    event('prepare', artifact_sha256=digest(artifact))
    event('release', hour + contract['collection_delay_hours'])
    return {'status': 'released', 'collected_microUSD': t['price_microUSD'],
            'units': contract['units'], 'artifact_sha256': digest(artifact)}
