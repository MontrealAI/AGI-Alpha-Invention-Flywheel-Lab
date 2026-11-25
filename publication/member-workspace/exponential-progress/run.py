# SPDX-License-Identifier: Apache-2.0
"""Run two dated local translation models with and without protected fields."""

import argparse
from datetime import datetime, timezone
from hashlib import file_digest
import json
from pathlib import Path
from resource import getrusage, RUSAGE_CHILDREN
from secrets import token_urlsafe
import socket
import subprocess
from tempfile import NamedTemporaryFile
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from qualify import canonical, fingerprint, frozen_cases, instruction, restore


DIRECT = 'publisher_style'
PROTECTED = 'protected_fields'
LOOPBACK = build_opener(ProxyHandler({}))


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def verify(path, expected, size=None):
    if size is not None and size != path.stat().st_size:
        raise ValueError(f'Unexpected model byte count at {path}')
    with path.open('rb') as stream:
        actual = file_digest(stream, 'sha256').hexdigest()
    if actual != expected:
        raise ValueError(f'Unexpected source digest at {path}')


def write_receipt(path, record):
    pending = path.with_suffix('.partial')
    pending.write_bytes(canonical(record))
    pending.replace(path)


def free_port():
    with socket.socket(socket.AF_INET) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def request(port, endpoint, timeout, token=None, body=None):
    headers = {'Authorization': f'Bearer {token}'} if token else {}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    data = canonical(body) if body is not None else None
    req = Request(f'http://127.0.0.1:{port}/{endpoint}', data=data, headers=headers)
    with LOOPBACK.open(req, timeout=timeout) as reply:
        raw = reply.read(65_537)
    if len(raw) > 65_536:
        raise ValueError('Unexpected response size from loopback runtime')
    return json.loads(raw)


def server_ready(proc, port, expected_model, token):
    # This is a local transport readiness limit. A startup failure remains in the retained log.
    expires = time.monotonic() + 120
    while time.monotonic() < expires:
        if proc.poll() is not None:
            raise RuntimeError(f'llama-server exited with {proc.returncode}')
        try:
            health = request(port, 'health', 2, token)
            if health == {'status': 'ok'}:
                models = request(port, 'v1/models', 2, token)
                if [row['id'] for row in models['data']] != [expected_model]:
                    raise RuntimeError('Unexpected model identity on the loopback listener')
                return
        except (OSError, URLError):
            pass
        time.sleep(0.25)
    raise RuntimeError('The local model server did not become ready')


def translation(port, model, prompt, runtime, token):
    start = time.monotonic()
    packet = request(port, 'v1/chat/completions', 300, token, {
        'model': model, 'messages': [{'role': 'user', 'content': prompt}],
        'temperature': runtime['temperature'], 'max_tokens': runtime['output_tokens'],
        'seed': 61125, 'stream': False, 'cache_prompt': False
    })
    elapsed = time.monotonic() - start
    row = packet['choices'][0]
    return {'raw': row['message']['content'], 'wall_seconds': elapsed,
            'tokens': packet['usage'], 'finish': row.get('finish_reason'),
            'reply_timestamp': now()}


def require_private_generation(port):
    try:
        request(port, 'v1/chat/completions', 2, body={'messages': []})
    except HTTPError as error:
        if error.code == 401:
            return error.code
        raise
    raise RuntimeError('An unauthenticated generation request was not refused')


def stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def run_model(runtime_path, model_path, model, config, cases, output):
    port = free_port()
    runtime = config['runtime']
    result = {'model': model, 'started': now(), 'cases': [], 'model_source': config['models'][model]}
    start = time.monotonic()
    usage = getrusage(RUSAGE_CHILDREN)
    with (output / f'{model}.log').open('w', encoding='utf-8') as log, NamedTemporaryFile(mode='w') as access:
        token = token_urlsafe(32)
        access.write(token + '\n')
        access.flush()
        proc = subprocess.Popen(
            [str(runtime_path), '-m', str(model_path), '--alias', model, '-ngl', '0',
             '-t', str(runtime['threads']), '-c', str(runtime['context']),
             '-b', '256', '-np', '1', '--jinja', '--host', '127.0.0.1', '--port', str(port),
             '--api-key-file', access.name, '--cors-origins', f'http://127.0.0.1:{port}'],
            stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            server_ready(proc, port, model, token)
            result['unauthenticated_generation_http_status'] = require_private_generation(port)
            result['startup_wall_seconds'] = time.monotonic() - start
            for index, case in enumerate(cases):
                strategies = (DIRECT, PROTECTED) if index % 2 == 0 else (PROTECTED, DIRECT)
                observed = {'id': case['id'], 'drafts': {}}
                for strategy in strategies:
                    locked = strategy == PROTECTED
                    prompt = instruction(case, locked=locked)
                    response = translation(port, model, prompt, runtime, token)
                    response['prompt_sha256'] = fingerprint(prompt.encode())
                    if locked:
                        response['guard'] = restore(case, response['raw'])
                    observed['drafts'][strategy] = response
                result['cases'].append(observed)
                write_receipt(output / f'{model}.json', result)
        finally:
            stop(proc)
    final = getrusage(RUSAGE_CHILDREN)
    result.update({'total_execution_wall_seconds': time.monotonic() - start,
                   'user_cpu_seconds': final.ru_utime - usage.ru_utime,
                   'system_cpu_seconds': final.ru_stime - usage.ru_stime,
                   'completed': now()})
    write_receipt(output / f'{model}.json', result)


def main():
    config, cases = frozen_cases()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llama-server', type=Path, required=True)
    parser.add_argument('--model-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--arm', choices=tuple(config['models']), action='append')
    parser.add_argument('--case', choices=[case['id'] for case in cases], action='append')
    args = parser.parse_args()
    runtime_path = args.llama_server.resolve()
    verify(runtime_path, config['runtime']['linux_x86_64_server_sha256'])
    selected = [case for case in cases if not args.case or case['id'] in args.case]
    args.output.mkdir(parents=True, exist_ok=False)
    for model in args.arm or tuple(config['models']):
        frozen = config['models'][model]
        path = (args.model_dir / f'{model}.gguf').resolve()
        verify(path, frozen['sha256'], frozen['bytes'])
        run_model(runtime_path, path, model, config, selected, args.output)


if __name__ == '__main__':
    main()
