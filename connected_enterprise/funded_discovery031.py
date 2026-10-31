"""Opt-in native-funded research; inert proposals, never delivery authority.

Uses the existing acquisition and ordinary-reuse implementations unchanged.
The deterministic research prices are simulated complete-operation envelopes,
not measured API billing. Actual host/model/engineering costs remain unknown.
"""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
import threading
import time

from commercial.ledger import digest
from connected_enterprise.finance import JournalAccount, source_identity
from mechanisms import construct, criticism, executor, mapping, memory, pipeline
from flywheel import retention, sandbox
from flywheel.retention import retrieve

ROOT = Path(__file__).resolve().parents[1]
LOCK = threading.RLock()
ARMS = ('no_memory', 'ordinary_reuse', 'acquired_reuse')
FEES = {'acquisition': 1_000_000, 'retrieval': 10_000,
        'construction': 50_000, 'verification': 100_000}
LIMITS = {'max_candidates': 64, 'max_combinations': 4, 'max_bundle_size': 2}
DEPENDENCIES = tuple('mechanisms/' + x + '.py' for x in
                     ('__init__', 'pipeline', 'construct', 'criticism', 'executor', 'mapping', 'memory')) + (
    'flywheel/__init__.py', 'flywheel/retention.py', 'flywheel/sandbox.py',
    'connected_enterprise/funded_discovery031.py', 'scripts/run_funded_discovery031.py')


