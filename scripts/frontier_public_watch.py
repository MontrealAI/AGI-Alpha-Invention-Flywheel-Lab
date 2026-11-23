#!/usr/bin/env python3
"""Stage versioned public references from the FRONTIER watch inbox."""

from base64 import b64decode
from datetime import date, datetime
from hashlib import sha1, sha256
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from unicodedata import category
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPOSITORY = 'MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
INBOX = 'frontier-watch-public'
INBOX_FILE = 'publication/frontier-watch-refs.json'
INBOX_URL = f'https://api.github.com/repos/{REPOSITORY}/contents/{INBOX_FILE}?ref={INBOX}'
SCHEMA = 'frontier-omega-alpha/public-watch-references-v1'
HOLD_SCHEMA = 'frontier-omega-alpha/public-reference-holds-v1'
HOLDS = Path(__file__).resolve().parents[1] / 'publication/frontier-public-holds.json'
MARKER = '<!-- FRONTIER_PUBLIC_WATCH -->'
SITE = 'https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/'
PAGES = {'index.html': 'en', 'fr.html': 'fr'}
STREAMS = {
    'living-possibility-watch': 'Unseen Advantage Watch',
    'possible-now': 'Possible Now',
    'verified-invention-watch': 'Ω ALPHA — Verified Invention Watch',
}
REQUIRED = {'living-possibility-watch', 'possible-now'}
SOURCES = {
    'lean4': 'leanprover/lean4',
    'llama-cpp': 'ggml-org/llama.cpp',
    'vllm': 'vllm-project/vllm',
    'rocm': 'ROCm/rocm-systems',
    'ollama': 'ollama/ollama',
    'scipy': 'scipy/scipy',
}
ARXIV = re.compile(r'(\d{2}(?:0[1-9]|1[0-2])\.\d{4,5})v[1-9]\d{0,2}', re.ASCII)
NUMBER = r'(?:0|[1-9]\d{0,5})'
TAG = re.compile(
    rf'(?:v?|therock-){NUMBER}\.{NUMBER}\.{NUMBER}'
    r'(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?',
    re.ASCII,
)
SHA256 = re.compile(r'[0-9a-f]{64}', re.ASCII)
LABELS = {
    'en': {
        'empty': 'No qualifying public reference available.',
        'test': 'Matched test proposed',
        'watch': 'Awaiting further evidence',
    },
    'fr': {
        'empty': 'Aucune référence publique admissible pour le moment.',
        'test': 'Essai comparatif proposé',
        'watch': 'En attente de preuves supplémentaires',
    },
}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url, limit):
    request = Request(url, headers={'User-Agent': 'Frontier-Public-Watch/1.0', 'Cache-Control': 'no-cache'})
    with build_opener(NoRedirect()).open(request, timeout=12) as response:
        if response.status != 200 or response.url != url:
            raise ValueError('Unexpected evidence response')
        body = response.read(limit + 1)
    if not body or len(body) > limit:
        raise ValueError('Evidence response exceeds its byte limit')
    return body


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Ambiguous input keys')
        result[key] = value
    return result


def parse_holds(raw):
    if not 0 < len(raw) <= 16_384:
        raise ValueError('Invalid public release hold size')
    value = json.loads(raw, object_pairs_hook=unique_object)
    if (not isinstance(value, dict) or set(value) != {'schema', 'canonical_reference_sha256'}
            or value['schema'] != HOLD_SCHEMA):
        raise ValueError('Unexpected public release hold schema')
    hashes = value['canonical_reference_sha256']
    if (not isinstance(hashes, list) or len(hashes) > 128
            or not all(isinstance(item, str) and SHA256.fullmatch(item) for item in hashes)
            or len(hashes) != len(set(hashes))):
        raise ValueError('Invalid public release hold')
    return frozenset(hashes)


def parse_inbox(raw):
    if not 0 < len(raw) <= 4096:
        raise ValueError('Invalid inbox size')
    value = json.loads(raw, object_pairs_hook=unique_object)
    if (not isinstance(value, dict) or set(value) - {'schema', *STREAMS}
            or not REQUIRED.issubset(value) or value.get('schema') != SCHEMA):
        raise ValueError('Unexpected inbox schema')
    result = {}
    for stream in STREAMS:
        entries = value.get(stream, [])
        if not isinstance(entries, list) or len(entries) > 4:
            raise ValueError('Each monitor may select up to four current references')
        result[stream] = {}
        for item in entries:
            if (not isinstance(item, dict) or set(item) != {'source', 'ref', 'decision'}
                    or not all(isinstance(field, str) for field in item.values())
                    or item['decision'] not in ('test', 'watch')):
                raise ValueError('Unexpected public reference fields')
            source, ref = item['source'], item['ref']
            match = ARXIV.fullmatch(ref) if source == 'arxiv' else None
            if match:
                identity = f'arxiv:{match[1]}'
            elif source in SOURCES and len(ref) <= 64 and TAG.fullmatch(ref):
                identity = f'{source}:{ref}'
            else:
                raise ValueError('Unregistered source or invalid exact version')
            if identity in result[stream]:
                raise ValueError('Repeated reference in the same monitor')
            result[stream][identity] = item
    return result


