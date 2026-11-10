"""Trusted guest entry point. No model-generated source is admitted by v1."""
import hashlib
import json
import os
from pathlib import Path
import sys


def capability_checks(request):
    checks = {}
    def denied(name, operation):
        try:
            operation()
        except (OSError, NotImplementedError, ImportError):
            checks[name] = True
        else:
            checks[name] = False
    root = Path('/sandbox')
    fixture = root / 'fixture.txt'
    checks['public_read'] = fixture.read_text() == 'public WASI read fixture\n'
    denied('create_file', lambda: (root / 'created.txt').write_text('unexpected'))
    denied('overwrite_file', lambda: fixture.write_text('unexpected'))
    denied('append_file', lambda: open(fixture, 'a').write('unexpected'))
    denied('create_directory', lambda: (root / 'created-dir').mkdir())
    denied('rename', lambda: fixture.rename(root / 'renamed.txt'))
    denied('delete', lambda: fixture.unlink())
    denied('absolute_outside_read', lambda: Path(request['outside_path']).read_bytes())
    denied('traversal_read', lambda: (root / '..' / 'outside.txt').read_bytes())
    denied('symlink_escape_read', lambda: (root / 'escape-link').read_bytes())
    denied('symlink_escape_write', lambda: (root / 'escape-link').write_text('unexpected'))
    denied('create_symlink', lambda: (root / 'created-link').symlink_to(request['outside_path']))
    checks['environment_not_inherited'] = dict(os.environ) == {}
    def connect():
        import socket
        with socket.socket() as sock:
            sock.settimeout(1)
            sock.connect(('127.0.0.1', request['port']))
    denied('loopback_network', connect)
    def spawn():
        import subprocess
        subprocess.run(['/bin/sh', '-c', 'exit 0'], check=True)
    denied('process_spawn', spawn)
    return {'checks': checks, 'python': sys.version, 'platform': sys.platform}


request = json.loads(sys.argv[1])
mode = request['mode']
if mode == 'capabilities':
    result = capability_checks(request)
elif mode == 'baseline':
    # The source file is readable solely from the dedicated read-only preopen.
    sys.path.insert(0, '/sandbox')
    import baseline
    source_hash = hashlib.sha256(Path(baseline.__file__).read_bytes()).hexdigest()
    try:
        value = baseline.evaluate(request['instrument'], request['inputs'], request['max_operations'])
        result = {'kind': 'value', 'output': value['output'], 'source_sha256': source_hash}
    except Exception as error:
        result = {'kind': 'error', 'type': type(error).__name__, 'message': str(error)[:2048], 'source_sha256': source_hash}
elif mode == 'output_limit':
    # Exercise the real WASI/Python output route, not a synthetic callback call.
    while True:
        os.write(1, b'x' * 4096)
else:
    raise ValueError('Unregistered guest mode')
print(json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')))
