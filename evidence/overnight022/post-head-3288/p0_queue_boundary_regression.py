#!/usr/bin/env python3
"""Read-only P0 migration boundary oracle; never authenticates or changes an account."""
import argparse
import hashlib
import json
from pathlib import Path
import unittest

FIXTURE_BLOBS = {
    'checkpoint': '91a4c08cac3a5d789d7dd9429815c1168c935bd5',
    'original': '70d843141bb5d399eec15f9ea21805fcdc392023',
    'upgraded': 'b77756b8ade1029b7ab28ce4e2e93beb3be09bc8',
}


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('DUPLICATE_JSON_FIELD:' + key)
        result[key] = value
    return result


def load_fixture(path, expected_sha):
    data = Path(path).read_bytes()
    actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if actual != expected_sha:
        raise ValueError('IMMUTABLE_FIXTURE_BLOB_CHANGED')
    return json.loads(data, object_pairs_hook=strict_object)


def clock_probe(checkpoint, original, proposed_hour):
    if type(proposed_hour) is not int or proposed_hour < 0:
        return {'eligible': False, 'errors': ['NONNEGATIVE_INTEGER_CLOCK_REQUIRED']}
    body, ledger = checkpoint['body'], original['ledger']
    state = body['state']
    queue = state['queue']
    native_last = max((entry['day'] for entry in ledger['actions']), default=0)
    pending_first = min((entry['time'] for entry in queue), default=None)
    errors = []
    if body['native_sequence'] != len(ledger['actions']) or body['native_actions_sha256'] != ledger['actions_sha256']:
        errors.append('ORIGINAL_NATIVE_PREFIX_MISMATCH')
    if body['source_sha256'] != original['connected_journal']['source']['sha256'] or body['contract'] != original['connected_journal']['contract']:
        errors.append('ORIGINAL_FINANCIAL_SOURCE_OR_CONTRACT_MISMATCH')
    if state.get('current') is not None:
        errors.append('INFLIGHT_EVENT_REQUIRES_AUTHENTICATED_INTENT_RECOVERY')
    if not queue:
        errors.append('NONEMPTY_QUEUE_FIXTURE_REQUIRED')
    elif (len({entry['id'] for entry in queue}) != len(queue)
          or any(type(entry.get('time')) is not int or not isinstance(entry.get('id'), str) for entry in queue)
          or any((queue[i]['time'], queue[i]['id']) > (queue[i + 1]['time'], queue[i + 1]['id']) for i in range(len(queue) - 1))
          or any(entry['time'] < state['last_time'] for entry in queue)):
        errors.append('LEGACY_QUEUE_PROVENANCE_INVALID')
    if proposed_hour < max(native_last, state['last_time']):
        errors.append('SOURCE_UPGRADE_CLOCK_ROLLBACK')
    if pending_first is not None and proposed_hour > pending_first:
        errors.append('SOURCE_UPGRADE_OVERTAKES_PENDING_EVENT')
    return {'eligible': not errors, 'errors': errors, 'native_last_hour': native_last,
            'operating_last_hour': state['last_time'], 'first_pending_hour': pending_first,
            'pending_events': len(queue), 'processed_events': state['processed_events'],
            'emitted_semantic_events': len(state['events'])}


def preservation_probe(checkpoint, original, upgraded):
    old, new = original['ledger'], upgraded['ledger']
    actions, new_actions = old['actions'], new['actions']
    transitions = upgraded.get('source_transitions', {})
    errors = []
    if len(new_actions) != len(actions) + 1 or new_actions[:len(actions)] != actions:
        errors.append('NATIVE_ACTION_PREFIX_CHANGED')
    if new['summary'] != old['summary'] or upgraded['snapshot']['summary'] != original['snapshot']['summary']:
        errors.append('FINANCIAL_LIABILITIES_OR_BALANCES_CHANGED')
    if len(transitions) != 1 or new_actions[-1]['op'] != 'source_transition':
        errors.append('EXACTLY_ONE_SOURCE_TRANSITION_REQUIRED')
    else:
        transition = new_actions[-1]
        ticket = next(iter(transitions.values()))['body']
        if (ticket['prior_record'] != original or ticket['day'] != transition['day']
                or ticket['from_source']['sha256'] != checkpoint['body']['source_sha256']
                or transition['before'] != transition['after']
                or ticket['prior_envelope']['body'] != original['connected_journal']):
            errors.append('UNBOUND_OR_NONNEUTRAL_SOURCE_TRANSITION')
    return {'preserved': not errors, 'errors': errors,
            'original_actions': len(actions), 'upgraded_actions': len(new_actions)}


