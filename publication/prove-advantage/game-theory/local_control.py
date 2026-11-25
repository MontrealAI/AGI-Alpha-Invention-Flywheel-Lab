# SPDX-License-Identifier: Apache-2.0
"""Run the held cases on a larger, already acquired CPU model in a loopback-only process."""

import argparse
import json
from pathlib import Path
import socket
import subprocess
from time import perf_counter, sleep
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

from curriculum import ACCESS, digest, read_cases, write_json


MODEL_SHA = '2fde00ce69dd4899c70d020845e2638353015bba0fdf161b3eb965f2bca4464e'
MODEL_REFERENCE = ('https://huggingface.co/bartowski/Qwen_Qwen3-4B-Instruct-2507-GGUF/'
                   'tree/ae44f08e1392f39c0e474af10c3ff8355c8b6688')
GUIDANCE = ('Use only the numbered rules. At each named choice, mark the datum known when the actor '
            'certainly possesses or can logically infer it in every applicable situation by the choice. '
            'Mark hidden for explicit denial or after-only access. Mark unclear when access is missing, '
            'conditional or conflicting. Give one decisive rule number per answer. Use number 0 only '
            'for unclear due to absence of a decisive rule. Keep query order. Return JSON.')


def serve(args, cases):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    base = f'http://127.0.0.1:{port}'
    connection = build_opener(ProxyHandler({}))
    command = [str(args.server.resolve()), '--model', str(args.weights.resolve()), '--host', '127.0.0.1',
               '--port', str(port), '--threads', '3', '--ctx-size', '4096', '--parallel', '1',
               '--gpu-layers', '0', '--reasoning', 'off', '--no-webui']
    with args.log.open('xb') as log, subprocess.Popen(command, stdout=log, stderr=log) as server:
        try:
            ready_start = perf_counter()
            while True:
                if server.poll() is not None:
                    raise RuntimeError('Local model process stopped during startup')
                try:
                    with connection.open(base + '/health', timeout=4) as response:
                        if json.load(response).get('status') == 'ok':
                            break
                except (URLError, TimeoutError):
                    sleep(1)
            startup = perf_counter() - ready_start
            records = {}
            for case in cases:
                records[case['id']] = request(connection, base, case)
                write_json(args.output, {'startup_seconds': startup, 'results': records, 'status': 'running'})
            return {'startup_seconds': startup, 'results': records, 'status': 'complete'}
        finally:
            server.terminate()
            try:
                server.wait(timeout=8)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


def request(connection, base, case):
    rules = '\n'.join(f'{i}. {rule}' for i, rule in enumerate(case['rules'], 1))
    queries = '\n'.join(f'{i}. Actor {query["observer"]}. Choice {query["decision"]}. Datum {query["datum"]}.'
                        for i, query in enumerate(case['queries'], 1))
    schema = {'type': 'object', 'properties': {'answers': {
        'type': 'array', 'minItems': len(case['queries']), 'maxItems': len(case['queries']),
        'items': {'type': 'object', 'properties': {'access': {'type': 'string', 'enum': list(ACCESS)},
                                                  'witness': {'type': 'integer', 'minimum': 0,
                                                              'maximum': len(case['rules'])}},
                  'required': ['access', 'witness'], 'additionalProperties': False}}},
        'required': ['answers'], 'additionalProperties': False}
    body = {
        'messages': [{'role': 'system', 'content': GUIDANCE},
                     {'role': 'user', 'content': f'Rules\n{rules}\n\nQueries\n{queries}'}],
        'max_tokens': 160, 'temperature': 0, 'seed': 728146,
        'response_format': {'type': 'json_schema', 'json_schema': {'name': 'rulings', 'schema': schema}},
    }
    start = perf_counter()
    action = Request(base + '/v1/chat/completions', data=json.dumps(body).encode(),
                     headers={'Content-Type': 'application/json'})
    try:
        with connection.open(action) as response:
            result = json.load(response)
        completion = result['choices'][0]['message']['content']
        choices = json.loads(completion)['answers']
        if len(choices) != len(case['queries']) or any(
                set(row) != {'access', 'witness'} or row['access'] not in ACCESS for row in choices):
            raise ValueError('Incomplete or invalid control result')
        return {'answers': choices, 'usage': result.get('usage', {}), 'content': completion,
                'wall_seconds': perf_counter() - start}
    except (ValueError, IndexError, KeyError, TypeError, URLError, TimeoutError) as error:
        return {'error': type(error).__name__, 'detail': str(error), 'wall_seconds': perf_counter() - start}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('server', 'weights', 'cases', 'output', 'log'):
        parser.add_argument('--' + option, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    if digest(args.weights) != MODEL_SHA:
        raise ValueError('Incorrect Apache-2.0 control model bytes')
    outcome = serve(args, read_cases(args.cases))
    write_json(args.output, {
        'schema': 'frontier/strategic-4b-control/v1', 'server_sha256': digest(args.server),
        'model': 'Qwen3-4B-Instruct-2507 Q4_K_M', 'weights_sha256': MODEL_SHA, 'source': MODEL_REFERENCE,
        'cases_sha256': digest(args.cases), 'cpu_threads': 3, **outcome,
    })
