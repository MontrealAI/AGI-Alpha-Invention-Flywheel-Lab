"""Prospective Linux-only build and baseline qualification; no candidate/model mode."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import signal
import shutil
import socket
import stat
import subprocess
import sys
import tarfile
import time
import urllib.request

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PRODUCT = REPO / 'products/alpha-genesis-harness'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def wait_owned_process(process, timeout, *, capture=False):
    """Reap the entire owned worker session on every exceptional wait exit."""
    try:
        return process.communicate(timeout=timeout) if capture else process.wait(timeout=timeout)
    finally:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


def strict_json(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError('Duplicate output key')
            result[key] = item
        return result
    return json.loads(value, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def same_json(left, right):
    # Independent host relation, never the candidate's equality implementation.
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if type(left) in (int, float) and type(right) in (int, float):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(same_json(x, y) for x, y in zip(left, right))
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(same_json(left[k], right[k]) for k in left)
    return left == right


def guest_payload(result):
    if result.get('worker_returncode') != 0 or result.get('output_overflow'):
        raise ValueError('Guest worker failed or exceeded output capacity')
    if result.get('outcome') != 'RETURN' and not (result.get('outcome') == 'EXIT' and result.get('exit_code') == 0):
        raise ValueError('Guest did not complete successfully')
    value = strict_json(result.get('stdout', ''))
    if not isinstance(value, dict):
        raise ValueError('Guest result must be an object')
    return value


def snapshot(root):
    records = {}
    for f in sorted(Path(root).rglob('*')):
        if f.is_symlink():
            records[f.relative_to(root).as_posix()] = {'symlink': os.readlink(f)}
        elif f.is_file():
            records[f.relative_to(root).as_posix()] = {'sha256': sha(f), 'bytes': f.stat().st_size}
        elif not f.is_dir():
            raise ValueError('Nonregular staging asset')
    return records


def download(pin, target):
    # Fixed official public URL; no credentials, package indexes or retries.
    with urllib.request.urlopen(pin['url'], timeout=60) as response, target.open('xb') as out:
        total = 0
        while block := response.read(1024 * 1024):
            total += len(block)
            if total > pin['max_bytes']:
                raise ValueError('Download exceeds preregistered size envelope')
            out.write(block)
    if sha(target) != pin['sha256']:
        raise ValueError('Download digest mismatch: ' + target.name)
    return {'file': target.name, 'bytes': total, 'sha256': sha(target), 'url': pin['url']}


def extract(archive, destination):
    destination.mkdir()
    # Only pinned trusted build archives; reject path escape and device entries.
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        if len(members) > 100000 or sum(m.size for m in members) > 4 * 1024**3:
            raise ValueError('Archive expansion exceeds build envelope')
        for member in members:
            path = Path(member.name)
            if path.is_absolute() or '..' in path.parts or member.isdev():
                raise ValueError('Unsafe build archive member')
        tar.extractall(destination, filter='data')


def build_wasi_all(source, command, environment):
    """Equivalent to upstream make_wasi_python's make step, without its launcher."""
    cpu_count = getattr(os, 'process_cpu_count', os.cpu_count)
    command(['make', '--jobs', str(cpu_count() or 1), 'all'],
            source / 'cross-build/wasm32-wasip1', environment)


