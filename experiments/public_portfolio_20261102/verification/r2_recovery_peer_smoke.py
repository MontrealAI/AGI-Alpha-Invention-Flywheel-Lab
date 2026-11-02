from __future__ import annotations
import argparse,hashlib,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from connected_enterprise.finance import JournalAccount,audit_journal
from experiments.public_portfolio_20261102 import service,recovery_run


def run():
    checks={};usd=1000000
    with tempfile.TemporaryDirectory(prefix='nonbusiness-independent-recovery-') as temporary:
        out=Path(temporary);(out/'control').mkdir();path=out/'private'/'case'/'account.sqlite';path.parent.mkdir(parents=True)
        manifest=service.prepare_manifest(ROOT,[],'nonbusiness-independent-recovery')
        settings={'opening':100*usd,'working':0,'contract':'NONBUSINESS-INDEPENDENT-RECOVERY'}
        with JournalAccount(ROOT,manifest,path,**settings) as original:
            original.cost('first',10*usd,0);original.cost('second',5*usd,1);prefix=original.export()
        receipt={};relay=recovery_run.PrefixRelay(ROOT,manifest,path,receipt=receipt,**settings)
        try:
            relay.cost('first',10*usd,0)
            rejected=False
            try:relay.cost('second',6*usd,1)
            except ValueError as error:
                rejected='HISTORICAL_JOURNAL_REQUEST_OR_RESULT_MISMATCH' in str(error)
            checks['independent_historical_request_mismatch_rejected']=rejected
            checks['original_unchanged_after_bad_reconstruction']=relay._live.export()==prefix
        finally:relay.close()
        receipt={};relay=recovery_run.PrefixRelay(ROOT,manifest,path,receipt=receipt,**settings)
        try:
            relay.cost('first',10*usd,0);relay.cost('second',5*usd,1);relay.cost('third',7*usd,2);final=relay.export()
            checks['exact_original_prefix_preserved']=final['ledger']['actions'][:len(prefix['ledger']['actions'])]==prefix['ledger']['actions']
            checks['one_missing_action_appended_without_reset']=len(final['ledger']['actions'])==len(prefix['ledger']['actions'])+1
            checks['same_account_cash_and_cost_history']=final['ledger']['summary']['cash']==78*usd and final['ledger']['summary']['expenses']==22*usd and final['ledger']['config']['opening']==100*usd
            checks['independent_full_native_replay']=audit_journal(final,root=ROOT,manifest=manifest)['accepted']
            checks['strict_prefix_match_recorded']=receipt['prefix_matched'] and receipt['historical_requests_reexecuted_on_original']==0
        finally:relay.close()
        receipt2={};relay=recovery_run.PrefixRelay(ROOT,manifest,path,receipt=receipt2,**settings)
        try:
            relay.cost('first',10*usd,0);relay.cost('second',5*usd,1);relay.cost('third',7*usd,2)
            checks['second_reconstruction_adds_no_duplicate_action']=relay.export()==final and receipt2['prefix_matched']
        finally:relay.close()
    return {'schema':'public-portfolio/independent-recovery-peer-smoke/v1','checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'recovery_driver_sha256':hashlib.sha256(Path(recovery_run.__file__).read_bytes()).hexdigest(),
            'checks':checks,'passed':all(checks.values()),
            'scope':'Independently authored disposable NONBUSINESS fixture only; none of original39/4/67 campaign cases or private keys opened, copied or modified. Original financial source remains unchanged.'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();output=Path(args.output)
    if output.exists():raise ValueError('refuse overwrite of peer smoke result')
    result=run();output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({'passed':result['passed'],'checks':len(result['checks'])}))
    raise SystemExit(0 if result['passed'] else 1)
