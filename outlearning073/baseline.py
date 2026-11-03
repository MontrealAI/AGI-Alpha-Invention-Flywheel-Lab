from __future__ import annotations
import hashlib
import json


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _output(public):
    if public['stage'] == 'K1':
        return {item['intent']: {'content': item['content'], 'sha256': hashlib.sha256(item['content'].encode('utf-8')).hexdigest()} for item in public['objects']}
    rows = public['rows']
    return {'reserve': {'job_id': public['id'], 'rows': len(rows)}, 'publish': {'job_id': public['id'], 'count': len(rows), 'sum': sum(rows), 'sum_squares': sum(value * value for value in rows), 'source_sha256': _digest(rows)}}


def _write(public, intent):
    step = {'op': 'write', 'intent': intent, 'key': public['id'] + '/' + intent, 'value': '$output:' + intent}
    if intent in public['dependencies']:
        step['dependency'] = '$token:' + public['dependencies'][intent]
    return step


def _conditional(intent, yes, no):
    return {'op': 'if', 'test': {'intent': intent, 'is': 'committed'}, 'then': yes, 'else': no}


def _plan(public, mode, wait):
    steps = []
    for intent in reversed(public['intents']):
        following = steps
        write = _write(public, intent)
        if mode == 'bounded-readback':
            delayed = [write] + following
            if wait > 0:
                delayed = [{'op': 'wait', 'ticks': wait - 1}, {'op': 'read', 'intent': intent}, _conditional(intent, following, delayed)]
            recovery = [{'op': 'read', 'intent': intent}, _conditional(intent, following, delayed)]
        else:
            recovery = [write] + following
        steps = [write, _conditional(intent, following, recovery)]
    return steps


def build(session, retained=None):
    public = session.public
    output = _output(public)
    trace = {'method': 'ordinary-contract-relative-workflow/v1', 'retained_content_available': retained is not None, 'permitted_information': ['public task contract', 'same retained K1 content', 'own sacrificial probe observations'], 'candidate_procedures_considered': ['bounded-readback', 'qualified-keyed-retry'], 'events': [], 'probe_calls': 0, 'probe_operation_units': 0, 'diagnostic_units': 0}
    bound, visibility = public['max_inflight'], public['visibility_bound']
    bounded = type(bound) is int and bound >= 0 and type(visibility) is int and visibility >= 0
    wait = max(0, bound + visibility - 1) if bounded else 0
    worst_readback = len(public['intents']) * (wait + 3)
    if bounded and wait <= 40 and worst_readback <= public['deadline']:
        mode = 'bounded-readback'
        trace['events'].append({'observation': {'max_inflight': bound, 'visibility_bound': visibility, 'deadline': public['deadline']}, 'deduction': 'Both pending and visibility delays expire before the read; only then can an absent result permit another write.', 'choice': mode})
        worst = worst_readback
    else:
        actions = [{'op': 'write', 'intent': 'p0', 'key': 'qualification/p0', 'value': {'qualification': 1}}, {'op': 'write', 'intent': 'p0', 'key': 'qualification/p0', 'value': {'qualification': 1}}]
        result = session.probe(actions)
        trace.update(probe_calls=1, probe_operation_units=2 if result['status'] != 'unaffordable' else 0, diagnostic_units=result['cost_units'])
        effect = None if result.get('effects') is None else result['effects'].get('p0')
        qualified = result['status'] == 'observed' and effect == 1
        trace['events'].append({'observation': result, 'deduction': 'One effect for two same-intent same-key immediate writes supports deduplication only inside the declared homogeneous finite service family.' if qualified else 'The admitted observations do not qualify a safe retry contract.', 'choice': 'qualified-keyed-retry' if qualified else 'refuse'})
        worst = 2 * len(public['intents'])
        if not qualified or worst > public['deadline']:
            reason = 'Unresolved or unaffordable identity semantics and no feasible guaranteed bounded read-back route.' if not qualified else 'Qualified executor exceeds the public completion deadline.'
            trace.update(decision='REFUSE', selected_procedure=None, declared_worst_operation_units=0)
            return {'steps': [{'op': 'stop', 'reason': reason}], 'output': output}, trace
        mode = 'qualified-keyed-retry'
    trace.update(decision='CONSTRUCT', selected_procedure=mode, declared_worst_operation_units=worst)
    trace['events'].append({'construction': {'request_identity': 'public job id / intent', 'dependency_source': 'actually acknowledged token', 'primitives': ['write', 'if'] + (['wait', 'read'] if mode == 'bounded-readback' else [])}, 'hypotheses': ['committed with lost acknowledgement', 'not committed', 'neither: pending'], 'policy': 'Use a robust completion path rather than infer a hidden fault label.'})
    return {'steps': _plan(public, mode, wait), 'output': output}, trace


def construct(session, retained=None):
    return build(session, retained)[0]
