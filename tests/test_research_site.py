import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('research_site', ROOT / 'scripts/build_research_site.py')
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


class ResearchSiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        for name in site.FILES:
            shutil.copyfile(ROOT / 'docs/research' / name, self.source / name)

    def test_build_is_allowlisted_and_preserves_bytes(self):
        (self.source / 'private-account.json').write_text('not for publication')
        out = site.build(self.source, self.root / 'site')
        self.assertEqual({p.name for p in out.iterdir()}, set(site.FILES) | {'.nojekyll'})
        for name in site.FILES:
            self.assertEqual((self.source / name).read_bytes(), (out / name).read_bytes())

    def test_changed_pdf_is_rejected(self):
        with (self.source / site.PAPERS[0]).open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            site.validate(self.source)

    def test_symlink_is_rejected(self):
        p = self.source / site.PAPERS[0]
        p.unlink()
        p.symlink_to(ROOT / 'docs/research' / site.PAPERS[0])
        with self.assertRaisesRegex(ValueError, 'regular'):
            site.validate(self.source)

    def test_existing_output_is_not_deleted(self):
        out = self.root / 'existing'
        out.mkdir()
        (out / 'keep').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'new directory'):
            site.build(self.source, out)
        self.assertEqual((out / 'keep').read_text(), 'keep')

    def test_broken_link_is_rejected(self):
        with (self.source / 'index.html').open('a') as stream:
            stream.write('<a href="../private.json">invalid</a>')
        with self.assertRaisesRegex(ValueError, 'outside publication'):
            site.validate(self.source)

    def test_mobile_and_pdf_fallbacks_present(self):
        text = (self.source / 'foundry-v2.html').read_text()
        self.assertIn('name="viewport"', text)
        self.assertIn('type="application/pdf"', text)
        self.assertIn('download>', text)
        self.assertIn('Skip to content', text)
        self.assertIn('Your browser does not display embedded PDFs', text)


if __name__ == '__main__':
    unittest.main()
