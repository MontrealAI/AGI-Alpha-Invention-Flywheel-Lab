"""Launch a source-bound companion from its downloaded ZIP on the current OS."""

import argparse
import json
import os
import platform
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
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
        guided = 'START-HERE.html' in manifest['file_sha256']
        runtime = destination / 'runtime' if guided else destination
        system = platform.system()
        launcher = {'Windows': 'Launch-FRONTIER.cmd', 'Darwin': 'Launch-FRONTIER.command',
                    'Linux': 'Launch-FRONTIER.sh'}[system]
        command = ['cmd.exe', '/d', '/c', launcher] if system == 'Windows' else ['sh', launcher]
        process = subprocess.Popen(
            [*command, '--port', '0', '--no-browser', '--workspace', str(root / 'private workspace')],
            cwd=runtime, env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1'}, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
        )
        try:
            pending = Queue()
            def read_output():
                for line in process.stdout:
                    pending.put(line)
                pending.put(None)

            Thread(target=read_output, daemon=True).start()
            started_at = monotonic()
            deadline = started_at + 60
            origin = None
            pairing_code_printed = False
            safe_diagnostics = []
            while monotonic() < deadline and not origin:
                try:
                    line = pending.get(timeout=max(0, deadline - monotonic()))
                except Empty:
                    break
                if line is None:
                    break
                if line.startswith('FRONTIER Ω one-use pairing code: '):
                    pairing_code_printed = len(line.strip().split()[-1]) == 43
                if line.startswith('ALPHA GENESIS HARNESS: http://127.0.0.1:'):
                    origin = line.strip().split()[-1]
                if line.startswith(('FRONTIER requires Python', 'Connector could not start.')):
                    safe_diagnostics.append(line.strip())
            require(origin and pairing_code_printed, 'Companion did not present the local pairing entrance '
                    f'(exit={process.poll()}, pairing_announced={pairing_code_printed}, '
                    f'loopback_announced={bool(origin)}, reported={safe_diagnostics})')
            startup_ms = round((monotonic() - started_at) * 1000)
            local_http = build_opener(ProxyHandler({}))
            hardware = None
            with local_http.open(origin + '/?setup=intelligence&route=api&lang=fr', timeout=5) as page:
                require(b'native-intelligence.js' in page.read() and page.headers['X-Frame-Options'] == 'DENY',
                        'Native guided setup was unavailable')
            if guided:
                for language in ('en', 'fr'):
                    with local_http.open(origin + f'/frontier-connect?lang={language}', timeout=5) as page:
                        require(page.headers['X-Frame-Options'] == 'DENY' and
                                f'<html lang="{language}">'.encode() in page.read(),
                                'Native pairing approval was unavailable')
                probe = 'from pathlib import Path; import json; from bridge.intelligence_profiles import _host_info; '
                probe += 'print(json.dumps(_host_info(Path.cwd())))'
                hardware = json.loads(subprocess.check_output([sys.executable, '-B', '-c', probe], cwd=runtime, timeout=10))
                require(hardware['system'] == system and hardware['architecture'] == platform.machine()
                        and hardware['physical_memory_bytes'] > 0 and hardware['available_workspace_bytes'] > 0,
                        'Packaged local setup could not measure this system')
            with local_http.open(Request(origin + '/api/session', headers={'X-Harness-Client': 'browser'}), timeout=5) as response:
                token = json.load(response)['token']
            request = Request(origin + '/api/frontier-intelligence/status', data=b'{}',
                              headers={'Content-Type': 'application/json', 'X-Harness-Token': token})
            with local_http.open(request, timeout=5) as response:
                status = json.load(response)
            require(status['profiles'] == [], 'A clean companion must have no inherited provider account')
            return {'source_commit': revision, 'sha256': fingerprint, 'version': manifest['version'],
                    'os': system, 'architecture': platform.machine(), 'interpreter': platform.python_version(),
                    'launcher': ('runtime/' if guided else '') + launcher, 'pairing_code_available': True,
                    'native_pairing_in_both_languages': guided,
                    'private_setup_served': True, 'default_provider_profiles': 0, 'inference_calls': 0,
                    'startup_ms': startup_ms,
                    **({'physical_memory_bytes': hardware['physical_memory_bytes']} if hardware else {})}
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
