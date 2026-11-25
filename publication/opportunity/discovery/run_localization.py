"""Execute the frozen public-document comparison with llama.cpp and no external inference calls."""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import file_digest, sha256
from http.client import HTTPConnection
import json
from pathlib import Path
import re
import socket
import subprocess
from time import monotonic, sleep


MODELS = {
    'hy-mt2': ('hymt2-q4.gguf', 1133080448, 'dc5f44fcf1fa496ee7ad725982c0c8c553a4de00259b53af84c4b89fb0c06699'),
    'hy-mt3': ('hymt3-q4.gguf', 1348432160, 'bae6e591103654ff43ef0de7d1492f6e6df1f955505f6bb2cc52e86fc399a942'),
}


def digest(path):
    with path.open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def request(port, path, body=None, timeout=2):
    channel = HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        if body is None:
            channel.request('GET', path)
        else:
            channel.request('POST', path, json.dumps(body), {'Content-Type': 'application/json'})
        response = channel.getresponse()
        return response.status, json.loads(response.read(1_000_000))
    finally:
        channel.close()


def localized_anchor(anchor, output):
    if ',' in anchor and anchor.replace(',', '').isdigit():
        pattern = r'(?:[,\.\s])?'.join(map(re.escape, anchor.split(',')))
    elif re.fullmatch(r'[0-9]+\.[0-9]+', anchor):
        pattern = r'[.,]'.join(map(re.escape, anchor.split('.')))
    else:
        pattern = re.escape(anchor)
    return re.search(r'(?<!\w)' + pattern + r'(?!\w)', output, re.IGNORECASE) is not None


def get_cases(repository, protocol):
    source_files = {}
    for case in protocol['cases']:
        path = case['path']
        if path not in source_files:
            source = subprocess.check_output(['git', 'show', f"{protocol['source_revision']}:{path}"], cwd=repository)
            source_files[path] = (source.decode().splitlines(), sha256(source).hexdigest())
        lines, source_sha = source_files[path]
        sentence = lines[case['line'] - 1]
        if case.get('table_cell'):
            sentence = sentence.split('|')[2].strip()
        if 'begin' in case:
            sentence = sentence[sentence.index(case['begin']):]
        if 'end' in case:
            sentence = sentence[:sentence.index(case['end']) + len(case['end'])]
        if any(anchor not in sentence for anchor in case['anchors']):
            raise ValueError(f"The source no longer matches the protected items for {case['id']}")
        yield {**case, 'source': sentence, 'source_file_sha256': source_sha,
               'source_text_sha256': sha256(sentence.encode()).hexdigest()}


def infer(runtime, weights, protocol, cases, log_path):
    with socket.socket() as socket_for_port:
        socket_for_port.bind(('127.0.0.1', 0))
        port = socket_for_port.getsockname()[1]
    options = protocol['runtime']
    args = [str(runtime), '--model', str(weights), '--host', '127.0.0.1', '--port', str(port),
            '--threads', str(options['cpu_threads']), '--threads-batch', str(options['cpu_threads']),
            '--ctx-size', str(options['context']), '--parallel', str(options['parallel']), '--cache-ram', '0',
            '--ctx-checkpoints', '0', '--n-gpu-layers', '0', '--no-ui', '--jinja', '--reasoning', 'off']
    wall0 = monotonic()
    results = {}
    with log_path.open('w') as log:
        child = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
        try:
            while True:
                if child.poll() is not None:
                    raise RuntimeError(f'Model server exited {child.returncode}; see {log_path.name}')
                status = None
                try:
                    status, _ = request(port, '/health')
                except (OSError, ValueError):
                    pass
                if status == 200:
                    break
                sleep(0.2)
            results['startup_seconds'] = monotonic() - wall0
            results['rows'] = []
            for case in cases:
                prompt = protocol['prompt'] + case['source']
                body = {'messages': [{'role': 'user', 'content': prompt}], **protocol['sampling']}
                t0 = monotonic()
                http_status, response = request(port, '/v1/chat/completions', body, timeout=180)
                seconds = monotonic() - t0
                if http_status != 200:
                    results['rows'].append({'id': case['id'], 'http': http_status, 'error': response,
                                            'wall_seconds': seconds})
                    continue
                choice, = response['choices']
                output = choice['message']['content'] or ''
                missing = [item for item in case['anchors'] if not localized_anchor(item, output)]
                results['rows'].append({'id': case['id'], 'use': case['use'], 'target': output,
                                        'wall_seconds': seconds, 'finish': choice['finish_reason'],
                                        'prompt_sha256': sha256(prompt.encode()).hexdigest(),
                                        'missing_anchors': missing, 'usage': response.get('usage'),
                                        'timings': response.get('timings')})
            proc_status = Path(f'/proc/{child.pid}/status')
            if proc_status.is_file():
                matches = re.search(r'^VmHWM:\s+(\d+) kB', proc_status.read_text(), re.MULTILINE)
                if matches:
                    results['peak_rss_kib'] = int(matches.group(1))
        finally:
            if child.poll() is None:
                child.terminate()
            child.wait()
    results['total_process_wall_seconds'] = monotonic() - wall0
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'server', 'weights', 'protocol', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--arm', choices=MODELS, action='append')
    options = parser.parse_args()
    protocol = json.loads(options.protocol.read_bytes())
    cases = list(get_cases(options.repo, protocol))
    options.output.mkdir(parents=True, exist_ok=False)
    (options.output / 'frozen-cases.json').write_text(json.dumps(cases, ensure_ascii=False, indent=2) + '\n')
    version = subprocess.run([str(options.server), '--version'], capture_output=True, text=True, check=True)
    for model in options.arm or protocol['initial_order']:
        name, bytes_expected, expected = MODELS[model]
        weight = options.weights / name
        if weight.stat().st_size != bytes_expected or digest(weight) != expected:
            raise ValueError(f'Invalid pinned weight for {model}')
        start = datetime.now(timezone.utc).isoformat()
        observations = infer(options.server, weight, protocol, cases, options.output / (model + '.log'))
        passes = defaultdict(int)
        for row in observations['rows']:
            if row.get('finish') == 'stop' and row['missing_anchors'] == []:
                passes[row['use']] += 1
        receipt = {'model': model, 'runtime': (version.stdout + version.stderr).strip(), 'start_utc': start,
                   'weight_sha256': expected, 'weight_bytes': bytes_expected, 'protocol_sha256': digest(options.protocol),
                   'anchor_pass_by_use': dict(passes), 'authority': 'DRAFT_REQUIRES_BILINGUAL_ACCEPTANCE',
                   **observations}
        (options.output / (model + '.json')).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
        print(model, dict(passes), round(observations['total_process_wall_seconds'], 2), flush=True)


if __name__ == '__main__':
    main()
