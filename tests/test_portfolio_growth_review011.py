import unittest
from commercial.portfolio_growth import NativeProjection,default_policy,money


class ProjectionEarnedCashReview(unittest.TestCase):
    def test_invoice_and_seed_cannot_fund_earned_work(self):
        book=NativeProjection(default_policy())
        try:
            book.native('invoice','uncollected-invoice',money(1000),month=0)
            before=book.state()
            self.assertEqual(before['collections'],0)
            self.assertEqual(before['unrestrictedEarned'],0)
            self.assertGreater(before['profit'],0)
            self.assertGreater(before['available'],money(1000))
            with self.assertRaises(ValueError):
                book.native('earned_work','blocked-investment',money(1),month=0,expected_net=money(2),artifact_sha256='a'*64)
            self.assertEqual(book.state(),before)
        finally:book.close()

    def test_uninvoiced_settlement_cannot_mint_earned_cash(self):
        book=NativeProjection(default_policy())
        try:
            before=book.state()
            with self.assertRaises(ValueError): book.native('settlement','unbacked-collection',money(1000),month=0)
            self.assertEqual(book.state(),before)
        finally:book.close()

    def test_settlement_cannot_exceed_net_invoice_after_provision(self):
        book=NativeProjection(default_policy())
        try:
            book.native('invoice','invoice',money(1000),month=0)
            book.native('default','bad-debt',money(200),month=0)
            before=book.state()
            with self.assertRaises(ValueError): book.native('settlement','too-much',money(801),month=1)
            self.assertEqual(book.state(),before)
            book.native('settlement','net-collected',money(800),month=1)
            self.assertEqual(book.state()['collections'],money(800))
            with self.assertRaises(ValueError): book.native('settlement','extra',money(1),month=1)
        finally:book.close()
