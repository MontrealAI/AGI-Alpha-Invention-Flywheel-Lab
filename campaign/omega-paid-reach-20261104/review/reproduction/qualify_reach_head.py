"""Exact-source targeted qualification for the registered native reach study."""
import argparse, faulthandler, hashlib, json, os, pathlib, subprocess, sys, time, unittest
P=pathlib.Path
arg=argparse.ArgumentParser()
arg.add_argument('--source',required=True,type=P);arg.add_argument('--commit',required=True)
arg.add_argument('--out',required=True,type=P)
op=arg.parse_args(); root=op.source.resolve(); out=op.out.resolve(); out.mkdir(parents=True,exist_ok=False)
def write(name,obj):
    t=out/(name+'.tmp');t.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n');t.replace(out/name)
def clean():
    return not subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=root,text=True).strip()
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==op.commit and clean()
sys.path.insert(0,str(root));os.chdir(root)
from mechanism_harness.reach_native import source_identity
from commercial.ledger import digest
original=source_identity(); assert original['campaign/omega-paid-reach-20261104/PROTOCOL.md']=='2b6eef4a9535f6f626e2ca88fcc432c672f1b9cc45ec5bef868e3378d38f5277'
loader=unittest.defaultTestLoader
suite=unittest.TestSuite([loader.discover(str(root/'tests'),pattern='test_omega*.py'),loader.loadTestsFromNames([
    'tests.test_connected_platform_runtime064','tests.test_compact_failure_export031',
    'tests.test_connected_omega_release','tests.test_connected_release','tests.test_connected_reach_release',
    'tests.test_connected_channels','mechanism_harness.test_game_maker',
    'tests.test_connected_cooperation044.Cooperation044Tests.test_positive_profit_without_earned_liquidity_cannot_fund'])])
def ids(s):
    for t in s:
        if isinstance(t,unittest.TestSuite):yield from ids(t)
        else:yield t.id()
names=list(ids(suite)); assert len(names)==len(set(names)) and len(names)>300
write('MANIFEST.json',{'source_commit':op.commit,'test_ids':names,'native_source':original})
started=time.monotonic()
class Progress(unittest.TextTestResult):
    def startTest(self,test):
        write('PROGRESS.json',{'test':test.id(),'started':self.testsRun+1,'elapsed':time.monotonic()-started})
        faulthandler.cancel_dump_traceback_later();faulthandler.dump_traceback_later(120,repeat=True)
        super().startTest(test)
with (out/'TESTS.log').open('x',buffering=1) as log:
    result=unittest.TextTestRunner(stream=log,verbosity=2,resultclass=Progress).run(suite)
faulthandler.cancel_dump_traceback_later()
unchanged=clean() and source_identity()==original
receipt={'source_commit':op.commit,'tests':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),
         'skipped':len(result.skipped),'native_source_files':len(original),'native_source_sha256':digest(original),
         'source_unchanged':unchanged,'elapsed_seconds':time.monotonic()-started,
         'tests_log_sha256':hashlib.sha256((out/'TESTS.log').read_bytes()).hexdigest(),
         'accepted':unchanged and result.wasSuccessful() and not result.skipped and result.testsRun==len(names)}
write('COMPLETION.json',receipt); print(json.dumps(receipt),flush=True);sys.exit(not receipt['accepted'])
