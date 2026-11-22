"""Research entry point. Run with python3 -m research from this product."""
from argparse import ArgumentParser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
from time import perf_counter
from urllib.parse import urlsplit

from . import receipt_check, receipt_index
from .member_packet import member_packet

PRODUCT = Path(__file__).resolve().parents[1]
REPO = PRODUCT.parents[1]
sys.path.insert(0, str(PRODUCT.parent / 'alpha-genesis-harness'))
from bridge.adapters import BridgeError, retrieve_source  # noqa: E402

PROTOCOL = PRODUCT / 'research' / 'protocol.json'
SCOPE = "Qualification of pinned published receipts. Customer acceptance, payment and profit are unproven."


def now():
    return datetime.now(timezone.utc).isoformat()


def private_path(value):
    path = Path(value).resolve()
    if path.is_relative_to(REPO):
        raise ValueError("Use a working path outside the checkout")
    return path


def digest(data):
    return sha256(data).hexdigest()


def read_plan(path):
    payload = path.read_bytes()
    plan = json.loads(payload)
    if plan['schema'] != 'frontier-omega-alpha/research-protocol-v1':
        raise ValueError('Unsupported research protocol')
    return plan, digest(payload)


def dump(value, path):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')


def through_egress_proxy(url, hosts, *, exact_bytes=False):
    """Use the operator's managed HTTPS egress when direct pinned DNS is unavailable."""
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in hosts or parsed.port not in (None, 443)
            or parsed.username or parsed.password or parsed.fragment or any(ord(char) < 32 for char in url)):
        raise BridgeError('SOURCE_URL', 'Use an operator-allowlisted HTTPS source.')
    command = ['curl', '-q', '--globoff', '--silent', '--fail', '--proto', '=https', '--max-filesize', '1048576',
               '--max-time', '30', '--header', 'Accept-Encoding: identity', '--write-out',
               '\n%{http_code} %{content_type}', '--', url]
    try:
        record = subprocess.run(command, capture_output=True, check=True).stdout
        data, metadata = record.rsplit(b'\n', 1)
        if not metadata.startswith(b'200 ') or len(data) > 1024 * 1024:
            raise ValueError('Unexpected HTTP response')
        mime = metadata[4:].split(b';', 1)[0].lower()
        text = {b'text/plain', b'text/html', b'application/json', b'text/markdown'}
        unspecified = {b'', b'application/octet-stream'}
        if mime not in text and not (exact_bytes and mime in unspecified):
            raise ValueError('Unexpected content type')
        return {'url': url, 'sha256': digest(data), 'retrieved_at': now(), 'text': data.decode('utf-8')}
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        raise BridgeError('SOURCE_EGRESS', 'Trusted HTTPS egress did not return bounded text.') from exc


def observe(plan, state, transport=retrieve_source):
    hosts = frozenset(urlsplit(source['url']).hostname for source in plan['sources'].values())

    def read(item):
        name, source = item
        try:
            return name, source, transport(source['url'], hosts), None
        except BridgeError as error:
            return name, source, None, error.code

    with sqlite3.connect(state) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY, url TEXT NOT NULL, observed TEXT NOT NULL, sha256 TEXT NOT NULL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS observation_url ON observations(url, id)")
        with ThreadPoolExecutor(max_workers=4) as pool:
            observations = list(pool.map(read, plan['sources'].items()))
        db.execute("BEGIN IMMEDIATE")
        result = {}
        for name, source, item, error in observations:
            latest = db.execute('SELECT sha256 FROM observations WHERE url=? ORDER BY id DESC LIMIT 1',
                                (source['url'],)).fetchone()
            previous = latest[0] if latest else None
            if error:
                result[name] = {**source, 'status': 'unavailable', 'previous_sha256': previous, 'error': error}
                continue
            current = item['sha256']
            status = 'first-observed' if previous is None else 'unchanged' if previous == current else 'bytes-changed'
            if status != 'unchanged':
                db.execute("INSERT INTO observations(url, observed, sha256) VALUES (?,?,?)",
                           (source['url'], item['retrieved_at'], current))
            result[name] = {**source, 'status': status, 'sha256': current,
                            'previous_sha256': previous, 'observed': item['retrieved_at']}
        return result


def rank(plan, observations):
    candidates = []
    for item in plan['opportunities']:
        signals = {key: observations.get(key, {}).get('status', 'unobserved') for key in item['sources']}
        score = sum(item['scores'][key] * weight for key, weight in plan['settings'].items())
        candidates.append({**item, 'rank_score': score, 'source_status': signals})
    return sorted(candidates, key=lambda item: (-item['rank_score'], item['id']))


