import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adaptive_enterprise.instruments import prepare_complete_offer_services
from connected_enterprise.engine import run_world
from connected_enterprise.verify import audit
from connected_enterprise.joint_planning import plan_actions
from experiments import comparator050 as c

ROOT=Path(__file__).resolve().parents[1]


class ComparatorPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='.comparator050-test-',dir=ROOT)
        cls.folder=Path(cls.temporary.name)
        cls.manifest=prepare_complete_offer_services(ROOT,str(cls.folder.relative_to(ROOT)/'services'),cohort_seed=c.PROTOCOL['cohort_seed'],jobs_per_service=c.PROTOCOL['jobs_per_service'],packet_jobs=c.PROTOCOL['packet_jobs'],packet_rows=c.PROTOCOL['packet_rows'])
        cls.manifest['native_engine']='exact-permanent-v2'

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_strong_conventional_has_identical_full_public_options_configuration(self):
        baseline,manifest,engine_arm=c.configuration(self.manifest,'central','strong_conventional')
        joint,_,joint_arm=c.configuration(self.manifest,'central','composed_joint')
        self.assertEqual(engine_arm,joint_arm)
        self.assertEqual(manifest,self.manifest)
        joint['strategic_allocation_policy'].pop('strategic_game')
        self.assertEqual(baseline,joint)

    def test_ablations_do_not_change_physical_contracts_or_public_markets(self):
        joint,_,_=c.configuration(self.manifest,'central','composed_joint')
        commerce,_,commerce_arm=c.configuration(self.manifest,'central','commerce_only')
        capability,_,capability_arm=c.configuration(self.manifest,'central','capability_only')
        self.assertEqual(commerce['strategic_allocation_policy']['capacity_menu']['max_quantity'],0)
        self.assertEqual(commerce_arm,'competitive_growth')
        self.assertEqual(capability_arm,'baseline')
        self.assertNotIn('sequence',capability['strategic_allocation_policy'])
        self.assertNotIn('channel_menu_policy',capability)
        for cfg in (commerce,capability):
            for field in ('opening','working','channels','initial_slots','maximum_slots','complete_offer_policy','capacity_price','production_cost','support_cost','nonpayment_bps'):
                self.assertEqual(cfg[field],joint[field])
        self.assertEqual(capability['setup_cost']+5000000,joint['setup_cost'])
        self.assertEqual(capability['maintenance_daily']+50000,joint['maintenance_daily'])

    def test_fixed_split_cannot_invent_an_untuned_share(self):
        with self.assertRaisesRegex(ValueError,'REGISTERED_DEVELOPMENT_SHARE'):
            c.configuration(self.manifest,'central','tuned_fixed_split')
        with self.assertRaises(ValueError):
            c.configuration(self.manifest,'central','tuned_fixed_split',split_bps=3333)

    def test_registered_fixed_share_uses_native_caps_and_explicit_tuning_cost(self):
        baseline,_,_=c.configuration(self.manifest,'central','strong_conventional')
        for share in c.SHARES:
            cfg,_,arm=c.configuration(self.manifest,'central','tuned_fixed_split',split_bps=share,tuning_charge=17)
            self.assertEqual(arm,'competitive_growth')
            self.assertEqual(cfg['strategic_allocation_policy']['category_budgets_bps'],{'acquisition':share,'capacity':10000-share})
            self.assertEqual(cfg['setup_cost'],baseline['setup_cost']+17)
            cfg['setup_cost']-=17
            cfg['strategic_allocation_policy'].pop('category_budgets_bps')
            self.assertEqual(cfg,baseline)

    def test_original_checkout_cannot_start_registered_frozen_accounts(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)
            c.write(output/'REGISTERED.json',{'protocol':c.PROTOCOL})
            with self.assertRaisesRegex(ValueError,'EXECUTE_FROM_REGISTERED_FROZEN_SOURCE'):
                c.plan(output)
            self.assertFalse((output/'private').exists())

    def test_same_prefix_generates_same_actions_for_strong_control_and_joint(self):
        cfg,_,engine_arm=c.configuration(self.manifest,'central','strong_conventional')
        game=c.configuration(self.manifest,'central','composed_joint')[0]['strategic_allocation_policy']['strategic_game']
        calls=[]
        def inspect(state,jobs,candidates,*args,**kwargs):
            ordinary=plan_actions(state,jobs,candidates,*args,**kwargs)
            alternative=copy.deepcopy(state)
            alternative['config']['strategic_allocation_policy']['strategic_game']=copy.deepcopy(game)
            joint=plan_actions(alternative,jobs,copy.deepcopy(candidates),*args,**kwargs)
            for key in ('deliveries','investments','observation','riskpolicy','max_delivery_slots','earned_deduction'):
                self.assertEqual(ordinary['allocation'][key],joint['allocation'][key])
            calls.append(ordinary)
            return ordinary
        with patch('connected_enterprise.joint_planning.plan_actions',inspect):
            result=run_world(ROOT,self.manifest,cfg,c.PROTOCOL['seed'],engine_arm,self.folder/'native-strong-control')
        self.assertEqual(len(calls),c.PROTOCOL['horizon_days'])
        self.assertTrue(audit(ROOT,self.manifest,result)['accepted'])


