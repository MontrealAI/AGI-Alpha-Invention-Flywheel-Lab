import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import release_tools as r

class PublicationIntegrity(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def manifest(self,text):(self.root/'SHA256SUMS').write_text(text,encoding='utf-8')
    def test_empty_manifest_rejected(self):
        self.manifest('')
        with self.assertRaises(ValueError):r.read_manifest(self.root)
    def test_bad_hash_rejected(self):
        self.manifest('not-a-hash  README.md\n')
        with self.assertRaises(ValueError):r.read_manifest(self.root)
    def test_duplicate_path_rejected(self):
        line='0'*64+'  README.md\n';self.manifest(line+line)
        with self.assertRaises(ValueError):r.read_manifest(self.root)
    def test_traversal_rejected(self):
        self.manifest('0'*64+'  ../outside\n')
        with self.assertRaises(ValueError):r.read_manifest(self.root)
    def test_absolute_path_rejected(self):
        self.manifest('0'*64+'  /tmp/outside\n')
        with self.assertRaises(ValueError):r.read_manifest(self.root)
    def test_windows_path_rejected(self):
        self.manifest('0'*64+'  C:\\outside\n')
        with self.assertRaises(ValueError):r.read_manifest(self.root)
    def test_noncanonical_path_rejected(self):
        self.manifest('0'*64+'  ./README.md\n')
        with self.assertRaises(ValueError):r.read_manifest(self.root)
    def test_source_symlink_rejected(self):
        (self.root/'link').symlink_to(self.root/'missing')
        with self.assertRaises(ValueError):r.source_files(self.root)
    def test_missing_required_files_rejected(self):
        self.manifest('0'*64+'  README.md\n')
        with self.assertRaises(ValueError):r.verify_manifest(self.root)
    def test_valid_and_tampered_inventory(self):
        for name in r.REQUIRED:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
        self.manifest(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+name+'\n' for name,p in sorted(r.source_files(self.root).items())))
        self.assertEqual(r.verify_manifest(self.root),len(r.REQUIRED))
        (self.root/'README.md').write_text('altered')
        with self.assertRaises(ValueError):r.verify_manifest(self.root)
    def test_extra_file_rejected(self):
        for name in r.REQUIRED:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
        self.manifest(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+name+'\n' for name,p in sorted(r.source_files(self.root).items())))
        (self.root/'unexpected.py').write_text('print(1)')
        with self.assertRaises(ValueError):r.verify_manifest(self.root)
    def test_valid_local_link_and_anchor(self):
        (self.root/'index.html').write_text('<a href="README.md">Read</a><a href="#x">X</a><div id="x"></div>')
        (self.root/'README.md').write_text('read')
        self.assertEqual(r.check_html_links(self.root),2)
    def test_missing_local_link_rejected(self):
        (self.root/'index.html').write_text('<a href="missing.pdf">Read</a>')
        with self.assertRaises(ValueError):r.check_html_links(self.root)
    def test_missing_anchor_rejected(self):
        (self.root/'index.html').write_text('<a href="#missing">Read</a>')
        with self.assertRaises(ValueError):r.check_html_links(self.root)
    def test_javascript_link_rejected(self):
        (self.root/'index.html').write_text('<a href="javascript:alert(1)">Read</a>')
        with self.assertRaises(ValueError):r.check_html_links(self.root)
    def test_inline_script_rejected(self):
        (self.root/'index.html').write_text('<script>alert(1)</script>')
        with self.assertRaises(ValueError):r.check_html_links(self.root)

if __name__=='__main__':unittest.main()
