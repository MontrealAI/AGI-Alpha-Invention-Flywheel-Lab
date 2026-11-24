"""Construct and compare portable candidates on committed development tasks."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
import signal
from time import time

from bridge.instruments import strict_portable_json
from model_step import brief, object_schema, step
from native_experiment import NativeRefused, run as native
from pages import digest
from study import atomic, lock


SCHEMA = 'frontier/amplification-v1'
ARMS = ('direct', 'harness', 'amplified')
CODE = object_schema({'hypothesis': brief(320), 'source': brief(11_000)})
STYLES = {
    'direct': 'Work as a competent independent scientist with a Python execution tool. Use the exact task, '
              'examples and any previous execution diagnostics to implement and improve the result.',
    'harness': 'Use the existing research harness process. Test a hypothesis, review development errors, '
               'and implement or repair an executable result.',
    'amplified': 'Use the same research harness process and read the attached diagnostics from a proposed '
                 'instrument. Treat them as fallible and verify them against the full examples.',
}


def read(path, maximum=2_000_000):
    with path.open('rb') as stream:
        body = stream.read(maximum + 1)
    if not 0 < len(body) <= maximum:
        raise ValueError('FILE_SIZE')
    return strict_portable_json(body.decode('utf-8')), sha256(body).hexdigest()


def canonical(output):
    return json.dumps(output, allow_nan=False, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def assess(source, cases):
    rows = []
    for case in cases:
        expected = case['expected']
        try:
            output = native(source, case['input'])
            accepted = 'result' in output and canonical(output['result']) == canonical(expected)
            rows.append({'id': case['id'], 'accepted': accepted, **output})
        except NativeRefused as error:
            rows.append({'id': case['id'], 'accepted': False, 'error': str(error)})
    return rows


def counts(rows):
    return {'accepted': sum(row['accepted'] for row in rows), 'cases': len(rows),
            'work_wall_ns': sum(row.get('wall_ns', 0) for row in rows)}


def development(path, expected):
    data, binding = read(path)
    if binding != expected or type(data) is not list or not data:
        raise ValueError('DEVELOPMENT_BINDING')
    ids = set()
    for row in data:
        if (type(row) is not dict or set(row) != {'id', 'input', 'expected'} or type(row['id']) is not str
                or row['id'] in ids):
            raise ValueError('CASE_CONTRACT')
        ids.add(row['id'])
    return data


def diagnostics(dataset, attempts):
    if not attempts:
        return []
    rows = attempts[-1]['development']
    by_id = {item['id']: item['expected'] for item in dataset}
    return [{**{key: row[key] for key in ('id', 'accepted', 'result', 'error') if key in row},
             'expected': by_id[row['id']]} for row in rows]


def proposed_instrument(proposal, contract, cases, feedback):
    try:
        answer = native(proposal['source'], {'contract': contract, 'examples': cases, 'feedback': feedback})
        result = answer.get('result')
        if not (type(result) is list and 0 < len(result) <= 12
                and all(type(item) is str and 0 < len(item) <= 240 for item in result)):
            return {'used': False, 'reason': 'INVALID_INSTRUMENT_OUTPUT', 'wall_ns': answer['wall_ns']}
        return {'used': True, 'notes': result, 'wall_ns': answer['wall_ns']}
    except NativeRefused as error:
        return {'used': False, 'reason': str(error)}


def design(args):
    policy, freeze = read(args.registration)
    cases = development(args.development, policy['development_sha256'])
    task = ('Invent an executable diagnostic instrument that helps the same model construct correct research '
            'software from evidence. Use the contract and development examples. You may construct a semantic '
            'map, an invariant extractor, an example transformer, or a different helpful mechanism. The '
            'decisive method is yours to discover. Avoid just copying the full examples or hard-coding answers. '
            'Produce Python source defining solve(request). request contains contract (string), examples (the '
            'case list below), and feedback (list of prior observed development errors, possibly empty). '
            'Return 1 to 12 short strings as actionable diagnostics. Use pure Python without files, network or '
            'processes. Return a JSON object with hypothesis and source.\n')
    prompt = task + canonical({'contract': policy['contract'], 'examples': cases})
    record = step(args.workspace, args.config, args.model, CODE, prompt, 'amplifier-design',
                  policy['design_tokens'], attempts=policy['design_attempts'], deadline=args.until)
    if record['status'] == 'SEALED':
        outcome = proposed_instrument(record['result'], policy['contract'], cases, [])
        atomic(args.workspace/'instrument.json', {'registration_sha256': freeze, 'result': record['result'],
                                                 'development_diagnostics': outcome})
    return record


def construct(args):
    policy, freeze = read(args.registration)
    cases = development(args.development, policy['development_sha256'])
    spec = policy['comparisons'][args.model]
    if args.arm not in spec['arms']:
        raise ValueError('UNREGISTERED_ARM')
    if args.arm == 'amplified':
        if args.instrument is None:
            raise ValueError('INSTRUMENT_REQUIRED')
        instrument, instrument_id = read(args.instrument)
        if instrument['registration_sha256'] != freeze:
            raise ValueError('INSTRUMENT_BINDING')
    else:
        if args.instrument is not None:
            raise ValueError('CONTROL_INSTRUMENT')
        instrument, instrument_id = None, None
    args.workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
    config_id = sha256(args.config.read_bytes()).hexdigest()
    binding = {'registration': freeze, 'model': args.model, 'model_config': config_id,
               'arm': args.arm, 'instrument': instrument_id, 'lease_until': args.until}
    path = args.workspace/'amplification-status.json'
    with lock(args.workspace):
        record = read(path)[0] if path.exists() else {'schema': SCHEMA, 'objective': policy['objective'],
                                                        'binding': binding, 'state': 'RUNNING', 'attempts': []}
        if record['binding'] != binding:
            raise ValueError('STUDY_BINDING')
        if record['state'] != 'RUNNING':
            return record
        atomic(path, record)
        while len(record['attempts']) < spec['attempts']:
            if int(time()) >= args.until:
                raise ValueError('LEASE_EXPIRED')
            feedback = diagnostics(cases, record['attempts'])
            trial = len(record['attempts']) + 1
            previous = record['attempts'][-1] if record['attempts'] else None
            prior = previous['candidate'] if previous else None
            enriched = proposed_instrument(instrument['result'], policy['contract'], cases, feedback) if instrument else None
            context = {'contract': policy['contract'], 'development': cases, 'previous': prior, 'feedback': feedback}
            if previous and prior is None:
                context['response_diagnostics'] = [event.get('diagnosis') or event.get('reason') or event['status']
                                                   for event in previous['request']['events']]
            if enriched and enriched['used']:
                context['proposed_instrument_diagnostics'] = enriched['notes']
            prompt = (f'{STYLES[args.arm]} Return a JSON object with hypothesis and source. The source defines '
                      'solve(input) returning exactly the specified JSON output. A fresh isolated Python worker '
                      'can run normal standard-library code on each case. It has no files beyond the runtime, '
                      'external connection or process creation. A development check will run before a repair. '
                      'Generalize to cases whose answers are not present.\n' + canonical(context))
            request = step(args.workspace/f'attempt-{trial}', args.config, args.model, CODE, prompt,
                           'portable-construction', spec['request_tokens'], attempts=1, deadline=args.until,
                           expected_config=config_id)
            candidate = request['result']
            results = assess(candidate['source'], cases) if candidate is not None else []
            record['attempts'].append({'number': trial, 'request': request, 'diagnostics': enriched,
                                       'candidate': candidate, 'development': results, 'scores': counts(results)})
            if results and all(row['accepted'] for row in results):
                record['state'] = 'DEVELOPMENT_PASS'
            atomic(path, record)
            if record['state'] == 'DEVELOPMENT_PASS':
                return record
        record['state'] = 'EXHAUSTED'
        atomic(path, record)
        return record


def selected(record):
    candidates = (item for item in record['attempts'] if item['candidate'] is not None)
    return max(candidates, key=lambda item: (item['scores']['accepted'], -item['number']), default=None)


def evaluate(args):
    policy, freeze = read(args.registration)
    cases = development(args.confirmation, policy['confirmation_sha256'])
    report = {'schema': SCHEMA, 'registration_sha256': freeze, 'objective': policy['objective'], 'arms': {}}
    for checkpoint in args.checkpoints:
        record, binding = read(checkpoint)
        if record['schema'] != SCHEMA or record['binding']['registration'] != freeze or record['state'] == 'RUNNING':
            raise ValueError('CHECKPOINT_BINDING')
        key = '/'.join((record['binding']['model'], record['binding']['arm']))
        if key in report['arms']:
            raise ValueError('DUPLICATE_ARM')
        chosen = selected(record)
        results = assess(chosen['candidate']['source'], cases) if chosen else []
        report['arms'][key] = {'checkpoint_sha256': binding, 'selection': chosen['number'] if chosen else None,
                               'source_sha256': digest(chosen['candidate']['source']) if chosen else None,
                               'counts': counts(results), 'results': results}
        report['arms'][key]['counts']['cases'] = len(cases)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    for name, action in (('design', design), ('construct', construct)):
        cli = sub.add_parser(name)
        cli.set_defaults(action=action)
        for flag in ('registration', 'development', 'workspace', 'config'):
            cli.add_argument('--'+flag, type=Path, required=True)
        cli.add_argument('--model', required=True)
        cli.add_argument('--until', type=int, required=True)
        if name == 'construct':
            cli.add_argument('--arm', choices=ARMS, required=True)
            cli.add_argument('--instrument', type=Path)
    cli = sub.add_parser('evaluate')
    cli.set_defaults(action=evaluate)
    cli.add_argument('--registration', type=Path, required=True)
    cli.add_argument('--confirmation', type=Path, required=True)
    cli.add_argument('checkpoints', type=Path, nargs='+')
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupt)
    try:
        print(json.dumps(args.action(args), ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        parser.exit(130, 'Paused. Reuse the same workspace, lease and resource bindings.\n')
    except ValueError as error:
        parser.exit(2, str(error) + '\n')


def interrupt(_signum, _frame):
    raise KeyboardInterrupt


if __name__ == '__main__':
    main()
