import unittest
from dataclasses import replace
from companion import *

class PlanningTests(unittest.TestCase):
    def test_nominal(self): self.assertEqual(solve(Spec())['terminal_cash'],330)
    def test_no_portable(self): self.assertEqual(solve(Spec(),False)['terminal_cash'],300)
    def test_legacy(self): self.assertEqual(solve(Spec(),legacy_only=True)['terminal_cash'],292)
    def test_equal_content(self): self.assertEqual(solve(Spec())['terminal_cash'],forward_oracle(Spec()))
    def test_oracle(self):
        for H,L,C in product((4,8),(2,4),(30,100)):
            p=Spec(horizon=H,epoch_length=L,initial_cash=C)
            for allow in (True,False):self.assertEqual(solve(p,allow)['terminal_cash'],forward_oracle(p,allow))
    def test_prefunding(self):
        p=Spec(initial_cash=20)
        self.assertEqual(solve(p)['terminal_cash'],20)
        self.assertEqual([x.action for x in transitions(State(0,20,False,-1,-1),p)],['idle'])
    def test_reserve(self):
        for row in solve(Spec())['trace']:self.assertGreaterEqual(row['pre_collection'],20)
    def test_cash_reconciliation(self):
        r=solve(Spec());self.assertEqual(100+r['collections']-r['outflows'],r['terminal_cash'])
    def test_turnover_invalidates(self):
        p=Spec();s=State(4,100,True,0,0)
        actions={x.action for x in transitions(s,p)}
        self.assertNotIn('run_f',actions);self.assertNotIn('run_p',actions);self.assertIn('renew_p',actions)
    def test_no_turnover(self):
        p=Spec(epoch_length=16)
        self.assertEqual(solve(p)['terminal_cash'],510)
        self.assertEqual(solve(p,False)['terminal_cash'],510)
    def test_no_demand(self):self.assertEqual(solve(Spec(demand=False))['terminal_cash'],100)
    def test_short_horizon(self):self.assertEqual(solve(Spec(horizon=4))['terminal_cash'],150)
    def test_always_retain_can_lose(self):self.assertLess(fixed_portable(Spec(horizon=4)),150)
    def test_always_retain_can_be_infeasible(self):self.assertIsNone(fixed_portable(Spec(initial_cash=40)))
    def test_crossover_formula(self):
        for n in range(1,5):self.assertEqual(fixed_portable(Spec(horizon=4*n))-100,70*n-50)
    def test_high_upkeep(self):
        p=Spec(maintenance=5)
        self.assertEqual(solve(p)['terminal_cash'],solve(p,False)['terminal_cash'])
    def test_negative_input(self):
        with self.assertRaises(ValueError):solve(Spec(renew=-1))
    def test_bad_horizon(self):
        with self.assertRaises(ValueError):solve(Spec(horizon=0))
    def test_opening_reserve(self):
        with self.assertRaises(ValueError):solve(Spec(initial_cash=19))
    def test_retirement(self):
        self.assertEqual([x.action for x in transitions(State(1,20,True,0,-1),Spec())],['retire'])

class QualificationTests(unittest.TestCase):
    def setUp(self):
        self.c=Context('mission','source','supplier','environment','evaluator','policy')
        self.i=Institution('owner-mission-1',('tool-v1','verified-failure'))
    def qualify(self):self.i.qualify(self.c,True,'producer','checker',10)
    def permit(self):
        self.qualify();self.i.authorize(self.c,['deliver'],True,0,8)
    def test_no_default_authority(self):self.assertFalse(self.i.permits(self.c,'deliver',0))
    def test_training_not_approval(self):
        self.qualify();self.assertFalse(self.i.permits(self.c,'deliver',0))
    def test_distinct_roles(self):
        with self.assertRaises(ValueError):self.i.qualify(self.c,True,'same','same',10)
    def test_failed_qualification(self):
        with self.assertRaises(ValueError):self.i.qualify(self.c,False,'a','b',10)
    def test_explicit_permission(self):
        self.qualify()
        with self.assertRaises(ValueError):self.i.authorize(self.c,['deliver'],False,0,8)
    def test_valid_scope(self):
        self.permit();self.assertTrue(self.i.permits(self.c,'deliver',1));self.assertFalse(self.i.permits(self.c,'transfer-money',1))
    def test_scope_subset(self):
        self.qualify()
        with self.assertRaises(ValueError):self.i.authorize(self.c,['transfer-money'],True,0,8)
    def test_expiry(self):
        self.permit();self.assertFalse(self.i.permits(self.c,'deliver',8))
    def test_no_authority_beyond_evidence(self):
        self.qualify()
        with self.assertRaises(ValueError):self.i.authorize(self.c,['deliver'],True,0,11)
    def test_all_context_fields_bound(self):
        self.permit()
        for field in asdict(self.c):self.assertFalse(self.i.permits(replace(self.c,**{field:'changed'}),'deliver',1))
    def test_revocation(self):
        self.permit();self.i.revoke();self.assertFalse(self.i.permits(self.c,'deliver',1))
    def test_restore_keeps_knowledge_not_authority(self):
        self.permit();j=Institution.restore(self.i.export())
        self.assertEqual(j.identity,self.i.identity);self.assertEqual(j.knowledge,self.i.knowledge)
        self.assertEqual(j.history,self.i.history);self.assertIsNone(j.proof);self.assertIsNone(j.authority)
    def test_restore_rejects_privilege(self):
        b=self.i.export();b['authority']=['all']
        with self.assertRaises(ValueError):Institution.restore(b)
    def test_new_qualification_clears_permission(self):
        self.permit();self.qualify();self.assertIsNone(self.i.authority)
    def test_negative_time(self):
        self.permit();self.assertFalse(self.i.permits(self.c,'deliver',-1))

if __name__=='__main__':unittest.main()
