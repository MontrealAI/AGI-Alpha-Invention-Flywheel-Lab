"""Use real native accounting and a deliberately omitted investment to challenge the public audits."""
import argparse
from contextlib import ExitStack, nullcontext
from pathlib import Path
import tempfile
import hashlib
import json
import sys
from unittest.mock import patch

def run(source,version,omit):
    sys.path.insert(0,str(source.resolve()))
    from mechanism_harness import inventor,inventor_native,economical_native,mechanism_native
    from commercial.ledger import digest
    from connected_enterprise.finance import JournalAccount,audit_journal
    from tests.test_omega_legacy_live_resume import small_workload
    op,w = {'v1':(inventor,inventor_native),'v2':(economical_native,inventor_native),'v3':(mechanism_native,mechanism_native)}[version]
    captured={}
    target='v3-successor' if version=='v3' else 'omega-successor'
    normal=JournalAccount.spend
    def challenge(account,ident,kind,amount,day,work,expected_net,allow_seed=False):
        if ident==target:
            state=account.snapshot()['summary']
            stop=(account.manifest.get('native_engine') in {'prospective-v1','exact-prospective-v2'} and state['investmentStopped'])
            captured.update(day=day,amount=amount,available=state['available'],unrestricted_earned=state['unrestrictedEarned'],investment_stopped=bool(stop),
                            eligible=bool(not stop and expected_net>0 and not allow_seed and min(state['available'],state['unrestrictedEarned'])>=amount))
            if omit:return None
        return normal(account,ident,kind,amount,day,work,expected_net,allow_seed=allow_seed)
    with tempfile.TemporaryDirectory(prefix='omega-funded-omission-') as directory,ExitStack() as fixture:
        path=Path(directory)/'synthetic'
        if version!='v3':
            fixture.enter_context(small_workload());fixture.enter_context(patch.object(inventor_native,'INDEXES',tuple(range(8,16))))
        with ExitStack() as generation:
            generation.enter_context(patch.object(op,'audit',return_value=None))
            if version in ('v1','v2'):
                generation.enter_context(patch.object(inventor_native,'audit_operation',return_value=None))
            generation.enter_context(patch.object(JournalAccount,'spend',challenge))
            res=op.run(path)
        source_report=res if version=='v3' else res['native']
        parse=lambda p:json.loads((path/p).read_bytes())
        export=parse('NATIVE_EXPORT.json')
        assert audit_journal(export,root=path/'runtime',manifest=parse('MANIFEST.json'))['accepted']
        cfg=export['ledger']['config'];assert (cfg['opening'],cfg['working'],cfg['contract'])==(w.OPENING,0,w.CONTRACT)
        rows=[e for e in export['connected_journal']['entries'] if e['request'].get('id')==target]
        assert captured and captured['eligible'] and len(rows)==int(not omit)
        confirmed=source_report['successor'] is not None
        assert confirmed == (not omit)
        try:result=op.audit(path)['accepted'];error=None
        except (ValueError,RuntimeError) as exc:result=False;error=str(exc)
        return {'version':version,'biased_producer_skipped_eligible_spend':omit,'actual_available_prefix':captured,
                'ledger_opening_microUSD':cfg['opening'],'ledger_working_microUSD':cfg['working'],'registered_contract':cfg['contract'],
                'generic_financial_replay':True,'successor_spends':len(rows),'successor_reported':confirmed,
                'operator_accepted':result,'operator_refusal':error,'profit_microUSD':export['ledger']['summary']['profit'],
                'expenses_microUSD':export['ledger']['summary']['expenses'],'collections_microUSD':export['ledger']['summary']['collections'],
                'native_source_sha256':digest(op.source_identity()), 'native_actions':len(export['ledger']['actions'])}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('version',choices=['v1','v2','v3']);p.add_argument('action',choices=['skip','normal']);p.add_argument('output',type=Path)
    args=p.parse_args();record=run(args.source,args.version,args.action=='skip')
    with args.output.open('x') as out:json.dump(record,out,indent=2,sort_keys=True);out.write('\n')
    print(record)
