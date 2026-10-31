import pathlib,tempfile,json,hashlib,unittest,ast
B=pathlib.Path(__file__).resolve().parents[1]
from types import SimpleNamespace
from connected_enterprise.upgrades import AUTHORIZATION_REUSE_HELPER
KNOWN_FINANCE=b'synthetic-known-finance-eligibility-fixture'
_real_hash=hashlib.sha256
def fixture_hash(raw=b''):
 if raw==KNOWN_FINANCE:return SimpleNamespace(hexdigest=lambda:'05b102ee40510b59c7693002251996ade2a03a3c383a885c08cedda54abf619a')
 return _real_hash(raw)
namespace={'Path':pathlib.Path,'hashlib':SimpleNamespace(sha256=fixture_hash)}
exec(AUTHORIZATION_REUSE_HELPER,namespace);snapshot=namespace['clean_authorization_snapshot']

class EligibilityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name);(self.root/'connected_enterprise').mkdir()
  (self.root/'connected_enterprise/finance.py').write_bytes(KNOWN_FINANCE)
  self.path=self.root/'account.sqlite';self.checkpoint={'body':{'synthetic':'not signed evidence'},'signature':'fixture'};self.operating={'prior_checkpoint':self.checkpoint}
  self.path.write_text('synthetic ledger');self.path.with_name(self.path.name+'.actions.jsonl').write_text('synthetic action')
  self.journal=self.path.with_name(self.path.name+'.connected-journal.json');self.journal.write_text(json.dumps({'body':{'entries':[{'status':'COMPLETE'}]},'signature':'fixture'}))
  (self.root/'STATE.json').write_text(json.dumps(self.checkpoint))
 def tearDown(self):self.tmp.cleanup()
 def test_exact_known_clean_unchanged_eligible(self):
  before=snapshot(self.root,self.path,self.operating);self.assertIsNotNone(before);self.assertEqual(before,snapshot(self.root,self.path,self.operating))
 def test_unknown_finance_falls_back(self):
  (self.root/'connected_enterprise/finance.py').write_text('unknown implementation');self.assertIsNone(snapshot(self.root,self.path,self.operating))
 def test_pending_journal_falls_back(self):
  self.journal.write_text(json.dumps({'body':{'entries':[{'status':'PENDING'}]},'signature':'fixture'}));self.assertIsNone(snapshot(self.root,self.path,self.operating))
 def test_operating_intent_falls_back(self):
  self.path.with_name(self.path.name+'.operating-checkpoint-intent.json').write_text('pending');self.assertIsNone(snapshot(self.root,self.path,self.operating))
 def test_changed_journal_is_not_reusable(self):
  before=snapshot(self.root,self.path,self.operating);self.journal.write_text(json.dumps({'body':{'entries':[{'status':'REJECTED'}]},'signature':'changed'}));self.assertNotEqual(before,snapshot(self.root,self.path,self.operating))
 def test_changed_native_or_checkpoint_is_not_reusable(self):
  before=snapshot(self.root,self.path,self.operating);self.path.write_text('different ledger');self.assertNotEqual(before,snapshot(self.root,self.path,self.operating))
  (self.root/'STATE.json').write_text('{}');self.assertIsNone(snapshot(self.root,self.path,self.operating))
 def test_missing_or_symlinked_authority_falls_back(self):
  self.journal.unlink();self.assertIsNone(snapshot(self.root,self.path,self.operating));self.journal.symlink_to(self.root/'STATE.json');self.assertIsNone(snapshot(self.root,self.path,self.operating))
 def test_signing_script_compiles_and_original_checkpoint_path_retained(self):
  tree=ast.parse((B/'connected_enterprise/upgrades.py').read_text());f=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='authorize_upgrade');assign=next(x for x in f.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='code' for t in x.targets));script=AUTHORIZATION_REUSE_HELPER+ast.literal_eval(assign.value.right);compile(script,'owner-authorization','exec')
  self.assertIn('if not reuse:a.audit()',script);self.assertIn("state=a.verify_checkpoint(p['operating']['prior_checkpoint'])",script);self.assertIn('OWNER_AUTHORITY_CHANGED_DURING_AUTHORIZATION',script)

if __name__=='__main__':unittest.main(verbosity=2)