class PaperMetadata(HTMLParser):
    def __init__(self, ref):
        super().__init__()
        self.fields = {}
        self.expected_citation = f'arXiv:{ref}'
        self.version_urls = {f'/abs/{ref}', f'https://arxiv.org/abs/{ref}'}
        self.citation = None
        self.version_confirmed = False

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == 'a':
            self.citation = [] if data.get('href') in self.version_urls else None
        if tag == 'meta':
            key = data.get('name')
            if key in ('citation_title', 'citation_arxiv_id', 'citation_online_date'):
                if key in self.fields or not data.get('content'):
                    raise ValueError('Ambiguous paper metadata')
                self.fields[key] = data['content']

    def handle_data(self, data):
        if self.citation is not None:
            self.citation.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.citation is not None:
            if ''.join(self.citation).strip() == self.expected_citation:
                self.version_confirmed = True
            self.citation = None


def evidence(item, request=fetch):
    source, ref = item['source'], item['ref']
    if source == 'arxiv':
        url = 'https://arxiv.org/abs/' + ref
        metadata = PaperMetadata(ref)
        metadata.feed(request(url, 256_000).decode('utf-8'))
        metadata.close()
        record = metadata.fields
        if record['citation_arxiv_id'] not in (ARXIV.fullmatch(ref)[1], ref) or not metadata.version_confirmed:
            raise ValueError('arXiv did not confirm the exact requested version')
        title = record['citation_title']
        published = date.fromisoformat(record['citation_online_date'].replace('/', '-')).isoformat()
    else:
        repository = SOURCES[source]
        tag = quote(ref, safe='')
        url = f'https://github.com/{repository}/releases/tag/{tag}'
        raw = request(f'https://api.github.com/repos/{repository}/releases/tags/{tag}', 128_000)
        release = json.loads(raw, object_pairs_hook=unique_object)
        if release['tag_name'] != ref or release['draft'] is not False or not release['published_at']:
            raise ValueError('The release is unavailable or does not match its tag')
        title = f'{repository} · {ref}'
        published = datetime.fromisoformat(release['published_at']).date().isoformat()
    if any(category(char) == 'Cf' for char in title):
        raise ValueError('Unexpected source title format')
    title = ' '.join(title.split())
    if not title or len(title) > 250 or any(ord(char) < 32 for char in title):
        raise ValueError('Unexpected source title length')
    return title, url, published


def read_inbox(request=fetch):
    value = json.loads(request(INBOX_URL, 16_384), object_pairs_hook=unique_object)
    if (value['type'] != 'file' or value['encoding'] != 'base64'
            or value['path'] != INBOX_FILE or type(value['size']) is not int or not 0 < value['size'] <= 4096):
        raise ValueError('Unexpected intake file')
    raw = b64decode(''.join(value['content'].splitlines()), validate=True)
    identity = sha1(f'blob {len(raw)}\0'.encode() + raw, usedforsecurity=False).hexdigest()
    if len(raw) != value['size'] or identity != value['sha']:
        raise ValueError('Intake file bytes do not match its Git blob')
    return parse_inbox(raw)


def collect(inbox, holds, request):
    seen = set()
    snapshot = {}
    for stream, items in inbox.items():
        references = []
        for identity, item in items.items():
            if identity in seen or sha256(identity.encode()).hexdigest() in holds:
                continue
            seen.add(identity)
            references.append((*evidence(item, request), item['decision']))
        snapshot[stream] = sorted(references, key=lambda row: (row[2], row[1]), reverse=True)
    return snapshot


def render(snapshot, language):
    labels = LABELS[language]
    cards = []
    for stream, name in STREAMS.items():
        entries = [
            '<li><a href="' + escape(url, quote=True) + '">' + escape(title) + '</a>'
            f'<p><time datetime="{published}">{published}</time> · {labels[decision]}</p></li>'
            for title, url, published, decision in snapshot[stream]
        ]
        results = f'<ul>{"".join(entries)}</ul>' if entries else f'<p>{labels["empty"]}</p>'
        cards.append(f'<article><h3>{name}</h3>{results}</article>')
    content = '\n'.join(cards)
    fingerprint = sha256(content.encode()).hexdigest()
    return f'<div class="watch-streams" data-frontier-feed="{fingerprint}">\n{content}\n</div>', fingerprint


def live_matches(filename, fingerprint, request):
    try:
        body = request(SITE + filename, 128_000)
    except HTTPError as error:
        if error.code == 404:
            return False
        raise
    return f'data-frontier-feed="{fingerprint}"'.encode() in body


def stage(directory, *, holds, periodic=False, request=fetch):
    snapshot = collect(read_inbox(request), holds, request)
    rendered = {}
    unchanged = periodic
    for filename, language in PAGES.items():
        path = directory / filename
        contents = path.read_text(encoding='utf-8')
        if contents.count(MARKER) != 1:
            raise ValueError('Wrong FRONTIER publication template')
        html, fingerprint = render(snapshot, language)
        unchanged = unchanged and live_matches(filename, fingerprint, request)
        rendered[path] = contents.replace(MARKER, html, 1)
    for path, contents in rendered.items():
        path.write_text(contents, encoding='utf-8')
    return not unchanged


if __name__ == '__main__':
    try:
        if len(sys.argv) != 3 or sys.argv[2] not in ('schedule', 'push', 'pull_request', 'workflow_dispatch'):
            raise ValueError('Expected the Pages directory and an authorized event')
        with HOLDS.open('rb') as source:
            holds = parse_holds(source.read(16_385))
        changed = stage(Path(sys.argv[1]), holds=holds, periodic=sys.argv[2] == 'schedule')
        print('true' if changed else 'false')
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        print('FRONTIER public references failed validation. No Pages publication was staged.', file=sys.stderr)
        sys.exit(1)
