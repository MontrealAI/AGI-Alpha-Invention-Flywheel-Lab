"""Finite preregistered fault-injection diagnosis of native cost completeness.

Tests use NEW ephemeral simulated accounts; never mutate the historical owner
account, credentials, evidence, source, prices, buyers or prior failed runs.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from connected_enterprise.finance import JournalAccount
from mechanism_harness import inventor as discovery
from mechanism_harness import inventor_native as native
from mechanism_harness.native_cost_witness import verify, CostWitnessError


SHORT = (8,)
TAXABLE = tuple(range(8, 24))
MATRIX = (
    ('fee_absent', SHORT, 'fee-', 'omit'),
    ('fee_undercharged', SHORT, 'fee-', 'undercharge'),
    ('maintenance_absent', SHORT, 'annual-maintenance', 'omit'),
    ('maintenance_undercharged', SHORT, 'annual-maintenance', 'undercharge'),
    ('tax_absent', TAXABLE, 'modeled-tax', 'omit'),
    ('tax_undercharged', TAXABLE, 'modeled-tax', 'undercharge'),
)


class CostWitnessQualification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = discovery.source_identity()
        cls.policy = discovery.policy(('unit', 'unique', 'text'), True)

    def run_fresh(self, indexes, fault=None, mode=None):
        original = JournalAccount.cost

        def changed(account, ident, amount, day):
            hit = (ident.startswith(fault) if fault == 'fee-' else ident == fault)
            if hit and mode == 'omit':
                return None
            if hit and mode == 'undercharge':
                if amount == 0:
                    raise AssertionError('REGISTERED_UNDERCHARGE_INAPPLICABLE_ZERO_TAX')
                return original(account, ident, amount - 1, day)
            return original(account, ident, amount, day)

        tmp = tempfile.TemporaryDirectory(prefix='omega-cost-witness-')
        path = Path(tmp.name)
        try:
            with patch.object(native, 'INDEXES', indexes), patch.object(
                    JournalAccount, 'cost', changed):
                result = native.operate(path, self.policy, self.source, 200912)
            return tmp, path, result
        except BaseException:
            tmp.cleanup()
            raise

    def test_original_native_contract_still_accepted(self):
        tmp, path, result = self.run_fresh(SHORT)
        try:
            with patch.object(native, 'INDEXES', SHORT):
                self.assertTrue(native.audit_operation(
                    path, result, self.source, self.policy)['accepted'])
                proof = verify(path, result, SHORT)
            self.assertTrue(proof['accepted'])
            self.assertEqual(proof['settled_fee_count'], 1)
            self.assertFalse(proof['actual_commerce'])
        finally:
            tmp.cleanup()

    def test_all_six_preregistered_omission_or_undercharge_faults(self):
        # Each fault has an independent freshly opened source-bound account.
        # The old owner's audit result is observed, not forced to retain a bug.
        for label, indexes, fault, mode in MATRIX:
            with self.subTest(label=label):
                tmp, path, result = self.run_fresh(indexes, fault, mode)
                try:
                    with patch.object(native, 'INDEXES', indexes):
                        try:
                            previous = native.audit_operation(
                                path, result, self.source, self.policy)['accepted']
                        except ValueError:
                            previous = False
                        with self.assertRaises(CostWitnessError):
                            verify(path, result, indexes)
                    # This line records whether the owner audit independently
                    # rejected the self-consistent *faulty* native account.
                    print('DECLARED_COST_FAULT:', label,
                          'owner_audit_missed:', previous,
                          'independent_witness_rejected:', True,
                          'scope: synthetic_new_account_only')
                finally:
                    tmp.cleanup()


if __name__ == '__main__':
    unittest.main()
