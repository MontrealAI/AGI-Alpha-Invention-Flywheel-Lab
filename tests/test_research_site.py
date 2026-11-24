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
        for name in (*site.FILES, site.POSSIBILITY_INPUT):
            (self.source / name).parent.mkdir(exist_ok=True, parents=True)
            shutil.copyfile(ROOT / 'docs/research' / name, self.source / name)

    def test_build_is_allowlisted_and_preserves_bytes(self):
        (self.source / 'private-account.json').write_text('not for publication')
        out = site.build(self.source, self.root / 'site')
        self.assertEqual({p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}, set(site.FILES) | {'.nojekyll'})
        for name in site.FILES:
            if name in site.POSSIBILITY_PAGES:
                self.assertEqual(site.render_possibility_page((self.source / name).read_text(), name,
                                                            site.read_possibilities(self.source)), (out / name).read_text())
            else:
                self.assertEqual((self.source / name).read_bytes(), (out / name).read_bytes())

    def test_possibility_feed_rejects_invalid_content_without_staging(self):
        import json
        path = self.source / site.POSSIBILITY_INPUT
        original = path.read_text()
        for reason in ('unknown field', 'text injection', 'link injection', 'private URL', 'duplicate ID', 'future label'):
            with self.subTest(reason=reason):
                data = json.loads(original)
                record = data['records'][0]
                if reason == 'unknown field':
                    record['automation_id'] = 'not public'
                elif reason == 'text injection':
                    record['en']['title'] = '<script>nothing</script>'
                elif reason == 'link injection':
                    record['sources'][0]['url'] = 'https://arxiv.org@localhost/abs/2611.23751'
                elif reason == 'private URL':
                    record['fr']['next'] = 'https://chatgpt.com/c/private'
                elif reason == 'duplicate ID':
                    data['records'].append(record)
                else:
                    record['evidence'] = 'verified'
                path.write_text(json.dumps(data))
                destination = self.root / 'rejected'
                with self.assertRaises(ValueError):
                    site.build(self.source, destination)
                self.assertFalse(destination.exists())

    def test_verified_invention_watch_requires_distinct_evidence_and_pinned_commit(self):
        import json
        path = self.source / site.POSSIBILITY_INPUT
        data = json.loads(path.read_text())
        row = data['records'][0]
        data['records'] = [row]
        ordinary = [{'url':'https://arxiv.org/abs/2611.21152',
                     'en':'External preprint', 'fr':'Prépublication externe'}]
        row.update(watch='living-watch', evidence='author-reported', sources=ordinary)
        row['assessment']['state'] = 'discovered'
        path.write_text(json.dumps(data))
        for name in site.POSSIBILITY_PAGES:
            page = (self.source / name).read_text()
            rendered = site.render_possibility_page(page, name, site.read_possibilities(self.source))
            self.assertIn('Rapporté par les auteurs' if name.endswith('/fr.html') else 'Author-reported', rendered)
            self.assertIn('data-state="discovered"', rendered)
        for watch, evidence, sources in (
            ('living-watch', 'verified-result', ordinary),
            ('verified-invention-watch', 'author-reported', ordinary),
            ('verified-invention-watch', 'falsified', ordinary),
            ('verified-invention-watch', 'verified-result', [
                {'url':'https://github.com/ThirdParty/Project/commit/' + 'a' * 40,
                 'en':'Public commit', 'fr':'Révision publique'}
            ]),
        ):
            with self.subTest(watch=watch, evidence=evidence):
                row.update(watch=watch, evidence=evidence, sources=sources)
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    site.read_possibilities(self.source)
        row['sources'] = [
            {'url':'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/' + 'a' * 40,
             'en':'Pinned evidence', 'fr':'Preuve figée'}
        ]
        for ev, en, fr in (
            ('verified-result', 'Verified bounded result', 'Résultat circonscrit vérifié'),
            ('falsified', 'Hypothesis falsified in tested scope', 'Hypothèse réfutée dans le périmètre testé'),
        ):
            row['evidence'] = ev
            path.write_text(json.dumps(data))
            for name in site.POSSIBILITY_PAGES:
                page = (self.source / name).read_text()
                ready = site.render_possibility_page(page, name, site.read_possibilities(self.source))
                self.assertIn(fr if name.endswith('/fr.html') else en, ready)
                self.assertNotIn('Author-reported' if not name.endswith('/fr.html') else 'Rapporté par les auteurs', ready)

    def test_public_research_cycle_requires_pinned_evidence_and_draft_label(self):
        import json
        path = self.source / site.POSSIBILITY_INPUT
        data = json.loads(path.read_text())
        row = next(item for item in data['records'] if item['watch'] == 'research-lab')
        data['records'] = [row]
        path.write_text(json.dumps(data))
        self.assertEqual(site.read_possibilities(self.source)[0]['id'], row['id'])
        for name in site.POSSIBILITY_PAGES:
            page = (self.source / name).read_text()
            rendered = site.render_possibility_page(page, name, site.read_possibilities(self.source))
            self.assertIn('Expérience circonscrite rejouée' if name.endswith('/fr.html')
                          else 'Replayed bounded experiment', rendered)
            self.assertIn('recherche en cours' if name.endswith('/fr.html') else 'draft research', rendered)
        original_sources = row['sources']
        row['sources'] = [{'url': 'https://arxiv.org/abs/2611.21152',
                           'en': 'Paper', 'fr': 'Article'}]
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            site.read_possibilities(self.source)
        row['sources'] = original_sources
        row['evidence'] = 'verified-result'
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            site.read_possibilities(self.source)

    def test_public_home_links_bilingual_frontier_atlas(self):
        home = (self.source / 'index.html').read_text()
        self.assertIn('href="frontier-omega-alpha/index.html"', home)
        self.assertIn('href="frontier-omega-alpha/fr.html"', home)
        self.assertIn('The living Possibility Atlas', home)
        self.assertIn('public files; confidential delivery is not enabled', home)
        out = site.build(self.source, self.root / 'frontier-nav')
        self.assertIn('href="frontier-omega-alpha/index.html"', (out / 'index.html').read_text())

    def test_possibility_sections_and_private_source_boundary(self):
        out = site.build(self.source, self.root / 'rendered')
        self.assertFalse((out / site.POSSIBILITY_INPUT).exists())
        for name in site.POSSIBILITY_PAGES:
            page = (out / name).read_text()
            self.assertNotIn(site.POSSIBILITY_MARKER, page)
            for record in site.read_possibilities(self.source):
                self.assertIn(f'id="shift-{record["id"]}"', page)
            self.assertLess(page.index('id="possibility-shifts"'), page.index('id="research"'))
            self.assertLess(page.index('id="access"'), page.index('id="possibility-shifts"'))
            self.assertLess(page.index('id="member-preview"'), page.index('id="possibility-shifts"'))
            self.assertIn('id="atlas-controls"', page)
            self.assertIn('id="member" class="frame workspace" hidden', page)
            self.assertNotIn('id="possibility-shifts" data-nosnippet', page)
            self.assertEqual(page.count('src="wallet-check.js"'), 1)

    def test_ignition_pages_exclude_private_files_and_reject_symlinked_subdirectory(self):
        (self.source / 'ignition/private.json').write_text('private')
        output = site.build(self.source, self.root / 'published')
        self.assertEqual({p.name for p in (output / 'ignition').iterdir()},
                         {'index.html', 'demo.html', 'public.js', 'studio.css'})
        private = self.root / 'elsewhere'
        (self.source / 'ignition').rename(private)
        (self.source / 'ignition').symlink_to(private, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'regular'):
            site.validate(self.source)

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

    def test_alpha_genesis_live_event_preview(self):
        event = (self.source / 'alpha-genesis-live.html').read_text()
        studio = (self.source / 'alpha-genesis-live-studio.html').read_text()
        index = (self.source / 'index.html').read_text()
        self.assertIn('ALPHA GENESIS FLYWHEEL Ω — LIVE', event)
        self.assertIn('Registration not open', event)
        self.assertIn('scripted', event.lower())
        self.assertIn('alpha-genesis-live.html', index)
        self.assertIn('ALPHA GENESIS FLYWHEEL', studio)
        self.assertIn('SCRIPTED PREVIEW', studio)

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
        self.assertEqual(len(site.PAPERS), 29)
        self.assertEqual(len(site.PAGES), 40)
        self.assertTrue({'alpha-genesis-live.html', 'alpha-genesis-live-studio.html'}.issubset(site.PAGES))
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
                self.assertIn('1.1.1', reader)
                self.assertIn('releases/tag/continuity-omega-v1.0.0', reader)
                suffix = '.fr' if lang == 'fr-CA' else ''
                for file in ('README' + suffix + '.md', 'REVIEW' + suffix + '.md',
                             'SOURCE_MAP' + suffix + '.md', 'CLAIMS' + suffix + '.json',
                             'EVIDENCE' + suffix + '.md'):
                    self.assertIn('docs/continuity-omega-paper/' + file, reader)
                self.assertIn('https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/continuity-omega-paper/CITATION' + suffix + '.cff', parser.links)
                self.assertIn('https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/continuity-omega/OUTPUTS' + suffix + '.md', parser.links)
                evidence_base = 'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/main/docs/continuity-omega-paper/'
                self.assertIn('<a class="btn primary" href="' + evidence_base + 'EVIDENCE' + suffix + '.md">', reader)
                for record in ('REPRODUCTION.json', 'COUNTEREXAMPLES.json'):
                    self.assertIn(evidence_base + 'evidence/' + record, parser.links)
                structured = json.loads(re.search(
                    r'<script type="application/ld\+json">(.*?)</script>', reader, re.S).group(1))
                self.assertEqual(structured['inLanguage'], lang)
                title = 'CONTINUITÉ Ω' if lang == 'fr-CA' else 'CONTINUITY Ω'
                self.assertTrue(structured['name'].startswith(title))
                self.assertIn(title, re.search(r'<title>(.*?)</title>', reader, re.S).group(1))
                for attribute in ('citation_title', 'og:title', 'twitter:title'):
                    self.assertRegex(reader, r'(?:name|property)="' + attribute + r'" content="' + title)
                self.assertIn('<h2 id="read-title">' + title + '</h2>', reader)
                self.assertEqual(structured['version'], '1.1.1')
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
                       'produites par les mêmes auteurs',
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
                title = 'CONTINUITÉ Ω' if lang == 'fr-CA' else 'CONTINUITY Ω'
                self.assertIn(title, re.search(r'<title>(.*?)</title>', gallery, re.S).group(1))
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
            french = name in ('continuity-omega-fr.html', 'continuity-omega-media-fr.html', 'frontier-omega-alpha/fr.html')
            self.assertIn('Aller au contenu' if french else 'Skip to content', text)
            styles = text
            if name == 'studio.html':
                styles = (self.source / 'alpha.css').read_text()
            elif name in ('ignition/index.html', 'ignition/demo.html'):
                self.assertIn('href="studio.css"', text)
                styles = (self.source / 'ignition/studio.css').read_text()
            elif name.startswith('frontier-omega-alpha/'):
                styles = (self.source / 'frontier-omega-alpha/frontier.css').read_text()
            self.assertIn('prefers-reduced-motion', styles)
            self.assertIn('@media(max-width:', styles.replace('@media (', '@media('))
            self.assertNotIn('↗', text)
            if not name.startswith('frontier-omega-alpha/') and name not in ('ignition/index.html', 'ignition/demo.html', 'frontier-conclave.html', 'index.html', 'out-series.html', 'studio.html', 'continuity-omega-media.html', 'continuity-omega-media-fr.html', 'alpha-genesis-live.html', 'alpha-genesis-live-studio.html'):
                self.assertIn('type="application/pdf"', text)
                self.assertIn('download>', text)
                self.assertIn('Votre navigateur n’affiche pas les PDF intégrés' if french else 'Your browser does not display embedded PDFs', text)

    def test_frontier_alpha_member_reading_uses_transaction_free_public_assets(self):
        import os
        import subprocess
        for name in ('index.html', 'fr.html'):
            language = 'fr' if name == 'fr.html' else 'en'
            template = (ROOT / 'products' / 'frontier-member-tools' / f'member.{language}.html').read_text()
            page = (self.source / 'frontier-omega-alpha' / name).read_text().replace('<!-- FRONTIER_MEMBER_VALUE -->', template)
            self.assertIn('src="wallet-check.js"', page)
            self.assertIn("connect-src 'none'", page)
            self.assertIn('data-connect="club" disabled', page)
            self.assertIn('data-connect="token" disabled', page)
            self.assertIn('id="brief-content" hidden', page)
            self.assertNotIn('member-brief-001.js', page)
        self.assertEqual(
            {name for name in site.FILES if name.startswith('frontier-omega-alpha/')},
            {'frontier-omega-alpha/index.html', 'frontier-omega-alpha/fr.html',
             'frontier-omega-alpha/frontier.css', 'frontier-omega-alpha/carina.webp',
             'frontier-omega-alpha/wallet-check.js', 'frontier-omega-alpha/member-brief-001.js',
             'frontier-omega-alpha/atlas.js', 'frontier-omega-alpha/endpoint-screen.mjs',
             'frontier-omega-alpha/outcome-receipt.mjs', 'frontier-omega-alpha/member-workbench.mjs',
             'frontier-omega-alpha/frontier-goals.mjs', 'frontier-omega-alpha/foundry-core.mjs',
             'frontier-omega-alpha/foundry-ui.mjs', 'frontier-omega-alpha/foundry-study.mjs',
             *site.DECISION_EDITION_ASSETS},
        )
        source = (self.source / 'frontier-omega-alpha' / 'wallet-check.js').read_text()
        self.assertIn("await import('./member-brief-001.js')", source)
        for forbidden in ('eth_sendTransaction', 'wallet_sendCalls', 'localStorage', 'sessionStorage', 'fetch('):
            self.assertNotIn(forbidden, source)
        # Real relative dynamic imports must resolve against the same files as the page.
        modules = self.source / 'frontier-omega-alpha'
        (modules / 'package.json').write_text('{"type":"module"}')
        subprocess.run(['node', '--input-type=module', '-e', r"""import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const walletURL=pathToFileURL(process.env.WALLET_PATH);
const {eligible,signInMessage}=await import(walletURL);
const acct='0x'+'12'.repeat(20), other='0x'+'34'.repeat(20), wrap='d4416b13d2b3a9abae7acd5d6c2bbdbe25686401';
const word=n=>BigInt(n).toString(16).padStart(64,'0');
const aw=a=>a.replace(/^0x/,'').padStart(64,'0');
const now=1700000000000, stamp=1700000000;
const block={hash:'0x'+'11'.repeat(32),number:'0x16',timestamp:'0x'+stamp.toString(16)};
const qty=n=>'0x'+word(n);
const rpc=(mode,balance=1000000n*10n**18n)=>({request:async({method,params})=>{
 if(method==='eth_chainId')return mode==='wrong-chain'?'0x2':'0x1';
 if(method==='eth_getBlockByNumber')return mode==='reorg'&&params[0]!=='latest'?{...block,hash:'0x'+'22'.repeat(32)}:block;
 if(method==='eth_getCode')return '0x1234';
 assert.equal(method,'eth_call');
 assert.equal(params[1],block.number);
 const {data,to}=params[0]; const sel=data.slice(0,10);
 if(sel==='0x313ce567')return qty(18);
 if(sel==='0x95d89b41')return '0x'+word(32)+word(8)+Buffer.from('AGIALPHA').toString('hex').padEnd(64,'0');
 if(sel==='0x70a08231'){assert.equal(data.slice(10),aw(acct));return qty(balance);}
 if(sel==='0x02571be3')return '0x'+aw(mode==='wrapped'||mode==='expired'?wrap:mode==='club-other'?other:acct);
 if(sel==='0x6352211e')return '0x'+aw(acct);
 if(sel==='0x0178fe3f')return '0x'+aw(acct)+word(65536)+word(mode==='expired'?stamp:stamp+3600);
 if(to.toLowerCase()==='0x57f1887a8bf19b14fc0df6fd9b2acc9af147ea85'){
   if(data.length===74)return qty(stamp+3600);
   if(data.length===10)return qty(7776000);
 }
 throw Error('unexpected method '+data);
}});
assert.equal(await eligible(rpc('token'),acct,'token','',now),true);
assert.equal(await eligible(rpc('token',999999n*10n**18n),acct,'token','',now),false);
assert.equal(await eligible(rpc('club'),acct,'club','founder',now),true);
assert.equal(await eligible(rpc('wrapped'),acct,'club','founder',now),true);
assert.equal(await eligible(rpc('expired'),acct,'club','founder',now),false);
assert.equal(await eligible(rpc('club-other'),acct,'club','founder',now),false);
await assert.rejects(eligible(rpc('club'),acct,'club','x.y',now),/label/);
await assert.rejects(eligible(rpc('wrong-chain'),acct,'token','',now),/network/);
await assert.rejects(eligible(rpc('reorg'),acct,'token','',now),/unavailable/);
await assert.rejects(eligible(rpc('token'),acct,'token','',now+91000),/unavailable/);
assert.match(signInMessage('https://montrealai.github.io',acct,'token',now,'nonce'),/does not approve a transaction/);
async function mounted(path){
 const node=()=>({children:[],attributes:{},focus(){},
  setAttribute(name,value){this.attributes[name]=value},
  replaceChildren(...children){this.children=children},
  append(...children){this.children.push(...children)}});
 const listeners={},button=node(),form={hidden:true},lock={},status={},entry={},preview={},route={},nav={},help={};
 const member={hidden:true,contains(){return false}};
 const portal=node(),label={value:'founder',focus(){}};
 portal.addEventListener=(name,run)=>{listeners.reveal=run};
 const brief=node(), open=node(), briefStatus=node();
 brief.hidden=true;
 open.addEventListener=(name,run)=>{listeners.open=run};
 const el={'status':status,'member':member,'club-label':label,'club-form':form,'lock':lock,'enter-club':portal,
  'access':entry,'member-preview':preview,'entry-help':help,'member-route':route,'member-nav':nav,
  'workspace-title':{focus(){}},'open-brief':open,'brief-status':briefStatus,'brief-content':brief};
 form.addEventListener=(name,run)=>{listeners[name]=run};
 lock.addEventListener=(name,run)=>{listeners['lock']=run};
 button.addEventListener=(name,run)=>{listeners['token']=run};
 globalThis.document={documentElement:{lang:path==='club'?'fr':'en'},getElementById:id=>el[id],
  querySelectorAll:selector=>selector==='[data-connect]'?[button]:[],querySelector:()=>button,createElement:node,addEventListener(){}};
 const chain=rpc(path);
 const calls=[],events={};
 globalThis.window={location:{origin:'https://montrealai.github.io'},addEventListener(){},dispatchEvent(){},scrollTo(){},ethereum:{
  isMetaMask:true, on(name,run){events[name]=run}, request:async msg=>{
   calls.push(msg.method);
   if(msg.method==='eth_requestAccounts'){
    events.accountsChanged([acct]);
    return [acct];
   }
   if(msg.method==='eth_accounts')return [acct];
   if(msg.method==='personal_sign')return '0x'+'ab'.repeat(65);
   return await chain.request(msg);
  }
 }};
 const realNow=Date.now;Date.now=()=>now;
 try{
  await import(new URL('#'+path,walletURL));
  assert.equal(member.hidden,true);
  if(path==='club'){
   listeners.reveal();
   assert.equal(form.hidden,false);
   assert.equal(portal.attributes['aria-expanded'],'true');
  }
  listeners[path==='club'?'submit':'token']({preventDefault(){}});
  for(let i=0;i<50&&member.hidden;i++)await new Promise(setImmediate);
  assert.equal(member.hidden,false);
  assert.equal(entry.hidden,true);
  assert.equal(preview.hidden,true);
  assert.equal(nav.href,'#member');
  assert.equal(brief.hidden,true);
  const beforeOpen=calls.length;
  listeners.open();
  for(let i=0;i<100&&brief.hidden;i++)await new Promise(resolve=>setTimeout(resolve,5));
  assert.equal(brief.hidden,false);
  assert(calls.slice(beforeOpen).includes('eth_accounts'));
  assert(calls.slice(beforeOpen).includes('eth_call'));
  assert.equal(open.attributes['aria-expanded'],'true');
  assert(brief.children.length>2);
  assert.equal(calls.filter(m=>m==='personal_sign').length,1);
  assert(calls.every(m=>['eth_requestAccounts','eth_accounts','eth_chainId','eth_getBlockByNumber','eth_getCode','eth_call','personal_sign'].includes(m)));
  events.accountsChanged([acct,other]);
  assert.equal(brief.hidden,false);
  events.accountsChanged([other]);
  assert.equal(member.hidden,true);
  assert.equal(entry.hidden,false);
  assert.equal(preview.hidden,false);
  assert.equal(route.textContent,'');
  assert.equal(brief.hidden,true);
  assert.equal(brief.children.length,0);
  assert.equal(open.attributes['aria-expanded'],'false');
 }finally{Date.now=realNow;delete globalThis.document;delete globalThis.window;}
}
await mounted('club');await mounted('token');
console.log('11 wallet qualification checks and both workspace open/lock fixtures passed');"""],
                       check=True, env={**os.environ, 'WALLET_PATH': str(modules / 'wallet-check.js')}, timeout=30)

    def test_member_brief_loads_once_from_the_hidden_workspace(self):
        for name, public_note in (('index.html', 'hosted as public GitHub Pages files'),
                                  ('fr.html', 'fichiers publics sur GitHub Pages')):
            with self.subTest(page=name):
                language = 'fr' if name == 'fr.html' else 'en'
                template = (ROOT / 'products' / 'frontier-member-tools' / f'member.{language}.html').read_text()
                page = (self.source / 'frontier-omega-alpha' / name).read_text().replace('<!-- FRONTIER_MEMBER_VALUE -->', template)
                before, workspace = page.split('<section id="member" class="frame workspace" hidden', 1)
                workspace, after = workspace.split('<section id="member-preview"', 1)
                self.assertIn(public_note, before)
                self.assertEqual(page.count('id="open-brief"'), 1)
                self.assertNotIn('id="open-brief"', before + after)
                self.assertIn('<div class="brief-entry" data-nosnippet>', workspace)
                self.assertIn('id="brief-content" hidden></article>', workspace)
                self.assertNotIn('id="member-brief-001"', page)
                self.assertNotIn('id="possibility-shifts"', workspace)
                self.assertIn('id="possibility-shifts" aria-labelledby="possibility-shifts-title"', after)
                self.assertIn('<!-- FRONTIER_POSSIBILITY_RECORDS -->', after)
                self.assertIn('<!-- FRONTIER_PUBLIC_WATCH -->', after)
                self.assertNotIn('data-nosnippet aria-labelledby="possibility-shifts-title"', after)
                self.assertIn('href="#possibility-shifts"', before)
                self.assertNotIn('id="possibility-shifts"', before)

    def test_frontier_alpha_workspace_links_to_bilingual_public_packets(self):
        for name in ('index.html', 'fr.html'):
            with self.subTest(page=name):
                language = 'fr' if name == 'fr.html' else 'en'
                template = (ROOT / 'products' / 'frontier-member-tools' / f'member.{language}.html').read_text()
                page = (self.source / 'frontier-omega-alpha' / name).read_text().replace('<!-- FRONTIER_MEMBER_VALUE -->', template)
                before, packets = page.split('id="research" aria-labelledby="public-results-title"', 1)
                workspace = before.split('id="member"', 1)[1]
                packets = packets.split('</section>', 1)[0]
                self.assertNotRegex(packets, r'<[^>]*\shidden\b')
                for slug in ('lean', 'qwen', 'retrofit'):
                    self.assertIn(f'href="#packet-{slug}"', workspace)
                    self.assertIn(f'<article class="packet" id="packet-{slug}"', packets)
                self.assertIn('href="#research-packet"', workspace)
                self.assertIn('href="#research-packet"', packets)
                six_records = page.split('id="research-packet"', 1)[1].split('</section>', 1)[0]
                self.assertEqual(six_records.count('<details id="packet-'), 6)
                for evidence in ('frontier-cycle.json', 'qwen-gguf-maintenance.json',
                                 'engineering-receipt.json', 'economic_alpha/qualification.json'):
                    self.assertIn(evidence, packets)

    def test_historical_edition_verifier_rejects_swapped_same_name(self):
        import json
        import subprocess

        directory = self.source / 'frontier-omega-alpha/decision-editions'
        verifier = directory / 'verify.py'
        earlier, later = [row['run'] for row in json.loads((directory / 'index.json').read_text())['editions']]
        recovered = self.root / 'recovered'
        launch = ['python3', str(verifier), earlier, '--output', str(recovered)]
        success = subprocess.run(launch, check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(success.stdout)['status'], 'MATCHED_PINNED_EDITION')
        self.assertEqual({p.name for p in recovered.iterdir()},
                         {'atlas-release.json', 'atlas-ledger.json', 'member-value.json'})
        target = directory / f'{earlier}.tar.zst'
        shutil.copyfile(directory / f'{later}.tar.zst', target)
        new_output = self.root / 'refused'
        denied = subprocess.run(launch[:-1] + [str(new_output)], capture_output=True, text=True)
        self.assertEqual(denied.returncode, 2)
        self.assertIn('ABSTAIN', denied.stderr)
        self.assertFalse(new_output.exists())

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


class ConclavePublicationTests(unittest.TestCase):
    def test_archive_and_source_agree(self):
        import zipfile
        import json
        kit = ROOT / 'experiments/frontier-conclave'
        archive = ROOT / 'docs/research/FRONTIER_CONCLAVE_COMPLETE.zip'
        self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(), 'dc4d124f63d8417016db3e004c6389620544f83b254d02bc64c39d493d8a89c6')
        manifest = json.loads((kit / 'DISTRIBUTION_SHA256SUMS.json').read_text())
        with zipfile.ZipFile(archive) as z:
            for name, digest in manifest.items():
                payload = z.read('FRONTIER_CONCLAVE_OMEGA_001/' + name)
                self.assertEqual(payload, (kit / name).read_bytes())
                self.assertEqual(hashlib.sha256(payload).hexdigest(), digest)
        page = (ROOT / 'docs/research/frontier-conclave.html').read_text()
        for claim in ('illustrative, not live candidate execution', 'No authenticated Pro-to-HARNESS connector', 'not event registration'):
            self.assertIn(claim, page)
