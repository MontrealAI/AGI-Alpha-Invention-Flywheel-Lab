"""Bounded key-free public evidence extraction; never imports owner authority."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

MAX_FILES=10_000
MAX_BYTES=512*1024*1024


def _relative(name):
    p=PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or '\\' in name or p.as_posix()!=name:
        raise ValueError('CANONICAL_RELATIVE_ARCHIVE_PATH_REQUIRED')
    if any(part in {'.git','__pycache__'} for part in p.parts) or '.sqlite' in p.name or p.name.endswith(('.key','-key')):
        raise ValueError('PRIVATE_OR_UNREGISTERED_ARCHIVE_PATH')
    return p


def extract(archive,output):
    """Extract without running archive code; bounds include its integrity file."""
    output=Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in [output,*output.parents]):
        raise FileExistsError('NEW_PUBLIC_OUTPUT_REQUIRED')
    if not output.parent.is_dir():raise ValueError('EXISTING_OUTPUT_PARENT_REQUIRED')
    with zipfile.ZipFile(archive) as z:
        entries=z.infolist();names=set();total=0
        if len(entries)>MAX_FILES:raise ValueError('PUBLIC_ARCHIVE_GUARD_EXCEEDED')
        for info in entries:
            _relative(info.filename)
            mode=info.external_attr>>16
            if info.is_dir() or (stat.S_IFMT(mode) not in (0,stat.S_IFREG)) or info.flag_bits&1:
                raise ValueError('REGULAR_UNENCRYPTED_ARCHIVE_MEMBER_REQUIRED')
            if info.filename in names:raise ValueError('DUPLICATE_ARCHIVE_MEMBER')
            names.add(info.filename);total+=info.file_size
            if info.file_size<0 or total>MAX_BYTES:raise ValueError('PUBLIC_ARCHIVE_GUARD_EXCEEDED')
        if 'INTEGRITY.json' not in names:raise ValueError('PORTABLE_INTEGRITY_REQUIRED')
        # Small integrity budget is derived from archive limits, not a relaxed file bound.
        with tempfile.TemporaryDirectory(prefix='portable-import-',dir=output.parent) as tmp:
            root=Path(tmp);actual={};used=0
            for info in entries:
                p=root.joinpath(*PurePosixPath(info.filename).parts);p.parent.mkdir(parents=True,exist_ok=True)
                h=hashlib.sha256();size=0
                with z.open(info) as src,p.open('xb') as dst:
                    while True:
                        chunk=src.read(min(1024*1024,MAX_BYTES-used+1))
                        if not chunk:break
                        size+=len(chunk);used+=len(chunk)
                        if used>MAX_BYTES or size>info.file_size:raise ValueError('PUBLIC_ARCHIVE_GUARD_EXCEEDED')
                        h.update(chunk);dst.write(chunk)
                if size!=info.file_size:raise ValueError('ARCHIVE_SIZE_CHANGED')
                actual[info.filename]={'bytes':size,'sha256':h.hexdigest()}
            def unique(pairs):
                d={}
                for k,v in pairs:
                    if k in d:raise ValueError('DUPLICATE_INTEGRITY_KEY')
                    d[k]=v
                return d
            integrity=json.loads((root/'INTEGRITY.json').read_bytes(),object_pairs_hook=unique)
            if set(integrity)!={'files','bytes','guards'} or integrity['guards']!={'files':MAX_FILES,'bytes':MAX_BYTES}:
                raise ValueError('EXACT_PUBLIC_INTEGRITY_REQUIRED')
            actual.pop('INTEGRITY.json')
            if actual!=integrity['files'] or sum(x['bytes'] for x in actual.values())!=integrity['bytes']:
                raise ValueError('PORTABLE_INTEGRITY_MISMATCH')
            # Source identity and original signed tickets are independently checked by
            # the normal public auditor. This manifest is transport integrity only.
            output.mkdir()  # Exclusive creation: never replace a competing destination.
            for child in root.iterdir():os.rename(child,output/child.name)
    return {'extracted':True,'files':len(entries),'bytes':used,'output':str(output),'audit_performed':False}


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps(extract(a.archive,a.output),sort_keys=True))


if __name__=='__main__':main()
