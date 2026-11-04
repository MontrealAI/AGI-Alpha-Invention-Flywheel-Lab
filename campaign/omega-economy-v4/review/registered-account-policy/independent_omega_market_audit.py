"""Independent private synthetic economic-identity witnesses on real native accounting."""
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import argparse
import json
import sys


def run(source, version, mutation):
    sys.path.insert(0, str(source.resolve()))
    from commercial.ledger import digest
    from connected_enterprise.finance import JournalAccount, audit_journal
    from mechanism_harness import inventor, inventor_native, economical_native, mechanism_native
    from tests.test_omega_legacy_live_resume import small_workload

    operator = {'v1': inventor, 'v2': economical_native, 'v3': mechanism_native}[version]
    edit_count = 0
    real_execute = JournalAccount.execute
    real_cost = JournalAccount.cost

    def execute(account, op, args, day):
        nonlocal edit_count
        if mutation == 'substitution' and op in ('wallet', 'offer'):
            edit_count += 1
            args = {**args, 'buyer': 'unregistered-'+args['buyer']}
        if mutation == 'budget' and op == 'wallet':
            edit_count += 1
            args = {**args, 'amount': args['amount']+1}
        if mutation == 'deadline' and op == 'offer':
            edit_count += 1
            args = {**args, 'deadline': args['deadline']+2}
        if mutation == 'event' and op == 'event' and args['action']=='consent':
            edit_count += 1
            args = {**args, 'event_id': args['event_id']+'-unregistered'}
        return real_execute(account, op, args, day)

    def cost(account, ident, amount, day):
        nonlocal edit_count
        if mutation == 'ghost' and ident in ('v3-maintenance','annual-maintenance'):
            edit_count += 1
            real_execute(account, 'wallet', {'buyer':'unregistered-bystander','amount':1}, day)
        return real_cost(account, ident, amount, day)

    with TemporaryDirectory(prefix='omega-synthetic-market-witness-') as tmp, small_workload():
        out = Path(tmp)/'account'
        with ExitStack() as gen:
            gen.enter_context(patch.object(operator, 'audit', return_value=None))
            if version in ('v1','v2'):
                gen.enter_context(patch.object(inventor_native, 'audit_operation', return_value=None))
            gen.enter_context(patch.object(JournalAccount, 'cost', cost))
            gen.enter_context(patch.object(JournalAccount, 'execute', execute))
            result=operator.run(out)
        assert edit_count > 0
        load=lambda name:json.loads((out/name).read_bytes())
        export=load('NATIVE_EXPORT.json')
        assert audit_journal(export, root=out/'runtime', manifest=load('MANIFEST.json'))['accepted']
        try:
            success=operator.audit(out)['accepted']
            error=None
        except (ValueError,RuntimeError) as e:
            success=False
            error=str(e)
        return dict(version=version, alteration=mutation, native_changes=edit_count, canonical_financial_replay=True,
                    operator_accepted=success, operator_refusal=error, operator_sha256=digest(operator.source_identity()),
                    native_profit_microUSD=export['ledger']['summary']['profit'],
                    native_collections_microUSD=export['ledger']['summary']['collections'])

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('source',type=Path);p.add_argument('version',choices=['v1','v2','v3'])
    p.add_argument('mutation',choices=['substitution','ghost','budget','deadline','event'])
    p.add_argument('output',type=Path)
    a=p.parse_args()
    data=run(a.source,a.version,a.mutation)
    with a.output.open('x') as f:json.dump(data,f,sort_keys=True,indent=2);f.write('\n')
    print(data)
