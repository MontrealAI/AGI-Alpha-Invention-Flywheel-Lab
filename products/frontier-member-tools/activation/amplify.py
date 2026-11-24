"""Construct and compare portable candidates on committed development tasks."""

import argparse
import json
from hashlib import sha256
from pathlib import Path
import signal
from time import time
from types import SimpleNamespace

from bridge.instruments import strict_portable_json
from bridge.output_schema import validate_output
from model_step import brief, object_schema, step
from native_experiment import NativeRefused, NativeUnavailable, require_worker, run as native
from pages import digest
from study import atomic, lock


SCHEMA = 'frontier/amplification-v1'
TRANSFER = 'frontier/amplification-transfer-v1'
ARMS = ('direct', 'harness', 'amplified')
CODE = object_schema({'hypothesis': brief(320), 'source': brief(11_000)})
STYLES = {
    'direct': 'Work as a competent independent scientist with a Python execution tool. Use the exact task, '
              'examples and any previous execution diagnostics to implement and improve the result.',
    'harness': 'Use the existing research harness process. Test a hypothesis, review development errors, '
               'and implement or repair an executable result.',
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
        except NativeUnavailable:
            raise
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
    except NativeUnavailable:
        raise
    except NativeRefused as error:
        return {'used': False, 'reason': str(error)}


def design(args):
    policy, freeze = read(args.registration)
    cases = development(args.development, policy['development_sha256'])
    require_worker()
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


def bound_instrument(path, registration):
    artifact, file_id = read(path)
    if type(artifact) is not dict:
        raise ValueError('INSTRUMENT_BINDING')
    if artifact.get('schema') != TRANSFER:
        if artifact.get('registration_sha256') != registration:
            raise ValueError('INSTRUMENT_BINDING')
        validate_output(artifact.get('result'), CODE)
        return artifact, file_id, None
    if artifact.get('target_registration_sha256') != registration or type(artifact.get('instrument_utf8')) is not str:
        raise ValueError('TRANSFER_BINDING')
    raw = artifact['instrument_utf8'].encode('utf-8')
    original = strict_portable_json(artifact['instrument_utf8'])
    if type(original) is not dict:
        raise ValueError('TRANSFER_PROVENANCE')
    validate_output(original.get('result'), CODE)
    old_scope = original.get('registration_sha256')
    if (type(old_scope) is not str or old_scope == registration or old_scope != artifact.get('source_registration_sha256')
            or sha256(raw).hexdigest() != artifact.get('instrument_sha256')
            or digest(original['result']['source']) != artifact.get('source_sha256')):
        raise ValueError('TRANSFER_PROVENANCE')
    return original, file_id, {'original_instrument_sha256':artifact['instrument_sha256'],
                               'original_registration_sha256':old_scope,'source_sha256':artifact['source_sha256']}


def prepare_transfer(args):
    policy, target = read(args.registration)
    with args.instrument.open('rb') as stream:
        raw = stream.read(200_001)
    if not 0 < len(raw) <= 200_000:
        raise ValueError('INSTRUMENT_SIZE')
    source_text = raw.decode('utf-8')
    original = strict_portable_json(source_text)
    origin = original.get('registration_sha256') if type(original) is dict else None
    if type(origin) is not str or origin == target or len(origin) != 64 or any(char not in '0123456789abcdef' for char in origin):
        raise ValueError('TRANSFER_ORIGIN')
    validate_output(original.get('result'), CODE)
    cases = development(args.development, policy['development_sha256'])
    record = {'schema':TRANSFER, 'source_registration_sha256':origin, 'target_registration_sha256':target,
              'instrument_sha256':sha256(raw).hexdigest(), 'source_sha256':digest(original['result']['source']),
              'instrument_utf8':source_text,
              'development_diagnostics':proposed_instrument(original['result'], policy['contract'], cases, [])}
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(canonical(record)+'\n')
    return {'schema':TRANSFER, 'source_registration_sha256':origin, 'target_registration_sha256':target,
            'instrument_sha256':record['instrument_sha256'], 'development_diagnostics':record['development_diagnostics']}


def construct(args):
    policy, freeze = read(args.registration)
    cases = development(args.development, policy['development_sha256'])
    spec = policy['comparisons'][args.model]
    if args.arm not in spec['arms']:
        raise ValueError('UNREGISTERED_ARM')
    if args.arm == 'amplified':
        if args.instrument is None:
            raise ValueError('INSTRUMENT_REQUIRED')
        instrument, instrument_id, transfer = bound_instrument(args.instrument,freeze)
    else:
        if args.instrument is not None:
            raise ValueError('CONTROL_INSTRUMENT')
        instrument, instrument_id, transfer = None, None, None
    args.workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
    config_id = sha256(args.config.read_bytes()).hexdigest()
    binding = {'registration': freeze, 'model': args.model, 'model_config': config_id,
               'arm': args.arm, 'instrument': instrument_id, 'lease_until': args.until}
    if transfer is not None:
        binding['transfer'] = transfer
    path = args.workspace/'amplification-status.json'
    with lock(args.workspace):
        record = read(path)[0] if path.exists() else {'schema': SCHEMA, 'objective': policy['objective'],
                                                        'binding': binding, 'state': 'RUNNING', 'attempts': []}
        if record['binding'] != binding:
            raise ValueError('STUDY_BINDING')
        if record['state'] != 'RUNNING':
            return record
        require_worker()
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
            instructions = STYLES['direct' if args.arm == 'direct' else 'harness']
            prompt = (f'{instructions} Return a JSON object with hypothesis and source. The source defines '
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


def compare(args):
    """Drain the registered constructor arms and leave confirmation to an evaluator."""
    policy, freeze = read(args.registration)
    allowed = policy['comparisons'][args.model]['arms']
    order = [arm for arm in policy.get('execution_order', {}).get(args.model, allowed) if arm != 'design']
    if set(order) != set(allowed) or not set(order) <= set(ARMS) or len(order) != len(allowed) or len(order) != len(set(order)):
        raise ValueError('COMPARISON_ORDER')
    if not args.prefix.isascii() or not args.prefix.replace('-', '').isalnum() or len(args.prefix) > 30:
        raise ValueError('COMPARISON_PREFIX')
    args.workspace.mkdir(mode=0o700, parents=True, exist_ok=True)
    binding = {'registration': freeze, 'model': args.model, 'lease': args.until,
               'config_sha256': sha256(args.config.read_bytes()).hexdigest()}
    seal = args.workspace / (args.prefix+'-comparison.json')
    with lock(args.workspace):
        result = read(seal)[0] if seal.exists() else {'schema': 'frontier/amplification-queue-v1', 'binding': binding,
                                                     'arms': {arm: 'QUEUED' for arm in order}}
        if result['binding'] != binding or list(result['arms']) != order:
            raise ValueError('COMPARISON_BINDING')
        result['state'] = 'RUNNING'
        atomic(seal, result)
        for arm in order:
            target = args.workspace/(args.prefix+'-'+arm)
            chosen = args.instrument if arm == 'amplified' else None
            if arm == 'amplified' and chosen is None:
                result['arms'][arm] = 'AWAITING_INSTRUMENT'
                atomic(seal, result)
                continue
            result['arms'][arm] = 'RUNNING'
            atomic(seal, result)
            finished = construct(SimpleNamespace(registration=args.registration, development=args.development,
                workspace=target, config=args.config, model=args.model, until=args.until, arm=arm, instrument=chosen))
            result['arms'][arm] = finished['state']
            atomic(seal, result)
        if 'AWAITING_INSTRUMENT' not in result['arms'].values():
            result['state'] = 'EVALUATION_READY'
        atomic(seal, result)
    return result


def evaluate(args):
    policy, freeze = read(args.registration)
    cases = development(args.confirmation, policy['confirmation_sha256'])
    require_worker()
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
    for name, action in (('design', design), ('construct', construct), ('compare', compare)):
        cli = sub.add_parser(name)
        cli.set_defaults(action=action)
        for flag in ('registration', 'development', 'workspace', 'config'):
            cli.add_argument('--'+flag, type=Path, required=True)
        cli.add_argument('--model', required=True)
        cli.add_argument('--until', type=int, required=True)
        if name == 'construct':
            cli.add_argument('--arm', choices=ARMS, required=True)
        if name != 'design':
            cli.add_argument('--instrument', type=Path)
        if name == 'compare':
            cli.add_argument('--prefix', default='trial')
    cli = sub.add_parser('evaluate')
    cli.set_defaults(action=evaluate)
    cli.add_argument('--registration', type=Path, required=True)
    cli.add_argument('--confirmation', type=Path, required=True)
    cli.add_argument('checkpoints', type=Path, nargs='+')
    cli = sub.add_parser('transfer')
    cli.set_defaults(action=prepare_transfer)
    for flag in ('registration','development','instrument','output'):
        cli.add_argument('--'+flag,type=Path,required=True)
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
