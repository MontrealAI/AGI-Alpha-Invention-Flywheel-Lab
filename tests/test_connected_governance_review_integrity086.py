"""Prospective frozen C8–C11 review-chain and report-digest addendum.

Synthetic, offline, not an authenticated reviewer or government-compliance system.
Original C0–C7 cases remain unchanged; protocol frozen at 1452578.
"""
from copy import deepcopy
import unittest

from campaign import governance_change086 as g


def fixture():
    rule = dict(
        id='R1', version=1, tags=['finance'], controls=['human'],
        retired=False, source=dict(text='Authored rule one.', uri='authored://r1/1',
                                  sha256=g.source_digest('Authored rule one.')))
    evidence = 'Authored control verification only.'
    return dict(
        systems=[dict(id='A', tags=['finance']), dict(id='B', tags=['hr'])],
        requirements=[rule],
        evidence=[dict(system='A', requirement='R1', version=1, control='human',
                       content=evidence, sha256=g.source_digest(evidence),
                       result='SATISFIED')])


def revised(data):
    old = data['requirements'][0]
    text = 'Authored rule revision changes scope.'
    return dict(id='R1', version=2, tags=['finance', 'hr'],
                controls=['human'], retired=False,
                source=dict(text=text, uri='authored://r1/2',
                            sha256=g.source_digest(text)),
                previous_sha256=g.digest(old))


class ReviewIntegrityAddendum(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        self.report = g.revise(self.data, revised(self.data),
                               expected_registration_hash=g.digest(self.data))
        self.roles = {'r1': 'reviewer', 'r2': 'reviewer', 'operator': 'operator'}

    def extend(self, history, actor, decision):
        return g.review(g.report_digest(self.report), self.roles, history,
                        actor=actor, decision=decision,
                        expected_head=g.digest(history[-1]) if history else 'GENESIS')

    def test_C8_report_hash_binds_assessment_and_reviewer_stub(self):
        bound = g.report_digest(self.report)
        self.assertEqual(len(bound), 64)
        self.assertEqual(bound, g.digest(g.canonical_report(self.report)))
        out = g.review(bound, self.roles, [], actor='r1', decision='REJECT',
                       expected_head='GENESIS')
        self.assertEqual(out[0]['report_hash'], bound)
        with self.assertRaisesRegex(ValueError, 'UNAUTHORIZED_REVIEW'):
            g.review(bound, self.roles, out, actor='operator', decision='APPROVE',
                     expected_head=g.digest(out[-1]))
        changed = deepcopy(self.report)
        changed['incremental'][('A', 'R1')] = 'MET'
        self.assertNotEqual(g.report_digest(changed), bound)

    def test_C9_non_tail_tampering_rejected_before_extension(self):
        h1 = self.extend([], 'r1', 'REJECT')
        h2 = self.extend(h1, 'r2', 'ANNOTATE')
        h3 = self.extend(h2, 'r1', 'APPROVE')
        self.assertEqual([e['seq'] for e in h3], [1, 2, 3])
        self.assertEqual(h3[2]['previous'], g.digest(h2[-1]))
        changed = deepcopy(h2)
        changed[0]['decision'] = 'APPROVE'
        with self.assertRaisesRegex(ValueError, 'INVALID_REVIEW_CHAIN'):
            self.extend(changed, 'r1', 'ANNOTATE')
        self.assertEqual(h2[0]['decision'], 'REJECT')

    def test_C10_broken_links_bad_sequence_stale_head_and_duplicate(self):
        h1 = self.extend([], 'r1', 'REJECT')
        h2 = self.extend(h1, 'r2', 'ANNOTATE')
        for field, value in [('seq', 9), ('previous', '0' * 64)]:
            changed = deepcopy(h2)
            changed[1][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'INVALID_REVIEW_CHAIN'):
                self.extend(changed, 'r1', 'APPROVE')
        with self.assertRaisesRegex(ValueError, 'STALE_REVIEW_LOG'):
            g.review(g.report_digest(self.report), self.roles, h2, actor='r1',
                     decision='APPROVE', expected_head='GENESIS')
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_REVIEW'):
            self.extend(h2, 'r1', 'REJECT')

    def test_C11_digest_stable_order_sensitive_contents_and_scope(self):
        original = g.report_digest(self.report)
        reordered = deepcopy(self.report)
        for key in ('incremental', 'full_scan'):
            reordered[key] = dict(reversed(list(reordered[key].items())))
        self.assertEqual(g.report_digest(reordered), original)
        changed = deepcopy(self.report)
        changed['affected'].append('Z')
        self.assertNotEqual(g.report_digest(changed), original)
        changed = deepcopy(self.report)
        changed['updated']['systems'][0]['tags'].append('hr')
        self.assertNotEqual(g.report_digest(changed), original)
        changed = deepcopy(self.report)
        changed['full_scan'][('B', 'R1')] = 'MET'
        self.assertNotEqual(g.report_digest(changed), original)


if __name__ == '__main__':
    unittest.main()
