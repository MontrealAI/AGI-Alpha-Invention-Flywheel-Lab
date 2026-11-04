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

    def test_genesis_reader_preserves_scope_and_package_links(self):
        import json
        reader = (self.source / 'alpha-genesis-flywheel-omega.html').read_text()
        self.assertIn('alpha-genesis-flywheel-omega.html', (self.source / 'index.html').read_text())
        for phrase in ('Frontier Replay', '68 tests', 'Not established:', '32 pages', 'ALPHA_GENESIS_FLYWHEEL_OMEGA_v1.1.0_SOURCE.zip', 'source/CLAIM_REGISTER.md'):
            self.assertIn(phrase, reader)
        manifest = json.loads((self.source / 'publication-manifest.json').read_text())
        entry = next(p for p in manifest['papers'] if p['file'] == 'alpha-genesis-flywheel-omega.pdf')
        self.assertIn('<code>' + entry['sha256'] + '</code>', reader)

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
        self.assertEqual(len(site.PAPERS), 23)
        self.assertEqual(len(site.PAGES), 25)
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

    def test_flagship_foundation_and_six_new_readers(self):
        import json
        home = (self.source / 'index.html').read_text()
        slugs = ('transformational-intelligence', 'agi-alpha', 'invent-the-economy',
                 'the-world-as-an-output', 'beyond-the-production-frontier', 'beyond-the-original-problem')
        self.assertLess(home.index('Flagship paper'), home.index('Foundational paper'))
        self.assertLess(home.index('Foundational paper'), home.index('out-collection'))
        self.assertNotIn('from exactly US$100,000', home)
        self.assertIn('jointly chosen', home)
        for slug in slugs:
            self.assertIn(slug + '.html', home)
            page = (self.source / (slug + '.html')).read_text()
            self.assertIn('RESEARCH_FOUNDATIONS.md', page)
            self.assertIn('Scope and evidence', page)
            self.assertIn('SHA-256:', page)
            self.assertIn('aria-label="Continue reading"', page)
            self.assertIn('type="application/pdf"', page)
            self.assertIn('download>', page)
        self.assertIn('Learning to Change the Game', (self.source / 'transformational-intelligence.html').read_text())
        self.assertIn('A Scalable Substrate for Intelligence Organizations', (self.source / 'agi-alpha.html').read_text())

    def test_flywheel_synthesis_has_reader_pdf_and_source_links(self):
        import json
        home = (self.source / 'index.html').read_text()
        reader = (self.source / 'agi-alpha-flywheel.html').read_text()
        self.assertIn('agi-alpha-flywheel.html', home)
        self.assertLess(home.index('Foundational paper'), home.index('id="flywheel-synthesis"'))
        parser = site.Links()
        parser.feed(reader)
        self.assertIn('agi-alpha-flywheel-20261102.pdf', parser.links)
        self.assertIn('agi-alpha-flywheel-20261102-v1.1.pdf', parser.links)
        self.assertIn('agi-alpha-flywheel-20261102-v1.1.pdf#view=FitH', parser.links)
        self.assertIn('https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/agi-alpha-flywheel/paper.tex', parser.links)
        self.assertIn('https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/main/docs/agi-alpha-flywheel', parser.links)
        self.assertIn('transformational-intelligence.html', parser.links)
        self.assertIn('agi-alpha.html', parser.links)
        for anchor in ('abstract', 'idea', 'flows', 'study', 'evidence', 'limits', 'read-title', 'reader', 'reproduce'):
            self.assertIn(anchor, parser.ids)
        self.assertIn('Where the evidence ends', reader)
        self.assertIn('SHA-256:', reader)
        self.assertIn('aria-label="Continue reading"', reader)
        manifest = json.loads((self.source / 'publication-manifest.json').read_text())
        paper = next(item for item in manifest['papers'] if item['file'] == 'agi-alpha-flywheel-20261102-v1.1.pdf')
        self.assertIn('<code>' + paper['sha256'] + '</code>', reader)

    def test_experimental_report_has_intact_pdf_source_and_scope(self):
        import json
        name = 'agi-alpha-flywheel-20261102-report.pdf'
        reader = (self.source / 'agi-alpha-flywheel-report-20261102.html').read_text()
        home = (self.source / 'index.html').read_text()
        self.assertIn('agi-alpha-flywheel-report-20261102.html', home)
        parser = site.Links()
        parser.feed(reader)
        self.assertIn(name, parser.links)
        self.assertIn(name + '#view=FitH', parser.links)
        self.assertIn('https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/main/docs/agi-alpha-flywheel-report-20261102', parser.links)
        manifest = json.loads((self.source / 'publication-manifest.json').read_text())
        entry = next(p for p in manifest['papers'] if p['file'] == name)
        self.assertIn('<code>' + entry['sha256'] + '</code>', reader)
        for text in ('110', '23 accounts', 'Scope and evidence', 'conventional', 'not a new full replay', '22 pages'):
            self.assertIn(text, reader)

    def test_unresolved_publication_metadata_is_rejected(self):
        page = self.source / 'agi-alpha-flywheel.html'
        page.write_text(page.read_text() + '<p>PAPER_SHA256_PLACEHOLDER</p>')
        with self.assertRaisesRegex(ValueError, 'Unresolved publication metadata'):
            site.validate(self.source)

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
