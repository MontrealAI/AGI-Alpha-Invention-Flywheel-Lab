import unittest

from connected_enterprise.verify import _check_contract_clock


class RefundContractClockTests(unittest.TestCase):
    def check(self, native_time=240, operating_time=240, *, deadline=240, due=240):
        return _check_contract_clock('order', {'args': {'deadline': deadline}},
                                     {'refund': {'day': native_time}},
                                     {('order', 'REFUND'): {'time': operating_time}}, 0,
                                     {'payment_deadline_hours': 240}, refund_due=due)

    def test_defaulted_refund_requires_exact_deadline_in_both_records(self):
        self.check()
        for native, operating in [(3, 3), (239, 239), (241, 241), (3, 240), (240, 3)]:
            with self.subTest(native=native, operating=operating), self.assertRaisesRegex(ValueError, 'REFUND_TIME_DIFFERS'):
                self.check(native, operating)

    def test_quality_rejection_refunds_at_failed_acceptance_not_payment_deadline(self):
        self.check(3, 3, due=3)
        for native, operating in [(2, 2), (240, 240), (3, 2), (2, 3)]:
            with self.subTest(native=native, operating=operating), self.assertRaisesRegex(ValueError, 'REFUND_TIME_DIFFERS'):
                self.check(native, operating, due=3)

    def test_native_offer_deadline_cannot_change_with_or_without_refund(self):
        for deadline in [239, 241, True, '240', None]:
            for due in [None, 240]:
                with self.subTest(deadline=deadline, due=due), self.assertRaises(ValueError):
                    self.check(deadline=deadline, due=due)

    def test_refund_timestamps_require_typed_present_integer_fields(self):
        for value in [None, True, '240', 240.0, -1]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check(value, 240)
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check(240, value)

    def test_nonzero_qualification_binds_absolute_deadline(self):
        _check_contract_clock('order', {'args': {'deadline': 288}},
                              {'refund': {'day': 288}}, {('order', 'REFUND'): {'time': 288}},
                              48, {'payment_deadline_hours': 240}, refund_due=288)


if __name__ == '__main__':
    unittest.main()
