#!/usr/bin/env python3
"""Validate and copy only the public research website; no repository export."""
import argparse
import hashlib
from datetime import date
from html import escape
from html.parser import HTMLParser
import json
import posixpath
import re
from pathlib import Path
import shutil
import unicodedata
from urllib.parse import unquote, urlsplit

PAPERS = (
    'learning-to-build-v1.1.0.pdf',
    'learning-to-build.pdf',
    'continuity-omega.pdf',
    'continuity-omega-fr.pdf',
    'surf-the-exponential.pdf',
    'alpha-genesis-flywheel-omega-v2.pdf',
    'alpha-genesis-flywheel-omega.pdf',
    'successor-omega.pdf',
    'flywheel-omega.pdf',
    'super-alpha.pdf',
    'out-accelerate.pdf',
    'transformational-intelligence-202610.pdf',
    'agi-alpha-foundation-20260430.pdf',
    'agi-alpha-flywheel-20261102.pdf',
    'agi-alpha-flywheel-20261102-v1.1.pdf',
    'agi-alpha-flywheel-20261102-report.pdf',
    'invent-the-economy-202610.pdf',
    'the-world-as-an-output-20261020.pdf',
    'beyond-the-production-frontier-20261019.pdf',
    'beyond-the-original-problem-20261019.pdf',

    'autonomous-enterprises-foundry-v2.pdf',
    'out-reflect-self-correcting-evidence-20261021.pdf',
    'transformational-autonomous-enterprises-v1.pdf',
    'out-learn-20261021.pdf',
    'out-think-20261021.pdf',
    'out-design-20261021.pdf',
    'out-strategise-20261020.pdf',
    'out-execute-20261021.pdf',
    'out-evolve-20261020.pdf',
)
PAGES = ('learning-to-build-v1.1.0.html', 'learning-to-build.html', 'continuity-omega.html', 'continuity-omega-fr.html', 'continuity-omega-media.html', 'continuity-omega-media-fr.html', 'surf-the-exponential.html', 'alpha-genesis-flywheel-omega-v2.html', 'alpha-genesis-flywheel-omega.html', 'successor-omega.html', 'flywheel-omega.html', 'super-alpha.html', 'agi-alpha-flywheel-report-20261102.html', 'out-accelerate.html', 'transformational-intelligence.html', 'agi-alpha.html', 'agi-alpha-flywheel.html', 'invent-the-economy.html', 'the-world-as-an-output.html', 'beyond-the-production-frontier.html', 'beyond-the-original-problem.html', 'index.html', 'studio.html', 'foundry-v2.html', 'transformational-enterprises.html', 'out-reflect.html',
         'out-series.html', 'out-learn.html', 'out-think.html', 'out-design.html', 'out-strategise.html', 'out-execute.html', 'out-evolve.html')
