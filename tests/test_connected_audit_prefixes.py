import copy
import unittest

from adaptive_enterprise.account import action_prefix_digests
from commercial.ledger import digest
from connected_enterprise.finance import _find_action


class ExactCanonicalAuditPrefixes(unittest.TestCase):
    def test_every_prefix_equals_independent_complete_canonical_serialization(self):
        rows = [{'z': ['é', '漢字', '\\', '\n', '\"'], 'a': {'b': True, 'n': None}},
                {'nested': [[], {}, {'x': [1, -1, 0.125, False]}]},
                {'seq': 2, 'op': 'cost', 'args': {'id': 'same-customer', 'amount': 10}}]
        original = copy.deepcopy(rows)
        self.assertEqual(action_prefix_digests(rows), [digest(rows[:n]) for n in range(len(rows) + 1)])
        self.assertEqual(rows, original)
        rows[0]['a']['b'] = False
        self.assertNotEqual(action_prefix_digests(rows)[-1], action_prefix_digests(original)[-1])
        self.assertEqual(action_prefix_digests([]), [digest([])])

    def test_duplicate_indexed_native_identity_is_still_rejected(self):
        row = {'seq': 0, 'op': 'cost', 'args': {'id': 'duplicate', 'amount': 7}, 'day': 0}
        tape = {'actions': [row, {**row, 'seq': 1}]}
        index = {'cost:duplicate': tape['actions']}
        with self.assertRaisesRegex(ValueError, 'JOURNALED_NATIVE_ACTION_NOT_UNIQUE'):
            _find_action(tape, 'cost', row['args'], 0, action_index=index)


if __name__ == '__main__':
    unittest.main()
