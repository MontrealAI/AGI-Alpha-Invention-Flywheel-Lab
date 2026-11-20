"""Synthetic, authority-external AI governance change-impact construction.

No regulatory interpretation, signer, real RBAC, native account, or customer access.
"""
from __future__ import annotations
import hashlib
import json
from copy import deepcopy

STATUSES = frozenset({'MET', 'PARTIAL', 'NOT_MET', 'UNABLE_TO_DETERMINE', 'NOT_APPLICABLE'})
ACTIONS = frozenset({'UPDATED', 'ADDED', 'RETIRED'})
DECISIONS = frozenset({'ACCEPT_FINDING', 'REJECT_FINDING', 'REQUEST_MORE_EVIDENCE'})
GENESIS = '0' * 64


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def _keys(obj, expected, label):
    if not isinstance(obj, dict) or set(obj) != set(expected):
        raise ValueError('EXACT_' + label + '_FIELDS_REQUIRED')


def _identity(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 128


def _version(v):
    return type(v) is int and v > 0


def validate_change(change):
    _keys(change, {'tenant', 'requirement_id', 'from_version', 'to_version', 'action'}, 'CHANGE')
    if not _identity(change['tenant']) or not _identity(change['requirement_id']):
        raise ValueError('CHANGE_IDENTITY_REQUIRED')
    if change['action'] not in ACTIONS or not _version(change['to_version']):
        raise ValueError('CHANGE_ACTION_OR_VERSION_INVALID')
    if change['action'] == 'ADDED':
        if change['from_version'] is not None:
            raise ValueError('ADDED_MUST_HAVE_NO_PRIOR_VERSION')
    elif not _version(change['from_version']) or change['to_version'] <= change['from_version']:
        raise ValueError('MONOTONIC_REQUIREMENT_VERSION_REQUIRED')


def validate_system(system):
    _keys(system, {'tenant', 'system_id', 'requirements', 'evidence'}, 'SYSTEM')
    if not _identity(system['tenant']) or not _identity(system['system_id']):
        raise ValueError('SYSTEM_IDENTITY_REQUIRED')
    if not isinstance(system['requirements'], list) or any(not _identity(r) for r in system['requirements']):
        raise ValueError('REQUIREMENT_IDENTIFIERS_REQUIRED')
    if len(set(system['requirements'])) != len(system['requirements']):
        raise ValueError('DUPLICATE_REQUIREMENT')
    if not isinstance(system['evidence'], list):
        raise ValueError('EVIDENCE_LIST_REQUIRED')
    seen = set()
    for record in system['evidence']:
        _keys(record, {'requirement_id', 'version', 'status', 'verified', 'reference'}, 'EVIDENCE')
        if not _identity(record['requirement_id']) or not _version(record['version']):
            raise ValueError('EVIDENCE_ID_OR_VERSION_INVALID')
        if record['status'] not in STATUSES or type(record['verified']) is not bool:
            raise ValueError('EVIDENCE_VERDICT_INVALID')
        if not _identity(record['reference']):
            raise ValueError('EVIDENCE_REFERENCE_REQUIRED')
        key = (record['requirement_id'], record['version'])
        if key in seen:
            raise ValueError('CONFLICTING_EVIDENCE_FOR_VERSION')
        seen.add(key)


def ordinary_affected(change, systems):
    """Competent conventional indexed-list comparison with the same data and scope."""
    validate_change(change)
    return sorted(s['system_id'] for s in systems
                  if s['tenant'] == change['tenant'] and change['requirement_id'] in s['requirements'])


def assess(change, systems):
    """Deterministic impact, not an opinion on legal compliance.

    All policy meaning, applicability and evidence-verification flags are supplied
    by a separately authoritative reviewer; they are not authenticated here.
    """
    validate_change(change)
    if not isinstance(systems, list):
        raise ValueError('SYSTEM_LIST_REQUIRED')
    identities = set()
    for s in systems:
        validate_system(s)
        identity = (s['tenant'], s['system_id'])
        if identity in identities:
            raise ValueError('DUPLICATE_SYSTEM_IDENTITY')
        identities.add(identity)
    target = ordinary_affected(change, systems)
    findings = []
    for s in systems:
        if s['tenant'] != change['tenant'] or change['requirement_id'] not in s['requirements']:
            continue
        evidence = next((r for r in s['evidence'] if r['requirement_id'] == change['requirement_id']
                         and r['version'] == change['to_version'] and r['verified']), None)
        if change['action'] == 'RETIRED':
            verdict = 'NOT_APPLICABLE'
            reference = None
        else:
            verdict = evidence['status'] if evidence is not None else 'UNABLE_TO_DETERMINE'
            reference = evidence['reference'] if evidence is not None else None
        finding = {'tenant': s['tenant'], 'system_id': s['system_id'],
                   'requirement_id': change['requirement_id'], 'requirement_version': change['to_version'],
                   'action': change['action'], 'evidence_state': verdict,
                   'evidence_reference': reference, 'decision': 'REASSESSMENT_NEEDED'}
        finding['finding_id'] = digest(finding)
        findings.append(finding)
    findings.sort(key=lambda r: r['system_id'])
    if [r['system_id'] for r in findings] != target:
        raise ValueError('ORDINARY_COMPARATOR_MISMATCH')
    return {'schema': 'agi-alpha/impact197/synthetic/v1', 'tenant': change['tenant'],
            'change': deepcopy(change), 'findings': findings, 'ordinary_tie': True,
            'authority': 'UNVERIFIED_EXPLICIT_HUMAN_CURATED_INPUT'}


class AuditChain:
    """Integrity-only history; no signature, durable write lock, or actor authentication."""
    def __init__(self):
        self.events = []

    def append(self, payload):
        if not isinstance(payload, dict):
            raise ValueError('EVENT_DICT_REQUIRED')
        prior = self.events[-1]['hash'] if self.events else GENESIS
        event = {'sequence': len(self.events) + 1, 'previous_hash': prior, 'payload': deepcopy(payload)}
        event['hash'] = digest(event)
        self.events.append(event)
        return deepcopy(event)

    @staticmethod
    def verify(events):
        if not isinstance(events, list):
            raise ValueError('AUDIT_LIST_REQUIRED')
        prior = GENESIS
        for index, event in enumerate(events, 1):
            _keys(event, {'sequence', 'previous_hash', 'payload', 'hash'}, 'AUDIT_EVENT')
            if type(event['sequence']) is not int or event['sequence'] != index or event['previous_hash'] != prior:
                raise ValueError('AUDIT_REORDER_OR_FORK')
            if not isinstance(event['payload'], dict):
                raise ValueError('AUDIT_PAYLOAD_REQUIRED')
            if event['hash'] != digest({k: event[k] for k in ('sequence', 'previous_hash', 'payload')}):
                raise ValueError('AUDIT_TAMPER')
            prior = event['hash']
        return True


def review(report, reviewer, finding_id, decision, annotation, chain):
    _keys(reviewer, {'id', 'tenant', 'role'}, 'REVIEWER')
    if not _identity(reviewer['id']) or not _identity(reviewer['tenant']) or reviewer['role'] != 'REVIEWER':
        raise ValueError('AUTHORIZED_REVIEWER_REQUIRED')
    if decision not in DECISIONS or not isinstance(annotation, str) or len(annotation) > 2000:
        raise ValueError('REVIEW_DECISION_INVALID')
    if reviewer['tenant'] != report['tenant']:
        raise ValueError('CROSS_TENANT_REVIEW_REFUSED')
    matches = [f for f in report['findings'] if f['finding_id'] == finding_id and f['tenant'] == reviewer['tenant']]
    if len(matches) != 1:
        raise ValueError('EXACT_FINDING_REQUIRED')
    # Review decision never rewrites the machine-evidence classification.
    chain.append({'type': 'HUMAN_REVIEW_ASSERTION', 'actor': reviewer['id'],
                  'tenant': reviewer['tenant'], 'finding_id': finding_id,
                  'decision': decision, 'annotation': annotation,
                  'unchanged_evidence_state': matches[0]['evidence_state']})
    return deepcopy(matches[0])


def commercial_gate(*, eligibility_verified, trl5to9_verified, all_essential_outcomes_verified,
                    complete_costs_and_authority_verified):
    flags = (eligibility_verified, trl5to9_verified, all_essential_outcomes_verified,
             complete_costs_and_authority_verified)
    if any(type(v) is not bool for v in flags):
        raise ValueError('EXPLICIT_BOOLEAN_EVIDENCE_REQUIRED')
    if not all(flags):
        return 'NO_BID_NO_DEPLOY'
    return 'REQUIRES_SEPARATE_OWNER_PROCUREMENT_AUTHORIZATION'


def demo():
    change = {'tenant': 'alpha', 'requirement_id': 'R1', 'from_version': 1,
              'to_version': 2, 'action': 'UPDATED'}
    systems = [
        {'tenant': 'alpha', 'system_id': 'case-a', 'requirements': ['R1'],
         'evidence': [{'requirement_id': 'R1', 'version': 1, 'status': 'MET',
                       'verified': True, 'reference': 'synthetic-v1'}]},
        {'tenant': 'alpha', 'system_id': 'case-b', 'requirements': ['R1'],
         'evidence': [{'requirement_id': 'R1', 'version': 2, 'status': 'PARTIAL',
                       'verified': True, 'reference': 'synthetic-v2'}]},
        {'tenant': 'beta', 'system_id': 'case-c', 'requirements': ['R1'], 'evidence': []},
    ]
    result = assess(change, systems)
    chain = AuditChain()
    chain.append({'type': 'ASSESSMENT_RECORDED', 'report_digest': digest(result)})
    review(result, {'id':'reviewer-a','tenant':'alpha','role':'REVIEWER'},
           result['findings'][0]['finding_id'], 'REQUEST_MORE_EVIDENCE', 'fixture', chain)
    assert AuditChain.verify(chain.events)
    return {'result': result, 'audit': chain.events,
            'commercial_decision': commercial_gate(eligibility_verified=False, trl5to9_verified=False,
            all_essential_outcomes_verified=False, complete_costs_and_authority_verified=False),
            'actual_collections_usd': None, 'complete_actual_costs_usd': None}


if __name__ == '__main__':
    print(canonical(demo()))
