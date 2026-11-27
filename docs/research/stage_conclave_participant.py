#!/usr/bin/env python3
"""Stage the exact approved participant ZIP; never stage the presenter master."""
import argparse
import hashlib
import json
import posixpath
import re
import shutil
import stat
import tempfile
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ARCHIVE = 'AGI-CLUB-OMEGA-PARTICIPANT-FINAL.zip'
TAG = 'frontier-conclave-participant-v2026.11.28'
SHA256 = 'c08b5e3432c2d5896e8f8d72845189947869acbef0fdc653540269e2aa155fa0'
BYTES = 265_584_373
COUNT = 259
UNPACKED_BYTES = 272_168_328
ROOT = 'AGI-CLUB-DOUBLE-FLYWHEEL'
DEST = 'conclave-participant'
MANIFEST = 'SHA256SUMS-COLLECTION.txt'
SITE_LIMIT = 1_000_000_000
TOPS = {'01-PRESENTATION', '03-INTELLECTUAL-ATLAS', '04-DOUBLE-FLYWHEEL',
        '05-FRONTIER-PLAYBOOK', '06-RESEARCH-LIBRARY', '07-AGI-CLUB-EDITION', 'assets',
        'START-HERE.html', 'START-HERE-FR.html', 'index.html', 'ART-GALLERY.html',
        'README-FIRST.txt', MANIFEST, 'VERIFICATION.txt'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def site_bytes(site):
    return sum(p.stat().st_size for p in site.rglob('*') if p.is_file())


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = []

    def handle_starttag(self, tag, attrs):
        self.values.extend(v for k, v in attrs if k in ('href', 'src', 'poster', 'data') and v)


def validate_paths(files, folder):
    for rel in sorted(files):
        if not rel.endswith('.html'):
            continue
        parser = Links()
        parser.feed((folder / rel).read_text(encoding='utf-8'))
        for link in parser.values:
            url = urlsplit(link)
            if url.scheme or url.netloc or not url.path:
                continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(rel), unquote(url.path)))
            require(target in files, f'Broken participant link: {rel}: {link}')


def stage(site, archive):
    site, archive = Path(site), Path(archive)
    require(site.is_dir() and not site.is_symlink() and (site / 'frontier-conclave.html').is_file(),
            'Stage only into the built Conclave site')
    target = site / DEST
    require(not target.exists() and not target.is_symlink(), 'Participant destination already exists')
    require(archive.name == ARCHIVE and archive.stat().st_size == BYTES and digest(archive) == SHA256,
            'Release asset does not match the approved participant archive')
    require(site_bytes(site) + UNPACKED_BYTES + 1024 <= SITE_LIMIT, 'Pages site would exceed 1 GB')
    with tempfile.TemporaryDirectory(prefix='.conclave-stage-', dir=site.parent) as tmp:
        staging = Path(tmp) / DEST
        folder = staging / ROOT
        folder.mkdir(parents=True)
        files, folded = set(), set()
        with zipfile.ZipFile(archive) as package:
            entries = package.infolist()
            require(len(entries) == COUNT and sum(i.file_size for i in entries) == UNPACKED_BYTES,
                    'Unexpected archive membership or expanded size')
            for item in entries:
                parts = item.filename.split('/')
                require(len(parts) >= 2 and parts[0] == ROOT and parts[1] in TOPS
                        and all(p not in ('', '.', '..') and not p.startswith('.') for p in parts)
                        and '\\' not in item.filename and '\x00' not in item.filename,
                        f'Unsafe or unapproved member: {item.filename}')
                rel = '/'.join(parts[1:])
                require(not item.is_dir() and not item.flag_bits & 1
                        and stat.S_IFMT(item.external_attr >> 16) in (0, stat.S_IFREG)
                        and not any(word in rel.lower() for word in ('presenter', 'private', '.pptx', 'credential'))
                        and rel.casefold() not in folded, f'Excluded or duplicate member: {rel}')
                files.add(rel)
                folded.add(rel.casefold())
                output = folder / rel
                output.parent.mkdir(parents=True, exist_ok=True)
                with package.open(item) as source, output.open('xb') as dest:
                    shutil.copyfileobj(source, dest)
        recorded = {}
        for line in (folder / MANIFEST).read_text(encoding='utf-8').splitlines():
            match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
            require(match is not None, 'Malformed participant checksum manifest')
            sha, name = match.groups()
            require(name in files and name not in recorded and name != MANIFEST, 'Unexpected manifest member')
            require(digest(folder / name) == sha, f'Participant member checksum mismatch: {name}')
            recorded[name] = sha
        require(set(recorded) == files - {MANIFEST}, 'Incomplete checksum coverage')
        require({f'06-RESEARCH-LIBRARY/papers/{i:02d}.pdf' for i in range(1, 23)} <= files,
                'Missing original research paper')
        for lang in ('EN', 'FR'):
            require(f'01-PRESENTATION/IMMERSIVE/films/Stellar-Journey-{lang}.mp4' in files, 'Missing film')
        validate_paths(files, folder)
        meta = {'schema': 1, 'tag': TAG, 'archive': ARCHIVE, 'sha256': SHA256,
                'bytes': BYTES, 'files': COUNT, 'root': ROOT}
        (staging / 'edition.json').write_text(json.dumps(meta, sort_keys=True) + '\n', encoding='utf-8')
        require(site_bytes(site) + site_bytes(staging) <= SITE_LIMIT, 'Pages site would exceed 1 GB')
        staging.rename(target)
    print(json.dumps(meta, sort_keys=True))


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--site', required=True, type=Path)
    cli.add_argument('--archive', type=Path)
    cli.add_argument('--size-only', action='store_true')
    args = cli.parse_args()
    if args.size_only:
        require(site_bytes(args.site) <= SITE_LIMIT, 'Final Pages site exceeds 1 GB')
        print(f'Pages bytes: {site_bytes(args.site)}')
    else:
        require(args.archive is not None, 'Supply the exact release archive')
        stage(args.site, args.archive)
