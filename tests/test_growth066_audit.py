"""Pure malformed-output audit fixtures; not native or economic execution claims."""
import copy
import unittest
from commercial.ledger import digest
from growth066.audit import check_financial_schedule,payment_unit_microUSD,daily_attainment


def fixture(stopped=False):
    reg={'operating_days':2,'month_days':30,'setup_usd':1,'tax_rate':.20}
    world={'settlement_days':1,'tail_days':2,'payment_rate':.029,'payment_fixed_usd':.30}
    actions=[];journal=[];profit=0
    def action(op,args,day,delta=0):
        nonlocal profit
        before={'profit':profit};profit+=delta
        actions.append({'seq':len(actions),'op':op,'args':args,'day':day,'before':before,'after':{'profit':profit}})
    setup={'operation':'spend','id':'initial-development','amount':1_000_000,'day':0,
           'kind':'reconciliation_bulk_resource','work':{'registration':digest(reg),'kind':'shared_development'}}
    journal.append({'status':'COMPLETE','funding':'SEED','request':setup})
    action('cost',{'id':'native-seed-setup','amount':1_000_000},0,-1_000_000)
    decision={'native_sequence_before':1,'proposal':{'chosen_orders':0 if stopped else 2,'collected_units':0 if stopped else 2,'unit_price_usd':20,'costs_microUSD':{}}}
    row={'decision':decision,'funding':{},'funded':not stopped,'native_after':{'profit':profit}}
    manifest={'jobs':[{'id':'job-m0'}]}
    def cost(ident,amount,day):
        journal.append({'status':'COMPLETE','request':{'operation':'execute','op':'cost','args':{'id':ident,'amount':amount},'day':day}})
        action('cost',{'id':ident,'amount':amount},day,-amount)
    if not stopped:
        action('register_terms',{'id':'job-m0-terms','terms':{'maturity_day':72}},1)
        action('offer',{'id':'job-m0','job_id':'job-m0','price':40_000_000,'decision_sha256':digest(decision)},1)
        for event in ('consent','fund'):action('event',{'id':'job-m0','action':event},1)
        action('event',{'id':'job-m0','action':'prepare'},2)
        cost('processing-job-m0',1_760_000,24)
        action('event',{'id':'job-m0','action':'release'},24,40_000_000)
        cost('tax-47',7_448_000,47)
    export={'ledger':{'actions':actions},'connected_journal':{'entries':journal}}
    result={'summary':actions[-1]['after'],'operating_end_hour':48,'settlement_drain_hour':48 if stopped else 73,
            'complete':True,'financially_stopped':stopped,'rows':[row]}
    return reg,world,manifest,result,export


class AuditTests(unittest.TestCase):
    def test_exact_cost_schedule_and_terminal_no_new_action_prefix(self):
        for stopped in (False,True):
            self.assertTrue(check_financial_schedule(*fixture(stopped))['accepted'])
    def test_missing_setup_processing_tax_and_changed_summary_refused(self):
        for kind in ('setup','processing','tax','summary','settlement','quantity'):
            args=list(fixture());result=args[3];export=args[4]
            if kind in {'setup','processing','tax'}:
                entries=export['connected_journal']['entries']
                prefix={'setup':'initial-development','processing':'processing-','tax':'tax-'}[kind]
                entries[:]=[e for e in entries if not e['request'].get('id',e['request'].get('args',{}).get('id','')).startswith(prefix)]
            elif kind=='summary':result['summary']={'profit':999}
            elif kind=='settlement':next(a for a in export['ledger']['actions'] if a['op']=='event' and a['args']['action']=='release')['day']+=1
            else:next(a for a in export['ledger']['actions'] if a['op']=='offer')['args']['price']+=1
            with self.subTest(kind=kind),self.assertRaises(ValueError):check_financial_schedule(*args)
    def test_exact_large_unit_fee(self):
        world={'payment_rate':.029,'payment_fixed_usd':.30}
        price=100_000_000_000_000_001
        expected=(price*29+999)//1000+300000
        self.assertEqual(payment_unit_microUSD(price,world),expected)
    def test_tax_overcharge_and_noncheckpoint_rejected(self):
        for mode in ('amount','time'):
            args=list(fixture());entry=next(e for e in args[4]['connected_journal']['entries'] if e['request'].get('args',{}).get('id')=='tax-47')
            if mode=='amount':entry['request']['args']['amount']+=1
            else:entry['request']['day']=46
            with self.subTest(mode=mode),self.assertRaises(ValueError):check_financial_schedule(*args)
    def test_attainment_exclusive_endpoint_and_signed_loss(self):
        tape={'actions':[{'day':0,'before':{'profit':0},'after':{'profit':100}},
                         {'day':8760,'before':{'profit':100},'after':{'profit':50}}]}
        result=daily_attainment(tape,8784,100)
        self.assertEqual(result['first_daily_attainment'],{'hour':8760,'trailing365_profit_microUSD':100})

if __name__=='__main__':unittest.main()
