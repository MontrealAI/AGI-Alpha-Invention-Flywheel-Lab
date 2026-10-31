import json, unittest

class Stub:
    def __init__(self, mutation):
        self.summary = {'cash': 100, 'profit': 20}
        self.mutation = mutation
        self.calls = 0
    def snapshot(self):
        return {'summary': self.summary.copy()}
    def advance_financial(self, hour):
        self.calls += 1
        if self.calls == 1:
            for key, value in self.mutation.items(): self.summary[key] += value
        return self.snapshot()

def candidate_maturity_guard(account, hour):
    account.advance_financial(hour)
    before = account.snapshot()['summary']
    after = account.advance_financial(hour)['summary']
    return before['profit'] == after['profit'] and before['cash'] == after['cash']

def before_first_advance_guard(account, hour):
    before = account.snapshot()['summary']
    after = account.advance_financial(hour)['summary']
    return before['profit'] == after['profit'] and before['cash'] == after['cash']

class Probe(unittest.TestCase):
    def test_noop(self):
        self.assertTrue(candidate_maturity_guard(Stub({}), 49))
        self.assertTrue(before_first_advance_guard(Stub({}), 49))
    def test_cash_mutation_before_handler_is_not_detected(self):
        self.assertTrue(candidate_maturity_guard(Stub({'cash': 50}), 49))
        self.assertFalse(before_first_advance_guard(Stub({'cash': 50}), 49))
    def test_profit_mutation_before_handler_is_not_detected(self):
        self.assertTrue(candidate_maturity_guard(Stub({'profit': 7}), 49))
        self.assertFalse(before_first_advance_guard(Stub({'profit': 7}), 49))
    def test_joint_mutation_before_handler_is_not_detected(self):
        self.assertTrue(candidate_maturity_guard(Stub({'cash': 50, 'profit': 7}), 49))
        self.assertFalse(before_first_advance_guard(Stub({'cash': 50, 'profit': 7}), 49))

if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Probe)
    res = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({'source': 'draft PR35 7d757664, connected_enterprise/engine.py control flow', 'tests_run':res.testsRun, 'failures':len(res.failures), 'errors':len(res.errors), 'scope':'Synthetic control-flow check only. No native finance was executed or attacked.', 'current_guard_detects_first_advance_changes':False, 'actual_prospective_engine_maturity_uses_neutral native action':'vendor/alpha_claim/protected_exchange_prospective_v1.py'}))
    raise SystemExit(not res.wasSuccessful())