ASSETS = ('continuity-omega-card.svg', 'continuity-omega-social.png', 'continuity-omega-fr-card.svg', 'continuity-omega-fr-social.png', 'surf-the-exponential-card.svg', 'surf-the-exponential-social.png', 'successor-omega-card.svg', 'successor-omega-social.png', 'flywheel-omega-card.svg', 'flywheel-omega-social.png', 'super-alpha-card.svg', 'super-alpha-social.png', 'alpha.css', 'alpha.js', 'alpha-mark.svg')
ASSETS += ('learning-to-build-card.svg', 'learning-to-build-social.png')
ASSETS += ('learning-to-build-v1.1.0-example.png',)
CONTINUITY_MEDIA = tuple(
    f'continuity-omega-{scene}-{language}{suffix}'
    for scene in ('ascent', 'reveal', 'journey', 'motion')
    for language in ('en', 'fr')
    for suffix in ('.gif', '-poster.png')
)
ASSETS += CONTINUITY_MEDIA + ('continuity-omega-media-manifest.json',)
CONCLAVE_PAGE = 'frontier-conclave.html'
PAGES += (CONCLAVE_PAGE,)
ASSETS += ('frontier-conclave-hero.png', 'frontier-conclave-salon.png', 'FRONTIER_CONCLAVE_COMPLETE.zip')
PAGES += ('alpha-genesis-live.html', 'alpha-genesis-live-studio.html')
PAGES += ('ignition/index.html', 'ignition/demo.html')
ASSETS += ('ignition/studio.css', 'ignition/public.js')
COMPANION_GUIDE = 'frontier-omega-alpha/companion-start.html'
PAGES += ('frontier-omega-alpha/index.html', 'frontier-omega-alpha/fr.html', COMPANION_GUIDE)
DECISION_EDITION_ASSETS = tuple(
    f'frontier-omega-alpha/decision-editions/{name}'
    for name in ('index.json', 'verify.py', '45278828750.tar.zst', '45287921702.tar.zst')
)
ASSETS += (
    'frontier-omega-alpha/frontier.css',
    'frontier-omega-alpha/double-flywheel.mjs',
    'frontier-omega-alpha/conclave-door.mjs',
    'frontier-omega-alpha/three-0.160.1.min.mjs',
    'frontier-omega-alpha/three-0.160.1-LICENSE.txt',
    'frontier-omega-alpha/double-flywheel-cover.webp',
    'frontier-omega-alpha/double-flywheel-finale.webp',
    'frontier-omega-alpha/wallet-check.js',
    'frontier-omega-alpha/member-brief-001.js',
    'frontier-omega-alpha/carina.webp',
    'frontier-omega-alpha/atlas.js',
    'frontier-omega-alpha/endpoint-screen.mjs',
    'frontier-omega-alpha/outcome-receipt.mjs',
    'frontier-omega-alpha/member-workbench.mjs',
    'frontier-omega-alpha/frontier-goals.mjs',
    'frontier-omega-alpha/frontier-mission.mjs',
    'frontier-omega-alpha/frontier-mission-router.mjs',
    'frontier-omega-alpha/frontier-mission-ui.mjs',
    'frontier-omega-alpha/frontier-native-work.mjs',
    'frontier-omega-alpha/frontier-mission-instruments.mjs',
    'frontier-omega-alpha/frontier-mission-context.mjs',
    'frontier-omega-alpha/frontier-artifact-exchange.mjs',
    'frontier-omega-alpha/dpp-source-review.mjs',
    'frontier-omega-alpha/frontier-battery-source-example.json',
    'frontier-omega-alpha/frontier-assisted-work.mjs',
    'frontier-omega-alpha/frontier-browser-model.mjs',
    'frontier-omega-alpha/frontier-execution.mjs',
    'frontier-omega-alpha/frontier-companion-link.mjs',
    'frontier-omega-alpha/foundry-core.mjs',
    'frontier-omega-alpha/foundry-ui.mjs',
    'frontier-omega-alpha/foundry-study.mjs',
) + DECISION_EDITION_ASSETS
FILES = PAPERS + PAGES + ASSETS + ('publication-manifest.json',)
PUBLIC_SITE = 'https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/'
EXTERNAL_RESEARCH_REFERENCES = frozenset({
    'https://bbbc.broadinstitute.org/BBBC007',
    'https://math.mit.edu/~drew/grh/',
    'https://blog.prusa3d.com/ht-hotend-is-out-plus-we-offer-new-materials-and-hightemp-sheets-for-core-one-l_138625/',
    'https://web.archive.org/web/20260929192630id_/https://www.prusa3d.com/product/ht-hotend-upgrade-for-core-one-and-core-one-l/',
    'https://api.github.com/repos/bambulab/BambuStudio/releases/tags/v02.09.02.62',
    'https://lean-lang.org/doc/reference/latest/releases/v4.36.0/',
    'https://leanprover-community.github.io/blog/posts/riemann-hypothesis/',
})


