import copy
import importlib
import json
from pathlib import Path

from .world import OPS, RESPONSES, SCHEDULES, Provider, ProbeSession, digest, make_world, public_task


def validate_program(spec, program):
    if not isinstance(program, dict) or set(program) != {'entry', 'nodes'}:
        raise ValueError('INERT_GRAPH_REQUIRED')
    nodes = program['nodes']
    if not isinstance(nodes, dict) or not 1 <= len(nodes) <= 256 or program['entry'] not in nodes:
        raise ValueError('BOUNDED_GRAPH_REQUIRED')
    providers = {p['id'] for p in spec['providers']}
    for name, node in nodes.items():
        if not isinstance(name, str) or not isinstance(node, dict):
            raise ValueError('NAMED_NODE_REQUIRED')
        if 'finish' in node:
            if set(node) != {'finish', 'obligations'} or node['finish'] not in ('delivered', 'aborted', 'unresolved'):
                raise ValueError('VALID_FINISH_REQUIRED')
            obligations = node['obligations']
            if not isinstance(obligations, list) or len(set(obligations)) != len(obligations) or not set(obligations) <= providers:
                raise ValueError('DECLARED_OBLIGATIONS_REQUIRED')
        else:
            if set(node) - {'op', 'provider', 'token', 'next', 'ticks'} or not {'op', 'provider', 'next'} <= set(node):
                raise ValueError('VALID_CALL_REQUIRED')
            if node['op'] not in OPS or node['provider'] not in providers or node.get('token', 'order') != 'order':
                raise ValueError('CURRENT_ORDER_OPERATION_REQUIRED')
            ticks = node.get('ticks', 1)
            if type(ticks) is not int or not 1 <= ticks <= 8:
                raise ValueError('BOUNDED_WAIT_REQUIRED')
            branches = node['next']
            if not isinstance(branches, dict) or '*' not in branches or not set(branches) <= set(RESPONSES) | {'*'} or not set(branches.values()) <= set(nodes):
                raise ValueError('TOTAL_RESPONSE_BRANCHES_REQUIRED')
    return True


def _acceptance(spec, states, disposition, declared, cost, trace, schedule, stopped):
    providers = [p['id'] for p in spec['providers']]
    counts = {ident: len(states[ident].effects) for ident in providers}
    holds = {ident: len(states[ident].holds) for ident in providers}
    actual_obligations = sorted(ident for ident in providers if counts[ident] or holds[ident])
    all_once = all(counts[ident] == 1 for ident in providers) and not any(holds.values())
    none_left = not actual_obligations
    delivered = disposition == 'delivered' and all_once and not declared and not stopped
    safe_abort = disposition == 'aborted' and none_left and not declared and not stopped
    truthful = set(actual_obligations) <= set(declared) if disposition == 'unresolved' else delivered or safe_abort
    effect_loss = 0 if delivered else sum(counts[p['id']] * p['config']['effect_cost_microUSD'] for p in spec['providers'])
    excess_loss = sum(max(0, counts[ident]-1) for ident in providers) * spec['loss_per_excess_effect_microUSD']
    partial = any(counts.values()) and not delivered
    concealed = bool(actual_obligations) and not delivered and not truthful
    harm = partial or concealed or excess_loss > 0
    return {'schedule': schedule, 'disposition': disposition, 'delivered': delivered,
            'safe_abort': safe_abort, 'safe': delivered or safe_abort,
            'unresolved': disposition == 'unresolved' or stopped,
            'harm': harm, 'truthful_obligations': truthful,
            'effect_counts': counts, 'hold_counts': holds,
            'residual_obligations': [] if delivered else actual_obligations,
            'declared_obligations': sorted(declared), 'operation_cost_microUSD': cost,
            'residual_exposure_microUSD': effect_loss + excess_loss,
            'steps': len(trace), 'stopped_at_bound': stopped,
            'trace': trace}


def execute_program(spec, program, schedule):
    validate_program(spec, program)
    if schedule not in SCHEDULES:
        raise ValueError('REGISTERED_SCHEDULE_REQUIRED')
    states = {p['id']: Provider(p['config']) for p in spec['providers']}
    prices = {p['id']: p['call_microUSD'] for p in spec['providers']}
    refused_provider = spec['refusal_provider']
    node_id, cost, trace = program['entry'], 0, []
    used_fault = set()
    for _ in range(spec['max_steps']+1):
        node = program['nodes'][node_id]
        if 'finish' in node:
            return _acceptance(spec, states, node['finish'], node['obligations'], cost, trace, schedule, False)
        if len(trace) >= spec['max_steps']:
            break
        ident, op = node['provider'], node['op']
        fault = 'none'
        productive = op == 'execute' or (op == 'commit' and states[ident].cfg['prepare'] and
                     (node.get('token', 'order') in states[ident].holds or
                      any(e['token'] == node.get('token', 'order') for e in states[ident].effects)))
        if productive and ident not in used_fault:
            if schedule == 'lost_request':
                fault = 'request_lost'
            elif schedule == 'lost_ack':
                fault = 'ack_lost'
            used_fault.add(ident)
        ticks = node.get('ticks', 1) if op == 'wait' else 1
        for other, engine in states.items():
            if other != ident:
                engine._advance(ticks)
        response = states[ident].call(op, node.get('token', 'order'), fault=fault, ticks=ticks,
                                     refuse=schedule == 'provider_refusal' and ident == refused_provider)
        cost += prices[ident]
        trace.append({'node': node_id, 'provider': ident, 'op': op, 'response': response,
                      'cost_microUSD': prices[ident]})
        node_id = node['next'].get(response, node['next']['*'])
    return _acceptance(spec, states, 'unresolved', [], cost, trace, schedule, True)


