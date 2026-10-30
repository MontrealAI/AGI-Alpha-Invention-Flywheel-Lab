"""Independent bounded reproductions of two reviewed resource-v2 defects."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

EXPECTED = '8a59559fd1d02af280719dabf6499295afd82f23a36a812d0d7c757dee82f6d5'


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')


def state(pid):
    own_ids = [int(x) for x in next(line for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('NSpid:')).split()[1:]]
    namespace_index = max(i for i, value in enumerate(own_ids) if value == os.getpid())
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            if (path / 'ns/pid').stat().st_ino != Path('/proc/self/ns/pid').stat().st_ino:
                continue
            ids = [int(x) for x in next(line for line in (path / 'status').read_text().splitlines() if line.startswith('NSpid:')).split()[1:]]
            if len(ids) > namespace_index and ids[namespace_index] == pid:
                return (path / 'stat').read_text().rsplit(')', 1)[1].split()[0]
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / 'experiments/resource006.py'
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED:
        raise ValueError('ORIGINAL_RESOURCE_SOURCE_IDENTITY_MISMATCH')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'resource-v2-source.txt').write_bytes(raw)
    # Adopt and explicitly reap the deliberately orphaned test worker.
    if ctypes.CDLL(None).prctl(36, 1, 0, 0, 0) != 0:
        raise OSError('SUBREAPER_UNAVAILABLE')
    pid_marker = args.output / 'worker-pid.txt'
    stopped_output = args.output / 'sigterm-supervisor'
    worker_code = 'import os,time;from pathlib import Path;Path(' + repr(str(pid_marker)) + ').write_text(str(os.getpid()));time.sleep(60)'
    supervisor = subprocess.Popen([sys.executable, '-m', 'experiments.resource006', '--ledger', str(args.output / 'signal-test-ledger.json'), '--run-id', 'signal-test', '--output', str(stopped_output), '--wall', '90', '--cpu', '2', '--memory-bytes', str(1024**3), '--output-bytes', '20000', '--storage-bytes', '50000', '--', sys.executable, '-c', worker_code], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    worker_pid = None
    try:
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and not pid_marker.exists():
            time.sleep(.002)
        if not pid_marker.exists():
            raise RuntimeError('REAL_WORKER_NOT_OBSERVED')
        worker_pid = int(pid_marker.read_text())
        os.kill(supervisor.pid, signal.SIGTERM)
        returned = supervisor.wait(timeout=3)
        observation = {'supervisor_returncode': returned, 'worker_pid': worker_pid,
            'worker_state_after_supervisor_exit': state(worker_pid),
            'pending_exists': (stopped_output / 'PENDING.json').exists(),
            'receipt_exists': (stopped_output / 'RECEIPT.json').exists()}
        observation['established'] = returned == -signal.SIGTERM and observation['worker_state_after_supervisor_exit'] not in (None, 'Z', 'X') and observation['pending_exists'] and not observation['receipt_exists']
    finally:
        if supervisor.poll() is None:
            supervisor.kill(); supervisor.wait(timeout=3)
        if worker_pid is not None:
            try:
                os.killpg(worker_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                os.waitpid(worker_pid, 0)
            except ChildProcessError:
                pass
    observation['owned_worker_cleanup_state'] = state(worker_pid) if worker_pid else None
    write(args.output / 'SIGTERM_ADJUDICATION.json', observation)
    sys.path.insert(0, str(root))
    from experiments.resource006 import run
    fast_output = args.output / 'fast-exit-storage'
    worker_code = 'from pathlib import Path;p=Path(' + repr(str(fast_output)) + ');[(p/(str(i)+".bin")).write_bytes(b"x"*4000) for i in range(3)]'
    result = run([sys.executable, '-c', worker_code], fast_output, args.output / 'storage-test-ledger.json', 'storage-test', {'wall_seconds': 10, 'cpu_seconds': 2, 'memory_bytes': 1024**3, 'output_bytes': 5000, 'storage_bytes': 10000}, cwd=root)
    receipt = result['receipt']
    ledger = json.loads((args.output / 'storage-test-ledger.json').read_text())
    fast = {'receipt_state': receipt['state'], 'output_bytes': receipt['output_bytes'], 'storage_limit': 10000,
        'ledger_state': ledger['state'], 'established': receipt['state'] == 'complete' and receipt['output_bytes'] > 10000 and ledger['state'] == 'blocked-overrun'}
    write(args.output / 'FAST_EXIT_STORAGE_ADJUDICATION.json', fast)
    findings = {'schema': 'agi-alpha/resource-v2-defect-adjudication006/v1', 'source_sha256': EXPECTED,
        'sigterm': observation, 'fast_exit_storage': fast, 'both_defects_established': observation['established'] and fast['established'],
        'constraints': ['SIGTERM during initialization and execution must preserve an incomplete receipt and settle conservatively after terminating/reaping its owned worker group.', 'Final post-exit output usage above declared bounds must prevent complete state; blocked ledger alone does not qualify the run.'],
        'scope': 'Reproduced implementation defects on this Linux host. Small independent test ledgers are fixtures inside the enclosing20CPU campaign reservation, not renewed campaign allocations. No generated science or protected outcomes executed.'}
    write(args.output / 'ADJUDICATION.json', findings)
    print(json.dumps(findings))
    raise SystemExit(0 if findings['both_defects_established'] else 1)


if __name__ == '__main__':
    main()