POSSIBILITY_INPUT = 'frontier-omega-alpha/possibility-shifts.json'
POSSIBILITY_PAGES = frozenset({'frontier-omega-alpha/index.html', 'frontier-omega-alpha/fr.html'})
POSSIBILITY_MARKER = '<!-- FRONTIER_POSSIBILITY_RECORDS -->'
POSSIBILITY_MAX_BYTES = 256_000
ATLAS_OUTPUTS = frozenset({
    'frontier-omega-alpha/atlas-ledger.json', 'frontier-omega-alpha/atlas-release.json',
    'frontier-omega-alpha/member-value.json', 'frontier-omega-alpha/endpoint-evidence-screen-1.0.0.zip',
    'frontier-omega-alpha/noaa-archive-point-1.0.0.zip',
    'frontier-omega-alpha/frontier-foundry-1.0.0.zip',
    'frontier-omega-alpha/frontier-foundry-1.1.0.zip',
    'frontier-omega-alpha/frontier-inventor-1.0.0.zip',
    'frontier-omega-alpha/frontier-learning-1.0.0.zip',
    'frontier-omega-alpha/frontier-activation-1.0.0.zip',
    'frontier-omega-alpha/frontier-activation-1.1.0.zip',
    'frontier-omega-alpha/frontier-activation-1.2.0.zip',
    'frontier-omega-alpha/frontier-activation-1.3.0.zip',
    'frontier-omega-alpha/frontier-activation-1.4.0.zip',
    'frontier-omega-alpha/cascade-results.json',
    'frontier-omega-alpha/cascade-fresh-domain.json',
    'frontier-omega-alpha/frontier-activation-1.5.0.zip',
    'frontier-omega-alpha/factory-results.json',
    'frontier-omega-alpha/frontier-game-theory-1.0.0.zip',
    'frontier-omega-alpha/frontier-game-observation-1.0.0.zip',
    'frontier-omega-alpha/frontier-harness-executor-1.0.0.zip',
    'frontier-omega-alpha/frontier-harness-executor-1.1.0.zip',
    'frontier-omega-alpha/frontier-harness-executor-1.2.0.zip',
    'frontier-omega-alpha/frontier-harness-executor-1.3.0.zip',
    'frontier-omega-alpha/frontier-harness-executor-1.3.0-cef4d1c.zip',
    'frontier-omega-alpha/frontier-harness-executor-1.4.0.zip',
    'frontier-omega-alpha/frontier-harness-executor-1.5.0.zip',
    'frontier-omega-alpha/opportunity-capture.json',
})
STATES = ('discovered', 'qualified', 'testing', 'verified', 'falsified', 'abstain', 'retained', 'deployed', 'value-verified')
POSSIBILITY_SOURCE_PATTERNS = (
    r'https://arxiv\.org/abs/[0-9]{4}\.[0-9]{4,5}(?:v[1-9][0-9]*)?',
    r'https://github\.com/[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}(?:/releases/tag/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}|/commit/[a-f0-9]{40}|/pull/[1-9][0-9]{0,8}|/blob/[a-f0-9]{40}/[A-Za-z0-9_./-]{1,150})?',
    r'https://console\.upstage\.ai/docs/models/[a-z0-9][a-z0-9-]{0,79}',
)


def possibility_source(url):
    return (isinstance(url, str) and len(url) <= 250 and
            any(re.fullmatch(pattern, url) for pattern in POSSIBILITY_SOURCE_PATTERNS))


def _possibility_text(value, limit):
    if (not isinstance(value, str) or not 1 <= len(value) <= limit or value != value.strip() or
            any(unicodedata.category(ch) in ('Cc', 'Cf', 'Cs') for ch in value) or
            any(ch in value for ch in '<>') or
            re.search(r'https?://|sentinel_|(?:room|task|automation|thread)_id\s*[:=]|\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}', value, re.I)):
        raise ValueError('Invalid possibility public text')


def _possibility_keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('Unexpected possibility record fields')


def read_possibilities(source):
    source = Path(source)
    path = source / POSSIBILITY_INPUT
    if path.is_symlink() or not path.is_file() or path.resolve() != source.resolve() / POSSIBILITY_INPUT:
        raise ValueError('Not a regular possibility input file')
    with path.open('rb') as stream:
        raw = stream.read(POSSIBILITY_MAX_BYTES + 1)
    if len(raw) > POSSIBILITY_MAX_BYTES:
        raise ValueError('Possibility data exceeds byte limit')

    return parse_possibilities(raw)


