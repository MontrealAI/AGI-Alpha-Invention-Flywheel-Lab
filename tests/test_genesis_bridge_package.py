import copy,hashlib,importlib.util,json,pathlib,stat,tempfile,unittest,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('bridge_packager',ROOT/'scripts/release_genesis_bridge.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
class PackageTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.root=pathlib.Path(cls.tmp.name);cls.commit='1'*40
  cls.result=p.build(ROOT,cls.root/'assets',cls.commit);cls.archive=cls.root/'assets/genesis-bridge-source.zip'
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def out(self):return self.root/self.id().split('.')[-1]
 def mutate(self,mutator):
  target=self.out().with_suffix('.zip')
  with zipfile.ZipFile(self.archive) as z:rows=[(i,z.read(i.filename)) for i in z.infolist()]
  rows=mutator(rows)
  with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as z:
   for i,b in rows:z.writestr(i,b)
  return target,hashlib.sha256(target.read_bytes()).hexdigest()
 def reject(self,mutator):
  a,h=self.mutate(mutator)
  with self.assertRaises((ValueError,KeyError)):p.extract(a,self.out(),h,self.commit)
 def test_deterministic(self):
  r=p.build(ROOT,self.out(),self.commit);self.assertEqual(r,self.result)
 def test_exact_extract(self):
  m=p.extract(self.archive,self.out(),self.result['archive_sha256'],self.commit)
  self.assertEqual(m['source_commit'],self.commit);self.assertFalse((self.out()/'.git').exists())
 def test_missing_expected_hash(self):
  with self.assertRaises(ValueError):p.extract(self.archive,self.out(),None,self.commit)
 def test_checksum(self):
  with self.assertRaises(ValueError):p.extract(self.archive,self.out(),'0'*64,self.commit)
 def test_commit(self):
  with self.assertRaises(ValueError):p.extract(self.archive,self.out(),self.result['archive_sha256'],'2'*40)
 def test_duplicate(self):self.reject(lambda rows:rows+[rows[0]])
 def test_missing_member(self):self.reject(lambda rows:rows[1:])
 def test_extra_member(self):
  def change(rows):
   i=zipfile.ZipInfo('extra.py');i.external_attr=(stat.S_IFREG|0o644)<<16;return rows+[(i,b'bad')]
  self.reject(change)
 def test_traversal(self):
  def change(rows):rows[0][0].filename='../escape.py';return rows
  self.reject(change)
 def test_symlink_member(self):
  def change(rows):rows[0][0].external_attr=(stat.S_IFLNK|0o777)<<16;return rows
  self.reject(change)
 def test_tampered_source(self):self.reject(lambda rows:[(rows[0][0],rows[0][1]+b'bad')]+rows[1:])
 def test_oversize(self):
  def change(rows):return [(rows[0][0],b'0'*(p.MAX_BYTES+1))]+rows[1:]
  self.reject(change)
 def test_existing_output(self):
  self.out().mkdir()
  with self.assertRaises(FileExistsError):p.extract(self.archive,self.out(),self.result['archive_sha256'],self.commit)
 def test_symlink_output(self):
  self.out().symlink_to(self.root,target_is_directory=True)
  with self.assertRaises(ValueError):p.extract(self.archive,self.out(),self.result['archive_sha256'],self.commit)
if __name__=='__main__':unittest.main()