def binding(root):
    """All imported proposal code must equal the account's declared source."""
    root = Path(root).resolve(strict=True)
    for module in (construct, criticism, executor, mapping, memory, pipeline, retention, sandbox):
        expected = ROOT / (module.__name__.replace('.', '/') + '.py')
        if Path(module.__file__).resolve() != expected.resolve():
            raise ValueError('DISCOVERY_IMPORTED_SOURCE_MISMATCH')
    files = source_identity(root)['files']
    for name in set(files) | set(DEPENDENCIES):
        p, executing = root / name, ROOT / name
        if any(x.is_symlink() for x in (p, *p.parents)) or not p.is_file():
            raise ValueError('DISCOVERY_SOURCE_DEPENDENCY_MISSING:' + name)
        if not executing.is_file() or p.read_bytes() != executing.read_bytes():
            raise ValueError('DISCOVERY_EXECUTING_SOURCE_MISMATCH:' + name)
        files[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return {'files': files, 'sha256': digest(files)}


def _pay(account, ident, stage, amount, day, request, allow_seed):
    # JournalAccount retries are idempotent financial operations, NOT permission
    # to repeat research after a crash. A new attempt requires a new paid id.
    if any(row['request'].get('operation') == 'spend' and row['request'].get('id') == ident for row in account.export()['connected_journal']['entries']):
        raise ValueError('DISCOVERY_ALREADY_ATTEMPTED')
    receipt = account.spend(ident, 'discovery031-' + stage, amount, day,
                            request, 0, allow_seed=allow_seed)
    if receipt is None:
        raise ValueError('DISCOVERY_NATIVE_FUNDS_INSUFFICIENT')
    rows = [row for row in account.export()['connected_journal']['entries']
            if row['request'].get('operation') == 'spend' and row['request'].get('id') == ident]
    if len(rows) != 1 or rows[0]['status'] != 'COMPLETE' or rows[0]['request']['amount'] != amount or rows[0]['receipt'] != receipt or receipt['amount'] != amount:
        raise ValueError('DISCOVERY_PAYMENT_NOT_COMPLETE')


def fresh_tasks():
    """Prospectively fixed engineering holdouts, not scientific confirmation.

    The extra independent action changes the graph, not merely its identifiers.
    Its interruption may invalidate an acquired four-role method; do not hide it.
    """
    base, _, _ = pipeline.example('heldout-reversed', reverse=True)
    branch, _, _ = pipeline.example('heldout-branch')
    reserve = branch['phases'][0]['id']
    branch['phases'].insert(2, {'id': 'heldout-branch-extra', 'kind': 'action',
                              'deps': [reserve], 'unit': 'event'})
    branch['phases'][-1]['deps'].append('heldout-branch-extra')
    return [base, branch]


def run_research(root, account, output, *, ident, enabled=False, day=0,
                 allow_seed=False):
    """Run a finite paid study on an existing canonical native account.

    Disabled means no work/no cost. Explicit seed funding is required because
    this study has no justified positive expected net commercial return.
    No new account, wallet, balance, reset, or financial authority is created.
    """
    if enabled is not True:
        return {'status': 'disabled', 'native_cost_microUSD': 0, 'authority': []}
    if type(account) is not JournalAccount:
        raise ValueError('CANONICAL_JOURNAL_ACCOUNT_REQUIRED')
    root, output = Path(root).resolve(strict=True), Path(output)
    with LOCK:
        start, cpu = time.monotonic(), time.process_time()
        source = binding(root)
        if account.source != source_identity(root):
            raise ValueError('DISCOVERY_ACCOUNT_SOURCE_MISMATCH')
        task, donors, graph = pipeline.example('acquisition031')
        targets = fresh_tasks()
        request = {'schema': 'funded-discovery031/v1', 'source_sha256': source['sha256'],
                   'acquisition_sha256': digest([task, donors, graph]),
                   'heldout_sha256': digest(targets), 'fees': FEES, 'limits': LIMITS,
                   'specification_sha256': digest(pipeline.SPECIFICATION),
                   'scope': 'SEED_FUNDED_SYNTHETIC_RESEARCH_PROPOSALS_ONLY'}
        if output.exists():
            raise ValueError('FRESH_RESEARCH_OUTPUT_REQUIRED')
        # Native reservation/completion precedes the actual acquisition call.
        _pay(account, ident + ':acquire', 'acquisition', FEES['acquisition'], day, request, allow_seed)
        output.mkdir(parents=True, exist_ok=False)
        store = output / 'memory'
        learned = pipeline.develop(task, donors, graph, output / 'acquisition', store)
        rows = []
        for index, target in enumerate(targets):
            for arm in ARMS:
                prefix = ident + ':' + str(index) + ':' + arm
                work = dict(request, target_sha256=digest(target), arm=arm)
                # Every arm pays the same prospectively declared retrieval and
                # construction envelope. No-memory receives no retained JSON.
                _pay(account, prefix + ':retrieve', 'retrieval', FEES['retrieval'], day, work, allow_seed)
                records = retrieve(store, {'schema_version': 1, 'conditions': target['conditions']}, root)['records'] if arm != 'no_memory' else []
                content = sorted(memory.digest(item['record']) for item in records)
                _pay(account, prefix + ':construct', 'construction', FEES['construction'], day, work, allow_seed)
                if arm == 'no_memory':
                    generated = {'candidates': [{'program': construct.conventional(target)}]}
                elif arm == 'ordinary_reuse':
                    generated = memory.ordinary_bundle(copy.deepcopy(records), target, donors, root, LIMITS)
                else:
                    generated = memory.generate_bundle(store, target, donors, root, LIMITS)
                    actual_content = sorted(memory.digest(item['record']) for item in generated['memory']['retrieval']['records'])
                    if actual_content != content:
                        raise ValueError('DISCOVERY_RETRIEVAL_CONTENT_CHANGED')
                candidates = generated['candidates']
                checks = []
                # All candidates are checked, including null/failed candidates;
                # no repeated paid invocation until a favorable answer occurs.
                for number, candidate in enumerate(candidates):
                    _pay(account, prefix + ':verify:' + str(number), 'verification', FEES['verification'], day,
                         dict(work, candidate_sha256=digest(candidate.get('program'))), allow_seed)
                    checked = pipeline.verify(target, candidate.get('program'), output / (str(index) + '-' + arm + '-' + str(number)))
                    checks.append({'candidate_sha256': digest(candidate.get('program')),
                                   'passed': checked['passed'], 'checks': len(checked.get('checks', []))})
                rows.append({'task': target['id'], 'arm': arm, 'content_sha256': content,
                             'accepted': any(check['passed'] for check in checks),
                             'candidates': checks, 'generation_status': generated.get('status'),
                             'native_cost_microUSD': FEES['retrieval'] + FEES['construction'] + len(checks) * FEES['verification'],
                             'authority': []})
        if binding(root) != source:
            raise ValueError('DISCOVERY_SOURCE_CHANGED_DURING_WORK')
        if not account.audit()['accepted']:
            raise ValueError('DISCOVERY_NATIVE_AUDIT_REJECTED')
        # Costs of acquisition are explicitly attributed equally to both reuse
        # counterfactual arms, but charged only once to this actual study ledger.
        total = FEES['acquisition'] + sum(row['native_cost_microUSD'] for row in rows)
        result = {'schema': request['schema'], 'source': source, 'protocol': request,
                  'acquisition': {'status': learned['status'], 'before_passed': learned.get('before_passed'),
                      'after_passed': learned.get('after_passed'), 'retained': learned.get('retained'),
                      'mechanism_path': learned.get('mechanism_path'), 'native_cost_microUSD': FEES['acquisition']},
                  'rows': rows, 'native_cost_microUSD': total, 'native_audit_accepted': True,
                  'counterfactual_acquisition_cost_each_reuse_arm_microUSD': FEES['acquisition'],
                  'scope': 'PROCEDURALLY_SEPARATE_FIXED_VERIFIER_SYNTHETIC_ENGINEERING',
                  'exposure': 'Builder-visible engineering cases distinct from acquisition, NOT untouched confirmation.',
                  'authority': [], 'canonical_default_changed': False,
                  'actual_customers': 0, 'actual_collections': 0, 'actual_profit': None,
                  'cost_basis': 'Authored simulated complete-operation envelopes, not API bills; engineering/model/host costs unknown.',
                  'claims_not_established': ['autonomous frontier-model invention', 'retained method advantage', 'commercial profit', 'annual scale', 'global optimality'],
                  'wall_seconds': time.monotonic() - start, 'process_cpu_seconds': time.process_time() - cpu}
        pipeline.write(output / 'SUMMARY.json', result)
        return result
