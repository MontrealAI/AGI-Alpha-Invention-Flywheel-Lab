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
PAGES = ('index.html', 'foundry-v2.html', 'transformational-enterprises.html', 'out-reflect.html',
         'out-series.html', 'out-learn.html', 'out-think.html', 'out-design.html', 'out-strategise.html', 'out-execute.html', 'out-evolve.html')
FILES = PAPERS + PAGES + ('publication-manifest.json',)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.add(attrs['id'])
        for key in ('href', 'src', 'data'):
            if key in attrs:
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
        parser.feed((source / name).read_text())
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
