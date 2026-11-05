"""Preregistered authored cases for Canadian SSC demand-research issue #259.

These are exposed engineering scenarios, never actual policy or customer assessment.
"""
from copy import deepcopy
import unittest
from campaign import governance_change086 as g


def source(content, uri):
    return dict(text=content, uri=uri, sha256=g.source_digest(content))


def fixture():
    systems = [dict(id=ident, tags=tags) for ident, tags in [
        ('A', ['finance']), ('B', ['health']), ('C', ['finance', 'research']),
        ('D', ['hr']), ('E', ['finance']), ('F', ['research'])]]
    requirements = [
        dict(id='R1', version=1, tags=['finance'], controls=['human', 'record'],
             retired=False, source=source('Authored v1: record decisions and human oversight.', 'authored://r1/1')),
        dict(id='R2', version=1, tags=['health'], controls=['risk'],
             retired=False, source=source('Authored v1: review health output risk.', 'authored://r2/1')),
        dict(id='R3', version=1, tags=['research'], controls=['trace'],
             retired=False, source=source('Authored v1: document research source.', 'authored://r3/1')),
    ]
    evidence = []
    for sid, rid, control, result in [
        ('A', 'R1', 'human', 'SATISFIED'), ('A', 'R1', 'record', 'SATISFIED'),
        ('C', 'R1', 'human', 'SATISFIED'), ('C', 'R1', 'record', 'FAILED'),
        ('E', 'R1', 'human', 'FAILED'), ('E', 'R1', 'record', 'FAILED'),
        ('B', 'R2', 'risk', 'SATISFIED'), ('F', 'R3', 'trace', 'SATISFIED'),
    ]:
        content = f'Authored local test: {sid}/{rid}/{control}/{result}'
        evidence.append(dict(system=sid, requirement=rid, version=1, control=control,
                             content=content, sha256=g.source_digest(content), result=result))
    return dict(systems=systems, requirements=requirements, evidence=evidence)


def changed(before, *, tags=('finance', 'hr'), retired=False):
    old = before['requirements'][0]
    return dict(id='R1', version=2, tags=list(tags), controls=['human', 'record'],
                retired=retired, source=source('Authored v2: changed scope of R1.', 'authored://r1/2'),
                previous_sha256=g.digest(old))


class ChangeImpactTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()

    def test_C0_original_coverage_and_five_valued_status(self):
        report = g.full_scan(self.data)
        self.assertEqual(report[('A', 'R1')], 'MET')
        self.assertEqual(report[('E', 'R1')], 'NOT_MET')
        self.assertEqual(report[('C', 'R1')], 'PARTIALLY_MET')
        self.assertEqual(report[('D', 'R1')], 'NOT_APPLICABLE')
        self.assertEqual(report[('C', 'R3')], 'UNABLE_TO_DETERMINE')

    def test_C1_cross_system_change_matches_full_scan_without_missing_old_applicability(self):
        out = g.revise(self.data, changed(self.data), expected_registration_hash=g.digest(self.data))
        self.assertEqual(out['affected'], ['A', 'C', 'D', 'E'])
        self.assertEqual(out['incremental'], out['full_scan'])
        self.assertEqual(out['incremental_cells_reassessed'], 4)
        self.assertEqual(out['full_scan_cells_reassessed'], 18)
        self.assertTrue(all(out['incremental'][(sid, 'R1')] == 'UNABLE_TO_DETERMINE'
                            for sid in out['affected']))
        self.assertEqual(out['incremental'][('F', 'R3')], 'MET')

    def test_C2_retire_requirement_removes_applicability_without_erasure(self):
        old = self.data['requirements'][2]
        replacement = dict(id='R3', version=2, tags=['research'], controls=['trace'],
                           retired=True, source=source('Authored retirement.', 'authored://r3/2'),
                           previous_sha256=g.digest(old))
        out = g.revise(self.data, replacement, expected_registration_hash=g.digest(self.data))
        self.assertEqual(out['affected'], ['C', 'F'])
        self.assertEqual(out['incremental'][('C', 'R3')], 'NOT_APPLICABLE')
        self.assertEqual(out['incremental'][('F', 'R3')], 'NOT_APPLICABLE')
        self.assertEqual(self.data['requirements'][2]['version'], 1)

    def test_C3_tampered_source_and_bad_evidence_rejected(self):
        mutated = deepcopy(self.data)
        mutated['requirements'][0]['source']['text'] += ' (undisclosed replacement)'
        with self.assertRaisesRegex(ValueError, 'INVALID_SOURCE'):
            g.full_scan(mutated)
        mutated = deepcopy(self.data)
        mutated['evidence'][0]['content'] = 'fabricated pass'
        with self.assertRaisesRegex(ValueError, 'INVALID_EVIDENCE'):
            g.full_scan(mutated)

    def test_C4_stale_tampered_and_downgrade_transitions_rejected(self):
        with self.assertRaisesRegex(ValueError, 'STALE_REGISTRATION'):
            g.revise(self.data, changed(self.data), expected_registration_hash='0' * 64)
        wrong = changed(self.data)
        wrong['previous_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'UNLINKED_REVISION'):
            g.revise(self.data, wrong, expected_registration_hash=g.digest(self.data))
        wrong = changed(self.data)
        wrong['version'] = 1
        with self.assertRaisesRegex(ValueError, 'REVISION_OR_DOWNGRADE'):
            g.revise(self.data, wrong, expected_registration_hash=g.digest(self.data))

    def test_C5_independent_explicit_oracle_checks_all_cells(self):
        out = g.revise(self.data, changed(self.data), expected_registration_hash=g.digest(self.data))
        # Check all 18 statuses against the authored oracle, not only against
        # another evaluator sharing the same applicability implementation.
        expected_r1 = ['UNABLE_TO_DETERMINE', 'NOT_APPLICABLE', 'UNABLE_TO_DETERMINE',
                       'UNABLE_TO_DETERMINE', 'UNABLE_TO_DETERMINE', 'NOT_APPLICABLE']
        self.assertEqual([out['incremental'][(k, 'R1')] for k in 'ABCDEF'], expected_r1)
        expected_r2 = ['NOT_APPLICABLE', 'MET', 'NOT_APPLICABLE', 'NOT_APPLICABLE',
                       'NOT_APPLICABLE', 'NOT_APPLICABLE']
        self.assertEqual([out['incremental'][(k, 'R2')] for k in 'ABCDEF'], expected_r2)
        self.assertEqual([out['incremental'][(k, 'R3')] for k in 'ABCDEF'],
                         ['NOT_APPLICABLE', 'NOT_APPLICABLE', 'UNABLE_TO_DETERMINE',
                          'NOT_APPLICABLE', 'NOT_APPLICABLE', 'MET'])

    def test_C6_role_stub_no_false_approval_and_review_replay_guard(self):
        report = g.revise(self.data, changed(self.data), expected_registration_hash=g.digest(self.data))
        target = report['registration_after']
        roles = {'reviewer-1': 'reviewer', 'operator-1': 'operator'}
        with self.assertRaisesRegex(ValueError, 'UNAUTHORIZED_REVIEW'):
            g.review(target, roles, [], actor='operator-1', decision='APPROVE', expected_head='GENESIS')
        history = g.review(target, roles, [], actor='reviewer-1', decision='REJECT', expected_head='GENESIS')
        with self.assertRaisesRegex(ValueError, 'STALE_REVIEW_LOG'):
            g.review(target, roles, history, actor='reviewer-1', decision='ANNOTATE', expected_head='GENESIS')
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_REVIEW'):
            g.review(target, roles, history, actor='reviewer-1', decision='REJECT', expected_head=g.digest(history[-1]))
        self.assertEqual(history[0]['decision'], 'REJECT')

    def test_C7_uncertainty_must_not_turn_into_compliance_or_legal_claim(self):
        out = g.revise(self.data, changed(self.data), expected_registration_hash=g.digest(self.data))
        self.assertEqual(out['evidence_tier'], 'AUTHORED_OFFLINE_MECHANICAL_ONLY_NO_COMPLIANCE_OR_COMMERCE')
        self.assertEqual(out['incremental'][('D', 'R1')], 'UNABLE_TO_DETERMINE')


if __name__ == '__main__':
    unittest.main()
