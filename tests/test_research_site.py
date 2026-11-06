import hashlib
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

    def test_genesis_stable_reader_features_v2_and_preserves_prior_access(self):
        import json
        reader = (self.source / 'alpha-genesis-flywheel-omega.html').read_text()
        self.assertIn('alpha-genesis-flywheel-omega.html', (self.source / 'index.html').read_text())
        for phrase in ('Research edition 2.0', '31-page', 'Three Orders of Intelligence',
                       'historical-source', 'does not rerun the native accounts',
                       'id="reader"', 'id="previous-edition"', 'Previous edition 1.1.0',
                       'Frontier Replay', '68-test', '32 pages',
                       'ALPHA_GENESIS_FLYWHEEL_OMEGA_v2_COMPLETE.zip',
                       'ALPHA_GENESIS_FLYWHEEL_OMEGA_v1.1.0_SOURCE.zip', 'source/CLAIM_REGISTER.md'):
            self.assertIn(phrase, reader)
        manifest = json.loads((self.source / 'publication-manifest.json').read_text())
        for filename in ('alpha-genesis-flywheel-omega-v2.pdf', 'alpha-genesis-flywheel-omega.pdf'):
            entry = next(p for p in manifest['papers'] if p['file'] == filename)
            self.assertIn('<code>' + entry['sha256'] + '</code>', reader)
        self.assertIn('name="citation_pdf_url" content="https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/alpha-genesis-flywheel-omega-v2.pdf"', reader)
        self.assertIn('data="alpha-genesis-flywheel-omega-v2.pdf#view=FitH"', reader)
        self.assertNotIn('data="alpha-genesis-flywheel-omega.pdf#view=FitH"', reader)
        self.assertLess(reader.index('id="reader"'), reader.index('id="previous-edition"'))
        self.assertIn('href="#previous-edition"', reader)
        parser = site.Links()
        parser.feed(reader)
        self.assertTrue({'proposition', 'replay', 'product', 'scope', 'reproduce',
                         'reader'}.issubset(parser.ids))
        for filename in ('index.html', 'alpha-genesis-flywheel-omega-v2.html'):
            self.assertIn('href="alpha-genesis-flywheel-omega.html#previous-edition"',
                          (self.source / filename).read_text())

    def test_genesis_v2_preserves_prior_edition_and_evidence_scope(self):
        import json
        page = (self.source / 'alpha-genesis-flywheel-omega-v2.html').read_text()
        home = (self.source / 'index.html').read_text()
        for phrase in ('31-page', 'Three Orders of Intelligence', 'historical-source', 'does not rerun the native accounts', 'alpha-genesis-flywheel-omega.html', 'ALPHA_GENESIS_FLYWHEEL_OMEGA_v2_COMPLETE.zip'):
            self.assertIn(phrase, page)
        self.assertLess(home.index('id="alpha-genesis-v2"'), home.index('id="alpha-genesis"'))
        entry = next(p for p in json.loads((self.source / 'publication-manifest.json').read_text())['papers'] if p['file'] == 'alpha-genesis-flywheel-omega-v2.pdf')
        self.assertIn(entry['sha256'], page)
        self.assertEqual(entry['sha256'], '4bd6400c247b5fea0d336e2cba11e69890b0596e24ebd51931ada257fe78414f')

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
        self.assertEqual(len(site.PAPERS), 27)
        self.assertEqual(len(site.PAGES), 31)
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
        self.assertIn('<h1 id="hero-title">🌌♾️ ALPHA GENESIS', home)
        self.assertIn('href="alpha-genesis-flywheel-omega-v2.html">Read the flagship paper', home)
        self.assertLess(home.index('id="alpha-genesis"'), home.index('Conceptual foundation'))
        self.assertLess(home.index('Conceptual foundation'), home.index('Foundational paper'))
        self.assertIn('Flagship programme &amp; paper', home)
        self.assertIn('Self-sustaining discovery, improved successors and actual commercial revenue remain to be demonstrated.', home)
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
        original = page.read_text()
        for token in ('PAPER_SHA256_PLACEHOLDER', 'SURF_PAGE_COUNT', 'SURF_SHA256', 'SURF_PDF_BYTES', 'CONTINUITY_PAGE_COUNT', 'CONTINUITY_SHA256', 'CONTINUITY_PDF_BYTES', 'CONTINUITY_EN_PAGE_COUNT', 'CONTINUITY_EN_SHA256', 'CONTINUITY_EN_PDF_BYTES', 'CONTINUITY_FR_PAGE_COUNT', 'CONTINUITY_FR_SHA256', 'CONTINUITY_FR_PDF_BYTES'):
            with self.subTest(token=token):
                page.write_text(original + '<p>' + token + '</p>')
                with self.assertRaisesRegex(ValueError, 'Unresolved publication metadata'):
                    site.validate(self.source)
        page.write_text(original)

    def test_continuity_reader_matches_pdf_scope_and_preserves_flagship(self):
        import json
        reader = (self.source / 'continuity-omega.html').read_text()
        home = (self.source / 'index.html').read_text()
        manifest = json.loads((self.source / 'publication-manifest.json').read_text())
        entry = next(p for p in manifest['papers'] if p['file'] == 'continuity-omega.pdf')
        pdf = (self.source / entry['file']).read_bytes()
        self.assertEqual(entry['sha256'], hashlib.sha256(pdf).hexdigest())
        self.assertEqual(entry['bytes'], len(pdf))
        self.assertIn('<code>' + entry['sha256'] + '</code>', reader)
        self.assertIn(str(entry['bytes']) + ' bytes', reader)
        parser = site.Links()
        parser.feed(reader)
        for link in ('continuity-omega.pdf', 'continuity-omega.pdf#view=FitH',
                     'transformational-intelligence.html', 'alpha-genesis-flywheel-omega-v2.html',
                     'invent-the-economy.html',
                     'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/tree/main/docs/continuity-omega-paper',
                     'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/continuity-omega-paper/evidence/REPRODUCTION.json',
                     'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/continuity-omega-paper/REVIEW.md'):
            self.assertIn(link, parser.links)
        self.assertEqual(parser.canonical_urls, [site.PUBLIC_SITE + 'continuity-omega.html'])
        self.assertIn('name="citation_pdf_url" content="' + site.PUBLIC_SITE + 'continuity-omega.pdf"', reader)
        for phrase in ('29 + 9', 'not a statistical sample of real incidents',
                       'Competent conventional reconciliation', 'What remains unestablished:',
                       'No feasible pool.'):
            self.assertIn(phrase, reader)
        self.assertTrue({'idea', 'first-service', 'pooling', 'evidence', 'reader'}.issubset(parser.ids))
        self.assertLess(home.index('id="alpha-genesis-v2"'), home.index('id="alpha-genesis"'))
        self.assertLess(home.index('id="alpha-genesis"'), home.index('id="continuity-omega"'))
        self.assertLess(home.index('id="continuity-omega"'), home.index('id="surf-the-exponential"'))
        self.assertIn('href="continuity-omega.html"', home)
        self.assertIn('href="continuity-omega.pdf"', home)
        for asset in ('continuity-omega-social.png', 'continuity-omega-card.svg'):
            self.assertIn(asset, site.ASSETS)
        self.assertIn('property="og:image" content="' + site.PUBLIC_SITE + 'continuity-omega-social.png"', reader)
        self.assertIn('name="twitter:card" content="summary_large_image"', reader)

    def test_continuity_languages_preserve_sources_controls_and_reciprocal_access(self):
        """Localization must retain the same evidence, computation and direct access."""
        import json
        import re
        manifest = json.loads((self.source / 'publication-manifest.json').read_text())
        expected_alternates = {
            ('en', site.PUBLIC_SITE + 'continuity-omega.html'),
            ('fr-CA', site.PUBLIC_SITE + 'continuity-omega-fr.html'),
            ('x-default', site.PUBLIC_SITE + 'continuity-omega.html'),
        }
        controls, scripts, anchors = [], [], []
        home = (self.source / 'index.html').read_text()
        for lang, slug, other, og_locale, unit in (
                ('en', 'continuity-omega', 'continuity-omega-fr', 'en_US', 'bytes'),
                ('fr-CA', 'continuity-omega-fr', 'continuity-omega', 'fr_CA', 'octets')):
            with self.subTest(language=lang):
                reader = (self.source / (slug + '.html')).read_text()
                parser = site.Links()
                parser.feed(reader)
                entry = next(p for p in manifest['papers'] if p['file'] == slug + '.pdf')
                self.assertIn('<html lang="' + lang + '">', reader)
                self.assertEqual(parser.canonical_urls, [site.PUBLIC_SITE + slug + '.html'])
                self.assertEqual(set(parser.alternate_urls), expected_alternates)
                self.assertIn('name="citation_language" content="' + lang + '"', reader)
                self.assertIn('property="og:locale" content="' + og_locale + '"', reader)
                self.assertIn('property="og:locale:alternate"', reader)
                self.assertIn('name="twitter:image:alt"', reader)
                self.assertIn('property="og:image:alt"', reader)
                self.assertIn('href="' + other + '.html"', reader)
                self.assertIn('data-language-switch="' + other + '.html"', reader)
                self.assertIn('href="' + slug + '.html"', home)
                for link in (slug + '.pdf', slug + '.pdf#view=FitH',
                             slug + '-card.svg', slug + '-social.png'):
                    self.assertIn(link, parser.links)
                self.assertIn('<code>' + entry['sha256'] + '</code>', reader)
                self.assertIn(str(entry['bytes']) + ' ' + unit, reader)
                self.assertIn('29 + 9', reader)
                self.assertIn('4 / 4', reader)
                self.assertIn('1.1.0', reader)
                self.assertIn('releases/tag/continuity-omega-v1.0.0', reader)
                suffix = '.fr' if lang == 'fr-CA' else ''
                for file in ('README' + suffix + '.md', 'REVIEW' + suffix + '.md',
                             'SOURCE_MAP' + suffix + '.md', 'CLAIMS' + suffix + '.json'):
                    self.assertIn('docs/continuity-omega-paper/' + file, reader)
                self.assertIn('https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/continuity-omega-paper/CITATION' + suffix + '.cff', parser.links)
                structured = json.loads(re.search(
                    r'<script type="application/ld\+json">(.*?)</script>', reader, re.S).group(1))
                self.assertEqual(structured['inLanguage'], lang)
                self.assertEqual(structured['version'], '1.1.0')
                self.assertEqual(structured['encoding']['contentUrl'], site.PUBLIC_SITE + slug + '.pdf')
                fields = ('id', 'name', 'type', 'min', 'max', 'step', 'value')
                inputs = [dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
                          for tag in re.findall(r'<input\b[^>]*>', reader)]
                controls.append([tuple(item.get(key) for key in fields) for item in inputs])
                scripts.append(re.search(r'<script>(.*?)</script>', reader, re.S).group(1))
                anchors.append(parser.ids)
        self.assertEqual(controls[0], controls[1])
        self.assertEqual(scripts[0], scripts[1])
        self.assertEqual(anchors[0], anchors[1])
        self.assertNotIn('navigator.language', scripts[0])
        french = (self.source / 'continuity-omega-fr.html').read_text()
        for phrase in ('Tenir parole.', 'Aucun groupe viable.', '3 acheteurs',
                       'Ce qui reste non établi', 'ne constitue', 'Aller au contenu',
                       'Votre navigateur n’affiche pas les PDF intégrés.'):
            self.assertIn(phrase, french)
        # Language alternates cannot become an exception for arbitrary external URLs.
        page = self.source / 'continuity-omega-fr.html'
        page.write_text(french.replace(
            'hreflang="en" href="' + site.PUBLIC_SITE + 'continuity-omega.html"',
            'hreflang="en" href="https://example.com/unpublished"'))
        with self.assertRaisesRegex(ValueError, 'Alternate language URL'):
            site.validate(self.source)
        page.write_text(french)
        media_manifest = json.loads((self.source / 'continuity-omega-media-manifest.json').read_text())
        gallery_scripts, gallery_ids = [], []
        for lang, suffix, locale, scope in (
                ('en', '', 'en', 'conceptual marketing illustrations'),
                ('fr-CA', '-fr', 'fr', 'illustrations conceptuelles de communication')):
            with self.subTest(gallery_language=lang):
                name = 'continuity-omega-media' + suffix + '.html'
                gallery = (self.source / name).read_text()
                parser = site.Links()
                parser.feed(gallery)
                self.assertIn('<html lang="' + lang + '">', gallery)
                self.assertEqual(parser.canonical_urls, [site.PUBLIC_SITE + name])
                self.assertEqual(set(parser.alternate_urls), {
                    ('en', site.PUBLIC_SITE + 'continuity-omega-media.html'),
                    ('fr-CA', site.PUBLIC_SITE + 'continuity-omega-media-fr.html'),
                    ('x-default', site.PUBLIC_SITE + 'continuity-omega-media.html'),
                })
                self.assertIn(scope, gallery)
                self.assertEqual(gallery.count('<details>'), 4)
                self.assertEqual(gallery.count('data-animation-control='), 4)
                self.assertNotRegex(gallery, r'<img\b[^>]*\bsrc="[^"]+\.gif"')
                for scene in ('ascent', 'reveal', 'journey', 'motion'):
                    media_entry = next(item for item in media_manifest['animations'] if item['id'] == scene)
                    for ending in ('.gif', '-poster.png'):
                        asset = f'continuity-omega-{scene}-{locale}{ending}'
                        self.assertIn(asset, parser.links)
                        self.assertIn(asset, site.ASSETS)
                        contents = (self.source / asset).read_bytes()
                        self.assertEqual(len(contents), media_entry['files'][asset]['bytes'])
                        self.assertEqual(hashlib.sha256(contents).hexdigest(), media_entry['files'][asset]['sha256'])
                    self.assertEqual(media_entry['english_original_sha256'],
                                     media_entry['files'][f'continuity-omega-{scene}-en.gif']['sha256'])
                    gif = (self.source / f'continuity-omega-{scene}-{locale}.gif').read_bytes()
                    self.assertIn(gif[:6], (b'GIF87a', b'GIF89a'))
                gallery_ids.append(parser.ids)
                gallery_scripts.append(re.search(r'<script>(.*?)</script>', gallery, re.S).group(1))
                self.assertIn('href="' + name + '"', (self.source / ('continuity-omega' + suffix + '.html')).read_text())
        self.assertEqual(gallery_ids[0], gallery_ids[1])
        self.assertEqual(gallery_scripts[0], gallery_scripts[1])

    def test_surf_reader_matches_published_pdf_and_preserves_flagship(self):
        import json
        reader = (self.source / 'surf-the-exponential.html').read_text()
        home = (self.source / 'index.html').read_text()
        manifest = json.loads((self.source / 'publication-manifest.json').read_text())
        entry = next(p for p in manifest['papers'] if p['file'] == 'surf-the-exponential.pdf')
        self.assertEqual(entry['sha256'], '90d57364e265744c443a18349d0abc35fff37eac2896ca98198eed695dda8fe9')
        self.assertEqual(entry['bytes'], 297488)
        self.assertIn('<code>' + entry['sha256'] + '</code>', reader)
        self.assertIn(str(entry['bytes']) + ' bytes', reader)
        self.assertIn('32 pages', reader)
        parser = site.Links()
        parser.feed(reader)
        for link in ('surf-the-exponential.pdf', 'surf-the-exponential.pdf#view=FitH',
                     'transformational-intelligence.html', 'alpha-genesis-flywheel-omega-v2.html',
                     'invent-the-economy.html',
                     'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/surf-the-exponential/paper.tex',
                     'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/surf-the-exponential/README.md',
                     'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/surf-the-exponential/evidence/results.json',
                     'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/surf-the-exponential/evidence/construct_results.json'):
            self.assertIn(link, parser.links)
        self.assertIn('name="citation_pdf_url" content="https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/surf-the-exponential.pdf"', reader)
        self.assertIn('Measured improvement from this architecture using frontier LLMs on fresh, independent campaigns.', reader)
        self.assertIn('Actual customer acceptance, collected revenue, and sustained commercial profitability.', reader)
        self.assertLess(home.index('id="alpha-genesis-v2"'), home.index('id="surf-the-exponential"'))
        self.assertLess(home.index('id="alpha-genesis"'), home.index('id="surf-the-exponential"'))
        self.assertIn('href="surf-the-exponential.html"', home)
        self.assertEqual(parser.canonical_urls, [site.PUBLIC_SITE + 'surf-the-exponential.html'])
        for asset in ('surf-the-exponential-social.png', 'surf-the-exponential-card.svg'):
            self.assertIn(asset, site.ASSETS)
            self.assertIn(asset, parser.links)
        self.assertIn('name="twitter:card" content="summary_large_image"', reader)

    def test_canonical_url_must_name_the_same_published_page(self):
        page = self.source / 'surf-the-exponential.html'
        original = page.read_text()
        expected = 'rel="canonical" href="' + site.PUBLIC_SITE + page.name + '"'
        for target in ('https://example.com/tracker', site.PUBLIC_SITE + 'index.html',
                       site.PUBLIC_SITE + page.name + '?tracking=1'):
            with self.subTest(target=target):
                page.write_text(original.replace(expected, 'rel="canonical" href="' + target + '"'))
                with self.assertRaisesRegex(ValueError, 'Canonical URL'):
                    site.validate(self.source)
        page.write_text(original)

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
            french = name in ('continuity-omega-fr.html', 'continuity-omega-media-fr.html')
            self.assertIn('Aller au contenu' if french else 'Skip to content', text)
            styles = text if name != 'studio.html' else (self.source / 'alpha.css').read_text()
            self.assertIn('prefers-reduced-motion', styles)
            self.assertIn('@media(max-width:', styles)
            self.assertNotIn('↗', text)
            if name not in ('index.html', 'out-series.html', 'studio.html', 'continuity-omega-media.html', 'continuity-omega-media-fr.html'):
                self.assertIn('type="application/pdf"', text)
                self.assertIn('download>', text)
                self.assertIn('Votre navigateur n’affiche pas les PDF intégrés' if french else 'Your browser does not display embedded PDFs', text)

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
        self.assertIn('GENESIS construction programme / Blue Sky evidence', home)
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
