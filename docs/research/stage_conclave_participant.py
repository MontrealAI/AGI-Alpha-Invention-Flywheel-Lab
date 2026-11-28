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
PRODUCTION_ARCHIVE = 'AGI-CLUB-OMEGA-PARTICIPANT-PRODUCTION.zip'
EDITIONS = {
    ARCHIVE: dict(sha256=SHA256, bytes=BYTES, files=COUNT, expanded=UNPACKED_BYTES),
    PRODUCTION_ARCHIVE: dict(sha256='79d62975b108be36c99caf321951eb34200e9b5a6e07980e5b178f02aa448152', bytes=267239031,
                            files=274, expanded=286478749),
}
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


def qualify_portal_layout(folder, recorded):
    """Apply a narrow web-only layout repair after authenticating the release.

    The downloadable ZIP is unchanged. The projected web manifest identifies
    the actual published bytes; the edition receipt records the exact delta.
    """
    name = 'assets/production.css'
    css = folder / name
    before = '6e31bc1ae3183b20d47961216cd6c6d30934969ee486824a30adc892882b9b3a'
    after = '0e4c5e7062c0b53c02b721c8f10fa42465b081bd878ebd7475527850f6fdfca8'
    require(recorded.get(name) == before and digest(css) == before,
            'Unexpected source stylesheet for the Conclave layout repair')
    old = b'.card>img{width:100%;aspect-ratio:16/9;object-fit:cover}'
    new = b'.card>img{width:100%;height:auto;aspect-ratio:16/9;object-fit:cover}'
    raw = css.read_bytes()
    require(raw.count(old) == 1, 'Unexpected Conclave card layout rule')
    fixed = raw.replace(old, new)
    require(hashlib.sha256(fixed).hexdigest() == after, 'Unexpected corrected stylesheet')
    manifest = folder / MANIFEST
    original_manifest = manifest.read_bytes()
    old_record = (before + '  ' + name).encode('ascii')
    new_record = (after + '  ' + name).encode('ascii')
    require(original_manifest.count(old_record) == 1, 'Missing original stylesheet receipt')
    corrected_manifest = original_manifest.replace(old_record, new_record)
    css.write_bytes(fixed)
    manifest.write_bytes(corrected_manifest)
    return {'schema': 1, 'repair': 'landscape-card-intrinsic-height',
            'css': name, 'source_css_sha256': before, 'published_css_sha256': after,
            'source_manifest_sha256': hashlib.sha256(original_manifest).hexdigest(),
            'published_manifest_sha256': hashlib.sha256(corrected_manifest).hexdigest()}


def stage(site, archive):
    site, archive = Path(site), Path(archive)
    require(site.is_dir() and not site.is_symlink() and (site / 'frontier-conclave.html').is_file(),
            'Stage only into the built Conclave site')
    target = site / DEST
    require(not target.exists() and not target.is_symlink(), 'Participant destination already exists')
    edition = EDITIONS.get(archive.name)
    require(edition is not None and archive.stat().st_size == edition['bytes']
            and digest(archive) == edition['sha256'],
            'Release asset does not match an approved participant archive')
    require(site_bytes(site) + edition['expanded'] + 1024 <= SITE_LIMIT, 'Pages site would exceed 1 GB')
    with tempfile.TemporaryDirectory(prefix='.conclave-stage-', dir=site.parent) as tmp:
        staging = Path(tmp) / DEST
        folder = staging / ROOT
        folder.mkdir(parents=True)
        files, folded = set(), set()
        with zipfile.ZipFile(archive) as package:
            entries = package.infolist()
            require(len(entries) == edition['files'] and sum(i.file_size for i in entries) == edition['expanded'],
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
        if archive.name == PRODUCTION_ARCHIVE:
            require({'assets/production/' + x + '.webp' for x in ('arrival', 'flywheel', 'sanctum', 'horizon')} <= files,
                    'Missing production artwork')
            require({'03-INTELLECTUAL-ATLAS/Production-Orientation.pdf',
                     '05-FRONTIER-PLAYBOOK/First-Loop-Production-Canvas.pdf',
                     '07-AGI-CLUB-EDITION/Production-Member-Guide.pdf'} <= files,
                    'Missing current production material')
        meta = {'schema': 1, 'tag': TAG, 'archive': archive.name, 'sha256': edition['sha256'],
                'bytes': edition['bytes'], 'files': edition['files'], 'root': ROOT}
        if archive.name == PRODUCTION_ARCHIVE:
            meta['web_layout'] = qualify_portal_layout(folder, recorded)
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
