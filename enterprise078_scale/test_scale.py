from __future__ import annotations
import copy, hashlib, json, tempfile, unittest
from pathlib import Path
from commercial.ledger import digest
from commercial.terms_exact_v2 import prospective_terms
from enterprise078.construct import produce
from enterprise078.verify import verify
from enterprise078.service import prepare_manifest
from .account import ScaleBusinessAccount
from .operator import ROOT, load_protocol, save, read, run_case, lease_units
from .model import USD, capital, opportunities, public_market, quote, buyer_choice
from .review import review

class PurePolicyTests(unittest.TestCase):
    def setUp(self):
        self.p=load_protocol();self.w=self.p['worlds'][0]
    def test_protocol_registered_bytes(self):
        self.assertEqual(hashlib.sha256((ROOT/'enterprise078_scale/PROTOCOL.json').read_bytes()).hexdigest(),'05b7f877da51a0df114b99fdbba9bc79ac651562be9bf7da56dabfe2c355cc34')
    def test_capital_is_prospective_and_reference_is_separate(self):
        self.assertEqual(capital(self.p,self.w),25000*USD)
        self.assertEqual(capital(self.p,next(w for w in self.p['worlds'] if w['id']=='reference_100k')),100000*USD)
        self.assertEqual(capital(self.p,{**self.w,'financing_available':False}),0)
        self.assertGreater(capital(self.p,{**self.w,'cost_multiplier':3}),25000*USD)
    def test_unique_varied_requests_and_overlap(self):
        rows=opportunities(self.p);self.assertEqual(len(rows),72);self.assertEqual(len({r['id'] for r in rows}),72)
        first=[r for r in rows if r['period']==0];self.assertLess(len({r['buyer'] for r in first}),len(first))
        self.assertGreater(len({r['request'].get('hidden_threshold') for r in rows}),10)
    def test_no_future_rival_peeking(self):
        history=[{'period':7,'kind':'preparation','quote':1}]
        self.assertEqual(public_market(self.p,self.w,'preparation',4,history),public_market(self.p,self.w,'preparation',4,[]))
    def test_ordinary_retention_is_not_discovery_advantage(self):
        retained={'family':'both_capabilities','policy':'retry_same_key'}
        for row in opportunities(self.p):
            a=produce(row['request']);b=produce(row['request'],retained=retained)
            self.assertEqual(a,b);self.assertTrue(verify(row['request'],a)['accepted'])
    def test_no_budget_replenishment(self):
        for row in opportunities(self.p)[:6]:
            public=public_market(self.p,self.w,row['request']['kind'],0,[]);price=quote(self.p,self.w,public)
            response=buyer_choice(self.p,self.w,row,public,price,10**20)
            self.assertFalse(response['accepted']);self.assertLess(response['remaining_budget'],0)
    def test_no_purchase_is_real_option(self):
        row=opportunities(self.p)[0];public=public_market(self.p,self.w,'preparation',0,[])
        response=buyer_choice(self.p,{**self.w,'need_basis_points':0},row,public,6000*USD,0)
        self.assertFalse(response['accepted']);self.assertEqual(response['outside_choice'],'no_purchase')
    def test_capacity_requires_lead_time_and_expires(self):
        s={'capacity':[{'active':72,'expires':144,'units':1}], 'used_slots':{}}
        self.assertEqual(lease_units(s,71,0),0);self.assertEqual(lease_units(s,72,0),1)
        self.assertEqual(lease_units(s,144,0),0)

class NativePrefixTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.tag=self.base.name.replace('_','-')
        self.requests=[{'id':self.tag+'-'+str(i),'kind':'preparation','family':'both_capabilities','samples':1,'components':1,'quantity':3+i} for i in range(2)]
        self.profile='enterprise078/scale_inputs/test-'+self.tag+'.json';save(ROOT/self.profile,self.requests)
        self.manifest=prepare_manifest(ROOT,[{'id':r['id'],'profile_path':self.profile,
            'delivery_path':'enterprise078/deliveries/test-'+self.tag+'/'+r['id']+'.json'} for r in self.requests])
    def account(self):return ScaleBusinessAccount(ROOT,self.manifest,self.base/'native',opening=25000*USD,contract=self.tag)
    def deliver(self,a,index,hour):
        r=self.requests[index];ident='order-'+r['id'];price=12500*USD
        terms=prospective_terms(ident,price,9000,hour+1,fee=300*USD,exposure=price+300*USD+200_000,residual=500*USD)
        a.begin_order(r['id'],ident,'buyer',price,50000*USD,hour,hour+2,terms)
        result=a.complete_order(ident,r['id'],produce(r),hour)
        self.assertTrue(result['accepted']);a.release(ident,hour+1)
    def test_prefix_and_full_history_audits_agree(self):
        with self.account() as a:
            for i in range(3):
                a.cost('development-'+str(i),10*USD,i)
                self.assertEqual(a.account._audit_incremental(),a.audit())
            self.deliver(a,0,10)
            self.assertEqual(a.account._audit_incremental(),a.audit())
    def test_prepared_artifact_tamper_invalidates_warm_cache(self):
        with self.account() as a:
            self.deliver(a,0,10);a.account._audit_incremental()
            path=ROOT/self.manifest['jobs'][0]['delivery_path'];raw=path.read_bytes()
            try:
                changed=json.loads(raw);changed['rows'][0]['quantity']+=1;path.write_text(json.dumps(changed))
                with self.assertRaises(ValueError):a.cost('must-not-pass',USD,12)
            finally:path.write_bytes(raw)
            self.assertTrue(a.audit()['accepted'])
    def test_positive_profit_does_not_allow_illiquid_spend(self):
        with self.account() as a:
            self.deliver(a,0,10);self.deliver(a,1,20)
            summary=a.snapshot()['summary'];self.assertGreater(summary['profit'],summary['available'])
            amount=(summary['profit']+summary['available'])//2
            before=a.export();self.assertIsNone(a.spend('blocked','capacity-lease',amount,22,{'scope':'test'},1,allow_seed=False))
            self.assertEqual(a.export(),before)
    def test_repeat_resource_identity_never_spends_twice(self):
        with self.account() as a:
            one=a.spend('once','acquisition',USD,0,{'scope':'test'},1,allow_seed=True);before=a.export()
            self.assertEqual(a.spend('once','acquisition',USD,0,{'scope':'test'},1,allow_seed=True),one)
            self.assertEqual(a.export(),before)
    def test_reopen_keeps_history_and_discards_private_cache(self):
        with self.account() as a:
            a.cost('first',USD,0);a.account._audit_incremental();record=a.export();envelope=a.seal_checkpoint({'queue':[{'hour':12,'job':'pending'}]})
        with self.account() as b:
            self.assertEqual(b.export(),record);self.assertEqual(b.verify_checkpoint(envelope),{'queue':[{'hour':12,'job':'pending'}]})
            self.assertIsNone(b.account._native_prefix)
    def test_single_writer_guard_is_inherited(self):
        with self.account():
            with self.assertRaises((ValueError,RuntimeError,OSError)):
                other=self.account();other.close()

class OperatingRecoveryTests(unittest.TestCase):
    def test_after_commit_before_ack_recovery_preserves_one_research_charge(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'run'
            with self.assertRaises(InterruptedError):run_case(output,'central',interrupt_after=1)
            result=run_case(output,'central',resume=True,max_events=1)
            tape=read(output/'public/central/account.json')['ledger']
            charges=[a for a in tape['actions'] if a['op']=='cost' and a['args']['id']=='scale-research-and-failures']
            self.assertEqual(len(charges),1);self.assertFalse(result['completed']);self.assertIsNone(result['observer']['trailing_365_day_profit_microUSD'])
            with self.assertRaises(ValueError):run_case(output,'central')
    def test_resume_without_private_authority_never_creates_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'run';private=output/'private/central';private.mkdir(parents=True)
            with self.assertRaisesRegex(ValueError,'ORIGINAL_PRIVATE_AUTHORITY'):
                run_case(output,'central',resume=True)
            self.assertEqual(list(private.iterdir()),[])
    def test_unexpected_native_append_blocks_operating_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'run';run_case(output,'central',max_events=1)
            public=output/'public/central';context=read(public/'context.json');m=read(public/'manifest.json')
            with ScaleBusinessAccount(ROOT,m,output/'private/central/account',opening=context['opening'],working=context['working'],contract=context['contract']) as a:
                a.cost('unexpected-writer',USD,0)
            with self.assertRaisesRegex(ValueError,'UNACKNOWLEDGED_NATIVE_SUFFIX'):
                run_case(output,'central',resume=True)
    def test_no_financing_still_retains_costs_and_complete_endpoint(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'run';r=run_case(output,'no_financing')
            self.assertEqual(r['summary']['profit'],-2700*USD);self.assertEqual(r['summary']['payables'],2700*USD)
            self.assertEqual(r['opening_microUSD'],0);self.assertTrue(review(output/'public/no_financing')['accepted'])
            path=output/'public/no_financing/result.json';corrupt=read(path);corrupt['summary']['profit']+=1;save(path,corrupt)
            with self.assertRaises(ValueError):review(path.parent)

if __name__=='__main__':unittest.main()
