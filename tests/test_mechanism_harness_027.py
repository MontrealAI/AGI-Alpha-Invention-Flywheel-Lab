"""Exercise actual synthetic P0 producer and its source-bound independent checker."""
import copy, json, tempfile, unittest
from pathlib import Path
from mechanism_harness.core import ContractError, compose
from mechanism_harness.operating027 import execute, verify
from mechanism_harness.study027 import run_study

ROOT=Path(__file__).resolve().parents[1]
SPEC=json.loads((ROOT/'campaign/mechanism-harness-027/EXISTING_OPERATIONS.json').read_text())


def paths(case):
    d=ROOT/'campaign/mechanism-harness-027/cases'/case
    return {'contract':str(d/'contract.json'),'invoices':str(d/'invoices.csv'),'payments':str(d/'payments.csv')}


class RealP0ExecutionTests(unittest.TestCase):
    def case(self,case):
        with tempfile.TemporaryDirectory() as d:
            spec=copy.deepcopy(SPEC);plan=compose(spec)
            record=execute(spec,plan,paths(case),Path(d)/'result')
            independent=verify(spec,plan,paths(case),Path(d)/'result')
            return record,independent

    def test_full_accepted_delivery(self):
        r,v=self.case('complete')
        self.assertEqual(r['status'],'ACCEPTED_IN_SYNTHETIC_SCOPE')
        self.assertTrue(v['accepted']);self.assertEqual(r['authority'],[]);self.assertIsNone(r['current_proof'])
        self.assertEqual(r['actual_collected_usd'],0)
    def test_ambiguous_refuses_strict_acceptance(self):
        r,v=self.case('ambiguous')
        self.assertFalse(v['accepted']);self.assertIn('REQUIRED_COMPLETE_UNMET',r['checker']['errors'])
    def test_multi_invoice_match(self):
        r,v=self.case('composite');self.assertTrue(v['accepted'])
    def test_source_bound_output_mutation_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p=compose(SPEC);o=Path(d)/'result';execute(SPEC,p,paths('complete'),o)
            (o/'production/reconciliation.json').write_text('{}')
            with self.assertRaises(ContractError):verify(SPEC,p,paths('complete'),o)
    def test_mutated_csv_exception_schedule_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p=compose(SPEC);o=Path(d)/'result';execute(SPEC,p,paths('ambiguous'),o)
            (o/'production/exceptions.csv').write_text('order_id,kind,row_id\n')
            with self.assertRaises(ContractError):verify(SPEC,p,paths('ambiguous'),o)
    def test_modified_receipt_proof_claim_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p=compose(SPEC);o=Path(d)/'result';execute(SPEC,p,paths('complete'),o)
            f=o/'RECEIPT.json';r=json.loads(f.read_text());r['current_proof']={'approved':True};f.write_text(json.dumps(r))
            with self.assertRaises(ContractError):verify(SPEC,p,paths('complete'),o)
    def test_modified_receipt_authority_claim_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p=compose(SPEC);o=Path(d)/'result';execute(SPEC,p,paths('complete'),o)
            f=o/'RECEIPT.json';r=json.loads(f.read_text());r['authority']=['spend'];f.write_text(json.dumps(r))
            with self.assertRaises(ContractError):verify(SPEC,p,paths('complete'),o)
    def test_undocumented_operator_refused(self):
        with tempfile.TemporaryDirectory() as d:
            s=copy.deepcopy(SPEC);s['mechanisms'][0]['id']='magic';p=compose(s)
            with self.assertRaises(ContractError):execute(s,p,paths('complete'),Path(d)/'result')
    def test_false_semantics_refused(self):
        with tempfile.TemporaryDirectory() as d:
            s=copy.deepcopy(SPEC);s['mechanisms'][0]['requires']=[];p=compose(s)
            with self.assertRaises(ContractError):execute(s,p,paths('complete'),Path(d)/'result')
    def test_candidate_bridge_cannot_execute(self):
        with tempfile.TemporaryDirectory() as d:
            s=copy.deepcopy(SPEC);s['candidate_bridges']=[{'id':'bad_bridge','requires':['canonical_order'],'provides':['independently_checked_delivery'],'cost':1,'effect':'pure','origin':'developer_supplied'}]
            p=compose(s)
            with self.assertRaises(ContractError):execute(s,p,paths('complete'),Path(d)/'result')
    def test_output_directory_create_only(self):
        with tempfile.TemporaryDirectory() as d:
            p=compose(SPEC);o=Path(d)/'result';execute(SPEC,p,paths('complete'),o)
            with self.assertRaises(ContractError):execute(SPEC,p,paths('complete'),o)
    def test_invalid_contract_rejected_without_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            f=Path(d)/'contract.json';f.write_text('{"order_id":"bad","scope":"SIMULATED","currency":"USD","require_complete":true}')
            ps=paths('complete');ps['contract']=str(f)
            with self.assertRaises(ValueError):execute(SPEC,compose(SPEC),ps,Path(d)/'bad')
            self.assertFalse((Path(d)/'bad/RECEIPT.json').exists())
    def test_changed_input_refuses_fresh_audit(self):
        with tempfile.TemporaryDirectory() as d:
            ps=paths('complete');cp=Path(d)/'contract.json';cp.write_bytes(Path(ps['contract']).read_bytes());ps['contract']=str(cp)
            p=compose(SPEC);o=Path(d)/'result';execute(SPEC,p,ps,o)
            cp.write_text(cp.read_text().replace('harness027-complete','harness027-altered'))
            with self.assertRaises(ContractError):verify(SPEC,p,ps,o)
    def test_duplicate_json_receipt_fails(self):
        with tempfile.TemporaryDirectory() as d:
            p=compose(SPEC);o=Path(d)/'result';execute(SPEC,p,paths('complete'),o)
            f=o/'RECEIPT.json';f.write_text(f.read_text().rstrip()[:-1]+',"status":"ACCEPTED_IN_SYNTHETIC_SCOPE"}')
            with self.assertRaises(ContractError):verify(SPEC,p,paths('complete'),o)
    def test_case_study_direct_replan_inherit(self):
        with tempfile.TemporaryDirectory() as d:
            report=run_study(ROOT,Path(d)/'study')
            self.assertEqual(len(report['cases']),3)
            self.assertEqual(report['accepted_cases'],2)
            self.assertEqual(report['rejected_cases'],1)
            self.assertTrue(all(x['same_semantic_output'] and x['same_acceptance'] for x in report['cases']))
            self.assertIsNone(report['causal_successor_inheritance_benefit'])
            self.assertEqual(report['parent_capsule']['authority'],[])
    def test_no_reuse_of_unverified_bridge_in_study(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises((ContractError, ValueError)):
                x=copy.deepcopy(SPEC);x['mechanisms'][2]['provides']=['secret_approval'];execute(x,compose(x),paths('complete'),Path(d)/'bad')

if __name__=='__main__':unittest.main()
