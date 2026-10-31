import argparse, ctypes, datetime, hashlib, json, os, resource, signal, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from connected_enterprise.runner import identity

def read(p): return json.loads(p.read_text())
def write(p, value): p.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def run(output, resume=False, source_root=ROOT, command_timeout=180):
    output = Path(output).absolute()
    if output.exists() and not resume: raise FileExistsError('NEW_EXPERIMENT_OUTPUT_REQUIRED')
    if resume and not output.is_dir(): raise FileNotFoundError('EXISTING_EXPERIMENT_REQUIRED')
    protocol = read(HERE / 'PROTOCOL.json')
    source_root = Path(source_root).absolute()
    if identity(source_root) != protocol['source']: raise ValueError('REGISTERED_SOURCE_CHANGED')
    if resume:
        if read(output / 'PROTOCOL.json') != protocol: raise ValueError('REGISTERED_PROTOCOL_CHANGED')
    else:
        output.mkdir(parents=True, mode=0o700)
        write(output / 'PROTOCOL.json', protocol)
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0: raise RuntimeError('CHILD_SUBREAPER_REQUIRED')
    receipt = {'schema': 'agi-alpha/native-recycling025-execution/v1', 'accepted': False,
               'command_timeout_seconds': command_timeout,
               'started_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'protocol_sha256': sha(HERE / 'PROTOCOL.json'), 'source_sha256': protocol['source']['sha256'],
               'launcher_source_sha256': identity(ROOT)['sha256'],
               'helper_sha256': sha(Path(__file__)), 'commands': [], 'cases': []}
    if resume and (output / 'EXECUTION.json').exists():
        previous = read(output / 'EXECUTION.json'); index = 1
        while (output / ('EXECUTION_PREDECESSOR_' + str(index) + '.json')).exists(): index += 1
        retained = output / ('EXECUTION_PREDECESSOR_' + str(index) + '.json')
        retained.write_bytes((output / 'EXECUTION.json').read_bytes())
        receipt['preserved_predecessor'] = {'path': retained.name, 'sha256': sha(retained)}
        receipt['commands'] = previous.get('commands', [])
        receipt['cases'] = previous.get('cases', [])
    started = time.monotonic()
    def command(label, args):
        original_label = label; retry = 1
        while (output / (label + '.stdout')).exists():
            label = original_label + '-retry-' + str(retry); retry += 1
        before = resource.getrusage(resource.RUSAGE_CHILDREN); tick = time.monotonic()
        timed_out = False
        with (output / (label + '.stdout')).open('w') as stdout, (output / (label + '.stderr')).open('w') as stderr:
            execution_root = source_root if '--config' in args else ROOT
            child = subprocess.Popen([sys.executable, '-m', 'connected_enterprise', *map(str, args)], cwd=execution_root,
                                     env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}, stdout=stdout,
                                     stderr=stderr, start_new_session=True)
            try: returncode = child.wait(timeout=command_timeout)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL); child.wait()
                while True:
                    try: os.waitpid(-1, 0)
                    except ChildProcessError: break
                returncode = child.returncode; timed_out = True
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt['commands'].append({'label': label, 'arguments': list(map(str, args)), 'returncode': returncode,
                                    'timed_out': timed_out,
                                    'wall_seconds': time.monotonic() - tick,
                                    'command_cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                                    'stdout_sha256': sha(output / (label + '.stdout')), 'stderr_sha256': sha(output / (label + '.stderr'))})
        write(output / 'EXECUTION.json', receipt)
        if timed_out: raise TimeoutError('BOUNDARY_WITH_EXISTING_NATIVE_ACCOUNT_PRESERVED:' + label)
        if returncode: raise RuntimeError('PUBLIC_COMMAND_FAILED:' + label)
    try:
        for case in protocol['cases']:
            name = case['id']; config = output / (name + '.config.json'); target = output / name
            if any(c['id'] == name for c in receipt['cases']): continue
            write(config, case['config'])
            arguments = ['comparison', '--output', target]
            if not target.exists(): arguments.extend(['--config', config])
            label_suffix = '-continuation-' + str(len(receipt['commands'])) if resume else ''
            command(name + '-01-operate' + label_suffix, arguments)
            command(name + '-02-audit', ['audit', '--output', target])
            first = {arm: read(target / 'arms' / arm / 'RESULT.json')['owned_account']['ledger']
                     for arm in ['recycling_enabled', 'recycling_disabled']}
            command(name + '-03-unchanged-resume', ['comparison', '--output', target])
            for arm, ledger in first.items():
                if read(target / 'arms' / arm / 'RESULT.json')['owned_account']['ledger'] != ledger:
                    raise ValueError('COMPLETED_RESUME_CHANGED_FINANCES:' + name + ':' + arm)
            command(name + '-04-audit-resume', ['audit', '--output', target])
            comparison = read(target / 'COMPARISON.json'); audit = read(target / 'CAPITAL_AUDIT.json')
            if audit['accepted'] is not True: raise ValueError('NATIVE_OR_OPERATING_AUDIT_REJECTED')
            rows = {}
            for arm, score in comparison['arms'].items():
                result = read(target / 'arms' / arm / 'RESULT.json'); summary = result['summary']
                native_sums = {}
                for row in result['owned_account']['ledger']['journal']:
                    native_sums[row['kind']] = native_sums.get(row['kind'], 0) + int(row['amount'])
                revenue = native_sums.get('revenue', 0) - native_sums.get('contra_revenue', 0)
                expenses = native_sums.get('expense', 0) - native_sums.get('expense_reversal', 0)
                collections = native_sums.get('collections', 0) - native_sums.get('reversal_paid', 0)
                recovery = native_sums.get('recovery_income', 0)
                cash = result['owned_account']['ledger']['config']['opening'] + collections + recovery - native_sums.get('expense_paid', 0) - native_sums.get('investment_paid', 0)
                positive_deferred = [d for d in result['state']['decisions']
                                     if d['audited_before']['summary']['profit'] > 0 and not d['affordable']]
                if (not result['complete'] or result['state']['queue'] or
                    revenue != summary['revenue'] or expenses != summary['expenses'] or
                    revenue + recovery - expenses != summary['profit'] or cash != summary['cash']):
                    raise ValueError('INDEPENDENT_NATIVE_COMPLETION_OR_PROFIT_RECONCILIATION_FAILED')
                rows[arm] = {'source_sha256': result['source_sha256'], 'native_summary': summary,
                             'settled_orders': score['settled_orders'], 'matured_orders': score['matured_orders'],
                             'profitable_earned_continuations': score['profitable_earned_continuations'],
                             'repeated_earned_financed_expansion': score['repeated_earned_financed_expansion'],
                             'all_arrivals': score['arrivals_observed'], 'last_hour': result['state']['last_hour'],
                             'remaining_queue': len(result['state']['queue']), 'unchanged_resume': True,
                             'independent_journal_reconciliation': {'revenue_microUSD': revenue, 'expenses_microUSD': expenses,
                                                                   'net_collections_microUSD': collections, 'cash_microUSD': cash},
                             'profit_positive_cash_deferred': [{'order_id': d['order_id'], 'hour': d['hour'],
                                                               'native_profit_microUSD': d['audited_before']['summary']['profit'],
                                                               'available_microUSD': d['audited_before']['summary']['available']}
                                                              for d in positive_deferred],
                             'funding_lineage': score['funding_lineage'], 'per_order_native_profit_microUSD': score['per_order_native_profit_microUSD'],
                             'result_sha256': sha(target / 'arms' / arm / 'RESULT.json')}
            receipt['cases'].append({'id': name, 'config': read(target / 'FROZEN.json')['config'], 'arms': rows,
                                     'settled_order_delta': comparison['settled_order_delta'],
                                     'profit_delta_microUSD': comparison['profit_delta_microUSD'],
                                     'audit_sha256': sha(target / 'CAPITAL_AUDIT.json')})
            write(output / 'EXECUTION.json', receipt)
            print(json.dumps({'case': name, 'arms': {a: {k: r[k] for k in ['settled_orders', 'native_summary', 'profitable_earned_continuations']}
                                                       for a, r in rows.items()}}, sort_keys=True), flush=True)
        primary = receipt['cases'][0]['arms']['recycling_enabled']
        if not (primary['settled_orders'] == 24 and primary['repeated_earned_financed_expansion']):
            raise ValueError('REGISTERED_PRIMARY_CRITERION_NOT_MET')
        receipt['accepted'] = True
    except BaseException as error:
        receipt['failure'] = {'type': type(error).__name__, 'message': str(error)}; raise
    finally:
        receipt['wall_seconds'] = time.monotonic() - started
        receipt['finished_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write(output / 'EXECUTION.json', receipt)
    return receipt

if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--output', required=True); parser.add_argument('--continue-existing', action='store_true'); parser.add_argument('--source-root', default=str(ROOT)); parser.add_argument('--command-timeout', type=int, default=180)
    args = parser.parse_args()
    if not 1 <= args.command_timeout <= 900: raise ValueError('BOUNDED_COMMAND_TIMEOUT_REQUIRED')
    run(args.output, args.continue_existing, args.source_root, args.command_timeout)