def main(args):
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    evidence = work / 'evidence'; evidence.mkdir()
    started = time.time()
    record = {'schema': 'harness-wasi-baseline-qualification/v1', 'status': 'FAIL',
              'stage': 'preflight', 'started_at_unix': started, 'downloads': [], 'commands': [],
              'capability_checks': {}, 'resource_checks': {}, 'baseline_cases': [],
              'model_calls': 0, 'candidate_execution': False, 'native_codex_gate_changed': False,
              'complete_cost_known': False, 'api_paid_requests': 0}
    source_before = {}
    def save():
        record['finished_at_unix'] = time.time()
        record['wall_seconds'] = time.time() - started
        record['child_cpu_seconds'] = sum(resource.getrusage(resource.RUSAGE_CHILDREN)[x] for x in (0, 1))
        dump(evidence / 'RESULT.json', record)
    def remaining():
        seconds = platform_start + 360 * 60 - 300 - time.time()
        if seconds <= 0:
            raise TimeoutError('Platform window reached; reserve retained for evidence upload')
        return seconds
    def command(argv, cwd, env=None):
        index = len(record['commands']) + 1
        log = work / ('command-%02d.log' % index)
        t = time.monotonic()
        row = {'argv': list(map(str, argv)), 'returncode': None}
        record['commands'].append(row); save()
        process = None
        try:
            timeout_seconds = remaining()
            with log.open('wb') as stream:
                process = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env, stdout=stream,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                row['returncode'] = wait_owned_process(process, timeout_seconds)
            if row['returncode']:
                raise RuntimeError('Build command %d failed with exit %d' % (index, row['returncode']))
        finally:
            if process is not None:
                row['returncode'] = process.returncode
            row['wall_seconds'] = time.monotonic() - t
            if log.exists():
                row['log_sha256'] = sha(log); row['log_bytes'] = log.stat().st_size
                with log.open('rb') as stream:
                    stream.seek(max(0, log.stat().st_size - 128 * 1024))
                    (evidence / log.name).write_bytes(stream.read())
                row['published_log_scope'] = 'Last128KiB; full original log hash and byte count retained'
            save()
    try:
        if platform.system() != 'Linux' or platform.machine() != 'x86_64':
            raise ValueError('Only Linux x86_64 is registered')
        platform_start = int(os.environ['AGI_JOB_START_EPOCH'])
        if not 0 <= started - platform_start < 360 * 60:
            raise ValueError('Missing or invalid platform start marker')
        protocol_path = HERE / 'PROTOCOL.json'
        if sha(protocol_path) != args.protocol_sha256:
            raise ValueError('Protocol differs from explicitly selected public preregistration')
        protocol = strict_json(protocol_path.read_text())
        record['attempt_id'] = protocol['attempt_id']
        revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
        if revision != args.source_sha or len(revision) != 40:
            raise ValueError('Checkout differs from selected public source revision')
        if subprocess.check_output(['git', 'status', '--porcelain'], cwd=REPO, text=True).strip():
            raise ValueError('Qualification requires a clean published checkout')
        for relative, expected in protocol['baseline_source_sha256'].items():
            if sha(REPO / relative) != expected:
                raise ValueError('Frozen48 baseline source differs')
        if sha(HERE / 'CASES.json') != protocol['cases_sha256']:
            raise ValueError('Baseline64-case protocol bytes changed')
        source_files = [*HERE.glob('*'), REPO / '.github/workflows/harness-wasi-v1.yml',
                        *(REPO / name for name in protocol['baseline_source_sha256'])]
        source_before = {str(f.relative_to(REPO)): sha(f) for f in source_files if f.is_file()}
        record.update(source_revision=revision, source_product_tree=subprocess.check_output(
            ['git', 'rev-parse', 'HEAD:products/alpha-genesis-harness'], cwd=REPO, text=True).strip(),
            source_sha256=source_before, protocol_sha256=args.protocol_sha256,
            baseline_revision=protocol['baseline_revision'], host={'platform':platform.platform(), 'python':sys.version},
            ci={key: os.environ.get(key) for key in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_SHA')})
        shutil.copyfile(protocol_path, evidence / 'PROTOCOL.json')
        shutil.copyfile(HERE / 'CASES.json', evidence / 'CASES.json')
        record['stage'] = 'download'; save()
        downloads = work / 'downloads'; downloads.mkdir()
        for key, pin in protocol['downloads'].items():
            record['downloads'].append(download(pin, downloads / pin['filename'])); save()
        record['stage'] = 'trusted_build'; save()
        extract(downloads / protocol['downloads']['cpython']['filename'], work / 'cpython')
        extract(downloads / protocol['downloads']['sdk']['filename'], work / 'sdk')
        source = work / 'cpython/Python-3.15.2'
        sdk = work / 'sdk/wasi-sdk-33.0-x86_64-linux'
        if not (sdk / 'bin/clang').is_file():
            raise ValueError('Pinned SDK archive has unexpected layout')
        build_env = {k: v for k, v in os.environ.items() if k in {'PATH', 'LANG', 'LC_ALL', 'TMPDIR'}}
        build_env['PYTHONDONTWRITEBYTECODE'] = '1'
        command(['cc', '--version'], work, build_env)
        command([sdk / 'bin/clang', '--version'], work, build_env)
        # Official configuration and build steps; avoid upstream convenience launcher,
        # which preopens its full source checkout. No WASI guest runs during build.
        command([sys.executable, 'Platforms/WASI', 'build-python', '--', '--without-ensurepip'], source, build_env)
        command([sys.executable, 'Platforms/WASI', 'configure-host', '--wasi-sdk', sdk,
                 '--host-runner', 'false', '--', '--prefix=/sandbox/python',
                 '--without-ensurepip', '--disable-test-modules'], source, build_env)
        build_wasi_all(source, command, build_env)
        wasm = source / 'cross-build/wasm32-wasip1/python.wasm'
        if not wasm.is_file():
            raise ValueError('Official build did not produce expected WASIp1 interpreter')
        record['wasm_sha256'] = sha(wasm)
        venv = work / 'venv'
        command([sys.executable, '-m', 'venv', venv], work, build_env)
        python = venv / 'bin/python'
        command([python, '-m', 'pip', 'install', '--no-index', '--no-deps',
                 downloads / protocol['downloads']['wasmtime_python']['filename']], work, build_env)
        record['stage'] = 'capability_negatives'; save()
        stage = work / 'stage'; stage.mkdir()
        library = stage / 'python/lib/python3.15'; library.parent.mkdir(parents=True)
        # Public pinned stdlib only. No repository, home, cache or build-tree mount.
        shutil.copytree(source / 'Lib', library, symlinks=False,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copyfile(HERE / 'guest_driver.py', stage / 'guest_driver.py')
        shutil.copyfile(PRODUCT / 'bridge/instruments.py', stage / 'baseline.py')
        (stage / 'fixture.txt').write_text('public WASI read fixture\n')
        outside = work / 'outside.txt'; outside.write_text('PUBLIC SYNTHETIC OUTSIDE SENTINEL\n')
        (stage / 'escape-link').symlink_to(outside)
        stage_before = snapshot(stage); outside_hash = sha(outside)
        dump(evidence / 'STAGING-INVENTORY.json', stage_before)
        worker_counter = 0
        def invoke(mode, guest=None, timeout=None):
            nonlocal worker_counter
            worker_counter += 1
            request = {'mode':mode, 'protocol':protocol, 'wasm':str(wasm), 'wasm_sha256':record['wasm_sha256'],
                       'stage':str(stage), 'guest':guest}
            req = work / ('worker-%03d-request.json' % worker_counter)
            out = work / ('worker-%03d-result.json' % worker_counter)
            progress = work / ('worker-%03d-progress.json' % worker_counter)
            request['progress'] = str(progress)
            dump(req, request)
            t = time.monotonic()
            try:
                timeout_seconds = min(timeout or protocol['guest_limits']['worker_wall_seconds'], remaining())
                proc = subprocess.Popen([str(python), '-I', '-B', str(HERE / 'worker.py'), str(req), str(out)],
                                        cwd=work, env={'PATH':os.defpath, 'LANG':'C.UTF-8',
                                                      'WASI_HOST_SENTINEL':'PUBLIC_NOT_A_CREDENTIAL'},
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                _stdout, stderr = wait_owned_process(proc, timeout_seconds, capture=True)
                result = strict_json(out.read_text()) if out.exists() else {'outcome':'WORKER_FAILED'}
                result['worker_returncode'] = proc.returncode
                result['host_stderr'] = stderr[-4096:].decode(errors='replace')
            except subprocess.TimeoutExpired:
                result = {'outcome':'WORKER_TIMEOUT'}
            result['supervisor_wall_seconds'] = time.monotonic() - t
            result['progress'] = strict_json(progress.read_text()) if progress.exists() else None
            dump(evidence / ('worker-%03d.json' % worker_counter), result)
            return result
        listener = socket.socket(); listener.bind(('127.0.0.1', 0)); listener.listen(1); listener.settimeout(0.1)
        try:
            result = invoke('python', {'mode':'capabilities', 'outside_path':str(outside), 'port':listener.getsockname()[1]})
            payload = guest_payload(result)
            if payload.get('platform') != 'wasi':
                raise ValueError('Capability checks did not run under CPython WASI')
            checks = payload['checks']
            expected = set(protocol['required_capability_checks'])
            record['capability_checks'] = checks
            if set(checks) != expected or any(value is not True for value in checks.values()):
                raise ValueError('Capability denial or positive read check failed')
            try:
                connection, _ = listener.accept(); connection.close()
                raise ValueError('Guest reached the host loopback sentinel')
            except socket.timeout:
                pass
        finally:
            listener.close()
        if snapshot(stage) != stage_before or sha(outside) != outside_hash:
            raise ValueError('Guest mutated staging or outside sentinel')
        record['stage'] = 'resource_negatives'; save()
        for mode, expected in [('fuel', 'OUT_OF_FUEL'), ('epoch', 'INTERRUPT'), ('memory', None)]:
            result = invoke(mode)
            accepted = (result.get('outcome') == 'RETURN' and result.get('value') == {'within':1, 'beyond':-1}) if mode == 'memory' else (
                result.get('outcome') == 'TRAP' and expected in result.get('trap_code', ''))
            record['resource_checks'][mode] = accepted
            if not accepted:
                raise ValueError('Resource boundary failed: ' + mode)
        result = invoke('python', {'mode':'output_limit'})
        record['resource_checks']['output_limit'] = result.get('output_overflow') is True
        if not record['resource_checks']['output_limit']:
            raise ValueError('Output limit did not stop the real guest output route')
        # Exercise supervisor cancellation independently of fuel/epoch completion.
        result = invoke('watchdog', timeout=protocol['guest_limits']['watchdog_probe_seconds'])
        record['resource_checks']['worker_watchdog'] = result['outcome'] == 'WORKER_TIMEOUT' and result['progress'] == {'phase':'entering_wasm', 'mode':'watchdog'}
        if not record['resource_checks']['worker_watchdog']:
            raise ValueError('Disposable worker watchdog did not cancel')
        (stage / 'escape-link').unlink(); (stage / 'fixture.txt').unlink()
        baseline_stage = snapshot(stage)
        if any('symlink' in row for row in baseline_stage.values()):
            raise ValueError('Baseline stage contains symlinks')
        record['stage'] = 'baseline64'; save()
        cases = strict_json((HERE / 'CASES.json').read_text())['cases']
        if len(cases) != 64:
            raise ValueError('Registered baseline case denominator changed')
        for case in cases:
            guest = {k:case[k] for k in ('instrument', 'inputs', 'max_operations')}
            result = invoke('python', {'mode':'baseline', **guest})
            value = guest_payload(result)
            accepted = value.get('source_sha256') == protocol['baseline_source_sha256']['products/alpha-genesis-harness/bridge/instruments.py']
            accepted = accepted and (value.get('kind') == 'error' if case.get('expect_error') else (
                value.get('kind') == 'value' and same_json(value.get('output'), case['expected'])))
            record['baseline_cases'].append({'id':case['id'], 'accepted':bool(accepted), 'observed':value})
            save()
        if snapshot(stage) != baseline_stage or sha(outside) != outside_hash:
            raise ValueError('Baseline mutated staging or outside sentinel')
        if not all(row['accepted'] for row in record['baseline_cases']):
            raise ValueError('Unchanged baseline failed one or more oracle cases')
        record['status'] = 'PASS'
        record['stage'] = 'complete'
    except Exception as error:
        record['failure'] = {'type':type(error).__name__, 'message':str(error)[:4096]}
    finally:
        record['source_unchanged'] = bool(source_before) and all((REPO / f).is_file() and sha(REPO / f) == value for f, value in source_before.items())
        if not record['source_unchanged']:
            record['status'] = 'FAIL'
        save()
    print(json.dumps({'status':record['status'], 'stage':record['stage'], 'failure':record.get('failure'),
                      'baseline_cases_executed':len(record['baseline_cases']), 'model_calls':0}, indent=2))
    return 0 if record['status'] == 'PASS' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--protocol-sha256', required=True)
    raise SystemExit(main(parser.parse_args()))
