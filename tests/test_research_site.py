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

    def test_out_collection_links_every_reader_and_original(self):
        slugs = ('learn', 'think', 'design', 'strategise', 'execute', 'evolve')
        collection = (self.source / 'out-series.html').read_text()
        homepage = (self.source / 'index.html').read_text()
        self.assertEqual(len(site.PAPERS), 9)
        self.assertEqual(len(site.PAGES), 12)
        self.assertIn('out-series.html', homepage)
        for slug in slugs:
            reader = 'out-' + slug + '.html'
            self.assertIn(reader, collection)
            self.assertIn(reader, homepage)
            text = (self.source / reader).read_text()
            self.assertIn('When to reach for this paper', text)
            self.assertIn('Scope and evidence', text)
            self.assertIn('OUT_PAPERS.md', text)
            self.assertIn('SHA-256:', text)
            self.assertIn('aria-label="Continue reading"', text)
            matches = [x for x in site.PAPERS if x.startswith('out-' + slug + '-')]
            self.assertEqual(len(matches), 1)
            self.assertIn('data="' + matches[0] + '#view=FitH"', text)

    def test_manifest_cannot_repeat_or_omit_a_paper(self):
        import json
        path = self.source / 'publication-manifest.json'
        manifest = json.loads(path.read_text())
        manifest['papers'][-1] = manifest['papers'][0]
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'allowlisted'):
            site.validate(self.source)

    def test_mobile_and_pdf_fallbacks_present(self):
        for name in site.PAGES:
            text = (self.source / name).read_text()
            self.assertIn('name="viewport"', text)
            self.assertIn('Skip to content', text)
            styles = text if name != 'studio.html' else (self.source / 'alpha.css').read_text()
            self.assertIn('prefers-reduced-motion', styles)
            self.assertIn('@media(max-width:', styles)
            self.assertNotIn('↗', text)
            if name not in ('index.html', 'out-series.html', 'studio.html'):
                self.assertIn('type="application/pdf"', text)
                self.assertIn('download>', text)
                self.assertIn('Your browser does not display embedded PDFs', text)

    def test_preferred_home_design_keeps_studio_and_published_anchors(self):
        home = (self.source / 'index.html').read_text()
        studio = (self.source / 'studio.html').read_text()
        self.assertIn('background:#f7f6fb', home)
        self.assertIn('studio.html#build', home)
        for anchor in ('build', 'evidence', 'research', 'papers'):
            self.assertIn('id="' + anchor + '"', home)
        self.assertIn('src="alpha.js"', studio)
        self.assertIn('href="index.html"', studio)
        self.assertIn('id="dispatch-form"', studio)
        for name in ('foundry-v2.html', 'transformational-enterprises.html', 'out-reflect.html'):
            self.assertIn(name, home)
        self.assertIn('docs/transformational063/REPORT.md', home)
        self.assertIn('docs/transformational063/paper.pdf', home)
        self.assertIn('campaign/transformational-063', home)

    def test_blue_sky_primary_preserves_conventional_history_separately(self):
        home = (self.source / 'index.html').read_text()
        studio = (self.source / 'studio.html').read_text()
        self.assertIn('id="frontier"', home)
        self.assertIn('Blue Sky flagship', home)
        self.assertNotIn('id="dispatch-form"', home)
        self.assertNotIn('src="alpha.js"', home)
        self.assertIn('Historical experiment / 063', home)
        self.assertIn('Historical research / Experiment 063', studio)
        self.assertIn('BLUE SKY: NOT_ESTABLISHED', studio)
        self.assertNotIn('research-history.html', home)

    def test_external_script_and_unknown_asset_are_rejected(self):
        for link in ('https://example.com/tracker.js', 'account-recovery.json'):
            with self.subTest(link=link):
                page = self.source / 'index.html'
                original = page.read_text()
                page.write_text(original + f'<script src="{link}"></script>')
                with self.assertRaises(ValueError):
                    site.validate(self.source)
                page.write_text(original)

    def test_allowlisted_interactive_assets_are_required_regular_files(self):
        asset = self.source / 'alpha.js'
        asset.unlink()
        with self.assertRaisesRegex(ValueError, 'regular'):
            site.validate(self.source)



if __name__ == '__main__':
    unittest.main()