def parse_possibilities(raw):
    if len(raw) > POSSIBILITY_MAX_BYTES:
        raise ValueError('Possibility data exceeds byte limit')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate possibility field')
            result[key] = value
        return result

    data = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs)
    _possibility_keys(data, ('schema', 'records'))
    if data['schema'] not in ('frontier-possibility-shifts/1', 'frontier-possibility-shifts/2'):
        raise ValueError('Unsupported possibility schema')
    records = data['records']
    if not isinstance(records, list) or not records:
        raise ValueError('Invalid possibility record count')
    ids = set()
    order = []
    for record in records:
        fields = ('id', 'date', 'watch', 'evidence', 'en', 'fr', 'sources')
        if data['schema'].endswith('/2'):
            fields += ('assessment',)
        _possibility_keys(record, fields)
        key, day = record['id'], record['date']
        if not isinstance(key, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}', key) or key in ids:
            raise ValueError('Duplicate or invalid possibility ID')
        if not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
            raise ValueError('Invalid possibility date')
        order.append((-date.fromisoformat(day).toordinal(), key))
        ids.add(key)
        watch, evidence = record['watch'], record['evidence']
        if watch not in ('living-watch', 'possible-now', 'verified-invention-watch', 'research-lab'):
            raise ValueError('Invalid possibility source stream')
        allowed_evidence = {'verified-invention-watch': ('verified-result', 'falsified'),
                            'research-lab': ('research-tested',)}.get(watch, ('author-reported', 'proposed-test'))
        if evidence not in allowed_evidence:
            raise ValueError('Evidence type does not belong to this possibility source stream')
        for lang in ('en', 'fr'):
            localized = record[lang]
            _possibility_keys(localized, ('title', 'signal', 'next'))
            for field, max_chars in (('title', 120), ('signal', 600), ('next', 650)):
                _possibility_text(localized[field], max_chars)
        if 'assessment' in record:
            assessment = record['assessment']
            _possibility_keys(assessment, ('state', 'priority', 'en', 'fr'))
            if assessment['state'] not in STATES or type(assessment['priority']) is not int or not 1 <= assessment['priority'] <= 3:
                raise ValueError('Invalid Atlas assessment')
            if evidence in ('author-reported', 'proposed-test') and assessment['state'] not in STATES[:3]:
                raise ValueError('A reference cannot attest an experimental outcome')
            for language in ('en', 'fr'):
                _possibility_keys(assessment[language], ('decision', 'alternative'))
                _possibility_text(assessment[language]['decision'], 350)
                _possibility_text(assessment[language]['alternative'], 350)
        sources = record['sources']
        if not isinstance(sources, list) or not 1 <= len(sources) <= 3:
            raise ValueError('Invalid possibility source count')
        urls = set()
        for citation in sources:
            _possibility_keys(citation, ('url', 'en', 'fr'))
            if not possibility_source(citation['url']) or citation['url'] in urls:
                raise ValueError('Unapproved or duplicate possibility source')
            urls.add(citation['url'])
            _possibility_text(citation['en'], 80)
            _possibility_text(citation['fr'], 80)
        if watch in ('verified-invention-watch', 'research-lab') and not any(
            re.fullmatch(r'https://github\.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/commit/[a-f0-9]{40}', url)
            for url in urls
        ):
            raise ValueError('Replayed research requires an immutable MONTREAL.AI evidence commit')
    if order != sorted(order):
        raise ValueError('Possibility records must be sorted by descending date then ascending ID')
    return records


STATE_LABELS = {
    'en': dict(zip(STATES, ('Discovered', 'Qualified', 'Testing', 'Verified', 'Falsified',
                           'Abstain', 'Retained', 'Deployed', 'Value verified'))),
    'fr': dict(zip(STATES, ('Repéré', 'Qualifié', 'À l’essai', 'Vérifié', 'Réfuté',
                           'Abstention', 'Conservé', 'Déployé', 'Valeur vérifiée'))),
}
EVIDENCE_LABELS = {
    'author-reported': ('Author-reported', 'Rapporté par les auteurs'),
    'proposed-test': ('Proposed test', 'Essai proposé'),
    'verified-result': ('Verified bounded result', 'Résultat circonscrit vérifié'),
    'falsified': ('Hypothesis falsified in tested scope', 'Hypothèse réfutée dans le périmètre testé'),
    'research-tested': ('Replayed bounded experiment · draft research',
                        'Expérience circonscrite rejouée · recherche en cours'),
}


def record_state(item):
    return item.get('assessment', {}).get('state', {
        'verified-result': 'verified', 'falsified': 'falsified',
    }.get(item['evidence'], 'discovered'))


