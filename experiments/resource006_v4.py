"""Prospective resource receipts for trusted experiment commands, not a sandbox."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import time
import threading

CAP_CPU = 5400
CAP_STORAGE = 6 * 1024**3
KEYS = {'wall_seconds', 'cpu_seconds', 'memory_bytes', 'output_bytes', 'storage_bytes'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


@contextlib.contextmanager
def _locked(path):
    path = Path(path).absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + '.lock')
    if path.is_symlink() or lock.is_symlink():
        raise ValueError('RESOURCE_LEDGER_SYMLINK')
    with lock.open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        state = json.loads(path.read_text()) if path.exists() else {
            'schema': 'agi-alpha/prospective-resources006/v1', 'capacity_cpu_seconds': CAP_CPU,
            'capacity_storage_bytes': CAP_STORAGE, 'state': 'active', 'runs': {}}
        if state.get('schema') != 'agi-alpha/prospective-resources006/v1' or state.get('capacity_cpu_seconds') != CAP_CPU or state.get('capacity_storage_bytes') != CAP_STORAGE:
            raise ValueError('RESOURCE_LEDGER_IDENTITY')
        yield state
        temporary = path.with_name(path.name + '.pending-%d' % os.getpid())
        with temporary.open('x') as output:
            json.dump(state, output, indent=2, allow_nan=False)
            output.write('\n'); output.flush(); os.fsync(output.fileno())
        os.replace(temporary, path)


def reserve(ledger, run_id, limits):
    if type(limits) is not dict or set(limits) != KEYS:
        raise ValueError('RESOURCE_LIMIT_KEYS')
    if any(type(limits[k]) is not int or limits[k] <= 0 for k in KEYS):
        raise ValueError('RESOURCE_LIMIT_VALUE')
    if limits['cpu_seconds'] > CAP_CPU or limits['wall_seconds'] > 7200 or limits['memory_bytes'] > 4 * 1024**3 or limits['output_bytes'] > limits['storage_bytes'] or limits['storage_bytes'] > CAP_STORAGE:
        raise ValueError('RESOURCE_LIMIT_OUT_OF_SCOPE')
    if type(run_id) is not str or not run_id or len(run_id) > 100 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in run_id):
        raise ValueError('RESOURCE_RUN_ID')
    with _locked(ledger) as state:
        if run_id in state['runs']:
            raise ValueError('RESOURCE_RUN_ID_REUSED')
        if state['state'] != 'active':
            raise ValueError('RESOURCE_LEDGER_BLOCKED')
        cpu = sum(item['budget_cpu_seconds'] for item in state['runs'].values())
        storage = sum(item['budget_storage_bytes'] for item in state['runs'].values())
        if cpu + limits['cpu_seconds'] > CAP_CPU or storage + limits['storage_bytes'] > CAP_STORAGE:
            raise ValueError('RESOURCE_ALLOCATION_EXHAUSTED')
        state['runs'][run_id] = {'state': 'pending', 'limits': limits.copy(),
            'budget_cpu_seconds': limits['cpu_seconds'], 'budget_storage_bytes': limits['storage_bytes']}


def settle(ledger, run_id, receipt):
    identity = digest(receipt)
    with _locked(ledger) as state:
        item = state['runs'][run_id]
        if item.get('receipt_sha256') == identity:
            return dict(item)
        if item.get('receipt_sha256'):
            raise ValueError('RESOURCE_SETTLEMENT_CONFLICT')
        item['receipt_sha256'] = identity
        item['outcome'] = receipt['state']
        item['observed_waited_cpu_seconds'] = receipt['waited_cpu_seconds']
        item['observed_output_bytes'] = receipt['output_bytes']
        if receipt['state'] in {'complete', 'failed', 'overrun'} and receipt['descendant_survivors'] is False:
            item['state'] = 'settled'
            item['budget_storage_bytes'] = receipt['output_bytes']
        else:
            item['state'] = 'pending-interruption'
        item['cpu_refund_seconds'] = 0
        item['cpu_refund_reason'] = 'No exact full process-group CPU attribution; preserve conservative reservation as budget charge, not measured cost.'
        if receipt['state'] == 'overrun' or receipt['output_bytes'] > item['limits']['storage_bytes'] or receipt['waited_cpu_seconds'] > item['limits']['cpu_seconds']:
            state['state'] = 'blocked-overrun'
        return dict(item)


def _file_sizes(path):
    """Sample present files/links without following links or racing two stats."""
    for entry in path.rglob('*'):
        try:
            observed = entry.lstat()
        except FileNotFoundError:
            # A live producer may remove a temporary file after enumeration.
            # Ignore only absence; permission and other I/O errors still fail.
            continue
        if stat.S_ISREG(observed.st_mode) or stat.S_ISLNK(observed.st_mode):
            yield observed.st_size


def _usage(path):
    return sum(_file_sizes(path))


def _group_exists(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _kill(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def normalize_command(command):
    requested = command.copy()
    executable = sys.executable if requested[0] in {'python', 'python3'} else requested[0]
    path = Path(executable)
    if not path.is_absolute():
        raise ValueError('RESOURCE_ABSOLUTE_EXECUTABLE_REQUIRED')
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError('RESOURCE_EXECUTABLE_UNAVAILABLE')
    return [executable, *requested[1:]]


def _exception(error):
    return {'type': type(error).__name__, 'message': str(error)[:512]}


def _preflight_refusal(command, output, run_id, limits, error, started, own):
    receipt = {'schema': 'agi-alpha/trusted-experiment-run006/v4', 'run_id': run_id,
        'requested_command': command, 'normalized_command': None, 'command': None,
        'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'limits': limits, 'state': 'refused', 'exit_code': None, 'reason': 'executable-preflight',
        'error': _exception(error), 'reservation_created': False,
        'wall_seconds': time.monotonic()-started, 'supervisor_cpu_seconds': time.process_time()-own,
        'waited_cpu_seconds': 0.0, 'aggregate_cpu_complete': False,
        'scope': 'No executable was launched and no reservation was requested; trusted-command wrapper, not a sandbox.'}
    try:
        output.mkdir(parents=True, exist_ok=False)
        _write(output / 'REFUSAL.json', receipt)
        receipt_path = str(output / 'REFUSAL.json')
    except OSError:
        receipt_path = None
    return {'receipt': receipt, 'settlement': None, 'receipt_sha256': digest(receipt), 'receipt_path': receipt_path}


@contextlib.contextmanager
def _blocked():
    prior = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
    try:
        yield prior
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, prior)


def _terminated(signum, frame):
    raise KeyboardInterrupt('RESOURCE_SIGNAL_' + str(signum))


def _final_receipt(receipt, output):
    """Charge the terminal receipt itself and reject final crossings before success."""
    sizes = list(_file_sizes(output)) if output.is_dir() else []
    base = sum(sizes)
    for _ in range(12):
        encoded_bytes = len((json.dumps(receipt, indent=2, allow_nan=False) + '\n').encode())
        receipt['output_bytes'] = base + encoded_bytes
        overrun = None
        if receipt['output_bytes'] > receipt['limits']['storage_bytes']:
            overrun = 'final-aggregate-output-storage-limit'
        elif max([encoded_bytes, *sizes]) > receipt['limits']['output_bytes']:
            overrun = 'final-output-file-limit'
        elif receipt['waited_cpu_seconds'] > receipt['limits']['cpu_seconds']:
            overrun = 'final-observed-cpu-limit'
        elif receipt['wall_seconds'] > receipt['limits']['wall_seconds']:
            overrun = 'final-wall-limit'
        if overrun and receipt['state'] != 'interrupted':
            receipt['state'], receipt['reason'] = 'overrun', overrun
        updated_bytes = len((json.dumps(receipt, indent=2, allow_nan=False) + '\n').encode())
        if receipt['output_bytes'] == base + updated_bytes:
            break
    return receipt


def run(command, output, ledger, run_id, limits, cwd=None):
    if threading.current_thread() is not threading.main_thread():
        raise ValueError('RESOURCE_MAIN_THREAD_REQUIRED_FOR_SIGNAL_CLEANUP')
    if type(command) is not list or not command or any(type(x) is not str or not x or '\x00' in x for x in command):
        raise ValueError('RESOURCE_TRUSTED_COMMAND_REQUIRED')
    output = Path(output).absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise FileExistsError(output)
    requested_command = command.copy()
    limits = limits.copy() if type(limits) is dict else limits
    started, own = time.monotonic(), time.process_time()
    previous_handler = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _terminated)
    process, code, reason, survivors, waited, failure = None, None, None, False, 0.0, None
    reserved = False
    cleanup_mask = None
    try:
        try:
            command = normalize_command(requested_command)
        except (OSError, ValueError) as error:
            return _preflight_refusal(requested_command, output, run_id, limits, error, started, own)
        pending = {'schema': 'agi-alpha/trusted-experiment-run006/v4', 'run_id': run_id, 'command': command,
            'requested_command': requested_command, 'normalized_command': command.copy(), 'reservation_created': True,
            'cwd': str(Path(cwd or '.').resolve()), 'limits': limits,
            'wrapper_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'state': 'pending'}
        try:
            # No signal can leave a successfully reserved/created output unowned.
            with _blocked():
                reserve(ledger, run_id, limits)
                reserved = True
                output.mkdir(parents=True, exist_ok=False)
                _write(output / 'PENDING.json', pending)
            with (output / 'stdout.log').open('xb') as stdout, (output / 'stderr.log').open('xb') as stderr:
                with _blocked() as child_mask:
                    def bounds():
                        resource.setrlimit(resource.RLIMIT_CPU, (limits['cpu_seconds'], limits['cpu_seconds']))
                        resource.setrlimit(resource.RLIMIT_AS, (limits['memory_bytes'], limits['memory_bytes']))
                        resource.setrlimit(resource.RLIMIT_FSIZE, (limits['output_bytes'], limits['output_bytes']))
                        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
                        signal.pthread_sigmask(signal.SIG_SETMASK, child_mask)
                    process = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr, start_new_session=True,
                        preexec_fn=bounds, env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8',
                            'PYTHONNOUSERSITE': '1', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'})
                while True:
                    # Reaping and recording ownership are one signal-atomic step.
                    with _blocked():
                        found, status, usage = os.wait4(process.pid, os.WNOHANG)
                        if found:
                            code = os.waitstatus_to_exitcode(status)
                            process.returncode = code
                            waited = usage.ru_utime + usage.ru_stime
                    if found:
                        break
                    if time.monotonic() - started > limits['wall_seconds']:
                        reason = 'wall-limit'
                    if _usage(output) > limits['storage_bytes']:
                        reason = 'output-storage-limit'
                    if reason:
                        with _blocked():
                            _kill(process.pid)
                            _, status, usage = os.wait4(process.pid, 0)
                            code = os.waitstatus_to_exitcode(status)
                            process.returncode = code
                            waited = usage.ru_utime + usage.ru_stime
                        break
                    time.sleep(0.02)
                code = os.waitstatus_to_exitcode(status)
                process.returncode = code
                waited = usage.ru_utime + usage.ru_stime
                survivors = _group_exists(process.pid)
                if survivors:
                    _kill(process.pid)
                    reason = reason or 'descendant-survivors'
        except BaseException as error:
            if not reserved:
                raise
            failure = _exception(error)
            reason = 'interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'launch-or-monitor-error'
            # A second signal cannot interrupt group termination and receipt settlement.
            cleanup_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
            if process is not None:
                _kill(process.pid)
                if process.returncode is None:
                    _, status, usage = os.wait4(process.pid, 0)
                    code = os.waitstatus_to_exitcode(status)
                    process.returncode = code
                    waited = usage.ru_utime + usage.ru_stime
                survivors = _group_exists(process.pid)
        with _blocked():
            state = 'interrupted' if reason == 'interrupted' else 'overrun' if reason in {'wall-limit', 'output-storage-limit'} else 'failed' if reason or code else 'complete'
            receipt = {**pending, 'state': state,
                'exit_code': code, 'reason': reason, 'error': failure, 'wall_seconds': time.monotonic()-started,
                'supervisor_cpu_seconds': time.process_time()-own, 'waited_cpu_seconds': waited,
                'descendant_survivors': survivors, 'output_bytes': 0,
                'logs': {name: hashlib.sha256((output/name).read_bytes()).hexdigest() for name in ('stdout.log', 'stderr.log') if (output/name).exists()},
                'scope': 'Trusted commands only. Per-process CPU/AS/file limits plus process-group wall termination, main-thread SIGTERM cleanup, and terminal aggregate-output/receipt checks. Waited-child rusage may omit escaped/unwaited descendants; this is not a sandbox or exact full-group CPU meter.',
                'aggregate_cpu_complete': False, 'complete_monetary_cost': None}
            receipt = _final_receipt(receipt, output)
            receipt_path = output / 'RECEIPT.json' if output.is_dir() else Path(ledger).with_name(Path(ledger).name + '.' + run_id + '.interrupted.json')
            _write(receipt_path, receipt)
            settled = settle(ledger, run_id, receipt)
        return {'receipt': receipt, 'settlement': settled, 'receipt_sha256': digest(receipt)}
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
        if cleanup_mask is not None:
            signal.pthread_sigmask(signal.SIG_SETMASK, cleanup_mask)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('ledger', 'run-id', 'output'):
        parser.add_argument('--'+key, required=True)
    for key, default in [('wall', 60), ('cpu', 60), ('memory-bytes', 1024**3), ('output-bytes', 20*1024**2), ('storage-bytes', 64*1024**2)]:
        parser.add_argument('--'+key, type=int, default=default)
    parser.add_argument('--cwd')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    result = run(command, args.output, args.ledger, args.run_id, {'wall_seconds': args.wall, 'cpu_seconds': args.cpu,
        'memory_bytes': args.memory_bytes, 'output_bytes': args.output_bytes, 'storage_bytes': args.storage_bytes}, args.cwd)
    print(json.dumps(result, allow_nan=False))
    raise SystemExit(0 if result['receipt']['state'] == 'complete' else 1)


if __name__ == '__main__':
    main()
