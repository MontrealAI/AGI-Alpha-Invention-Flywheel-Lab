import argparse
import asyncio
import hashlib
import importlib.metadata
import json
from pathlib import Path
import resource
import sqlite3
import time

from inventions.lifetime007.compiler import construct, validate_plan


async def run_case(spec, plan, path, fault=None):
    from fastapi import Depends, FastAPI
    from starlette.responses import StreamingResponse
    mapping = validate_plan(spec, plan)
    if spec['domain'] != 'sqlite' or fault not in (None, 'commit', 'mid_consume', 'mid_interrupt'):
        raise ValueError('ASGI_ADAPTER_SCOPE')
    setup = sqlite3.connect(path)
    setup.execute('PRAGMA foreign_keys=ON')
    setup.executescript('CREATE TABLE parent(id INTEGER PRIMARY KEY); CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED); INSERT INTO parent VALUES(1);')
    setup.commit()
    setup.close()
    events = []
    app = FastAPI()
    reverse = {v: k for k, v in mapping.items()}
    cut = plan['order'].index(mapping['consume'])
    before, after = plan['order'][:cut], plan['order'][cut+1:]
    state = {'conn': None, 'closed': False}

    def step(ident):
        role = reverse[ident]
        if role == 'acquire':
            state['conn'] = sqlite3.connect(path)
            state['conn'].execute('PRAGMA foreign_keys=ON')
        elif role == 'prepare':
            state['conn'].executemany('INSERT INTO child VALUES(?,?)', [(7, 2 if fault == 'commit' else 1), (8, 1)])
        elif role == 'durable':
            state['conn'].commit()
        elif role == 'release':
            state['conn'].close()
            state['closed'] = True
        else:
            raise ValueError('EFFECT_PHASE')
        events.append({'event': role, 'effect': ident})

    async def dependency():
        try:
            for ident in before:
                step(ident)
            yield state['conn']
        finally:
            if state['conn'] is not None:
                for ident in after:
                    if not state['closed']:
                        step(ident)

    async def endpoint(conn=Depends(dependency, scope='request')):
        async def stream():
            for i, row in enumerate(conn.execute('SELECT id FROM child ORDER BY id')):
                if i == 1 and fault == 'mid_consume':
                    raise RuntimeError('INJECTED_MIDSTREAM_FAILURE')
                if i == 1 and fault == 'mid_interrupt':
                    raise InterruptedError('INJECTED_MIDSTREAM_INTERRUPTION')
                events.append({'event': 'consume', 'value': row[0], 'live': not state['closed']})
                yield (str(row[0])+'\n').encode()
            events.append({'event': 'stream_complete'})
        return StreamingResponse(stream(), media_type='text/plain')

    app.add_api_route('/export', endpoint, methods=['GET'])
    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}
    async def send(message):
        if message['type'] == 'http.response.start':
            other = sqlite3.connect(path)
            try:
                rows = other.execute('SELECT id FROM child ORDER BY id').fetchall()
            finally:
                other.close()
            events.append({'event': 'response_start', 'status': message['status'], 'visible_rows': rows})
        elif message['type'] == 'http.response.body':
            events.append({'event': 'response_body', 'body': message.get('body', b'').decode(), 'more_body': message.get('more_body', False)})
    scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.4'}, 'http_version': '1.1',
             'method': 'GET', 'scheme': 'http', 'path': '/export', 'raw_path': b'/export', 'query_string': b'',
             'root_path': '', 'headers': [], 'client': ('127.0.0.1', 12345), 'server': ('localhost', 80)}
    error = None
    try:
        await asyncio.wait_for(app(scope, receive, send), timeout=5)
    except Exception as exc:
        error = type(exc).__name__+':'+str(exc)
    starts = [e for e in events if e['event'] == 'response_start']
    success = any(e['status'] == 200 for e in starts)
    kinds = [e['event'] for e in events]
    visible = [e for e in events if e['event'] == 'response_body' and e['body']]
    commit_first = not success or ('durable' in kinds and kinds.index('durable') < kinds.index('response_start'))
    valid = (not success and error is not None and 'consume' not in kinds and
             all(e['status'] >= 400 and not e['visible_rows'] for e in starts)) if fault == 'commit' else (
        success and error is None and [e['body'] for e in visible] == ['7\n', '8\n']) if fault is None else (
        success and error is not None and [e['body'] for e in visible] == ['7\n'])
    return {'fault': fault, 'events': events, 'error': error, 'closed': state['closed'],
            'commit_before_success': commit_first, 'contract_pass': bool(valid and commit_first and state['closed']),
            'full_delivery_accepted': fault is None and valid, 'partial_delivery_is_full_delivery': False,
            'actual_network_disconnect_tested': False}


def main(output):
    output.mkdir(parents=True, exist_ok=False)
    start, cpu = time.monotonic(), time.process_time()
    spec = json.loads(Path('campaign/cycle-007/LIFETIME_SPEC.json').read_text())
    plan = construct(spec)
    async def run_all():
        return [await run_case(spec, plan, output/(str(i)+'.sqlite3'), fault) for i, fault in enumerate([None, 'commit', 'mid_consume', 'mid_interrupt'])]
    results = asyncio.run(run_all())
    report = {'schema': 'agi-alpha/generated-asgi007/v1', 'spec': spec, 'plan': plan, 'results': results,
              'all_passed': all(r['contract_pass'] for r in results),
              'candidate_sources': {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in [__file__, 'inventions/lifetime007/compiler.py']},
              'packages': {x: importlib.metadata.version(x) for x in ['fastapi', 'starlette', 'pydantic']},
              'wall_seconds': time.monotonic()-start, 'self_cpu_seconds': time.process_time()-cpu,
              'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              'comparison': 'The ordinary explicit commit/request-close route already meets the same obligations. This generated plan establishes scoped construction, not a consequential enabling advantage.'}
    (output/'REPORT.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    if not report['all_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    main(parser.parse_args().output)
