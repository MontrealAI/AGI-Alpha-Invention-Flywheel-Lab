"""Local publication integrity checks. Hashes detect change, not publisher identity."""
from __future__ import annotations
import hashlib
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote, urlsplit

REQUIRED={'ALPHA_GENESIS_FLYWHEEL_OMEGA.pdf','ALPHA_GENESIS_FLYWHEEL_OMEGA.tex',
          'README.md','START_HERE.html','DEPLOYMENT.md','RELEASE_STATUS.json',
          'verify.py','release_tools.py','study/companion.py','study/results/results.json',
          'study/results/compiled_observer.py','study/results/measurement_plan.json',
          'study/results/lag.csv','source/CLAIM_REGISTER.md'}
IGNORED={'build','__pycache__','.git','runs'}


def source_files(root: Path) -> dict[str, Path]:
    root=root.resolve(); result={}
    for path in root.rglob('*'):
        rel=path.relative_to(root)
        if any(part in IGNORED for part in rel.parts) or path.name=='SHA256SUMS':
            continue
        if path.is_symlink():
            raise ValueError(f'Symlinks are not release files: {rel.as_posix()}')
        if path.is_file(): result[rel.as_posix()]=path
    return result


def read_manifest(root: Path) -> dict[str,str]:
    manifest=root/'SHA256SUMS'
    entries={}
    for line in manifest.read_text(encoding='utf-8').splitlines():
        match=re.fullmatch(r'([0-9a-f]{64})  (.+)',line)
        if not match: raise ValueError('Malformed checksum line.')
        digest,relative=match.groups(); path=PurePosixPath(relative)
        if (path.is_absolute() or '..' in path.parts or '\\' in relative or ':' in relative
            or path.as_posix()!=relative or relative in ('','SHA256SUMS','.')
            or any(part in IGNORED for part in path.parts)):
            raise ValueError(f'Unsafe or noncanonical release path: {relative}')
        if relative in entries: raise ValueError(f'Duplicate manifest path: {relative}')
        target=root/relative
        if not target.resolve().is_relative_to(root.resolve()) or target.is_symlink():
            raise ValueError(f'Release path escapes package: {relative}')
        entries[relative]=digest
    if not entries: raise ValueError('Empty checksum manifest.')
    return entries


def verify_manifest(root: Path) -> int:
    entries=read_manifest(root); files=source_files(root)
    if not REQUIRED <= set(entries):
        raise ValueError('Manifest omits required release files: '+', '.join(sorted(REQUIRED-set(entries))))
    if set(entries)!=set(files):
        raise ValueError('Manifest/file inventory mismatch: '+', '.join(sorted(set(entries)^set(files))))
    for rel,digest in entries.items():
        if hashlib.sha256(files[rel].read_bytes()).hexdigest()!=digest:
            raise ValueError(f'Hash mismatch: {rel}')
    return len(entries)


class Links(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.ids=set();self.inline_scripts=0
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.add(attrs['id'])
        if tag=='script' and 'src' not in attrs:self.inline_scripts+=1
        for name in ('href','src'):
            if name in attrs:self.links.append(attrs[name])


def check_html_links(root: Path) -> int:
    checked=0
    for page in sorted(root.glob('*.html')):
        parser=Links();parser.feed(page.read_text(encoding='utf-8'))
        if parser.inline_scripts:raise ValueError(f'Unexpected inline script in {page.name}')
        for link in parser.links:
            split=urlsplit(link)
            if split.scheme or split.netloc:
                if split.scheme not in ('https','mailto'):raise ValueError('Unsupported URL scheme.')
                continue
            target=(page.parent/unquote(split.path)).resolve() if split.path else page
            if not target.is_relative_to(root.resolve()) or not target.is_file():
                raise ValueError(f'Broken local link: {page.name} -> {link}')
            if split.fragment and target.suffix.lower()=='.html':
                other=Links();other.feed(target.read_text(encoding='utf-8'))
                if unquote(split.fragment) not in other.ids:raise ValueError(f'Broken anchor: {link}')
            checked+=1
    return checked
