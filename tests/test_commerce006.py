import copy
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from experiments import commerce006 as c


class Commerce006Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        (self.root/'verification').mkdir()
        self.verifier=self.root/'verification/fixture_verifier.py';self.verifier.write_text('FIXTURE_INTERFACE_ONLY = True\n')
        self.obligations=self.root/'verification/fixture_obligations.json'
        self.dump(self.obligations,{'schema':'agi-alpha/functional-obligations006/v1','scope':'source-bound-pilot-report-delivery',
            'requires_truthful_all_arms_and_failures':True,'does_not_require_scientific_advantage':True,
            'buyer_participation_is_fixture_only':True,'commercial_price_is_not_established':True})
        for rel in c.PINS:
            target=self.root/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(c.ROOT/rel,target)
        self.artifact=self.root/'artifact.json';self.dump(self.artifact,{'schema':'fixture-audit/v1','full_comparison':'preserved','scientific_advantage':False})
        self.contract=self.root/'contract.json';self.receipt=self.root/'receipt.json'
        self.contract_value={'schema':'agi-alpha/conditional-functional-contract006/v1','scope':'source-bound-pilot-report-delivery',
            'requirements':copy.deepcopy(c.REQUIREMENTS),'verifier_source':{'path':'verification/fixture_verifier.py','sha256':self.hash(self.verifier)},
            'functional_obligations':{'path':'verification/fixture_obligations.json','sha256':self.hash(self.obligations)},
            'scenario':copy.deepcopy(c.SCENARIO),'commercial_cohort_admitted':False}
        self.dump(self.contract,self.contract_value)
        self.receipt_value={'schema':'agi-alpha/functional-acceptance006/v1','artifact_sha256':self.hash(self.artifact),
            'contract_sha256':self.hash(self.contract),'functional_obligations_sha256':self.hash(self.obligations),
            'verifier_source_sha256':self.hash(self.verifier),'accepted':True,'scope':'source-bound-pilot-report-delivery'}
        self.dump(self.receipt,self.receipt_value)
        self.authority={'expected_contract_sha256':self.hash(self.contract),'expected_receipt_sha256':self.hash(self.receipt)}
        self.output=self.root/'output'

    def tearDown(self):self.temp.cleanup()
    def dump(self,path,value):path.write_text(json.dumps(value,indent=2)+'\n')
    def hash(self,path):return hashlib.sha256(path.read_bytes()).hexdigest()
    def run_fixture(self):
        with patch.object(c,'ROOT',self.root):
            return c.run(self.artifact,self.receipt,self.contract,self.output,**self.authority)

    def test_positive_settlement_and_all_adverse_paths_same_actual_artifact(self):
        report=self.run_fixture()
        self.assertTrue(report['all_qualification_checks_passed'])
        self.assertGreater(len(report['checks']),12)
        self.assertEqual((self.output/'DELIVERED.json').read_bytes(),c.canonical(json.loads(self.artifact.read_text())))
        primary=report['snapshots']['primary_conditional_qualification']['snapshot']
        stress=report['snapshots']['correlated_reversal_stress']['snapshot']
        liquidity=report['snapshots']['positive_profit_but_no_unrestricted_cash']['snapshot']
        self.assertGreater(primary['unrestrictedEarned'],0)
        self.assertEqual(stress['unrestrictedEarned'],0)
        self.assertEqual(stress['collections'],0)
        self.assertGreater(liquidity['profit'],0)
        self.assertEqual(liquidity['available'],0)
        self.assertEqual(report['commercial_decision']['available_commercial_earned_funds'],0)
        self.assertEqual(len(report['conditional_frontier']['all_fixture_admitted_cases']),7)
        self.assertEqual(len(report['all_scenario_cases_including_separate_liquidity_falsifier']),9)
        self.assertEqual(primary['expenses'],7*sum(c.SCENARIO['cost_per_admitted_case'].values()))
        self.assertIsNone(report['conditional_frontier']['unpriced_complete_lifecycle_cost_K'])
        self.assertIsNone(report['conditional_frontier']['same_cohort_baseline_complete_cost_profit'])
        self.assertTrue(all(x['artifact_sha256']==self.hash(self.artifact) for x in report['conditional_frontier']['all_fixture_admitted_cases']))

    def test_forged_or_stale_receipt_refused_before_effects(self):
        self.receipt_value['accepted']=False;self.dump(self.receipt,self.receipt_value)
        with self.assertRaisesRegex(ValueError,'FROZEN_RECEIPT_MISMATCH'):self.run_fixture()
        self.assertFalse(self.output.exists())

    def test_authoritatively_negative_receipt_stays_refused(self):
        self.receipt_value['accepted']=False;self.dump(self.receipt,self.receipt_value);self.authority['expected_receipt_sha256']=self.hash(self.receipt)
        with self.assertRaisesRegex(ValueError,'FUNCTIONAL_ACCEPTANCE_NOT_ESTABLISHED'):self.run_fixture()
        self.assertFalse(self.output.exists())

    def test_changed_artifact_cannot_use_old_acceptance(self):
        self.dump(self.artifact,{'substituted':True})
        with self.assertRaisesRegex(ValueError,'ACCEPTANCE_RECEIPT_BINDING'):self.run_fixture()
        self.assertFalse(self.output.exists())

    def test_unsupported_invariant_is_not_silently_ignored(self):
        self.contract_value['requirements'].append('guaranteed-biological-truth');self.dump(self.contract,self.contract_value)
        self.authority['expected_contract_sha256']=self.hash(self.contract)
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_FUNCTIONAL_SCOPE_OR_REQUIREMENTS'):self.run_fixture()
        self.assertFalse(self.output.exists())

    def test_commercial_admission_cannot_be_claimed_from_fixture(self):
        self.contract_value['commercial_cohort_admitted']=True;self.dump(self.contract,self.contract_value);self.authority['expected_contract_sha256']=self.hash(self.contract)
        with self.assertRaisesRegex(ValueError,'COMMERCIAL_ADMISSION_NOT_QUALIFIED'):self.run_fixture()

    def test_corrupted_verifier_and_exchange_sources_refuse(self):
        self.verifier.write_text('SUBSTITUTED=True\n')
        with self.assertRaisesRegex(ValueError,'VERIFICATION_DEPENDENCY_CHANGED'):self.run_fixture()
        self.assertFalse(self.output.exists())
        self.verifier.write_text('FIXTURE_INTERFACE_ONLY = True\n')
        (self.root/'vendor/alpha_claim/protected_exchange.py').write_text('SUBSTITUTED=True\n')
        with self.assertRaisesRegex(ValueError,'PINNED_EXCHANGE_SOURCE_MISMATCH'):self.run_fixture()
        self.assertFalse(self.output.exists())

    def test_unknown_contract_fields_and_weakened_obligations_refuse(self):
        self.contract_value['network_allowed']=True;self.dump(self.contract,self.contract_value);self.authority['expected_contract_sha256']=self.hash(self.contract)
        with self.assertRaisesRegex(ValueError,'CONTRACT_SCHEMA'):self.run_fixture()
        del self.contract_value['network_allowed'];self.dump(self.contract,self.contract_value);self.authority['expected_contract_sha256']=self.hash(self.contract)
        value=json.loads(self.obligations.read_text());value['requires_truthful_all_arms_and_failures']=False;self.dump(self.obligations,value)
        self.contract_value['functional_obligations']['sha256']=self.hash(self.obligations);self.dump(self.contract,self.contract_value);self.authority['expected_contract_sha256']=self.hash(self.contract)
        with self.assertRaisesRegex(ValueError,'UNSUPPORTED_OR_WEAKENED_OBLIGATION'):self.run_fixture()

    def test_existing_evidence_never_overwritten(self):
        self.run_fixture();before={str(p.relative_to(self.output)):self.hash(p) for p in self.output.rglob('*') if p.is_file()}
        with self.assertRaises(FileExistsError):self.run_fixture()
        after={str(p.relative_to(self.output)):self.hash(p) for p in self.output.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

    def test_parent_symlink_and_missing_external_authority_refuse(self):
        self.authority['expected_contract_sha256']=''
        with self.assertRaisesRegex(ValueError,'EXTERNAL_FROZEN_AUTHORITY_HASH_REQUIRED'):self.run_fixture()
        self.assertFalse(self.output.exists())

if __name__=='__main__':unittest.main()
