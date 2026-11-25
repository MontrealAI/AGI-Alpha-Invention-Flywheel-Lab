import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time


root = Path(__file__).resolve().parent
runtime = root.parents[1]
product = root / 'quote-source' / 'products' / 'alpha-genesis-harness'
program = product / 'scripts' / 'qualify_quote_workflow_006.py'
protocol = product / 'evidence' / 'LOCAL-QUOTE-PROTOCOL-006.json'
source_tree = 'c7fc43f31762992a59acd28d554a3448591ca50e'
scope = root / 'quote-manufacturing'
model = root / 'assets' / 'model.gguf'
server = runtime / 'models' / 'llama-b12242' / 'llama-server'
expected_first = ('5f2cca0214199364891517c1556f0611367738b275682ba533f57caf2bf6c93c',
                  'a7fcb99ddc5b8461cdc42e272b16500cdff1c47ac0d25311eb2dec944fad24bb')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def run_original_manufacturing():
    assert digest(program.read_bytes()) == 'd5635b8135ba8cb6e2692c679b4c03c3742e2dd2a8443993e9d19fdfb1d6b853'
    assert digest(protocol.read_bytes()) == '4eafe9112f48d34425adb8c744da0c40393188f650bcad1be0641bd293b693fb'
    actual_tree = subprocess.check_output(['git', 'rev-parse', 'HEAD:products/alpha-genesis-harness'],
                                          cwd=product, text=True).strip()
    assert actual_tree == source_tree
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--', '.'], cwd=product)
    spec = importlib.util.spec_from_file_location('historical_quote_006', program)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    original_read = module.read

    def read_scoped(path):
        data = original_read(path)
        if path == protocol:
            data['arms'] = [arm for arm in data['arms']
                            if arm['id'] in {'ordinary_direct_formula', 'manufacturing_construct'}]
        return data

    module.read = read_scoped
    original_generate = module.Runtime.generate
    calls = 0

    def observe_first(self, data, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            prompt = digest(data['prompt'].encode())
            schema = digest(json.dumps(data['json_schema'], sort_keys=True, separators=(',', ':'),
                                       ensure_ascii=False, allow_nan=False).encode())
            write(root / 'QUOTE-FIRST-REQUEST.json', {'prompt_sha256': prompt, 'schema_sha256': schema,
                   'matches_historical_request': (prompt, schema) == expected_first,
                   'configured_transport_timeout_seconds': self.timeout,
                   'max_output_tokens': data.get('max_output_tokens')})
            if (prompt, schema) != expected_first or self.timeout != 600:
                raise RuntimeError('The manufactured first request differs from the recorded historical condition.')
        return original_generate(self, data, *args, **kwargs)

    module.Runtime.generate = observe_first
    sys.argv = [str(program), '--binary', str(server), '--model', str(model),
                '--output', str(scope), '--model-receipt', str(root / 'assets' / 'MODEL-DOWNLOAD.json')]
    return module.main()


def coordinate():
    with (runtime / 'qwen-default.lock').open('a+b') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('The shared model lease is active.')
            return 75
        for port in (8080, 38461, 18767):
            with socket.socket() as connection:
                connection.settimeout(.3)
                if connection.connect_ex(('127.0.0.1', port)) == 0:
                    print('A model is active on a known local test port.')
                    return 75
        assert not scope.exists() and not (root / 'QUOTE-PREEMPT').exists()
        assert digest(server.read_bytes()) == 'fe211d00c4754aa67aaa492d2c755ab0f6ef60bf30eee3c0c74a3496189cde17'
        env = {key: os.environ[key] for key in ('PATH', 'LANG', 'LC_ALL', 'TMPDIR') if key in os.environ}
        env.update(LD_LIBRARY_PATH=str(server.parent), NO_PROXY='127.0.0.1,localhost', PYTHONUNBUFFERED='1')
        started = time.monotonic()
        preempted = False
        with (root / 'quote-driver.log').open('wb') as log:
            process = subprocess.Popen([sys.executable, '-B', __file__, '--driver'], cwd=product,
                                       env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            while process.poll() is None:
                if (root / 'QUOTE-PREEMPT').exists():
                    preempted = True
                    process.send_signal(signal.SIGINT)
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=5)
                    break
                time.sleep(1)
        summary = {'driver_exit': process.returncode, 'wall_seconds': time.monotonic() - started,
                   'production_preemption': preempted, 'scope': 'Historical quote 006 manufacturing arm only'}
        write(root / 'QUOTE-LEASE-CHECKPOINT.json', summary)
        print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == '__main__':
    if sys.argv[1:] == ['--driver']:
        try:
            raise SystemExit(run_original_manufacturing())
        except KeyboardInterrupt:
            raise SystemExit(130) from None
    raise SystemExit(coordinate())
