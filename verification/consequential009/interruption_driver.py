import importlib.util
import json
import os
from pathlib import Path
import signal
import sys

root, output, mode = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
output.mkdir(parents=True, exist_ok=False)


def pause(stage):
    identity = {'stage': stage, 'namespace_pid': os.getpid(), 'host_pid': int(Path('/proc/self/stat').read_text().split()[0])}
    with (output / (stage + '.json')).open('x') as stream:
        json.dump(identity, stream)
    os.kill(os.getpid(), signal.SIGSTOP)


if mode == 'before-import':
    pause('before-import')

spec = importlib.util.spec_from_file_location('source_pinned_resource_v3', root / 'experiments/resource006_v3.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

if mode == 'before-reservation':
    original_normalize = runner.normalize_command
    def normalize(command):
        pause('before-reservation')
        return original_normalize(command)
    runner.normalize_command = normalize

if mode == 'initialization':
    original_write = runner._write
    def write(path, value):
        if path.name == 'PENDING.json':
            pause('initialization')
        return original_write(path, value)
    runner._write = write

original_final = runner._final_receipt
def final(receipt, path):
    if mode in {'initialization', 'active'} and receipt['state'] == 'interrupted':
        pause('cleanup')
    if mode == 'teardown':
        pause('teardown')
    return original_final(receipt, path)
runner._final_receipt = final

payload = 'pass'
if mode == 'active':
    payload = '''import json,os,subprocess,sys,time
from pathlib import Path
p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
with Path(sys.argv[1]).open('x') as stream:
 json.dump({'namespace_pid':os.getpid(),'host_pid':int(Path('/proc/self/stat').read_text().split()[0]),'child_namespace_pid':p.pid},stream)
time.sleep(30)
'''
command = [sys.executable, '-c', payload, str(output / 'active.json')]
limits = {'wall_seconds': 10, 'cpu_seconds': 5, 'memory_bytes': 128 * 1024 ** 2,
          'output_bytes': 1024 ** 2, 'storage_bytes': 4 * 1024 ** 2}
result = runner.run(command, output / 'actual-run', output / 'resource-ledger.json', mode, limits, root)
with (output / 'driver-result.json').open('x') as stream:
    json.dump(result, stream, indent=2)
