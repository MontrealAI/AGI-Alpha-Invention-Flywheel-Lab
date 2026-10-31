"""Calendar authority tests; synthetic ticket objects isolate operating binding.

Cryptographic authentication remains covered by native transition tests/audits.
"""
import copy
import importlib.util
from pathlib import Path
import unittest
from commercial.ledger import digest
from connected_enterprise.engine import default_config
from connected_enterprise.migration import default_policy

path=Path(__file__).resolve().parents[1]/'connected_enterprise/verify.py'
spec=importlib.util.spec_from_file_location('connected_enterprise.calendar_audit_test',path)
verify=importlib.util.module_from_spec(spec);spec.loader.exec_module(verify)

class CalendarAuditBindingTests(unittest.TestCase):
    def fixture(self):
        cfg=default_config();cfg['horizon_days']=8;p=default_policy();p['protection_hours']=2
        old={'config':copy.deepcopy(cfg),'queue':[],'current':None,'last_time':183,'events':[{'kind':'BUSINESS_DECISION','time':i*24} for i in range(8)],'prospective_policy':p,'orders':[{'id':'settled','outcome':'SETTLED','price':123}]}
        policy={**p,'schema':'agi-alpha/connected-prospective-policy/v3-calendar','calendar_until_day':70}
        ticket={'body':{'schema':'agi-alpha/native-source-transition/v1','id':'extension','day':183,'operating':{'policy':policy,'prior_checkpoint':{'body':{'state':old},'signature':'fixture-prior'}}},'signature':'fixture-ticket'}
        row={'from_day':8,'until_day':70,'ticket_sha256':digest(ticket),'prior_checkpoint_sha256':digest(ticket['body']['operating']['prior_checkpoint'])}
        result={'config':cfg,'orders':copy.deepcopy(old['orders']),'calendar_extensions':[row],'operating_state':{'calendar_extensions':[copy.deepcopy(row)]},'owned_account':{'source_transitions':{'extension':ticket},'ledger':{'actions':[{'op':'source_transition','args':{'id':'extension'}}]}}}
        return result,ticket,old

    def check_rejected(self,change):
        r,t,o=self.fixture();change(r,t,o)
        with self.assertRaises(ValueError):verify._audited_calendar_horizon(r)

    def test_valid_extension_preserves_original_config(self):
        r,t,o=self.fixture();before=copy.deepcopy(r);self.assertEqual(verify._audited_calendar_horizon(r),70);self.assertEqual(r,before);self.assertEqual(r['config']['horizon_days'],8)

    def test_legacy_horizon_unchanged(self):
        self.assertEqual(verify._audited_calendar_horizon({'config':{'horizon_days':8}}),8)

    def test_unbound_metadata_rejected(self):
        self.check_rejected(lambda r,t,o:r['owned_account']['ledger']['actions'].clear())

    def test_missing_metadata_rejected(self):
        self.check_rejected(lambda r,t,o:r.pop('calendar_extensions'))

    def test_changed_metadata_rejected(self):
        self.check_rejected(lambda r,t,o:r['calendar_extensions'][0].__setitem__('until_day',71))

    def test_nonempty_old_queue_or_current_rejected(self):
        for field,value in [('queue',[{'time':192}]),('current',{'prepared':True})]:
            with self.subTest(field=field):self.check_rejected(lambda r,t,o:o.__setitem__(field,value))

    def test_invalid_endpoints_rejected(self):
        for value in [True,8,7,366,'70',70.5]:
            with self.subTest(value=value):self.check_rejected(lambda r,t,o:t['body']['operating']['policy'].__setitem__('calendar_until_day',value))

    def test_old_calendar_truncation_or_duplicate_rejected(self):
        self.check_rejected(lambda r,t,o:o['events'].pop())
        self.check_rejected(lambda r,t,o:o['events'].append(copy.deepcopy(o['events'][-1])))

    def test_backdated_or_skipped_start_rejected(self):
        self.check_rejected(lambda r,t,o:o.__setitem__('last_time',192))
        self.check_rejected(lambda r,t,o:t['body'].__setitem__('day',182))

    def test_old_terms_change_rejected(self):
        self.check_rejected(lambda r,t,o:t['body']['operating']['policy'].__setitem__('premium_microUSD',1))

    def test_completed_order_rewrite_rejected(self):
        self.check_rejected(lambda r,t,o:r['orders'][0].__setitem__('outcome','REFUNDED'))

    def test_prior_extension_prefix_tamper_rejected(self):
        self.check_rejected(lambda r,t,o:o.__setitem__('calendar_extensions',[{'fake':True}]))

    def test_operating_state_extension_mismatch_rejected(self):
        self.check_rejected(lambda r,t,o:r['operating_state']['calendar_extensions'].clear())

if __name__=='__main__':unittest.main()
