"""Independent acceptance of actual effects and exact synthetic data products."""
from __future__ import annotations
import copy
import hashlib
from .worlds import ToolSandbox, _spec, fault_schedules, identity, validate_request


def _expected(public):
    if public['stage'] == 'K1':
        return {row['intent']: {'content': row['content'], 'sha256': hashlib.sha256(row['content'].encode()).hexdigest()} for row in public['objects']}
    values = public['rows']
    return {'reserve': {'job_id': public['id'], 'rows': len(values)}, 'publish': {'job_id': public['id'], 'count': len(values), 'sum': sum(values), 'sum_squares': sum(x * x for x in values), 'source_sha256': identity(values)}}


def grade_execution(public, artifact, sandbox, end_time, error=None):
    expected = _expected(public)
    output_ok = artifact['output'] == expected
    counts = {intent: len([e for e in sandbox.effects if e['intent'] == intent]) for intent in public['intents']}
    exact_once = all(count == 1 for count in counts.values())
    content_ok = all(e['intent'] in expected and e['payload'] == expected[e['intent']] for e in sandbox.effects)
    dependency_ok = True
    if public['stage'] == 'K2':
        reserve = [e for e in sandbox.effects if e['intent'] == 'reserve']
        publish = [e for e in sandbox.effects if e['intent'] == 'publish']
        dependency_ok = len(reserve) == len(publish) == 1 and publish[0]['dependency'] == reserve[0]['token'] and reserve[0]['committed_at'] <= publish[0]['submitted_at']
        if dependency_ok:
            dependency_ok = any(o['intent'] == 'reserve' and o['status'] == 'committed' and o.get('token') == reserve[0]['token'] and o['time'] <= publish[0]['submitted_at'] for o in sandbox.trace)
    deadline_ok = all(e['committed_at'] <= public['deadline'] for e in sandbox.effects) and end_time <= public['deadline']
    accepted = error is None and output_ok and exact_once and content_ok and dependency_ok and deadline_ok and not sandbox.stopped
    harm = sum(max(0, count - 1) for count in counts.values()) * 7 + (0 if content_ok else 11) + (0 if dependency_ok or not sandbox.effects else 5)
    return {'accepted': accepted, 'counts': counts, 'output_ok': output_ok, 'content_ok': content_ok, 'dependency_ok': dependency_ok, 'deadline_ok': deadline_ok, 'cost_units': sandbox.cost_units, 'avoidable_loss_units': harm, 'end_time': end_time, 'error': error, 'stopped': sandbox.stopped, 'trace_sha256': identity(sandbox.trace), 'effects_sha256': identity(sandbox.effects)}


def verify(request, artifact):
    request = validate_request(request)
    spec = _spec(request)
    public = spec['public']
    if not isinstance(artifact, dict) or set(artifact) != {'steps', 'output'} or not isinstance(artifact['steps'], list) or not isinstance(artifact['output'], dict):
        return {'accepted': False, 'reason': 'EXACT_EXECUTABLE_ARTIFACT_REQUIRED', 'request_sha256': identity(request)}
    results = []
    for faults in fault_schedules(public):
        sandbox = ToolSandbox(spec, faults)
        error = None
        try:
            sandbox.execute(artifact['steps'], artifact['output'])
        except (ValueError, KeyError, TypeError, RecursionError) as exc:
            error = type(exc).__name__ + ':' + str(exc)[:180]
        end_time = sandbox.time
        sandbox.drain()
        results.append({'faults': faults, **grade_execution(public, artifact, sandbox, end_time, error)})
    accepted = all(row['accepted'] for row in results)
    declined = bool(artifact['steps'] and artifact['steps'][0].get('op') == 'stop')
    return {'accepted': accepted, 'decision': 'DELIVER' if accepted else 'REFUSE' if declined else 'REJECT', 'scope': 'FINITE_AUTHORED_SOFTWARE_MODEL', 'request_sha256': identity(request), 'artifact_sha256': identity(artifact), 'fault_schedules': len(results), 'accepted_schedules': sum(row['accepted'] for row in results), 'maximum_operation_units': max(row['cost_units'] for row in results), 'maximum_avoidable_loss_units': max(row['avoidable_loss_units'] for row in results), 'output_ok': artifact['output'] == _expected(public), 'results': results}
