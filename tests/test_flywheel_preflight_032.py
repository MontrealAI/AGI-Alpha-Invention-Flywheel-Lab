import tempfile
import unittest
from pathlib import Path
from flywheel_wheel.preflight import benefit_members, same_canonical, fresh_output
from flywheel_wheel.readout import EvidenceError


class PreflightTests(unittest.TestCase):
    def test_actual_complementary_actions_remain_allowed(self):
        benefit_members([{'members': ['instrument', 'delivery']}], {'instrument', 'delivery'})

    def test_zero_cost_reward_and_reserve_cannot_generate_synergy(self):
        with self.assertRaisesRegex(EvidenceError, 'ORIGINAL_PRODUCTIVE'):
            benefit_members([{'members': ['wheel-cost-shared-x', 'wheel-cost-reward-y']}], {'delivery'})

    def test_mixed_productive_and_bookkeeping_benefit_is_refused(self):
        with self.assertRaises(EvidenceError):
            benefit_members([{'members': ['delivery', 'wheel-cost-reward-y']}], {'delivery'})

    def test_duplicate_missing_nonstring_members_refused(self):
        for members in (['a','a'], ['a','missing'], ['a',True], ['a'], 'ab'):
            with self.subTest(members=members), self.assertRaises(EvidenceError):
                benefit_members([{'members': members}], {'a','b'})

    def test_synergy_search_is_bounded(self):
        with self.assertRaises(EvidenceError): benefit_members([{'members':['a','b']}]*129, {'a','b'})

    def test_boolean_is_not_integer_or_float(self):
        self.assertFalse(same_canonical({'funding_authority':0}, {'funding_authority':False}))
        self.assertFalse(same_canonical({'funding_authority':0.0}, {'funding_authority':False}))
        self.assertFalse(same_canonical({'amount':1.0}, {'amount':1}))

    def test_true_is_not_one(self):
        self.assertFalse(same_canonical({'accepted':1}, {'accepted':True}))

    def test_canonical_object_order_does_not_matter(self):
        self.assertTrue(same_canonical({'a':1,'b':False}, {'b':False,'a':1}))

    def test_nonfinite_output_refused(self):
        self.assertFalse(same_canonical({'x':float('nan')}, {'x':float('nan')}))

    def test_output_must_not_be_in_enterprise(self):
        with tempfile.TemporaryDirectory() as d:
            enterprise=Path(d)/'enterprise'; enterprise.mkdir()
            with self.assertRaisesRegex(EvidenceError, 'OUTSIDE_NATIVE'):
                fresh_output(enterprise/'view', enterprise)

    def test_sibling_output_allowed_without_creating_anything(self):
        with tempfile.TemporaryDirectory() as d:
            enterprise=Path(d)/'enterprise'; enterprise.mkdir()
            target=Path(d)/'view'
            self.assertEqual(fresh_output(target, enterprise), target)
            self.assertFalse(target.exists())

    def test_existing_output_and_parent_traversal_refused(self):
        with tempfile.TemporaryDirectory() as d:
            for path in (Path(d), Path(d)/'..'/'view'):
                with self.assertRaises(EvidenceError): fresh_output(path)

    def test_symbolic_link_parent_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); (p/'real').mkdir(); (p/'link').symlink_to(p/'real',target_is_directory=True)
            with self.assertRaises(EvidenceError): fresh_output(p/'link'/'view')

    def test_no_permission_from_a_valid_path_or_contract(self):
        self.assertIsNone(benefit_members([],set()))
        with tempfile.TemporaryDirectory() as d:
            self.assertIsInstance(fresh_output(Path(d)/'view'),Path)


def sample():
    from test_flywheel_wheel_030 import fixtures
    from flywheel_wheel.coupling import context_from_rederived, SCHEMA
    from flywheel_wheel.readout import sha
    a,r,b=fixtures()
    for world in b['businesses']:
        world['executed_hours']=168
        world['native_actions_sha256']='c'*64
        world['financial_state_microUSD'].update(available=12_000_000,unrestrictedEarned=8_000_000,investmentStopped=False)
    c=context_from_rederived(a,r,b,'case-0')
    action={'id':'delivery','lane':'delivery','catalog_id':'reconciliation','cost':1_000_000,
            'requires':[],'exclusive_group':None,'cash_returns':{'central':2_000_000},
            'evidence':'declared-not-market-data','authorized':True}
    q={'schema':SCHEMA,'expected_context_sha256':sha(c),'planning_cap_microUSD':4_000_000,
       'allocation':{'schema':'alpha-transformational-allocation/v1','scope':'SIMULATED',
          'currency':'simulated-microUSD','scenarios':{'central':10000},'actions':[action],
          'synergies':[],'max_states':256,'worst_loss_limit':0,'downside_penalty_bps':0},
       'assets':[],'incentives':[{'id':'review','role':'verifier','payee':'checker',
          'adjudicator':'auditor','basis':'completed_check','cap_microUSD':0,'evidence_ref':'contract'}],
       'shared_costs':[{'id':'setup','kind':'integration','amount_microUSD':0}],
       'attachments':{'delivery':{'scope':'reconciliation','asset_ids':[], 'incentive_ids':['review'],
          'shared_cost_ids':['setup'],'producer':'producer','checker':'checker',
          'fresh_mission_check':True,'base_excludes_declared_extras':True}}}
    return q,c,{'jobs':[{'id':'reconciliation'}]}


class IntegratedPreflightTests(unittest.TestCase):
    def test_compiled_cost_nodes_cannot_earn_fictional_benefits(self):
        from flywheel_wheel.coupling import assess
        q,c,u=sample()
        q['allocation']['synergies']=[{'id':'fiction','members':['wheel-cost-shared-setup',
            'wheel-cost-reward-review'],'incremental_cash':{'central':900_000_000},'evidence':'fabricated-premise'}]
        with self.assertRaisesRegex(EvidenceError,'ORIGINAL_PRODUCTIVE'): assess(q,c,u)

    def test_numeric_authority_substitution_rejected_by_actual_verifier(self):
        from flywheel_wheel.coupling import assess,verify_proposal
        q,c,u=sample(); p=assess(q,c,u);p['funding_authority']=0
        with self.assertRaisesRegex(EvidenceError,'PROPOSAL_OR_NATIVE'): verify_proposal(p,q,c,u)

    def test_unchanged_proposal_still_rederives(self):
        from flywheel_wheel.coupling import assess,verify_proposal
        q,c,u=sample();p=assess(q,c,u)
        self.assertEqual(p['selected_actions'],['delivery'])
        self.assertEqual(p['total_proposed_commitment_microUSD'],1_000_000)
        self.assertTrue(verify_proposal(p,q,c,u)['accepted'])
        self.assertIs(p['funding_authority'],False)


if __name__=='__main__':unittest.main()
