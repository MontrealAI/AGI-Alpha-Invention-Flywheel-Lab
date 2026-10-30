import argparse
import copy
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

parser=argparse.ArgumentParser()
parser.add_argument('--source-root',required=True,type=Path)
parser.add_argument('--output',required=True,type=Path)
parser.add_argument('--source-sha',default='c8c1705bae4d0679f090c4cb58e87386424be9b8')
parser.add_argument('--account-git-blob')
arguments=parser.parse_args()
ROOT=arguments.source_root.resolve()
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from test_adaptive_account import AdaptiveAccountTests, _plan
from adaptive_enterprise.account import Account, action_digest, audit_account
from commercial.ledger import digest
from connected_enterprise.engine import default_config, validate_config


def load_old():
    p=Path(__file__).with_name('unsafe_account_original.py.txt')
    loader=importlib.machinery.SourceFileLoader('_unsafe_account018',str(p))
    spec=importlib.util.spec_from_loader(loader.name,loader)
    result=importlib.util.module_from_spec(spec); loader.exec_module(result)
    return result


def plan(later):
    option={'id':'capacity','kind':'capacity','upfront_cost':40_000_000,
            'later_liabilities':{'ordinary':later},'execution':{'kind':'capacity','source_sha256':'a'*64}}
    return dict(_plan(),selected_options=[option],upfront_cost=40_000_000,
                worst_later_reserve=later,reserve_amount=40_000_000+later,expected_net=10_000_000)


def reserve(account,p,digest_fn=action_digest):
    state=account.snapshot()['state_digest']; amount=p['reserve_amount']
    return account.reserve(p,expected_state_digest=state,authorized_digest=digest_fn(p,state,amount,10_000_000),
                           amount=amount,expected_net=10_000_000,day=1)


def main():
    p=arguments.output
    if p.exists(): raise ValueError('NEW_EVIDENCE_REQUIRED')
    if arguments.account_git_blob:
        raw=(ROOT/'adaptive_enterprise/account.py').read_bytes()
        if hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()!=arguments.account_git_blob:
            raise ValueError('EXACT_ACCOUNT_SOURCE_REQUIRED')
    fixture=AdaptiveAccountTests
    fixture.setUpClass()
    records=[]
    try:
        old=load_old()
        with tempfile.TemporaryDirectory() as tmp:
            with old.Account(fixture.root,fixture.manifest,Path(tmp)/'unsafe.sqlite',opening=1_000_000_000,working=0,contract='adaptive-account-test') as a:
                fixture().earn(a); reserve(a,plan(0),old.action_digest)
                a.finish('next-delivery',0,'b'*64,2)
                assert a.audit()['accepted'] and a.snapshot()['summary']['expenses']==10_000_000
                records.append({'case':'P1_original','verdict':'UNSAFE_PATH_REPRODUCED','summary':a.snapshot()['summary']})
        for later in [0,30_000_000]:
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'repaired.sqlite'; selected=plan(later)
                with Account(fixture.root,fixture.manifest,path,opening=1_000_000_000,working=0,contract='adaptive-account-test') as a:
                    fixture().earn(a); reserve(a,selected); before=a.snapshot()
                    try:a.finish('next-delivery',0,'b'*64,2)
                    except ValueError as exc:assert 'RESOLUTION_REQUIRED' in str(exc)
                    else:raise AssertionError('UNRECONCILED_RELEASE')
                    assert a.snapshot()==before
                    receipt={'schema':'agi-alpha/adaptive012-obligation-resolution/v1','plan_id':'next-delivery','resolved_at_day':2,
                        'native_actions_sha256':a.snapshot()['actions_sha256'],'work_artifact_sha256':'b'*64,
                        'upfront_incurred_microUSD':40_000_000,'later_incurred_microUSD':later,'unused_reserve_microUSD':0,
                        'deliveries':[],'growth':[{'option_id':'capacity','execution_sha256':digest(selected['selected_options'][0]['execution']),
                                                   'prepaid_support_microUSD':later}]}
                    forged=copy.deepcopy(receipt); forged['upfront_incurred_microUSD']=0
                    try:a.finish('next-delivery',later,'b'*64,2,obligation_receipt=forged)
                    except ValueError:pass
                    else:raise AssertionError('FORGED_UPFRONT_INVOICE_ACCEPTED')
                    original=a._owner.execute
                    def fail(op,*args,**kwargs):
                        if op=='finish':raise InterruptedError('after durable resolution, before native finish')
                        return original(op,*args,**kwargs)
                    with patch.object(a._owner,'execute',side_effect=fail):
                        try:a.finish('next-delivery',40_000_000+later,'b'*64,2,obligation_receipt=receipt)
                        except InterruptedError:pass
                        else:raise AssertionError('CRASH_HOOK_NOT_EXERCISED')
                with Account(fixture.root,fixture.manifest,path,opening=1_000_000_000,working=0,contract='adaptive-account-test') as a:
                    a.finish('next-delivery',40_000_000+later,'b'*64,2,obligation_receipt=receipt)
                    settled=a.snapshot();a.finish('next-delivery',40_000_000+later,'b'*64,2,obligation_receipt=receipt)
                    assert a.snapshot()==settled
                    assert settled['summary']['expenses']==50_000_000+later
                    assert settled['summary']['reservedInvestment']==0 and a.audit()['accepted']
                    audit_account(a.export(),root=fixture.root,manifest=fixture.manifest)
                    records.append({'case':'P1_repaired','later_microUSD':later,'verdict':'RECONCILED_CRASH_RETRY_REPLAY','summary':settled['summary']})
        with tempfile.TemporaryDirectory() as tmp:
            with Account(fixture.root,fixture.manifest,Path(tmp)/'rejected.sqlite',opening=1_000_000_000,working=0,contract='adaptive-account-test') as a:
                selected=plan(0); before=a.export()
                try:reserve(a,selected)
                except ValueError:pass
                else:raise AssertionError('UNFUNDED_RESERVATION_ACCEPTED')
                assert a.export()==before
                fixture().earn(a);reserve(a,selected)
                assert a.snapshot()['summary']['reservedInvestment']==40_000_000
                records.append({'case':'P2_reauthorization','verdict':'REJECTED_STATE_CLEARED_HISTORY_UNCHANGED_FRESH_RESERVE_ACCEPTED'})
        cfg=default_config();cfg['clearing_hours']=cfg['payment_deadline_hours']
        validate_config(cfg)
        total=cfg['production_hours']+cfg['acceptance_hours']+cfg['clearing_hours']
        assert total>cfg['payment_deadline_hours']
        records.append({'case':'P2_deadline','verdict':'UNRESOLVED_FINDING_REPRODUCED_AT_CHECKPOINT',
                        'admitted_completion_hour':total,'deadline_hour':cfg['payment_deadline_hours']})
    finally:fixture.tearDownClass()
    p.write_text(json.dumps({'checkpoint':arguments.source_sha,'account_git_blob':arguments.account_git_blob,'records':records,
        'release_qualified':False,'limits':'Same-session independent code-path challenge; not external certification. Original18 account regressions separately include concurrent writers and interrupted reservations.'},indent=2)+'\n')
    print(p.read_text())


if __name__=='__main__':main()
