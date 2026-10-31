import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from commercial.ledger import digest
from tests.connected_legacy_fixture import materialize

ROOT=Path(__file__).resolve().parents[1]


class CompatibleRecoveryTests(unittest.TestCase):
    def test_public_recovery_uses_unchanged_failed_verifier_and_preserves_live_history(self):
        with tempfile.TemporaryDirectory(prefix='connected022-compatible-recovery-') as temporary:
            case=Path(temporary);old=case/'old';world=case/'business'
            materialize(ROOT,'9c74bc5a8de61167a9c157c9cd2532c4a9b7577d',old)
            code='''import json,sys
from pathlib import Path
from adaptive_enterprise.instruments import prepare_services
from connected_enterprise.engine import run_world,default_config
from connected_enterprise.runner import identity
from connected_enterprise import finance
p=Path(sys.argv[1]);r=Path.cwd();m=prepare_services(r,'service-inputs',cohort_seed=2610312231)
(p/'SERVICES.json').write_text(json.dumps(m));cfg=default_config();cfg.update(horizon_days=2,customer_pool=4)
original=finance.atomic_bytes;captured=[]
def capture(path,raw):
 if str(path).endswith('.operating-checkpoint-intent.json') and not captured:captured.append(raw)
 return original(path,raw)
finance.atomic_bytes=capture
run_world(r,m,cfg,2610312231,'growth',p/'business',source=identity(r),stop_after_events=8)
(p/'business/account.sqlite.operating-checkpoint-intent.json').write_bytes(captured[0])
'''
            done=subprocess.run([sys.executable,'-c',code,str(case)],cwd=old,text=True,capture_output=True,timeout=120)
            self.assertEqual(done.returncode,0,done.stderr)
            intent=world/'account.sqlite.operating-checkpoint-intent.json';saved=intent.read_bytes()
            protected=['STATE.json','account.sqlite.actions.jsonl','account.sqlite.connected-journal.json']
            before={n:(world/n).read_bytes() for n in protected};key=world/'account.sqlite.adaptive-simulation-key';inode=key.stat().st_ino
            args=[sys.executable,'-m','connected_enterprise','recover-checkpoint','--output',str(world),
                  '--historical-source',str(old),'--manifest',str(case/'SERVICES.json'),
                  '--expected-checkpoint',digest(json.loads(before['STATE.json'])),'--id','verified-obsolete']
            invalid=json.loads(saved);invalid['signature']='0'*64;intent.write_text(json.dumps(invalid))
            bad=subprocess.run(args,cwd=ROOT,text=True,capture_output=True,timeout=120)
            self.assertNotEqual(bad.returncode,0);self.assertIn('SIGNATURE_MISMATCH',bad.stderr)
            self.assertEqual({n:(world/n).read_bytes() for n in protected},before)
            intent.write_bytes(saved)
            recovered=subprocess.run(args,cwd=ROOT,text=True,capture_output=True,timeout=120)
            self.assertEqual(recovered.returncode,0,recovered.stderr)
            self.assertTrue(json.loads(recovered.stdout)['account_history_unchanged'])
            reopen='''import json,sys
from pathlib import Path
from connected_enterprise.finance import JournalAccount
p=Path(sys.argv[1]);h=json.loads((p/'account.sqlite.connected-journal.json').read_text())['body']
with JournalAccount(Path.cwd(),json.loads((p.parent/'SERVICES.json').read_text()),p/'account.sqlite',opening=h['opening'],working=h['working'],contract=h['contract']) as a:assert a.audit()['accepted']
'''
            opened=subprocess.run([sys.executable,'-c',reopen,str(world)],cwd=old,text=True,capture_output=True,timeout=120)
            self.assertEqual(opened.returncode,0,opened.stderr);self.assertFalse(intent.exists())
            self.assertEqual({n:(world/n).read_bytes() for n in protected},before);self.assertEqual(key.stat().st_ino,inode)
            self.assertEqual((world/'CHECKPOINT_RECOVERY/verified-obsolete.obsolete-intent.json').read_bytes(),saved)


if __name__=='__main__':unittest.main()