def read_logs(stage, root):
    result = {}
    for kind, source in stage['files'].items():
        if Path(source['file']).name != source['file'] or not 0 < source['bytes'] <= 1024 * 1024:
            raise ValueError('Invalid receipt registration')
        with (root / source['file']).open('rb') as stream:
            payload = stream.read(source['bytes'] + 1)
        if len(payload) != source['bytes'] or digest(payload) != source['sha256']:
            raise ValueError('Source bytes do not match the registered digest: ' + source['file'])
        result[kind] = payload.decode('utf-8')
    return result


def cases(stage, logs):
    names = stage['theorems']
    yield 'published-set', logs, names, True
    theorem = names[0]
    line = f'con-ron: theorem {theorem} justified by the solution'
    yield 'missing_statement_match', {**logs, 'con-ron': logs['con-ron'].replace(line + '\n', '', 1)}, names, False
    yield 'failed_checker', {**logs, 'con-ron': logs['con-ron'].replace('Exit status: 0', 'Exit status: 1', 1)}, names, False
    axiom_line = f"'{theorem}' depends on axioms: [propext,"
    yield 'disallowed_axiom', {**logs, 'audit': logs['audit'].replace(axiom_line, f"'{theorem}' depends on axioms: [sorryAx,", 1)}, names, False
    yield 'unregistered_theorem', logs, [*names, 'unknown_theorem'], False
    yield 'duplicate_witness', {**logs, 'con-ron': logs['con-ron'] + '\n' + line + '\n'}, names, False
    number = stage['challenge_declarations']
    yield 'wrong_declaration_count', {**logs, 'con-leche': logs['con-leche'].replace(f'accepted {number} declarations,', f'accepted {number - 1} declarations,', 1)}, names, False


def single_stage(plan, stage, logs, profile):
    rows = []
    for case, inputs, names, expected in cases(stage, logs):
        baseline = receipt_check.assess(stage, inputs, plan['allowed_axioms'], names)
        candidate = receipt_index.assess(profile, stage, inputs, plan['allowed_axioms'], names)
        rows.append({'case': case, 'expected': expected, 'direct_inspection': baseline, 'reusable_index': candidate})
    accepted = all(row['direct_inspection'] == row['reusable_index'] == row['expected'] for row in rows)
    registered = ['published-set', *plan['negative_cases']]
    if [row['case'] for row in rows] != registered:
        raise ValueError('Registered cases do not match the execution')
    return {'stage': stage['id'], 'theorems': stage['theorems'], 'files': stage['files'],
            'acceptance_matrix_matched': accepted, 'cases': rows}


def run_experiment(plan, plan_hash, inputs, output):
    prepared = [(stage, read_logs(stage, inputs)) for stage in plan['stages']]
    output.mkdir(mode=0o700)
    started = perf_counter()
    first_stage, first_inputs = prepared[0]
    first = single_stage(plan, first_stage, first_inputs, receipt_index.PROFILE)
    profile_path = output / 'retained-profile.json'
    if first['acceptance_matrix_matched']:
        dump(receipt_index.PROFILE, profile_path)
    remaining = []
    if profile_path.is_file():
        profile = json.loads(profile_path.read_text())
        remaining = [single_stage(plan, stage, logs, profile) for stage, logs in prepared[1:]]
    verdicts = [first, *remaining]
    verified = len(prepared) == len(verdicts) and all(item['acceptance_matrix_matched'] for item in verdicts)
    result = {
        'protocol_sha256': plan_hash, 'scope': SCOPE, 'executed_at_utc': now(),
        'technical_verdict': 'receipt-agreement' if verified else 'failed',
        'stages': verdicts,
        'retained_profile_sha256': digest(profile_path.read_bytes()) if profile_path.is_file() else None,
        'economic': {'status': 'unproven', 'payment': None, 'complete_cost_profit': None,
                     'labor': None, 'external_billing': None, 'replay_wall_seconds': perf_counter() - started},
        'causal_invention_improvement': 'unproven',
    }
    dump(result, output / 'research-receipt.json')
    return result


def verify_experiment(plan, plan_hash, inputs, report):
    if report.get('protocol_sha256') != plan_hash or report.get('technical_verdict') != 'receipt-agreement':
        return False
    stages = report.get('stages', [])
    if len(plan['stages']) != len(stages):
        return False
    for stage, result in zip(plan['stages'], stages, strict=True):
        if any(result.get(key) != stage[key] for key in ('theorems', 'files')) or result.get('stage') != stage['id']:
            return False
        inputs_by_kind = read_logs(stage, inputs)
        claimed = result.get('cases', [])
        expected_cases = list(cases(stage, inputs_by_kind))
        if len(claimed) != len(expected_cases):
            return False
        for row, (name, values, theorems, expected) in zip(claimed, expected_cases, strict=True):
            verified = receipt_check.assess(stage, values, plan['allowed_axioms'], theorems)
            if row != {'case': name, 'expected': expected, 'direct_inspection': verified, 'reusable_index': verified} or verified != expected:
                return False
    return True


