"""Launch a source-bound companion from its downloaded ZIP on the current OS."""

import argparse
import json
import os
import platform
from pathlib import Path
from queue import Empty, Queue
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic
from urllib.request import ProxyHandler, Request, build_opener

from qualify_frontier_member import install, require


def launch(package, fingerprint, revision):
    with TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        destination = root / 'companion'
        manifest = install(package, destination, {'sha256': fingerprint})
        require(manifest['id'] == 'frontier-harness-executor'
                and manifest['source'].endswith('/commit/' + revision), 'Unexpected companion source')
        system = platform.system()
        launcher = {'Windows': 'Launch-FRONTIER.cmd', 'Darwin': 'Launch-FRONTIER.command',
                    'Linux': 'Launch-FRONTIER.sh'}[system]
        command = ['cmd.exe', '/d', '/c', launcher] if system == 'Windows' else ['sh', launcher]
        process = subprocess.Popen(
            [*command, '--port', '0', '--no-browser', '--workspace', str(root / 'private workspace')],
            cwd=destination, env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1'}, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
        )
        try:
            pending = Queue()
            def read_output():
                for line in process.stdout:
                    pending.put(line)
                pending.put(None)

            Thread(target=read_output, daemon=True).start()
            start = monotonic()
            origin = None
            pairing_code_printed = False
            while monotonic() - start < 20 and not origin:
                try:
                    line = pending.get(timeout=max(0, 20 - (monotonic() - start)))
                except Empty:
                    break
                if line is None:
                    break
                if line.startswith('FRONTIER Ω one-use pairing code: '):
                    pairing_code_printed = len(line.strip().split()[-1]) == 43
                if line.startswith('ALPHA GENESIS HARNESS: http://127.0.0.1:'):
                    origin = line.strip().split()[-1]
            require(origin and pairing_code_printed, 'Companion did not present the local pairing entrance')
            local_http = build_opener(ProxyHandler({}))
            with local_http.open(origin + '/?setup=intelligence&route=api&lang=fr', timeout=5) as page:
                require(b'native-intelligence.js' in page.read() and page.headers['X-Frame-Options'] == 'DENY',
                        'Native guided setup was unavailable')
            with local_http.open(Request(origin + '/api/session', headers={'X-Harness-Client': 'browser'}), timeout=5) as response:
                token = json.load(response)['token']
            request = Request(origin + '/api/frontier-intelligence/status', data=b'{}',
                              headers={'Content-Type': 'application/json', 'X-Harness-Token': token})
            with local_http.open(request, timeout=5) as response:
                status = json.load(response)
            require(status['profiles'] == [], 'A clean companion must have no inherited provider account')
            return {'source_commit': revision, 'sha256': fingerprint, 'version': manifest['version'],
                    'os': system, 'launcher': launcher, 'pairing_code_available': True,
                    'private_setup_served': True, 'default_provider_profiles': 0, 'inference_calls': 0}
        finally:
            if system == 'Windows' and process.poll() is None:
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=10)
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            process.stdout.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('sha256')
    parser.add_argument('source_commit')
    args = parser.parse_args()
    print(json.dumps(launch(args.archive, args.sha256, args.source_commit), sort_keys=True))
