#!/usr/bin/env python3
"""Isolated same-runner proof; never accepts an existing enterprise directory."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def load(path):
    return json.loads(Path(path).read_text())


def setup(root):
    sys.path.insert(0, str(root))


def checkpoint(output):
    """Owner-only partial validation, not a completed operating audit."""
    require_fixture(output)
    from commercial.ledger import digest
    from connected_enterprise.runner import read_freeze, tasks, task_config
    from connected_enterprise.finance import JournalAccount
    from enterprise.runner import RunLock
    f = read_freeze(output)
    manifest = load(output / 'SERVICES.json')
    rows = []
    with RunLock(output):
        for task in tasks(f['protocol']):
            cfg = task_config(f, task)
            binding = digest(dict(config=cfg, seed=task['seed'], arm=task['arm'],
                                  source=f['source'], manifest=manifest))
            directory = output / 'worlds' / task['id']
            # Refuse to initialize missing accounts while validating a checkpoint.
            for suffix in ['', '.adaptive-simulation-key']:
                if not (directory / ('account.sqlite' + suffix)).is_file():
                    raise ValueError('EXISTING_TEST_ACCOUNT_REQUIRED')
            with JournalAccount(output / 'source', manifest, directory / 'account.sqlite',
                                opening=cfg['opening'], working=cfg['working'],
                                contract='connected014/' + binding) as account:
                state = account.verify_checkpoint(load(directory / 'STATE.json'))
                if digest(dict(config=state['config'], seed=state['seed'], arm=state['arm'],
                               source=state['source'], manifest=manifest)) != binding:
                    raise ValueError('CHECKPOINT_TASK_BINDING_CHANGED')
                audit = account.audit()
                if not audit['accepted']:
                    raise ValueError('NATIVE_CHECKPOINT_AUDIT_REJECTED')
                tape = account.export()['ledger']
                rows.append(dict(task=task['id'], processed_events=state['processed_events'],
                                 queued_events=len(state['queue']), pending_event=state['current'] is not None,
                                 native_actions=len(tape['actions']), native_actions_sha256=tape['actions_sha256'],
                                 contract_sha256=digest(tape['config']['contract']), native_audit_accepted=True))
    return dict(execution_state='CHECKPOINTED_PENDING_FULL_AUDIT',
                claim_verdict='NOT_A_COMPLETED_OPERATING_AUDIT', next_action='CONTINUE_SAME_LOCAL_ACCOUNT',
                source_sha256=f['source']['sha256'], worlds=rows)


def require_fixture(output):
    marker = output / '.isolated-continuation-proof.json'
    if not marker.is_file() or marker.is_symlink() or load(marker) != {'purpose': 'DISPOSABLE_SYNTHETIC_CONTINUATION_PROOF', 'output': str(output)}:
        raise ValueError('ISOLATED_PROOF_FIXTURE_REQUIRED')


def interrupt(output):
    require_fixture(output)
    from connected_enterprise.runner import read_freeze, tasks, task_config
    from connected_enterprise.engine import run_world
    from enterprise.runner import RunLock
    f = read_freeze(output); task = tasks(f['protocol'])[1]
    def fault(name, state, account):
        if name == 'after_event_before_checkpoint' and state['current']['event']['kind'] == 'produce':
            os._exit(73)  # Only reached in this script's newly registered disposable fixture.
    with RunLock(output):
        run_world(output / 'source', load(output / 'SERVICES.json'), task_config(f, task),
                  task['seed'], task['arm'], output / 'worlds' / task['id'], source=f['source'], failpoint=fault)
    raise ValueError('REGISTERED_FAULT_NOT_REACHED')


def stable(result):
    # Reuse canonical independent-owner comparison. Exclusions never change money,
    # obligations, native actions, source, orders, outcomes, or event timestamps.
    from adaptive_enterprise.model import stable_projection
    from commercial.ledger import digest
    value = copy.deepcopy(result); value.pop('resource_receipt', None)
    value = stable_projection(value)
    journal = value.get('owned_account', {}).get('connected_journal')
    if isinstance(journal, dict):
        for row in journal.get('entries', []):
            attempt = row.get('attempt')
            if isinstance(attempt, dict) and 'account_record_sha256' in attempt:
                attempt['account_record_sha256'] = 'LOCAL_ACCOUNT_AUTHORITY_WITNESS'
        value['owned_account']['connected_journal_sha256'] = digest(journal)
    return value


def prove(root, receipt_path):
    from commercial.ledger import digest
    from connected_enterprise.engine import default_config
    from connected_enterprise.runner import tasks, read_freeze
    from enterprise.runner import RunLock
    script = Path(__file__).resolve(); commands = []
    cpu0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    wall0 = time.monotonic()
    def command(argv, cwd=root, expected=0, error=None):
        started = time.monotonic()
        process = subprocess.Popen([sys.executable, *map(str, argv)], cwd=cwd,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise
        p = subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)
        commands.append(dict(index=len(commands), returncode=p.returncode,
                             wall_seconds=time.monotonic()-started,
                             stdout_sha256=hashlib.sha256(p.stdout.encode()).hexdigest(),
                             stderr_sha256=hashlib.sha256(p.stderr.encode()).hexdigest()))
        if p.returncode != expected or (error is not None and error not in p.stderr):
            raise RuntimeError(f'COMMAND_FAILED_{len(commands)}: {p.returncode}: {p.stderr[-2000:]}')
        return json.loads(p.stdout) if p.stdout.strip() else None
    with tempfile.TemporaryDirectory(prefix='isolated-harness-continuation-') as tmp:
        base = Path(tmp); trial = base/'continued'; reference = base/'reference'
        cfg = default_config()
        cfg.update(horizon_days=14, customer_pool=8, setup_cost=10_000_000,
                   arrival_bps=10000, retention_bps=10000, nonpayment_bps=0)
        cfg['channels']['pilot'].update(price_microUSD=1_000_000,
                                       activation_reliability_bps=10000, realization_bps=10000, overlap_bps=0)
        registration = dict(schema='agi-alpha/connected014-registration/v1',
            label='harness-same-runner-proof-001', evidence_role='development', seeds=[341014],
            configs={'central':cfg}, arms=['baseline','growth'], control_arm='baseline',
            candidate_arm='growth', service_cohort_seed=341014, workers=1)
        config = base/'registration.json'; config.write_text(json.dumps(registration))
        for output in [trial, reference]:
            command(['-m','connected_enterprise','register','--config',config,'--output',output])
        (trial/'.isolated-continuation-proof.json').write_text(json.dumps({'purpose':'DISPOSABLE_SYNTHETIC_CONTINUATION_PROOF','output':str(trial)}))
        frozen = read_freeze(trial)
        command(['-m','connected_enterprise','operate','--output',trial,'--max-events','1'])
        first = command([script,'--root',trial/'source','--checkpoint',trial])
        # Share exact public workload, including its measured preparation receipt.
        # Independently preparing it embeds different CPU in the manifest/contract.
        assert not (reference/'worlds').exists(), 'REFERENCE_ACCOUNT_MUST_NOT_EXIST_BEFORE_PUBLIC_INPUT_COPY'
        assert not list(reference.rglob('*.adaptive-simulation-key')), 'REFERENCE_AUTHORITY_MUST_NOT_EXIST'
        shutil.copytree(trial/'source'/'service-inputs', reference/'source'/'service-inputs')
        shutil.copyfile(trial/'SERVICES.json', reference/'SERVICES.json')
        assert load(trial/'SERVICES.json') == load(reference/'SERVICES.json')
        keys = {t['id']:(trial/'worlds'/t['id']/'account.sqlite.adaptive-simulation-key').read_bytes()
                for t in tasks(frozen['protocol'])}
        prefixes = {t['id']:(trial/'worlds'/t['id']/'account.sqlite.actions.jsonl').read_bytes()
                    for t in tasks(frozen['protocol'])}
        command(['-m','connected_enterprise','operate','--output',trial,'--max-events','2'])
        second = command([script,'--root',trial/'source','--checkpoint',trial])
        assert all(b['processed_events'] > a['processed_events'] for a,b in zip(first['worlds'],second['worlds']))
        assert not (trial/'COMPLETE.json').exists() and not (trial/'REPORT.json').exists()
        with RunLock(trial):
            command(['-m','connected_enterprise','operate','--output',trial,'--max-events','1'],
                    expected=1, error='ANOTHER_CURRENT_RUN_OWNS_OUTPUT')
        from connected_enterprise.finance import JournalAccount
        from connected_enterprise.runner import task_config
        task = tasks(frozen['protocol'])[0]; tc = task_config(frozen, task)
        manifest = load(trial/'SERVICES.json')
        binding = digest(dict(config=tc, seed=task['seed'], arm=task['arm'], source=frozen['source'], manifest=manifest))
        with JournalAccount(trial/'source', manifest, trial/'worlds'/task['id']/'account.sqlite', opening=tc['opening'], working=tc['working'], contract='connected014/'+binding):
            command([script,'--root',trial/'source','--checkpoint',trial], expected=1, error='TAPE_ALREADY_OWNED')
        command([script,'--root',trial/'source','--interrupt',trial], expected=73)
        interrupted = command([script,'--root',trial/'source','--checkpoint',trial])
        assert interrupted['worlds'][1]['pending_event']
        assert not (trial/'COMPLETE.json').exists() and not (trial/'REPORT.json').exists()
        command(['-m','connected_enterprise','resume','--output',trial])
        audit_trial = command(['-m','connected_enterprise','audit','--output',trial])
        command(['-m','connected_enterprise','resume','--output',reference])
        audit_reference = command(['-m','connected_enterprise','audit','--output',reference])
        rows=[]; snapshots={}
        for t in tasks(frozen['protocol']):
            ident=t['id']; directory=trial/'worlds'/ident
            actual=load(directory/'RESULT.json'); expected=load(reference/'worlds'/ident/'RESULT.json')
            if stable(actual)!=stable(expected):
                def differences(a,b,path=''):
                    if type(a)!=type(b): return [path+':type']
                    if isinstance(a,dict):
                        if set(a)!=set(b): return [path+':keys']
                        return [x for k in a for x in differences(a[k],b[k],path+'/'+k)]
                    if isinstance(a,list):
                        if len(a)!=len(b): return [path+':length']
                        return [x for i,(v,w) in enumerate(zip(a,b)) for x in differences(v,w,path+'/'+str(i))]
                    return [] if a==b else [path]
                raise AssertionError('CONTINUED_REFERENCE_SEMANTICS_DIFFER:'+json.dumps(differences(stable(actual),stable(expected))[:30]))
            assert (directory/'account.sqlite.adaptive-simulation-key').read_bytes()==keys[ident]
            assert (directory/'account.sqlite.actions.jsonl').read_bytes().startswith(prefixes[ident])
            snapshots[ident]=stable(actual)
            rows.append(dict(task=ident, semantic_sha256=digest(stable(actual)),
                native_actions_sha256=actual['owned_account']['ledger']['actions_sha256'],
                paid_jobs=actual['paid_jobs'], profit_microUSD=actual['summary']['profit'],
                processed_events=actual['processed_events'], reference_equal=True))
        # Duplicate completed trigger: no financial/event advancement. This is NOT
        # a durable duplicate-trigger inbox for partial cross-workflow requests.
        command(['-m','connected_enterprise','resume','--output',trial])
        for t in tasks(frozen['protocol']):
            assert stable(load(trial/'worlds'/t['id']/'RESULT.json'))==snapshots[t['id']]
        final_audit=command(['-m','connected_enterprise','audit','--output',trial])
        assert audit_trial['accepted'] and audit_reference['accepted'] and final_audit['accepted']
        receipt=dict(schema='agi-alpha/harness-same-runner-proof/v1', accepted=True,
            execution_state='COMPLETED_ISOLATED_ENGINEERING_PROOF', claim_verdict='SAME_RUNNER_CROSS_PROCESS_ONLY',
            next_action='REVIEW_EXISTING_PRIVATE_DURABLE_CUSTODY_BEFORE_CROSS_WORKFLOW_USE',
            source_sha256=frozen['source']['sha256'], registration=registration,
            shared_public_manifest_sha256=digest(load(trial/'SERVICES.json')),
            harness_sha256=hashlib.sha256(script.read_bytes()).hexdigest(),
            checkpoints=[first,second,interrupted], worlds=rows,
            run_lock_concurrent_writer_rejected=True, native_concurrent_writer_rejected=True, isolated_abrupt_production_exit=73,
            same_private_key_and_native_prefix_preserved=True, duplicate_completed_trigger_unchanged=True,
            native_and_operating_audits_accepted=True, commands=commands,
            limitations=['No cross-workflow durable private custody or distributed fencing.',
                'No partial-trigger inbox/idempotency protocol is established.',
                'Synthetic finite development fixture; no commercial scale or actual commerce claim.',
                'Reference comparison excludes only canonical independent-owner witnesses and CPU/wall timing.',
                'Host/model billing unavailable, not zero; modeled financial costs remain unchanged.'])
    cpu1=resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt['resources']=dict(child_cpu_seconds=cpu1.ru_utime+cpu1.ru_stime-cpu0.ru_utime-cpu0.ru_stime,
                              wall_seconds=time.monotonic()-wall0,billing='UNAVAILABLE_NOT_ZERO',
                              scope='THIS_PROOF_INVOCATION_CHILD_PROCESSES_ONLY',
                              discarded_development_attempt_cpu='UNMEASURED_NOT_ZERO')
    receipt_path.parent.mkdir(parents=True,exist_ok=True)
    receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    return dict(accepted=True,receipt=str(receipt_path),source_sha256=receipt['source_sha256'])


def main():
    if not __debug__:
        raise ValueError('ASSERTION_ENABLED_PROOF_REQUIRED')
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--receipt',type=Path); p.add_argument('--checkpoint',type=Path); p.add_argument('--interrupt',type=Path)
    args=p.parse_args(); root=args.root.resolve(); setup(root)
    if args.checkpoint: result=checkpoint(args.checkpoint.resolve())
    elif args.interrupt: return interrupt(args.interrupt.resolve())
    else:
        if args.receipt is None: p.error('--receipt required')
        try:
            result=prove(root,args.receipt.resolve())
        except BaseException as exc:
            args.receipt.parent.mkdir(parents=True,exist_ok=True)
            args.receipt.write_text(json.dumps({'accepted':False,'execution_state':'PROOF_FAILED','claim_verdict':'NOT_ESTABLISHED','error_type':type(exc).__name__,'error_sha256':hashlib.sha256(str(exc).encode()).hexdigest(),'source_root_label':'CURRENT_CHECKOUT','private_authority_exported':False},indent=2)+'\n')
            raise
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__': main()
