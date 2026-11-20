"""Eight fixed preregistered technical and commercial control groups."""
import copy
import unittest
from impact import AuditChain, assess, commercial_gate, demo, ordinary_affected, review


def cases():
    change={'tenant':'A','requirement_id':'R','from_version':1,'to_version':2,'action':'UPDATED'}
    systems=[
      {'tenant':'A','system_id':'A1','requirements':['R'],
       'evidence':[{'requirement_id':'R','version':1,'status':'MET','verified':True,'reference':'old'}]},
      {'tenant':'A','system_id':'A2','requirements':['R'],
       'evidence':[{'requirement_id':'R','version':2,'status':'MET','verified':True,'reference':'new'}]},
      {'tenant':'B','system_id':'B1','requirements':['R'],
       'evidence':[{'requirement_id':'R','version':2,'status':'MET','verified':True,'reference':'other'}]},
    ]
    return change, systems


class FrozenTests(unittest.TestCase):
    def test_01_tenant_bound_impact(self):
        change,sys=cases(); result=assess(change,sys)
        self.assertEqual(['A1','A2'],[f['system_id'] for f in result['findings']]); self.assertNotIn('B1',repr(result))

    def test_02_unknown_evidence_never_met(self):
        change,sys=cases(); sys[0]['evidence']=[]
        self.assertEqual('UNABLE_TO_DETERMINE',assess(change,sys)['findings'][0]['evidence_state'])
        sys[0]['evidence']=[{'requirement_id':'R','version':2,'status':'MET','verified':False,'reference':'untrusted'}]
        self.assertEqual('UNABLE_TO_DETERMINE',assess(change,sys)['findings'][0]['evidence_state'])

    def test_03_new_version_requires_matching_verified_evidence(self):
        change,sys=cases(); result=assess(change,sys)
        self.assertEqual('UNABLE_TO_DETERMINE',result['findings'][0]['evidence_state'])
        self.assertEqual('MET',result['findings'][1]['evidence_state'])

    def test_04_retirement_not_whole_system_compliance(self):
        change,sys=cases(); change['action']='RETIRED'
        result=assess(change,sys)
        self.assertTrue(all(f['evidence_state']=='NOT_APPLICABLE' for f in result['findings']))
        self.assertTrue(all(f['decision']=='REASSESSMENT_NEEDED' for f in result['findings']))

    def test_05_review_tenant_and_role_controls(self):
        change,sys=cases(); report=assess(change,sys); chain=AuditChain(); fid=report['findings'][0]['finding_id']
        for actor in [{'id':'r','tenant':'B','role':'REVIEWER'}, {'id':'r','tenant':'A','role':'OBSERVER'}]:
            with self.assertRaises(ValueError): review(report, actor, fid, 'ACCEPT_FINDING','',chain)
        original=report['findings'][0]['evidence_state']
        review(report, {'id':'r','tenant':'A','role':'REVIEWER'}, fid, 'ACCEPT_FINDING','needs independent validation',chain)
        self.assertEqual(original,report['findings'][0]['evidence_state']); self.assertEqual(1,len(chain.events))

    def test_06_audit_reorder_and_tamper_refused(self):
        chain=AuditChain(); chain.append({'a':1}); chain.append({'b':2})
        self.assertTrue(AuditChain.verify(chain.events))
        tampered=copy.deepcopy(chain.events);tampered[0]['payload']['a']=7
        with self.assertRaises(ValueError):AuditChain.verify(tampered)
        reordered=copy.deepcopy(chain.events)[::-1]
        with self.assertRaises(ValueError):AuditChain.verify(reordered)

    def test_07_competent_ordinary_join_parity(self):
        change,sys=cases();result=assess(change,sys)
        self.assertEqual(ordinary_affected(change,sys),[f['system_id'] for f in result['findings']])
        self.assertTrue(result['ordinary_tie'])

    def test_08_unknown_mandatory_eligibility_stops_bidding(self):
        self.assertEqual('NO_BID_NO_DEPLOY',commercial_gate(eligibility_verified=False,trl5to9_verified=False,
          all_essential_outcomes_verified=False,complete_costs_and_authority_verified=False))
        self.assertEqual('REQUIRES_SEPARATE_OWNER_PROCUREMENT_AUTHORIZATION',commercial_gate(eligibility_verified=True,trl5to9_verified=True,
          all_essential_outcomes_verified=True,complete_costs_and_authority_verified=True))
        self.assertEqual('NO_BID_NO_DEPLOY',demo()['commercial_decision'])

if __name__=='__main__':unittest.main()