def possibility_card(item, lang, revisions=''):
    local = item[lang]
    state = record_state(item)
    evidence = EVIDENCE_LABELS[item['evidence']][lang == 'fr']
    key = 'shift-' + item['id']
    labels = ('Source evidence', 'Decision', 'Strongest alternative', 'Next step') if lang == 'en' else (
        'Sources et preuves', 'Décision', 'Meilleure solution de rechange', 'Prochaine étape')
    links = ''.join(f'<li><a href="{escape(s["url"])}">{escape(s[lang])}</a></li>' for s in item['sources'])
    assessment = item.get('assessment', {}).get(lang)
    notes = ''
    if assessment:
        notes = ''.join(f'<div><dt>{label}</dt><dd>{escape(assessment[field])}</dd></div>'
                        for label, field in zip(labels[1:3], ('decision', 'alternative')))
    return (
        f'<article class="atlas-card" id="{key}" data-atlas-record data-state="{state}" aria-labelledby="{key}-title">'
        f'<div class="atlas-card-meta"><strong>{STATE_LABELS[lang][state]}</strong>'
        f'<time datetime="{item["date"]}">{item["date"]}</time></div>'
        f'<h3 id="{key}-title">{escape(local["title"])}</h3><p class="atlas-evidence">{escape(evidence)}</p>'
        f'<p>{escape(local["signal"])}</p><dl>{notes}'
        f'<div><dt>{labels[3]}</dt><dd>{escape(local["next"])}</dd></div></dl>'
        f'<ul aria-label="{labels[0]}" class="atlas-links">{links}</ul>{revisions}</article>'
    )


def render_possibility_page(page, name, records):
    if page.count(POSSIBILITY_MARKER) != 1:
        raise ValueError('The possibility page must contain exactly one render marker')
    lang = 'fr' if name.endswith('/fr.html') else 'en'
    entries = ''.join(possibility_card(item, lang) for item in records)
    return page.replace(POSSIBILITY_MARKER, f'<div class="atlas-grid" id="atlas-records">{entries}</div>')


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.canonical_urls = []
        self.alternate_urls = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        for key in ('href', 'src', 'data'):
            if key in attrs:
                if tag == 'link' and key == 'href' and 'canonical' in attrs.get('rel', '').split():
                    self.canonical_urls.append(attrs[key])
                elif tag == 'link' and key == 'href' and 'alternate' in attrs.get('rel', '').split() and 'hreflang' in attrs:
                    self.alternate_urls.append((attrs['hreflang'], attrs[key]))
                else:
                    self.links.append(attrs[key])


def render_conclave(page):
    """Use the exact canonical bilingual demo sections, never a second implementation."""
    templates = Path(__file__).resolve().parents[1] / 'products/frontier-member-tools'
    for lang in ('en', 'fr'):
        marker = f'<!-- CONCLAVE_DEMO_{lang.upper()} -->'
        source = (templates / f'member.{lang}.html').read_text()
        sections = re.findall(r'<section class="df" id="double-flywheel"[^>]*>.*?</section>', source, re.S)
        if page.count(marker) != 1 or len(sections) != 1 or 'data-double-flywheel' not in sections[0]:
            raise ValueError('Missing or ambiguous Conclave demo template')
        page = page.replace(marker, sections[0])
    return page