class Regression(unittest.TestCase):
    def setUp(self):
        self.original = {'ledger': {'actions': [{'day': 0}], 'actions_sha256': 'actions', 'summary': {'cash': 7, 'reserve': 3}},
                         'snapshot': {'summary': {'cash': 7, 'reserve': 3}},
                         'connected_journal': {'contract': 'c', 'source': {'sha256': 'src'}}}
        self.checkpoint = {'body': {'native_sequence': 1, 'native_actions_sha256': 'actions', 'source_sha256': 'src',
                                   'contract': 'c', 'state': {'last_time': 2, 'current': None, 'processed_events': 3,
                                   'events': [1, 2, 3, 4], 'queue': [{'id': 'accept', 'time': 3}, {'id': 'plan', 'time': 24}]}}}
        ticket = {'prior_record': self.original, 'day': 2, 'from_source': {'sha256': 'src'},
                  'prior_envelope': {'body': self.original['connected_journal']}}
        self.upgraded = {'ledger': {'actions': [{'day': 0}, {'op': 'source_transition', 'day': 2,
                         'before': {'cash': 7, 'reserve': 3}, 'after': {'cash': 7, 'reserve': 3}}],
                         'summary': {'cash': 7, 'reserve': 3}},
                         'snapshot': {'summary': {'cash': 7, 'reserve': 3}}, 'source_transitions': {'ticket': {'body': ticket}}}

    def test_same_clock_and_native_prefix_pass_structurally(self):
        self.assertTrue(clock_probe(self.checkpoint, self.original, 2)['eligible'])
        self.assertTrue(preservation_probe(self.checkpoint, self.original, self.upgraded)['preserved'])

    def test_native_only_late_clock_is_rejected(self):
        result = clock_probe(self.checkpoint, self.original, 4)
        self.assertIn('SOURCE_UPGRADE_OVERTAKES_PENDING_EVENT', result['errors'])

    def test_rollback_duplicated_queue_and_inflight_are_rejected(self):
        self.assertIn('SOURCE_UPGRADE_CLOCK_ROLLBACK', clock_probe(self.checkpoint, self.original, 1)['errors'])
        self.checkpoint['body']['state']['queue'].append({'id': 'accept', 'time': 3})
        self.assertIn('LEGACY_QUEUE_PROVENANCE_INVALID', clock_probe(self.checkpoint, self.original, 2)['errors'])
        self.checkpoint['body']['state']['current'] = {'id': 'accept'}
        self.assertIn('INFLIGHT_EVENT_REQUIRES_AUTHENTICATED_INTENT_RECOVERY', clock_probe(self.checkpoint, self.original, 2)['errors'])

    def test_same_hour_legacy_queue_tie_order_is_preserved(self):
        queue = self.checkpoint['body']['state']['queue']
        queue[:] = [{'id': 'plan-b', 'time': 3}, {'id': 'accept-a', 'time': 3}]
        self.assertIn('LEGACY_QUEUE_PROVENANCE_INVALID', clock_probe(self.checkpoint, self.original, 2)['errors'])
        queue.reverse()
        self.assertTrue(clock_probe(self.checkpoint, self.original, 2)['eligible'])

    def test_noninteger_queue_clock_is_rejected(self):
        self.checkpoint['body']['state']['queue'][0]['time'] = 3.0
        self.assertIn('LEGACY_QUEUE_PROVENANCE_INVALID', clock_probe(self.checkpoint, self.original, 2)['errors'])

    def test_changed_liability_or_prefix_is_rejected(self):
        self.upgraded['ledger']['summary']['reserve'] = 0
        self.assertIn('FINANCIAL_LIABILITIES_OR_BALANCES_CHANGED', preservation_probe(self.checkpoint, self.original, self.upgraded)['errors'])
        self.upgraded['ledger']['actions'][0] = {'day': 99}
        self.assertIn('NATIVE_ACTION_PREFIX_CHANGED', preservation_probe(self.checkpoint, self.original, self.upgraded)['errors'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--checkpoint')
    parser.add_argument('--original')
    parser.add_argument('--upgraded')
    parser.add_argument('--hour', type=int, default=2)
    parser.add_argument('--self-test', action='store_true')
    options = parser.parse_args()
    if options.self_test:
        unittest.main(argv=['p0_queue_boundary_regression.py'], exit=False, verbosity=2)
    else:
        if not all([options.checkpoint, options.original, options.upgraded]):
            parser.error('all three immutable public fixture paths are required')
        c = load_fixture(options.checkpoint, FIXTURE_BLOBS['checkpoint'])
        o = load_fixture(options.original, FIXTURE_BLOBS['original'])
        u = load_fixture(options.upgraded, FIXTURE_BLOBS['upgraded'])
        print(json.dumps({'scope': 'UNSIGNED_PUBLIC_STRUCTURAL_PREFLIGHT_NOT_AN_AUTHENTICATED_MIGRATION',
                          'clock': clock_probe(c, o, options.hour), 'preservation': preservation_probe(c, o, u)}, sort_keys=True))
