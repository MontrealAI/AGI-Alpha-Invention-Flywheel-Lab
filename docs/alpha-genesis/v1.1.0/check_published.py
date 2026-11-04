#!/usr/bin/env python3
"""Compare a hosted publication with a LOCAL expected manifest.

Network access occurs only when this script is explicitly invoked with a base URL.
This checks served bytes, not hosting security, scientific truth or product readiness.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
from release_tools import read_manifest


def validate_base(url: str) -> str:
    parsed=urlsplit(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Base URL must not contain credentials, query or fragment.')
    local=parsed.hostname in ('127.0.0.1','localhost','::1')
    if not parsed.netloc or (parsed.scheme!='https' and not (parsed.scheme=='http' and local)):
        raise ValueError('Use HTTPS; HTTP is allowed only for a local preview.')
    return url.rstrip('/')+'/'


def check(base: str, manifest: Path) -> dict:
    base=validate_base(base)
    if manifest.name!='SHA256SUMS':raise ValueError('Expected manifest must be named SHA256SUMS.')
    entries=read_manifest(manifest.parent)
    checked=0; total=0
    for relative,expected in sorted(entries.items()):
        request=Request(base+quote(relative,safe='/'),headers={'User-Agent':'GENESIS-Publication-Check/1.1'})
        digest=hashlib.sha256();size=0
        with urlopen(request,timeout=30) as response:
            final=urlsplit(response.geturl());origin=urlsplit(base)
            if (final.scheme,final.netloc)!=(origin.scheme,origin.netloc):
                raise ValueError(f'Unexpected cross-origin redirect: {relative}')
            if response.status!=200:raise ValueError(f'HTTP {response.status}: {relative}')
            while chunk:=response.read(1024*1024):
                size+=len(chunk)
                if size>128*1024*1024:raise ValueError(f'Unexpectedly large response: {relative}')
                digest.update(chunk)
        if digest.hexdigest()!=expected:raise ValueError(f'Served bytes differ: {relative}')
        checked+=1;total+=size
    return {'status':'SERVED_BYTES_MATCH_LOCAL_MANIFEST','base_url':base,
            'files':checked,'bytes':total,'scope':'Publication delivery only; no GENESIS runtime test.'}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True)
    parser.add_argument('--expected',type=Path,required=True,help='Trusted local site/SHA256SUMS; not the source manifest.')
    args=parser.parse_args()
    try:print(json.dumps(check(args.base_url,args.expected),indent=2));return 0
    except (OSError,ValueError) as exc:print(f'Publication check failed: {exc}',file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
