import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile

from .compiler import validate_plan


def execute(spec, plan, values, fault=None):
    roles = validate_plan(spec, plan)
    if type(values) is not list or not 1 <= len(values) <= 64 or any(type(x) is not str or len(x.encode()) > 256 for x in values):
        raise ValueError('BOUNDED_STRING_INPUT_REQUIRED')
    if fault not in (None, 'commit', 'consume', 'interrupt'):
        raise ValueError('UNSUPPORTED_FAULT')
    reverse = {v: k for k, v in roles.items()}
    trace, output = [], []
    resource = None
    committed = False
    closed = False
    error = None
    with tempfile.TemporaryDirectory(prefix='alpha-lifetime007-') as directory:
        path = Path(directory) / 'payload'
        try:
            for ident in plan['order']:
                role = reverse[ident]
                if role == 'acquire':
                    resource = sqlite3.connect(path) if spec['domain'] == 'sqlite' else path.open('w+b')
                    trace.append({'event': 'acquire', 'effect': ident})
                elif role == 'prepare':
                    if spec['domain'] == 'sqlite':
                        resource.execute('CREATE TABLE payload (seq INTEGER PRIMARY KEY, value TEXT)')
                        resource.executemany('INSERT INTO payload(value) VALUES (?)', [(v,) for v in values])
                    else:
                        for value in values:
                            raw = value.encode()
                            resource.write(len(raw).to_bytes(4, 'big') + raw)
                    trace.append({'event': 'prepare', 'effect': ident})
                elif role == 'durable':
                    if fault == 'commit':
                        raise RuntimeError('INJECTED_COMMIT_FAILURE')
                    if spec['domain'] == 'sqlite':
                        resource.commit()
                        other = sqlite3.connect(path)
                        try:
                            external = [r[0] for r in other.execute('SELECT value FROM payload ORDER BY seq')]
                        finally:
                            other.close()
                        if external != values:
                            raise RuntimeError('EXTERNAL_DURABILITY_CHECK_FAILED')
                    else:
                        resource.flush()
                        os.fsync(resource.fileno())
                    committed = True
                    trace.append({'event': 'durable', 'effect': ident})
                elif role == 'consume':
                    if not committed or closed:
                        raise RuntimeError('INVARIANT_VIOLATION')
                    if spec['domain'] == 'sqlite':
                        rows = (r[0] for r in resource.execute('SELECT value FROM payload ORDER BY seq'))
                    else:
                        resource.seek(0)
                        def records():
                            while header := resource.read(4):
                                if len(header) != 4:
                                    raise RuntimeError('TRUNCATED_RECORD')
                                length = int.from_bytes(header, 'big')
                                if length > 256:
                                    raise RuntimeError('RECORD_BOUND')
                                raw = resource.read(length)
                                if len(raw) != length:
                                    raise RuntimeError('TRUNCATED_RECORD')
                                yield raw.decode()
                        rows = records()
                    for i, value in enumerate(rows):
                        if i == 0 and fault == 'consume':
                            raise RuntimeError('INJECTED_CONSUMPTION_FAILURE')
                        if i == 0 and fault == 'interrupt':
                            raise InterruptedError('INJECTED_INTERRUPT')
                        trace.append({'event': 'consume', 'effect': ident, 'durable': committed, 'live': not closed})
                        output.append(value)
                        trace.append({'event': 'visible', 'sha256': hashlib.sha256(value.encode()).hexdigest()})
                elif role == 'release':
                    resource.close()
                    closed = True
                    trace.append({'event': 'release', 'effect': ident})
        except (RuntimeError, InterruptedError, sqlite3.Error, OSError) as exc:
            error = type(exc).__name__ + ':' + str(exc)
        finally:
            if resource is not None and not closed:
                resource.close()
                closed = True
                trace.append({'event': 'release', 'effect': roles['release'], 'finally': True})
    return {'schema': 'agi-alpha/lifetime-execution007/v1', 'task_id': spec['task_id'],
            'output': output, 'trace': trace, 'committed': committed, 'closed': closed, 'error': error,
            'scope': 'Fixed capability interpreter over a maximum of five whitelisted effects and 64 bounded values; no generated Python, shell, network, paths or dynamic imports.'}