class TuningSelectionTests(unittest.TestCase):
    def development(self):
        profits={0:(40,-20),5000:(35,-10),10000:(100,-30)}
        rows=[{'case':case,'arm':str(share),'summary':{'profit':profits[share][i],'expenses':7+i}} for share in c.SHARES for i,case in enumerate(c.PROTOCOL['cases'])]
        return {'status':'COMPLETED','rows':rows}

    def test_preregistered_worst_case_selection_and_exact_once_cost_attribution(self):
        result=c.choose(self.development())
        self.assertEqual(result['selected_acquisition_bps'],5000)
        self.assertEqual(result['selected_capacity_bps'],5000)
        self.assertEqual(result['tuning_expense_microUSD'],45)
        self.assertEqual(result['evaluation_cost_attribution'],{'central':23,'no_demand':22})
        self.assertFalse(result['account_balances_transferred'])
        self.assertIsNone(result['study_financial_sum'])
        self.assertIsNone(result['actual_external_tuning_bill'])

    def test_tie_break_is_frozen_and_input_order_does_not_select_after_outcome(self):
        development=self.development()
        for row in development['rows']:row['summary']['profit']=0
        first=c.choose(development)
        development['rows'].reverse()
        second=c.choose(development)
        self.assertEqual(first['selected_acquisition_bps'],5000)
        self.assertEqual(first['selected_acquisition_bps'],second['selected_acquisition_bps'])

    def test_incomplete_duplicate_or_unregistered_development_refuses_selection(self):
        for change in ('missing','duplicate','unknown'):
            development=self.development()
            if change=='missing':development['rows'].pop()
            elif change=='duplicate':development['rows'][-1]=copy.deepcopy(development['rows'][0])
            else:development['rows'][0]['arm']='3333'
            with self.assertRaisesRegex(ValueError,'COMPLETE_REGISTERED_TUNING_REQUIRED'):
                c.choose(development)

    def test_fabricated_completed_development_cannot_freeze_evaluation(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)
            development=self.development()
            development.update(phase='development',source_sha256='s',protocol_sha256=c.digest(c.PROTOCOL),authority=[])
            frozen={'source':{'sha256':'s'},'configs':{'development':{case:{str(share):{'config':{},'engine_arm':'competitive_growth'} for share in c.SHARES} for case in c.PROTOCOL['cases']}},'manifests':{'development':{}}}
            c.write(output/'DEVELOPMENT.json',development)
            c.write(output/'SELECTED.json',c.choose(development))
            with self.assertRaises(FileNotFoundError):
                c.selected_evaluation(output,frozen)
            self.assertFalse((output/'EVALUATION_FROZEN.json').exists())

    def test_completed_resume_receipt_binds_persisted_telemetry_without_changing_money(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)
            original={'owned_account':{'journal':'unchanged'},'resource_seconds':17.5}
            resumed={'owned_account':{'journal':'unchanged'},'resource_seconds':0.001}
            c.write(output/'RESULT.json',resumed)
            result=c.persisted_after_resume(original,resumed,output)
            self.assertEqual(c.digest(result),c.digest(resumed))
            self.assertNotEqual(c.digest(result),c.digest(original))
            with self.assertRaisesRegex(ValueError,'CHANGED_NATIVE_HISTORY'):
                c.persisted_after_resume(original,dict(resumed,owned_account={'journal':'changed'}),output)
            with self.assertRaisesRegex(ValueError,'NOT_PERSISTED_BYTES'):
                c.persisted_after_resume(original,dict(resumed,resource_seconds=99),output)


