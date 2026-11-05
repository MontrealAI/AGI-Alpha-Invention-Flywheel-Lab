"""Source-hash-bound *authored* AI-governance change impact probe.

Research-only, offline, no legal conclusions, credentials, real approvals or money.
The source hash is a local integrity check, NOT origin authentication.
"""
from copy import deepcopy
from hashlib import sha256
import json

STATUS = ('MET', 'NOT_MET', 'PARTIALLY_MET', 'NOT_APPLICABLE', 'UNABLE_TO_DETERMINE')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def digest(value):
    return sha256(canonical(value)).hexdigest()


def source_digest(text):
    if type(text) is not str:
        raise ValueError('SOURCE_TEXT_REQUIRED')
    return sha256(text.encode('utf-8')).hexdigest()


def validate(data):
    """Fail closed on contradictory registry/evidence; input authority is external."""
    systems, rules, evidence = (data[k] for k in ('systems', 'requirements', 'evidence'))
    if not all(type(x) is list for x in (systems, rules, evidence)):
        raise ValueError('REGISTRATION_MUST_BE_LISTS')
    if len({x['id'] for x in systems}) != len(systems) or len({x['id'] for x in rules}) != len(rules):
        raise ValueError('DUPLICATE_REGISTRATION')
    for s in systems:
        if type(s['id']) is not str or not s['id'] or type(s['tags']) is not list or not all(type(t) is str for t in s['tags']):
            raise ValueError('INVALID_SYSTEM')
    for rule in rules:
        src = rule['source']
        if (type(rule['version']) is not int or rule['version'] < 1
                or type(rule['tags']) is not list or type(rule['controls']) is not list
                or not rule['controls'] or len(set(rule['controls'])) != len(rule['controls'])
                or type(rule['retired']) is not bool or type(src['uri']) is not str
                or src['sha256'] != source_digest(src['text'])):
            raise ValueError('INVALID_SOURCE_OR_REQUIREMENT')
    known_systems = {s['id'] for s in systems}
    known_rules = {r['id']: r for r in rules}
    keys = set()
    for ev in evidence:
        key = (ev['system'], ev['requirement'], ev['version'], ev['control'])
        if key in keys:
            raise ValueError('DUPLICATE_EVIDENCE')
        keys.add(key)
        rule = known_rules.get(ev['requirement'])
        if (ev['system'] not in known_systems or rule is None
                or type(ev['version']) is not int or ev['version'] < 1
                or ev['version'] > rule['version'] or type(ev['content']) is not str
                or ev['sha256'] != source_digest(ev['content'])
                or ev['result'] not in ('SATISFIED', 'FAILED', 'INCOMPLETE')):
            raise ValueError('INVALID_EVIDENCE')


def applicable(rule, system):
    return not rule['retired'] and bool(set(rule['tags']) & set(system['tags']))


def assess_cell(rule, system, evidence):
    if not applicable(rule, system):
        return 'NOT_APPLICABLE'
    outcomes = {}
    for ev in evidence:
        if ev['system'] == system['id'] and ev['requirement'] == rule['id'] and ev['version'] == rule['version']:
            outcomes[ev['control']] = ev['result']
    if set(outcomes) != set(rule['controls']) or 'INCOMPLETE' in outcomes.values():
        return 'UNABLE_TO_DETERMINE'
    passed = sum(outcome == 'SATISFIED' for outcome in outcomes.values())
    return 'MET' if passed == len(outcomes) else 'NOT_MET' if passed == 0 else 'PARTIALLY_MET'


def full_scan(data):
    validate(data)
    return {(s['id'], r['id']): assess_cell(r, s, data['evidence'])
            for s in data['systems'] for r in data['requirements']}


