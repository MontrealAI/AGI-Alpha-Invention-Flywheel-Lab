"""Read-only public GitHub release observer for GENESIS Frontier Observatory.

This does not classify release capabilities or verify user access. No tokens, spending,
network tools, remote code execution or changes to GitHub are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import urllib.request


_REPO = re.compile(r'^[A-Za-z0-9_.-]{1,80}/[A-Za-z0-9_.-]{1,100}$')


def get_public_releases(repo: str, limit: int = 3, transport=None) -> list[dict]:
    if not _REPO.fullmatch(repo) or not 1 <= limit <= 10:
        raise ValueError('public owner/repository and limit 1..10 required')
    url = f'https://api.github.com/repos/{repo}/releases?per_page={limit}'
    request = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'genesis-frontier-research-v0.1'})
    downloader = transport or urllib.request.urlopen
    with downloader(request, timeout=15) as response:
        blob = response.read(1_000_001)
    if len(blob) > 1_000_000:
        raise ValueError('release payload exceeds declared 1 MB limit')
    data = json.loads(blob)
    if not isinstance(data, list):
        raise ValueError('unexpected release payload')
    out = []
    for e in data[:limit]:
        if not isinstance(e, dict) or e.get('draft') or e.get('prerelease'):
            continue
        ref = str(e.get('html_url', ''))
        if not ref.startswith(f'https://github.com/{repo}/releases/tag/'):
            raise ValueError('release URL not on approved repository path')
        out.append({'repository': repo, 'url': ref, 'tag': str(e.get('tag_name', ''))[:160],
                    'published_at': e.get('published_at'), 'name': str(e.get('name') or '')[:240],
                    'source': 'public_github_release_metadata',
                    'access': 'UNVERIFIED', 'operational_capability': 'NOT_DEMONSTRATED',
                    'source_response_sha256': hashlib.sha256(blob).hexdigest()})
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', action='append', required=True,
                   help='public GitHub owner/repo; repeated for multiple repositories')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        p.error('output already exists; previous observations are preserved')
    records = []
    for repo in sorted(set(a.repo)):
        records += get_public_releases(repo)
    a.out.mkdir(parents=True)
    (a.out / 'frontier_events.json').write_text(json.dumps({
        'scope': 'PUBLIC_RELEASE_METADATA_ONLY',
        'not_established': ['user access', 'operational capability', 'commercial opportunity',
                             'global frontier completeness'], 'observations': records}, indent=2) + '\n')
    print(f'{len(records)} source-bound release records; no capability promotion')


if __name__ == '__main__':
    main()
