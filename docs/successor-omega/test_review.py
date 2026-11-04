"""Counterexamples added during the 1.1.0 adversarial review."""
import unittest
from dataclasses import replace
from companion import Context,Institution

class TemporalReview(unittest.TestCase):
    def setUp(self):
        self.c=Context('mission','source','supplier','environment','evaluator','policy')
        self.i=Institution('owner',('knowledge',))
        self.i.qualify(self.c,True,'builder','checker',10,now=2)
        self.i.authorize(self.c,['deliver'],True,5,8)
    def test_before_grant_denied(self):self.assertFalse(self.i.permits(self.c,'deliver',4))
    def test_at_grant_allowed(self):self.assertTrue(self.i.permits(self.c,'deliver',5))
    def test_at_expiry_denied(self):self.assertFalse(self.i.permits(self.c,'deliver',8))
    def test_failed_renewal_revokes(self):
        with self.assertRaises(ValueError):self.i.qualify(self.c,False,'b','v',10,now=6)
        self.assertFalse(self.i.permits(self.c,'deliver',6));self.assertIsNone(self.i.proof)
    def test_qualification_start_is_required(self):
        i=Institution('x');i.qualify(self.c,True,'b','v',10,now=5)
        with self.assertRaises(ValueError):i.authorize(self.c,['deliver'],True,4,8)
    def test_rewind_qualification_rejected(self):
        with self.assertRaises(ValueError):self.i.qualify(self.c,True,'b','v',10,now=4)
    def test_rewind_authorization_rejected(self):
        with self.assertRaises(ValueError):self.i.authorize(self.c,['deliver'],True,4,8)
    def test_rewind_revocation_rejected(self):
        with self.assertRaises(ValueError):self.i.revoke(now=4)
    def test_noninteger_times_denied(self):
        for t in (True,False,1.5,float('nan'),float('inf'),'6',None):
            self.assertFalse(self.i.permits(self.c,'deliver',t))
    def test_noninteger_expiry_rejected(self):
        for t in (True,8.5,float('nan'),float('inf'),'8',None):
            with self.assertRaises(ValueError):self.i.authorize(self.c,['deliver'],True,6,t)
    def test_string_scope_rejected(self):
        with self.assertRaises(ValueError):self.i.authorize(self.c,'deliver',True,6,8)
    def test_nonstring_action_rejected(self):
        with self.assertRaises(ValueError):self.i.authorize(self.c,[7],True,6,8)
    def test_empty_context_rejected(self):
        for k in ('mission','source','supplier','environment','evaluator','policy'):
            with self.assertRaises(ValueError):replace(self.c,**{k:''})
    def test_empty_role_rejected(self):
        with self.assertRaises(ValueError):self.i.qualify(self.c,True,'','v',10,now=6)
    def test_restored_history_has_no_authority(self):
        j=Institution.restore(self.i.export())
        self.assertEqual(j.history,self.i.history);self.assertFalse(j.permits(self.c,'deliver',6))
    def test_restore_rejects_unrecognized_fields(self):
        b=self.i.export();b['secret_grant']=True
        with self.assertRaises(ValueError):Institution.restore(b)
    def test_restore_rejects_malformed_history(self):
        b=self.i.export();b['history']='qualified'
        with self.assertRaises(ValueError):Institution.restore(b)
    def test_requalification_requires_new_grant(self):
        self.i.qualify(self.c,True,'b','v',12,now=6)
        self.assertFalse(self.i.permits(self.c,'deliver',7))
    def test_interval_matrix(self):
        count=0
        for pstart in range(3):
            for gstart in range(pstart,6):
                for end in range(gstart+1,8):
                    i=Institution('x');i.qualify(self.c,True,'b','v',9,now=pstart)
                    i.authorize(self.c,['deliver'],True,gstart,end)
                    for t in range(11):
                        self.assertEqual(i.permits(self.c,'deliver',t),gstart<=t<end)
                        count+=1
        self.assertEqual(count, 671)

if __name__=='__main__':unittest.main()
