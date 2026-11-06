#!/usr/bin/env python3
"""Validate and copy only the public research website; no repository export."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import shutil
from urllib.parse import unquote, urlsplit

PAPERS = (
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
PAGES = ('continuity-omega.html', 'continuity-omega-fr.html', 'continuity-omega-media.html', 'continuity-omega-media-fr.html', 'surf-the-exponential.html', 'alpha-genesis-flywheel-omega-v2.html', 'alpha-genesis-flywheel-omega.html', 'successor-omega.html', 'flywheel-omega.html', 'super-alpha.html', 'agi-alpha-flywheel-report-20261102.html', 'out-accelerate.html', 'transformational-intelligence.html', 'agi-alpha.html', 'agi-alpha-flywheel.html', 'invent-the-economy.html', 'the-world-as-an-output.html', 'beyond-the-production-frontier.html', 'beyond-the-original-problem.html', 'index.html', 'studio.html', 'foundry-v2.html', 'transformational-enterprises.html', 'out-reflect.html',
         'out-series.html', 'out-learn.html', 'out-think.html', 'out-design.html', 'out-strategise.html', 'out-execute.html', 'out-evolve.html')
ASSETS = ('continuity-omega-card.svg', 'continuity-omega-social.png', 'continuity-omega-fr-card.svg', 'continuity-omega-fr-social.png', 'surf-the-exponential-card.svg', 'surf-the-exponential-social.png', 'successor-omega-card.svg', 'successor-omega-social.png', 'flywheel-omega-card.svg', 'flywheel-omega-social.png', 'super-alpha-card.svg', 'super-alpha-social.png', 'alpha.css', 'alpha.js', 'alpha-mark.svg')
CONTINUITY_MEDIA = tuple(
    f'continuity-omega-{scene}-{language}{suffix}'
    for scene in ('ascent', 'reveal', 'journey', 'motion')
    for language in ('en', 'fr')
    for suffix in ('.gif', '-poster.png')
)
ASSETS += CONTINUITY_MEDIA + ('continuity-omega-media-manifest.json',)
FILES = PAPERS + PAGES + ASSETS + ('publication-manifest.json',)
PUBLIC_SITE = 'https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/'


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


def validate(source):
    """Fail closed on changed PDFs, nonlocal files, or broken relative links."""
    source = Path(source)
    for name in FILES:
        path = source / name
        if path.is_symlink() or not path.is_file() or path.resolve().parent != source.resolve():
            raise ValueError(f'Not a regular publication file: {name}')
    manifest = json.loads((source / 'publication-manifest.json').read_text())
    entries = manifest['papers']
    if manifest['schema_version'] != 1 or len(entries) != len(PAPERS) or {p['file'] for p in entries} != set(PAPERS):
        raise ValueError('Manifest must describe exactly the allowlisted public papers')
    for item in entries:
        data = (source / item['file']).read_bytes()
        if not data.startswith(b'%PDF-') or len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError(f'PDF integrity mismatch: {item["file"]}')
    parsed = {}
    for name in PAGES:
        parser = Links()
        page = (source / name).read_text()
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
                if url.scheme != 'https' or url.netloc != 'github.com':
                    raise ValueError(f'Unexpected external link: {link}')
                continue
            if url.netloc or url.query:
                raise ValueError(f'Unexpected relative link: {link}')
            target = unquote(url.path) or name
            if target not in FILES:
                raise ValueError(f'Link outside publication: {link}')
            if url.fragment and target in parsed and unquote(url.fragment) not in parsed[target].ids:
                raise ValueError(f'Unknown HTML anchor: {link}')
    return manifest


def build(source, output):
    source, output = Path(source), Path(output)
    validate(source)
    # Never clean an existing directory: callers must choose an empty staging path.
    if output.is_symlink() or output.exists():
        raise ValueError('Output must be a new directory')
    output.mkdir(parents=True)
    for name in FILES:
        shutil.copyfile(source / name, output / name)
    (output / '.nojekyll').write_text('')
    validate(output)
    if {p.name for p in output.iterdir()} != set(FILES) | {'.nojekyll'}:
        raise ValueError('Unexpected published file')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1] / 'docs/research')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(build(args.source, args.output))
