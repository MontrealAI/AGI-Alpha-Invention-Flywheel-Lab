"""Run the registered trial in a freshly extracted IGNITION recipient; keep CT local."""
import argparse
from array import array
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile

import numpy as np


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def trial(archive, observations):
    inputs = json.loads((observations / 'window_inputs.json').read_text())
    rows = []
    with tempfile.TemporaryDirectory(prefix="ignition-qualification-") as td:
        root = Path(td)
        with zipfile.ZipFile(archive) as z:
            if any(Path(name).is_absolute() or '..' in Path(name).parts for name in z.namelist()):
                raise ValueError('unexpected member path')
            z.extractall(root)
        env = {'PATH': os.defpath, 'HOME': td, 'TMPDIR': td}
        cli = [sys.executable, '-IB', str(root/'scroll_tool.py')]
        checked = subprocess.run(cli + ['self-check', '--cache', str(root/'compile')], cwd=td, env=env,
                                 check=True, capture_output=True)
        spec = importlib.util.spec_from_file_location('recipient', root/'scroll_tool.py')
        operator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(operator)
        libs = {a:operator.compiled(a,root/'compile') for a in operator.ARMS}
        for w in inputs['tiles']:
            path = observations/'research_data'/w['filename']
            raw = path.read_bytes()
            if digest(raw) != w['sha256'] or len(raw) != 17 * 384 * 384:
                raise ValueError('source window mismatch')
            # Each independent process invocation exercises the public CLI with exactly these recipient bytes.
            verified = subprocess.run(cli + ['verify','--input',str(path),'--cache', str(root/'compile')],
                                      cwd=td,env=env,check=True,capture_output=True)
            cli_result = json.loads(verified.stdout)
            if len(set(cli_result['sha256'].values())) != 1:
                raise ValueError('receiver CLI mismatch')
            expected_sha = cli_result['sha256']['base']
            data = np.frombuffer(raw, dtype=np.uint8).astype(np.float32).tobytes()
            measures = {a: [] for a in libs}
            for pass_index in range(8):  # First loop warms all arms.
                offset = pass_index % len(libs)
                order = list(libs)[offset:] + list(libs)[:offset]
                for arm in order:
                    values = array('f')
                    values.frombytes(data)
                    before = time.process_time_ns()
                    operator.call(libs[arm],values)
                    elapsed = (time.process_time_ns() - before) * 1e-6
                    if digest(operator.little_bytes(values)) != expected_sha:
                        raise ValueError('normalized byte disagreement')
                    if pass_index:
                        measures[arm].append(round(elapsed,4))
            med = {a: round(statistics.median(t),4) for a,t in measures.items()}
            rows.append({'ordinal': w['ordinal'], 'y': w['y'], 'x': w['x'], 'source_sha256': w['sha256'],
                         'mad': w['mad'], 'nonzero_voxels': w['occupied'],
                         'recipient_output_sha256': expected_sha,
                         'cpu_ms_by_pass': measures, 'median_cpu_ms': med,
                         'incumbent_over_candidate': round(med['incumbent']/med['candidate'],4)})
        return {'recipient_sha256':digest(archive.read_bytes()), 'synthetic':json.loads(checked.stdout),
                'system':platform.platform(), 'python':platform.python_version(), 'numpy':np.__version__,
                'compiler':subprocess.check_output(['c++','--version'],text=True).splitlines()[0],
                'tests':rows, 'scope':'Six registered scheduler windows. CPU component times only.'}


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('observations',type=Path)
    p.add_argument('output',type=Path)
    args=p.parse_args()
    args.output.write_text(json.dumps(trial(args.archive.resolve(),args.observations.resolve()),indent=2)+'\n')
