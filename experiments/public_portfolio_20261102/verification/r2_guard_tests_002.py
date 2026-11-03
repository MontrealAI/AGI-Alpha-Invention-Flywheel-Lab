from __future__ import annotations
import argparse,hashlib,io,json,time,unittest
from pathlib import Path
import r2_guard_tests as original


class R2GuardTests002(original.R2GuardTests):
    def test_stale_lease_cannot_reuse_private_prefix(self):
        account=self.account();released=False
        try:
            account.cost('first',1000,0);account.account._audit_incremental()
            account.account._account._owner.lease.close();released=True
            with self.assertRaises(ValueError):account.account._audit_incremental()
            self.assertIsNone(account.account._native_prefix._replay)
        finally:
            if released:
                with self.assertRaisesRegex(ValueError,'TAPE_WRITER_LEASE_NOT_OWNED'):account.close()
            else:
                account.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();output=Path(args.output)
    if output.exists():raise ValueError('refuse overwrite of independent R2 guard result')
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(R2GuardTests002);stream=io.StringIO();started=time.time()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    value={'schema':'public-portfolio-r2-independent-guards/v2','checker_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'inherited_checker_sha256':hashlib.sha256(Path(original.__file__).read_bytes()).hexdigest(),
           'amendment_sha256':hashlib.sha256(Path(__file__).with_name('r2_guard_amendment_002.json').read_bytes()).hexdigest(),
           'source_hashes':{name:hashlib.sha256((original.ROOT/name).read_bytes()).hexdigest() for name in ['experiments/public_portfolio_20261102/service.py','commercial/ledger.py','connected_enterprise/finance.py','connected_enterprise/runner.py']},
           'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful(),
           'wall_seconds':time.time()-started,'report':stream.getvalue(),
           'original_result':'r2_guard_results_001.json','original_result_preserved':True,
           'scope':'Only stale-owner fixture cleanup expectation corrected. All14 guard requirements and canonical financial source unchanged; no R1 mutation/migration or business account reset.'}
    output.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');print(json.dumps({k:value[k] for k in ('tests_run','failures','errors','passed','wall_seconds')}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
