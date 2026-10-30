import argparse
import hashlib
import json
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

COMMON = ['anyio==4.15.1', 'certifi==2026.10.23', 'h11==0.16.0', 'httpcore==1.0.9', 'idna==3.20', 'iniconfig==2.3.1', 'packaging==26.3', 'pluggy==1.7.0', 'pydantic==1.10.27', 'pytest==8.3.5', 'sniffio==1.3.1', 'typing_extensions==4.16.0']
ARMS = {'baseline': ['fastapi==0.99.1', 'starlette==0.27.0', 'httpx==0.27.2'], 'target': ['fastapi==0.110.1', 'starlette==0.37.2', 'httpx==0.28.1']}


def setup(directory, output):
    initial_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    started_all = time.monotonic()
    directory, output = Path(directory).resolve(), Path(output).resolve()
    if directory.exists() or output.exists():
        raise FileExistsError('New environment and output directories required')
    directory.mkdir(parents=True)
    output.mkdir(parents=True)
    uv = shutil.which('uv') or str(Path(sys.executable).with_name('uv'))
    if not Path(uv).is_file():
        raise ValueError('Free uv installer unavailable')
    receipts = []
    for arm, dependencies in ARMS.items():
        environment = directory / arm
        commands = [[uv, 'venv', '--python', sys.executable, str(environment)],
                    [uv, 'pip', 'install', '--python', str(environment / 'bin/python'), *COMMON, *dependencies]]
        for index, command in enumerate(commands):
            started = time.monotonic()
            logfile = output / (arm + '-' + str(index) + '.log')
            with logfile.open('xb') as stream:
                result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=120)
            receipts.append({'arm': arm, 'command': command, 'returncode': result.returncode, 'wall_seconds': time.monotonic()-started,
                             'log_sha256': hashlib.sha256(logfile.read_bytes()).hexdigest()})
            if result.returncode:
                (output / 'FAILED.json').write_text(json.dumps(receipts, indent=2)+'\n')
                raise ValueError('Fresh environment setup failed; preserve logs')
    final_cpu = resource.getrusage(resource.RUSAGE_CHILDREN)
    (output / 'SETUP.json').write_text(json.dumps({'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'receipts': receipts,
                                                'packages': {arm: COMMON+dependencies for arm, dependencies in ARMS.items()},
                                                'wall_seconds': time.monotonic()-started_all,
                                                'waited_child_cpu_seconds': final_cpu.ru_utime+final_cpu.ru_stime-initial_cpu.ru_utime-initial_cpu.ru_stime,
                                                'own_cpu_seconds': time.process_time(), 'scope': 'Free package installation, inherited approved proxy environment;120s timeout per command; no generated code, no paid provider call; monetary project/inference costs unknown.'}, indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    setup(args.directory, args.output)
