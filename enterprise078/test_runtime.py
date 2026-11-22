import hashlib,json,tempfile,unittest
from pathlib import Path
from .runtime import materialize,OVERRIDES,EXPECTED_FREEZE

ROOT=Path(__file__).resolve().parents[1]
class IsolatedRuntimeTests(unittest.TestCase):
 def test_isolation_uses_original_native_bytes_and_preserves_current_runtime(self):
  before={n:(ROOT/n).read_bytes() for n in OVERRIDES}
  with tempfile.TemporaryDirectory() as t:
   stage=materialize(ROOT,Path(t)/'science');frozen=json.loads((ROOT/'enterprise078/FROZEN.json').read_text())
   self.assertEqual(len(frozen['files']),306)
   for n,h in frozen['files'].items(): self.assertEqual(hashlib.sha256((stage/n).read_bytes()).hexdigest(),h)
   for n in OVERRIDES:
    self.assertNotEqual((stage/n).read_bytes(),before[n])
    self.assertEqual((ROOT/n).read_bytes(),before[n])
 def test_existing_directory_is_not_overwritten(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t);(p/'owned').write_text('retain')
   with self.assertRaisesRegex(ValueError,'NEW_SCIENTIFIC_DIRECTORY_REQUIRED'): materialize(ROOT,p)
   self.assertEqual((p/'owned').read_text(),'retain')
 def test_substituted_source_inventory_is_refused_before_creation(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'enterprise078').mkdir()
   (root/'enterprise078/FROZEN.json').write_text(json.dumps({'sha256':EXPECTED_FREEZE,'files':{}}))
   with self.assertRaisesRegex(ValueError,'ORIGINAL_306_FILE_FREEZE_REQUIRED'): materialize(root,root/'stage')
   self.assertFalse((root/'stage').exists())
if __name__=='__main__': unittest.main()
