"""Create small isolated, coherently signed accounts under wrong native configurations."""
import argparse
from contextlib import ExitStack
from pathlib import Path
import hashlib
import json
import tempfile
import sys
from unittest.mock import patch

def check(source,version,field):
    sys.path.insert(0,str(source.resolve()))
    from connected_enterprise.finance import JournalAccount,audit_journal
    from mechanism_harness import inventor,inventor_native,economical_native,mechanism_native,cart_native,cart_campaign
    from tests.test_omega_legacy_live_resume import small_workload
    from tests.test_omega_cart_native import small_native_fixture
    op,writer = {'v1':(inventor,inventor_native),'v2':(economical_native,inventor_native),
                 'v3':(mechanism_native,mechanism_native),'v4':(cart_native,cart_native)}[version]
    fields={'opening':2*writer.OPENING,'working':1_000_000,'contract':'independent-wrong-economic-purpose'}
    changed=({field:fields[field]} if field!='correct' else {})
    options={} if version in ('v1','v2') else {'stress':'no_demand'}
    sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='omega-tmp-config-check-') as tmp, ExitStack() as workload:
        out=Path(tmp)/'account'
        workload.enter_context(small_native_fixture() if version=='v4' else small_workload())
        with ExitStack() as isolated:
            # Defer only the artifact author's final public audit while the witness is being written.
            # Both subsequent audit calls use the real unpatched implementations.
            isolated.enter_context(patch.object(op,'audit',return_value=None))
            if version in ('v1','v2'):
                isolated.enter_context(patch.object(inventor_native,'audit_operation',return_value=None))
            real=writer.JournalAccount
            def make(*args,**kwargs):
                return real(*args,**{**kwargs,**changed})
            isolated.enter_context(patch.object(writer,'JournalAccount',side_effect=make))
            op.run(out,**options)
        read=lambda name:json.loads((out/name).read_bytes())
        export=read('NATIVE_EXPORT.json')
        cfg=export['ledger']['config'];journal=export['connected_journal']
        assert all(cfg[k]==journal[k]==v for k,v in {'opening':writer.OPENING,'working':0,'contract':writer.CONTRACT,**changed}.items())
        canonical=audit_journal(export,root=out/'runtime',manifest=read('MANIFEST.json'))
        assert canonical['accepted']
        before=sha(out/'NATIVE_EXPORT.json')
        try:
            accepted=op.audit(out)['accepted'];code=None
        except ValueError as exc:
            accepted=False;code=str(exc)
        try:
            op.run(out,resume=True,**options);live=True;livecode=None
        except (ValueError,RuntimeError) as exc:
            live=False;livecode=str(exc)
        assert sha(out/'NATIVE_EXPORT.json')==before
        return {'operator':version,'field':field,'native_capital_microUSD':cfg['opening'],
                'native_working_microUSD':cfg['working'],'native_contract':cfg['contract'],
                'native_actions':len(export['ledger']['actions']),'generic_financial_replay':True,
                'public_operator_accepted':accepted,'public_refusal':code,
                'completed_resume_accepted':live,'live_refusal':livecode,
                'native_export_unchanged':True, 'native_opening_claim_microUSD':writer.OPENING,
                'runtime':op.source_identity()}

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('source',type=Path);ap.add_argument('version',choices=['v1','v2','v3','v4'])
    ap.add_argument('field',choices=['opening','working','contract','correct']);ap.add_argument('output',type=Path)
    ao=ap.parse_args();r=check(ao.source,ao.version,ao.field)
    from commercial.ledger import digest
    r['runtime_sha256']=digest(r.pop('runtime'))
    with ao.output.open('x') as f:json.dump(r,f,indent=2,sort_keys=True);f.write('\n')
    print(ao.version,ao.field,r['generic_financial_replay'],r['public_operator_accepted'],r['completed_resume_accepted'])
