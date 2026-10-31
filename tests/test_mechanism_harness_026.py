import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from mechanism_harness import ContractError, audit, capability_capsule, compose, digest, reflect, validate_spec, experiment

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / 'campaign/mechanism-harness-026/EXAMPLE.json'
REFLECTION = ROOT / 'campaign/mechanism-harness-026/REFLECTION.json'


def example():
    return json.loads(EXAMPLE.read_text())


class CompositionTests(unittest.TestCase):
    def test_constructs_cheaper_composition(self):
        s=example();p=compose(s);self.assertEqual(p['cost_units'],9);self.assertEqual(p['sequence'],['collect_sources','bridge_inventory_to_canonical','compile_claims','verify_claims','build_deliverable']);self.assertEqual(p['status'],'CANDIDATE_REQUIRES_INDEPENDENT_QUALIFICATION');self.assertTrue(audit(s,p)['accepted'])
    def test_fresh_successor_requires_new_proof(self):
        s=example();old=compose(s)
        fresh=json.loads((ROOT/'campaign/mechanism-harness-026/FRESH_SUCCESSOR.json').read_text())
        new=compose(fresh);self.assertEqual(new['cost_units'],11)
        self.assertTrue(audit(fresh,new)['accepted'])
        with self.assertRaises(ContractError):audit(fresh,old)
        self.assertIsNone(capability_capsule(fresh,new,audit(fresh,new))['current_proof'])
    def test_full_study_preserves_claim_distinctions(self):
        s=example();t=json.loads((ROOT/'campaign/mechanism-harness-026/FRESH_SUCCESSOR.json').read_text());r=json.loads(REFLECTION.read_text());report=experiment(s,t,r)
        self.assertEqual(report['primary']['symbolic_incremental_cost_units'],11)
        self.assertEqual(report['fresh_surface_successor']['symbolic_incremental_cost_units'],8)
        self.assertIsNone(report['observed_successor_inheritance_benefit'])
        self.assertEqual(report['actual_collected_usd'],0)
    def test_without_bridge_chooses_direct(self):
        s=example();s['candidate_bridges']=[];p=compose(s);self.assertEqual(p['sequence'],['direct_expert']);self.assertEqual(p['cost_units'],20);self.assertEqual(p['status'],'SYMBOLIC_PLAN_FOUND');self.assertFalse(audit(s,p)['candidate_bridges_require_separate_qualification'])
    def test_budget_abstention_without_inventing_impossibility(self):
        s=example();s['purpose']['max_cost']=5;p=compose(s);self.assertEqual(p['status'],'NO_SUPPORTED_PLAN_FOUND_WITHIN_BOUNDS');self.assertIn('NO_IMPOSSIBILITY',p['claim']);self.assertTrue(audit(s,p)['accepted'])
    def test_search_exhaustion_explicit(self):
        s=example();s['purpose']['max_states']=1;p=compose(s);self.assertEqual(p['status'],'SEARCH_BOUND_EXHAUSTED');self.assertTrue(audit(s,p)['accepted'])
    def test_already_satisfied(self):
        s=example();s['purpose']['goal']=['raw_customer_files'];p=compose(s);self.assertEqual(p['status'],'GOAL_ALREADY_SATISFIED');self.assertTrue(audit(s,p)['accepted'])
    def test_capsule_has_no_current_proof_or_authority(self):
        s=example();p=compose(s);c=capability_capsule(s,p,audit(s,p));self.assertIsNone(c['current_proof']);self.assertEqual(c['authority'],[]);self.assertIn('CANDIDATE_ONLY',c['promotion_status'])
    def test_no_capsule_from_unresolved(self):
        s=example();s['purpose']['max_cost']=3;p=compose(s)
        with self.assertRaises(ContractError):capability_capsule(s,p,audit(s,p))
    def test_source_mutation_invalidates_receipt(self):
        s=example();p=compose(s);s['mechanisms'][0]['cost']+=1
        with self.assertRaises(ContractError):audit(s,p)
    def test_wrong_order_is_rejected(self):
        s=example();p=compose(s);p['sequence'][0],p['sequence'][1]=p['sequence'][1],p['sequence'][0]
        with self.assertRaises(ContractError):audit(s,p)
    def test_fake_price_is_rejected(self):
        s=example();p=compose(s);p['cost_units']=1
        with self.assertRaises(ContractError):audit(s,p)
    def test_fake_bridge_omission_is_rejected(self):
        s=example();p=compose(s);p['candidate_bridge_ids']=[]
        with self.assertRaises(ContractError):audit(s,p)
    def test_fake_abstention_is_rejected(self):
        s=example();p=compose(s);p.update(sequence=[],cost_units=None,candidate_bridge_provenance={},status='NO_SUPPORTED_PLAN_FOUND_WITHIN_BOUNDS',candidate_bridge_ids=[],claim='NO_IMPOSSIBILITY_OR_OPERATING_AUTHORITY_ASSERTED')
        with self.assertRaises(ContractError):audit(s,p)
    def test_unauthorized_effects_fail(self):
        s=example();s['mechanisms'][0]['effect']='external_write'
        with self.assertRaises(ContractError):compose(s)
    def test_bridge_origin_preserved_without_fabricating_autonomy(self):
        s=example();p=compose(s);self.assertEqual(p['candidate_bridge_provenance'], {'bridge_inventory_to_canonical':'developer_supplied'})
        p['candidate_bridge_provenance']['bridge_inventory_to_canonical']='machine_proposed'
        with self.assertRaises(ContractError):audit(s,p)
    def test_unsorted_facts_fail(self):
        s=example();s['mechanisms'][2]['requires']=['structured_claims','source_inventory']
        with self.assertRaises(ContractError):validate_spec(s)
    def test_cost_bound_rejects_float(self):
        s=example();s['mechanisms'][0]['cost']=2.0
        with self.assertRaises(ContractError):validate_spec(s)
    def test_duplicate_ids_rejected(self):
        s=example();s['mechanisms'][0]['id']=s['mechanisms'][1]['id']
        with self.assertRaises(ContractError):compose(s)
    def test_deterministic_digest_and_plan(self):
        s=example();self.assertEqual(compose(s),compose(copy.deepcopy(s)));self.assertEqual(digest(s),digest(copy.deepcopy(s)))