def revise(data, proposed, *, expected_registration_hash):
    """A compare-and-validate *pure* transition, not a durable CAS or signature."""
    validate(data)
    if expected_registration_hash != digest(data):
        raise ValueError('STALE_REGISTRATION')
    current = next((r for r in data['requirements'] if r['id'] == proposed['id']), None)
    if current is None or proposed['version'] != current['version'] + 1:
        raise ValueError('REVISION_OR_DOWNGRADE')
    if proposed.get('previous_sha256') != digest(current):
        raise ValueError('UNLINKED_REVISION')
    updated = deepcopy(data)
    proposed = deepcopy(proposed)
    del proposed['previous_sha256']
    updated['requirements'] = [proposed if r['id'] == current['id'] else r
                               for r in updated['requirements']]
    validate(updated)
    previous = full_scan(data)
    affected = sorted(s['id'] for s in data['systems']
                      if applicable(current, s) or applicable(proposed, s))
    incremental = dict(previous)
    for s in updated['systems']:
        if s['id'] in affected:
            incremental[(s['id'], proposed['id'])] = assess_cell(proposed, s, updated['evidence'])
    baseline = full_scan(updated)  # Competent deterministic all-system control.
    if incremental != baseline:
        raise ValueError('IMPACT_BRIDGE_DISAGREES_WITH_FULL_SCAN')
    return {
        'registration_before': digest(data), 'registration_after': digest(updated),
        'updated': updated, 'affected': affected, 'incremental': incremental,
        'full_scan': baseline, 'incremental_cells_reassessed': len(affected),
        'full_scan_cells_reassessed': len(updated['systems']) * len(updated['requirements']),
        'evidence_tier': 'AUTHORED_OFFLINE_MECHANICAL_ONLY_NO_COMPLIANCE_OR_COMMERCE',
    }


def canonical_report(report):
    """Deterministic JSON-compatible *whole report* including tuple-keyed cells.

    This is local content integrity, NOT provenance or reviewer authentication.
    Avoid silently hashing registration_after in place of actual assessments.
    """
    if type(report) is not dict:
        raise ValueError('INVALID_REPORT')
    converted = deepcopy(report)
    for name in ('incremental', 'full_scan'):
        cells = report.get(name)
        if type(cells) is not dict:
            raise ValueError('INVALID_REPORT_CELLS')
        rows = []
        for key, status in cells.items():
            if (type(key) is not tuple or len(key) != 2
                    or not all(type(part) is str and part for part in key)
                    or status not in STATUS):
                raise ValueError('INVALID_REPORT_CELLS')
            rows.append(dict(system=key[0], requirement=key[1], status=status))
        converted[name] = sorted(rows, key=lambda row: (row['system'], row['requirement']))
    return converted


def report_digest(report):
    """Hash full revision/evidence assessment, not just its registration version."""
    return digest(canonical_report(report))


def review(report_hash, roles, history, *, actor, decision, expected_head):
    """Trusted-role demonstration; not durable/authenticated or an actual approval.

    Check all supplied predecessor links, not just the tail hash. A complete
    rewritten self-consistent history still needs an *external* trusted anchor.
    """
    if roles.get(actor) != 'reviewer':
        raise ValueError('UNAUTHORIZED_REVIEW')
    if decision not in ('APPROVE', 'REJECT', 'ANNOTATE'):
        raise ValueError('INVALID_REVIEW_DECISION')
    if (type(report_hash) is not str or len(report_hash) != 64
            or any(ch not in '0123456789abcdef' for ch in report_hash)):
        raise ValueError('INVALID_REPORT_HASH')
    if type(history) is not list:
        raise ValueError('INVALID_REVIEW_CHAIN')
    head = 'GENESIS'
    for expected_seq, row in enumerate(history, start=1):
        if (type(row) is not dict
                or set(row) != {'seq', 'previous', 'actor', 'report_hash', 'decision'}
                or type(row['seq']) is not int or row['seq'] != expected_seq
                or row['previous'] != head
                or type(row['actor']) is not str or not row['actor']
                or type(row['report_hash']) is not str or len(row['report_hash']) != 64
                or any(ch not in '0123456789abcdef' for ch in row['report_hash'])
                or row['decision'] not in ('APPROVE', 'REJECT', 'ANNOTATE')):
            raise ValueError('INVALID_REVIEW_CHAIN')
        head = digest(row)
    if expected_head != head:
        raise ValueError('STALE_REVIEW_LOG')
    if any(row['report_hash'] == report_hash and row['actor'] == actor
           and row['decision'] == decision for row in history):
        raise ValueError('DUPLICATE_REVIEW')
    new = dict(seq=len(history) + 1, previous=head, actor=actor,
               report_hash=report_hash, decision=decision)
    return history + [new]