def validate(source, *, staged=False):
    """Fail closed on changed PDFs, nonlocal files, or broken relative links."""
    source = Path(source)
    for name in FILES:
        path = source / name
        if path.is_symlink() or not path.is_file() or path.resolve() != source.resolve() / name:
            raise ValueError(f'Not a regular publication file: {name}')
    three = 'frontier-omega-alpha/three-0.160.1.min.mjs'
    if hashlib.sha256((source / three).read_bytes()).hexdigest() != '3e690ac7d180b0aadf0891bea39eec643e29e2d3e75c99b18689518665f69ba6':
        raise ValueError('Pinned Three.js asset changed')
    manifest = json.loads((source / 'publication-manifest.json').read_text())
    entries = manifest['papers']
    if manifest['schema_version'] != 1 or len(entries) != len(PAPERS) or {p['file'] for p in entries} != set(PAPERS):
        raise ValueError('Manifest must describe exactly the allowlisted public papers')
    for item in entries:
        data = (source / item['file']).read_bytes()
        if not data.startswith(b'%PDF-') or len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError(f'PDF integrity mismatch: {item["file"]}')
    records = None if staged else read_possibilities(source)
    parsed = {}
    for name in PAGES:
        parser = Links()
        page = (source / name).read_text()
        if name == CONCLAVE_PAGE:
            if staged and '<!-- CONCLAVE_DEMO_' in page:
                raise ValueError('Unrendered Conclave member templates')
            if not staged:
                page = render_conclave(page)
        if name in POSSIBILITY_PAGES:
            if staged and POSSIBILITY_MARKER in page:
                raise ValueError('Unrendered possibility publication')
            if not staged:
                page = render_possibility_page(page, name, records)
        if any(token in page for token in ('PAPER_SHA256_PLACEHOLDER', 'PAPER_PAGECOUNT_PLACEHOLDER', 'TODO_RESULT_', 'SUPER_ALPHA_PAGE_COUNT', 'SUPER_ALPHA_PDF_SHA', 'FLYWHEEL_OMEGA_PAGE_COUNT', 'FLYWHEEL_OMEGA_PDF_SHA', 'SURF_PAGE_COUNT', 'SURF_SHA256', 'SURF_PDF_BYTES', 'CONTINUITY_PAGE_COUNT', 'CONTINUITY_SHA256', 'CONTINUITY_PDF_BYTES', 'CONTINUITY_EN_PAGE_COUNT', 'CONTINUITY_EN_SHA256', 'CONTINUITY_EN_PDF_BYTES', 'CONTINUITY_FR_PAGE_COUNT', 'CONTINUITY_FR_SHA256', 'CONTINUITY_FR_PDF_BYTES')):
            raise ValueError(f'Unresolved publication metadata: {name}')
        parser.feed(page)
        if parser.canonical_urls and parser.canonical_urls != [PUBLIC_SITE + name]:
            raise ValueError(f'Canonical URL must identify this published page: {name}')
        for _, alternate in parser.alternate_urls:
            if alternate not in {PUBLIC_SITE + page_name for page_name in PAGES}:
                raise ValueError(f'Alternate language URL must identify an allowlisted page: {alternate}')
        parsed[name] = parser
    for name, parser in parsed.items():
        for link in parser.links:
            url = urlsplit(link)
            if url.scheme:
                frontier_source = name in POSSIBILITY_PAGES and (possibility_source(link) or link in (
                    'https://metamask.io/download', 'https://chatgpt.com/', 'https://chatgpt.com/codex/',
                    'https://ollama.com/download',
                    'https://lmstudio.ai/download', 'https://docs.vllm.ai/en/latest/getting_started/installation/',
                ))
                companion_source = name == COMPANION_GUIDE and link in (
                    'https://www.python.org/downloads/', PUBLIC_SITE + 'frontier-omega-alpha/#my-frontier',
                    PUBLIC_SITE + 'frontier-omega-alpha/fr.html#my-frontier',
                )
                if (not frontier_source and not companion_source and link not in EXTERNAL_RESEARCH_REFERENCES
                        and (url.scheme != 'https' or url.netloc != 'github.com')):
                    raise ValueError(f'Unexpected external link: {link}')
                continue
            if url.netloc or url.query:
                raise ValueError(f'Unexpected relative link: {link}')
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(url.path))) if url.path else name
            if target not in FILES and not (name in POSSIBILITY_PAGES and target in ATLAS_OUTPUTS):
                raise ValueError(f'Link outside publication: {link}')
            if url.fragment and target in parsed and unquote(url.fragment) not in parsed[target].ids:
                raise ValueError(f'Unknown HTML anchor: {link}')
    return manifest


def build(source, output):
    source, output = Path(source), Path(output)
    validate(source)
    records = read_possibilities(source)
    # Never clean an existing directory: callers must choose an empty staging path.
    if output.is_symlink() or output.exists():
        raise ValueError('Output must be a new directory')
    output.mkdir(parents=True)
    for name in FILES:
        (output / name).parent.mkdir(parents=True, exist_ok=True)
        if name in POSSIBILITY_PAGES:
            (output / name).write_text(render_possibility_page((source / name).read_text(), name, records))
        elif name == CONCLAVE_PAGE:
            (output / name).write_text(render_conclave((source / name).read_text()))
        else:
            shutil.copyfile(source / name, output / name)
    (output / '.nojekyll').write_text('')
    validate(output, staged=True)
    published = {p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()}
    if published != set(FILES) | {'.nojekyll'}:
        raise ValueError('Unexpected published file')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1] / 'docs/research')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(build(args.source, args.output))