class ComparatorHeaderTests(unittest.TestCase):
    def fixture(self,output):
        # Pure wrapper fixture: the native checker is stubbed, never represented
        # as a real financial audit. Actual public_row reconciliation still runs.
        frozen={'source':{'sha256':'f'*64},'configs':{'development':{}},
                'manifests':{'development':{},'evaluation':{}}}
        evaluation={}
        selection={'evaluation_cost_attribution':{'central':1,'no_demand':1},
                   'tuning_expense_microUSD':2}
        for phase,arms,seed,name in (
                ('development',tuple(str(s) for s in c.SHARES),c.PROTOCOL['development_seed'],'DEVELOPMENT.json'),
                ('evaluation',c.ARMS,c.PROTOCOL['seed'],'PUBLIC.json')):
            configs=frozen['configs']['development'] if phase=='development' else evaluation
            rows=[]
            for case in c.PROTOCOL['cases']:
                configs[case]={}
                for arm in arms:
                    config={'opening':c.PROTOCOL['opening_microUSD_per_account'],
                            'horizon_days':c.PROTOCOL['horizon_days']}
                    engine_arm='baseline' if arm=='capability_only' else 'competitive_growth'
                    configs[case][arm]={'config':config,'engine_arm':engine_arm}
                    result={'config':config,'seed':seed,'arm':engine_arm,'source':frozen['source'],
                            'complete':True,'summary':{'profit':0,'revenue':0,'recoveryIncome':0,'expenses':0},
                            'owned_account':{'ledger':{'actions_sha256':'a'*64}},
                            'paid_jobs':0,'customers':0,'repeat_customers':0,'orders':[],
                            'channels':{'exposures_by_day':{}},'investments':[],
                            'conditional_simulated_commercial_success':False}
                    folder=output/'private'/phase/(case+'-'+arm)
                    folder.mkdir(parents=True)
                    c.write(folder/'RESULT.json',result)
                    rows.append(c.public_row(config,phase,case,arm,result,{'accepted':True},True))
            report={'source_sha256':frozen['source']['sha256'],'protocol_sha256':c.digest(c.PROTOCOL),
                    'phase':phase,'status':'COMPLETED','rows':rows,'authority':[],
                    'wall_seconds':0.0,'process_cpu_seconds':0.0}
            if phase=='evaluation':
                report.update(five_policy_comparison_complete=True,selection_sha256=c.digest(selection))
            c.write(output/name,report)
        return frozen,evaluation,selection

    def test_final_verify_binds_valid_headers_with_existing_row_reconciliation(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)
            frozen,evaluation,selection=self.fixture(output)
            with patch.object(c,'plan',return_value=(output,frozen)), \
                    patch.object(c,'selected_evaluation',return_value=(evaluation,selection)), \
                    patch('connected_enterprise.verify.audit',return_value={'accepted':True}) as checker:
                value=c.verify(output)
            self.assertTrue(value['accepted'])
            self.assertEqual(value['worlds'],{'development':6,'evaluation':10})
            self.assertEqual(value['public_sha256'],c.digest(c.read(output/'PUBLIC.json')))
            self.assertEqual(checker.call_count,16)

    def test_final_verify_rejects_header_only_changes_and_missing_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)
            frozen,evaluation,selection=self.fixture(output)
            original=c.read(output/'PUBLIC.json')
            for field,value in (('source_sha256','0'*64),('protocol_sha256','0'*64),
                                ('phase','development'),('authority',['spend'])):
                for missing in (False,True):
                    with self.subTest(field=field,missing=missing):
                        report=copy.deepcopy(original)
                        if missing:report.pop(field)
                        else:report[field]=value
                        c.write(output/'PUBLIC.json',report)
                        (output/'VERIFY.json').unlink(missing_ok=True)
                        with patch.object(c,'plan',return_value=(output,frozen)), \
                                patch.object(c,'selected_evaluation',return_value=(evaluation,selection)), \
                                patch('connected_enterprise.verify.audit',return_value={'accepted':True}) as checker:
                            with self.assertRaisesRegex(ValueError,'RECORDED_COMPARATOR_IDENTITY_CHANGED'):
                                c.verify(output)
                        self.assertEqual(checker.call_count,6)
                        self.assertFalse((output/'VERIFY.json').exists())
                        self.assertEqual(report['rows'],original['rows'])

    def test_operate_and_development_reject_false_authority_before_checking_or_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            output=Path(temporary)
            frozen,evaluation,selection=self.fixture(output)
            report=c.read(output/'PUBLIC.json');report['authority']=['spend']
            c.write(output/'PUBLIC.json',report)
            with patch.object(c,'plan',return_value=(output,frozen)), \
                    patch.object(c,'selected_evaluation',return_value=(evaluation,selection)), \
                    patch('connected_enterprise.engine.run_world') as execute:
                with self.assertRaisesRegex(ValueError,'RECORDED_COMPARATOR_IDENTITY_CHANGED'):
                    c.operate(output,'evaluation')
            execute.assert_not_called()
            development=c.read(output/'DEVELOPMENT.json');development['authority']=['spend']
            with patch('connected_enterprise.verify.audit') as checker:
                with self.assertRaisesRegex(ValueError,'RECORDED_COMPARATOR_IDENTITY_CHANGED'):
                    c.verify_development(output,frozen,development)
            checker.assert_not_called()


if __name__=='__main__':
    unittest.main()