def evaluate(spec, program):
    try:
        validate_program(spec, program)
        outcomes = [execute_program(spec, program, schedule) for schedule in SCHEDULES]
        all_safe = all(row['safe'] for row in outcomes)
        return {'schema': 'outlearning-independent-evaluation/v1', 'world_id': spec['world_id'],
                'world_sha256': digest(spec), 'program_sha256': digest(program),
                'valid_program': True, 'all_safe': all_safe,
                'accepted': all_safe and any(row['delivered'] for row in outcomes),
                'delivered_count': sum(row['delivered'] for row in outcomes),
                'safe_abort_count': sum(row['safe_abort'] for row in outcomes),
                'harm_count': sum(row['harm'] for row in outcomes),
                'operation_cost_microUSD': sum(row['operation_cost_microUSD'] for row in outcomes),
                'residual_exposure_microUSD': sum(row['residual_exposure_microUSD'] for row in outcomes),
                'outcomes': outcomes}
    except (ValueError, TypeError, KeyError) as exc:
        return {'schema': 'outlearning-independent-evaluation/v1', 'world_id': spec['world_id'],
                'world_sha256': digest(spec), 'program_sha256': digest(program),
                'valid_program': False, 'all_safe': False, 'accepted': False,
                'delivered_count': 0, 'safe_abort_count': 0, 'harm_count': 0,
                'operation_cost_microUSD': 0, 'residual_exposure_microUSD': 0,
                'outcomes': [], 'error': str(exc)}


def run_construction(spec, construct):
    probe = ProbeSession(spec)
    task = public_task(spec)
    result = construct(copy.deepcopy(task), probe)
    if isinstance(result, dict) and 'program' in result:
        program = result['program']
        metadata = {k: v for k, v in result.items() if k != 'program'}
    else:
        program, metadata = result, {}
    evaluation = evaluate(spec, program)
    return {'task': task, 'program': program, 'construction': metadata,
            'probe_cost_microUSD': probe.spent_microUSD, 'probe_transcript': probe.transcript,
            'evaluation': evaluation}


def confirmation_specs():
    for stratum in range(6):
        for replicate in range(8):
            seed = 'OUTLEARN-20261102-906c4f4d/confirmation/v1/' + str(stratum) + '/' + str(replicate)
            yield make_world(seed, 'K2', stratum)


def development_specs():
    for i in range(8):
        yield make_world('development-only-' + str(i), 'K1', i)


def summary(rows):
    return {'worlds': len(rows),
            'schedules': 4 * len(rows),
            'valid_programs': sum(r['evaluation']['valid_program'] for r in rows),
            'all_safe_worlds': sum(r['evaluation']['all_safe'] for r in rows),
            'accepted_worlds': sum(r['evaluation']['accepted'] for r in rows),
            'delivered_schedules': sum(r['evaluation']['delivered_count'] for r in rows),
            'safe_abort_schedules': sum(r['evaluation']['safe_abort_count'] for r in rows),
            'harm_schedules': sum(r['evaluation']['harm_count'] for r in rows),
            'probe_cost_microUSD': sum(r['probe_cost_microUSD'] for r in rows),
            'operation_cost_microUSD': sum(r['evaluation']['operation_cost_microUSD'] for r in rows),
            'residual_exposure_microUSD': sum(r['evaluation']['residual_exposure_microUSD'] for r in rows)}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--method', required=True)
    parser.add_argument('--phase', choices=('development', 'confirmation'), default='development')
    parser.add_argument('--output', required=True)
    parser.add_argument('--freeze', help='Source freeze manifest is mandatory for confirmation')
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('NEW_OUTPUT_REQUIRED_NO_TRIAL_REPLACEMENT')
    if args.phase == 'confirmation':
        if not args.freeze:
            raise ValueError('PUBLISHED_SOURCE_FREEZE_REQUIRED')
        frozen = json.loads(Path(args.freeze).read_text())
        root = Path(__file__).resolve().parents[2]
        for name, expected in frozen['files'].items():
            import hashlib
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
                raise ValueError('SOURCE_FREEZE_MISMATCH:' + name)
    method = importlib.import_module(args.method).construct
    specs = development_specs() if args.phase == 'development' else confirmation_specs()
    rows = [run_construction(spec, method) for spec in specs]
    result = {'phase': args.phase, 'method': args.method, 'summary': summary(rows), 'rows': rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, sort_keys=True, indent=2)+'\n')
    print(json.dumps(result['summary'], sort_keys=True))


if __name__ == '__main__':
    main()