class EvidenceTests(unittest.TestCase):
    def test_conditional_one_group_error_recovery(self):
        data=json.loads(REFLECTION.read_text());r=reflect(data);self.assertEqual(r['recovered_value'],'valid');self.assertEqual(r['status'],'CONDITIONAL_RECOVERY');self.assertEqual(r['authority'],[])
    def test_same_group_not_independent_vote(self):
        x=json.loads(REFLECTION.read_text());x['records'][2]['source_group']='independent_check';x['records'][2]['value']='valid';r=reflect(x);self.assertEqual(r['status'],'INSUFFICIENT_INDEPENDENT_GROUPS_ASSUMED')
    def test_correlated_group_conflict_is_not_corrected(self):
        x=json.loads(REFLECTION.read_text());x['records'][2]['source_group']='independent_check';r=reflect(x);self.assertEqual(r['status'],'INCONSISTENT_WITH_DECLARED_PREMISES')
    def test_two_bad_groups_rejected_in_three_group_budget(self):
        x=json.loads(REFLECTION.read_text());x['records'][0]['value']='invalid';x['records'][1]['value']='unknown';x['records'][2]['value']='valid';r=reflect(x);self.assertEqual(r['status'],'INCONSISTENT_WITH_DECLARED_PREMISES')
    def test_beyond_declared_fault_budget_can_mislead(self):
        x=json.loads(REFLECTION.read_text());x['records'][0]['value']='invalid';x['records'][1]['value']='invalid';r=reflect(x)
        self.assertEqual(r['status'],'CONDITIONAL_RECOVERY')
        self.assertEqual(r['recovered_value'],'invalid')
        self.assertIn('assumptions',r['limitation'])
    def test_zero_source_groups_does_not_invent_truth(self):
        x=json.loads(REFLECTION.read_text());x['records']=[];r=reflect(x);self.assertIsNone(r['recovered_value'])
    def test_unjustified_fault_model_refused(self):
        x=json.loads(REFLECTION.read_text());x['declared_fault_model']='unbounded'
        with self.assertRaises(ContractError):reflect(x)
    def test_shared_wrong_source_is_not_proved_true(self):
        x=json.loads(REFLECTION.read_text());x['records'][2]['value']='valid';r=reflect(x);self.assertIn('assumptions',r['limitation']);self.assertEqual(r['scope'],'CATEGORICAL_EQUALITY_WITH_ASSUMED_SOURCE_FAULT_BOUND')


class CLIIntegrationTests(unittest.TestCase):
    def test_compose_audit_and_capsule_create_once(self):
        with tempfile.TemporaryDirectory() as d:
            def run(*args):
                return subprocess.run([sys.executable,'-m','mechanism_harness',*args],cwd=ROOT,text=True,capture_output=True)
            spec=str(EXAMPLE);plan=str(Path(d)/'PLAN.json');check=str(Path(d)/'CHECK.json');cap=str(Path(d)/'CAPSULE.json')
            self.assertEqual(run('compose','--spec',spec,'--output',plan).returncode,0)
            self.assertEqual(run('audit','--spec',spec,'--plan',plan,'--output',check).returncode,0)
            self.assertEqual(run('capsule','--spec',spec,'--plan',plan,'--check',check,'--output',cap).returncode,0)
            self.assertEqual(json.loads(Path(cap).read_text())['authority'],[])
            self.assertNotEqual(run('compose','--spec',spec,'--output',plan).returncode,0)
    def test_cli_reflect(self):
        with tempfile.TemporaryDirectory() as d:
            out=str(Path(d)/'REFLECTION_RESULT.json')
            r=subprocess.run([sys.executable,'-m','mechanism_harness','reflect','--spec',str(REFLECTION),'--output',out],cwd=ROOT,capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(json.loads(Path(out).read_text())['status'],'CONDITIONAL_RECOVERY')


if __name__=='__main__':unittest.main()