def main():
    os.umask(0o077)
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=PROTOCOL)
    commands = parser.add_subparsers(dest='command', required=True)
    scanner = commands.add_parser('scan', help='Observe allowlisted sources and rank registered hypotheses')
    scanner.add_argument('--state', required=True)
    scanner.add_argument('--allow-network', required=True, action='store_true')
    scanner.add_argument('--environment-egress', action='store_true')
    fetcher = commands.add_parser('fetch', help='Acquire registered receipts and check exact bytes')
    fetcher.add_argument('--output', required=True)
    fetcher.add_argument('--allow-network', required=True, action='store_true')
    fetcher.add_argument('--environment-egress', action='store_true')
    comparison = commands.add_parser('compare-source', help='Compare a registered source with a pinned predecessor')
    comparison.add_argument('--source', required=True)
    comparison.add_argument('--previous', required=True)
    comparison.add_argument('--current', help='Use an explicit current revision on the registered host')
    comparison.add_argument('--allow-network', required=True, action='store_true')
    comparison.add_argument('--environment-egress', action='store_true')
    runner = commands.add_parser('run', help='Execute the finite receipt comparison')
    runner.add_argument('--inputs', required=True)
    runner.add_argument('--output', required=True)
    verifier = commands.add_parser('verify', help='Independently replay the direct receipt checks')
    verifier.add_argument('--inputs', required=True)
    verifier.add_argument('--report', type=Path, required=True)
    publisher = commands.add_parser('packet', help='Prepare a bilingual private packet after independent replay')
    publisher.add_argument('--inputs', required=True)
    publisher.add_argument('--report', type=Path, required=True)
    publisher.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        plan, plan_hash = read_plan(args.protocol)
        transport = through_egress_proxy if getattr(args, 'environment_egress', False) else retrieve_source
        if args.command == 'scan':
            observations = observe(plan, private_path(args.state), transport)
            print(json.dumps({'observations': observations, 'ranked_opportunities': rank(plan, observations)}, ensure_ascii=False))
            return int(all(item['status'] == 'unavailable' for item in observations.values()))
        if args.command == 'compare-source':
            if args.source not in plan['sources']:
                raise ValueError('Choose a source in the registered protocol')
            url = plan['sources'][args.source]['url']
            hosts = frozenset({urlsplit(url).hostname})
            previous = transport(args.previous, hosts)
            current = transport(args.current or url, hosts)
            field_names = ('url', 'sha256', 'retrieved_at')
            print(json.dumps({'source': url, 'status': 'unchanged' if previous['sha256'] == current['sha256'] else 'bytes-changed',
                              'previous': {key: previous[key] for key in field_names},
                              'current': {key: current[key] for key in field_names}}))
            return 0
        if args.command == 'fetch':
            sources = [src for stage in plan['stages'] for src in stage['files'].values()]
            hosts = frozenset(urlsplit(src['url']).hostname for src in sources)
            output = private_path(args.output)
            verified = {}
            for src in sources:
                if args.environment_egress:
                    record = through_egress_proxy(src['url'], hosts, exact_bytes=True)
                else:
                    record = transport(src['url'], hosts)
                data = record['text'].encode('utf-8')
                if len(data) != src['bytes'] or digest(data) != src['sha256'] or Path(src['file']).name != src['file']:
                    raise ValueError('Remote receipt does not match the registered bytes')
                verified[src['file']] = data
            output.mkdir(mode=0o700)
            for name, data in verified.items():
                (output / name).write_bytes(data)
            return 0
        if args.command == 'run':
            result = run_experiment(plan, plan_hash, Path(args.inputs), private_path(args.output))
            print(json.dumps({'technical_verdict': result['technical_verdict'], 'scope': result['scope']}))
            return int(result['technical_verdict'] != 'receipt-agreement')
        report = json.loads(args.report.read_text())
        verdict = verify_experiment(plan, plan_hash, Path(args.inputs), report)
        if args.command == 'packet' and verdict:
            if [stage['id'] for stage in plan['stages']] != ['riemann-dirichlet', 'robin-lagarias']:
                raise ValueError('This bilingual packet describes the registered two-stage Lean experiment')
            packet = member_packet(plan, report)
            output = private_path(args.output)
            output.mkdir(mode=0o700)
            for name, document in packet.items():
                dump(document, output / (name + '.json'))
        print(json.dumps({'independent_receipt_replay': 'passed' if verdict else 'failed', 'scope': SCOPE}))
        return int(not verdict)
    except (ValueError, OSError, sqlite3.Error) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
