"""Actual signal probes of unchanged trusted-command supervisor, not legacy repair."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import time


def state(host_pid):
    try:
        raw = Path('/proc', str(host_pid), 'stat').read_text().rsplit(')', 1)[1].split()
        return {'state': raw[0], 'parent': int(raw[1]), 'start_ticks': int(raw[19])}
    except FileNotFoundError:
        return None


def descendants():
    own = int(Path('/proc/self/stat').read_text().split()[0])
    observed = {int(path.name): state(int(path.name)) for path in Path('/proc').iterdir() if path.name.isdigit()}
    result = {}
    for pid, item in observed.items():
        if item is None:
            continue
        current, seen = item['parent'], set()
        while current != own and current in observed and observed[current] and current not in seen:
            seen.add(current)
            current = observed[current]['parent']
        if current == own:
            ids = next(line for line in Path('/proc', str(pid), 'status').read_text().splitlines() if line.startswith('NSpid:')).split()[1:]
            result[pid] = {**item, 'namespace_pid': int(ids[-1])}
    return result


def wait_for(path, process, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists():
            try:
                item = json.loads(path.read_text())
            except json.JSONDecodeError:
                time.sleep(.002)
                continue
            if path.name == 'active.json':
                return item
            current = state(item['host_pid'])
            if current and current['state'] in {'T', 't'}:
                return item
        if process.poll() is not None:
            raise AssertionError('DRIVER_EXITED_BEFORE_BARRIER ' + path.name)
        time.sleep(.002)
    raise TimeoutError('BARRIER_TIMEOUT ' + path.name)


def reap():
    observed, deadline = [], time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            pid, status = os.waitpid(-1, os.WNOHANG)
            if pid:
                observed.append({'namespace_pid': pid, 'wait_status': status})
            else:
                time.sleep(.005)
        except ChildProcessError:
            return observed, True
    return observed, False


def run(root, output):
    if ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0) != 0:
        raise RuntimeError('SUBREAPER_UNAVAILABLE')
    output.mkdir(parents=True, exist_ok=False)
    initial = resource.getrusage(resource.RUSAGE_CHILDREN)
    before, wall = time.process_time(), time.monotonic()
    wrapper = root / 'experiments/resource006_v3.py'
    driver = Path(__file__).with_name('interruption_driver.py')
    source_before = hashlib.sha256(wrapper.read_bytes()).hexdigest()
    trials = []
    for mode in ['before-import', 'before-reservation', 'initialization', 'active', 'teardown']:
        case = output / mode
        command = [sys.executable, '-I', str(driver), str(root), str(case), mode]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True,
                                   env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
        observed = {}
        try:
            barrier = wait_for(case / (mode + '.json'), process)
            observed.update(descendants())
            process.send_signal(signal.SIGINT)
            if mode in {'before-import', 'before-reservation', 'teardown'}:
                process.send_signal(signal.SIGTERM)
                process.send_signal(signal.SIGCONT)
                second_phase = mode
            else:
                if mode == 'initialization':
                    process.send_signal(signal.SIGCONT)
                wait_for(case / 'cleanup.json', process)
                observed.update(descendants())
                process.send_signal(signal.SIGTERM)
                process.send_signal(signal.SIGCONT)
                second_phase = 'signal-blocked terminal cleanup'
            stdout, stderr = process.communicate(timeout=10)
            reaped, no_children = reap()
            final_states = {str(pid): state(pid) for pid in observed}
            same_live = {str(pid): item for pid, identity in observed.items() if (item := state(pid)) and item['start_ticks'] == identity['start_ticks'] and item['state'] != 'Z'}
            receipt_path = case / 'actual-run/RECEIPT.json'
            receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else None
            ledger_path = case / 'resource-ledger.json'
            ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else None
            early = mode in {'before-import', 'before-reservation'}
            if early:
                lifecycle_pass = receipt is None and ledger is None and not (case / 'actual-run').exists()
            else:
                lifecycle_pass = receipt is not None and ledger is not None and (receipt['state'] == 'interrupted' if mode != 'teardown' else receipt['state'] == 'complete')
            trials.append({'mode': mode, 'passed': lifecycle_pass and no_children and not same_live,
                           'first_signal': 'SIGINT', 'second_signal': 'SIGTERM', 'second_signal_phase': second_phase,
                           'returncode': process.returncode, 'no_live_descendant_with_original_identity': not same_live,
                           'all_children_reaped': no_children, 'barrier': barrier, 'observed_descendants': observed,
                           'final_states': final_states, 'reaped_adopted_descendants': reaped,
                           'receipt_state': receipt['state'] if receipt else None,
                           'conservative_cpu_reservation_seconds': sum(x['budget_cpu_seconds'] for x in ledger['runs'].values()) if ledger else 0,
                           'receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest() if receipt else None,
                           'stdout': stdout, 'stderr': stderr,
                           'interpretation': 'Before reservation/worker launch there is no owned evidence or child and no terminal receipt is required.' if early else 'Teardown signals arrive after trusted child already exited; completed receipt remains valid and no work survives.' if mode == 'teardown' else 'Second signal arrives at an established barrier inside masked cleanup; terminal receipt preserved and process tree dead.'})
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=3)
            for pid, item in observed.items():
                current = state(pid)
                if current and current['start_ticks'] == item['start_ticks'] and current['state'] != 'Z':
                    try:
                        os.kill(item['namespace_pid'], signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            reap()
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    result = {'schema': 'agi-alpha/consequential009-supervisor-signal-verification/v1', 'passed': all(x['passed'] for x in trials),
              'source_sha256_before': source_before, 'source_sha256_after': hashlib.sha256(wrapper.read_bytes()).hexdigest(),
              'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'driver_sha256': hashlib.sha256(driver.read_bytes()).hexdigest(),
              'trials': trials, 'resources': {'verifier_cpu_seconds': time.process_time() - before, 'wall_seconds': time.monotonic() - wall,
                                            'waited_child_cpu_seconds': usage.ru_utime + usage.ru_stime - initial.ru_utime - initial.ru_stime,
                                            'conservative_cpu_reservations_seconds': sum(x['conservative_cpu_reservation_seconds'] for x in trials), 'complete_monetary_cost': None},
              'scope': 'Actual catchable signals at established barriers in a verifier driver importing unchanged trusted-command resource006_v3.run; hooks pause before import/reservation, PENDING creation, running child+grandchild, and terminal receipt. This is not testing every application-internal phase, arbitrary adversarial process escape, SIGKILL/powerloss durability, or repairing frozen run_cycle legacy startup.',
              'historical_legacy_failure_preserved': True}
    result['passed'] &= result['source_sha256_before'] == result['source_sha256_after']
    with (output / 'REPORT.json').open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.root.resolve(), args.output.resolve())
    print(json.dumps({'passed': result['passed'], 'trials': len(result['trials']), 'resources': result['resources']}))
    raise SystemExit(0 if result['passed'] else 1)
