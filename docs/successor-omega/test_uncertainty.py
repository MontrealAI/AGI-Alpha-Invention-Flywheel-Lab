import unittest
from fractions import Fraction as F
from uncertainty import Risk, optimize,oracle,history_tree,actions,branches

class UncertaintyTests(unittest.TestCase):
    def test_no_change(self):self.assertEqual(optimize(Risk(change=F(0)))['expected'],270)
    def test_certain_change(self):self.assertEqual(optimize(Risk(change=F(1)))['expected'],196)
    def test_failed_renewal_does_not_qualify(self):
        r=Risk(change=F(0),failure=F(1));self.assertEqual(branches('renew_p',(80,True,True,False),r),((F(1),(80,True,False,False)),))
    def test_reserve_only(self):self.assertEqual(optimize(Risk(initial_cash=20))['expected'],20)
    def test_exact_oracle(self):
        for allow in (True,False):self.assertEqual(optimize(Risk(horizon=4),allow)['expected'],oracle(Risk(horizon=4),allow))
    def test_history_tree(self):
        for c in (40,100):
            for q in (F(0),F(1,4),F(1)):
                for fail in (F(0),F(1,2)):
                    r=Risk(horizon=3,initial_cash=c,change=q,failure=fail)
                    for allow in (False,True):self.assertEqual(optimize(r,allow)['expected'],history_tree(r,allow))
    def test_reject_probability(self):
        with self.assertRaises(ValueError):optimize(Risk(change=.5))
    def test_liquidity_before_receipts(self):
        self.assertEqual([a for a,_,_ in actions((20,False,False,False),Risk())],['idle'])

if __name__=='__main__':unittest.main()
