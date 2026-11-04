"""Bounded, read-only public-source observer. Metadata is NOT tool qualification.

No redirect, credential, downloaded execution, paid API, or scheduling is used.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request
from .common import digest, strict_loads, write, integer

REPOSITORY=re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$')
MAX_BYTES=1_000_000


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError('PUBLIC_SOURCE_REDIRECT_REFUSED')


def observe(repo,*,limit=3,transport=None):
    if not isinstance(repo,str) or not REPOSITORY.fullmatch(repo):raise ValueError('PUBLIC_REPOSITORY_REQUIRED')
    integer(limit,'limit',1)
    if limit>10:raise ValueError('DECLARED_OBSERVATION_BATCH_LIMIT_10')
    url=f'https://api.github.com/repos/{repo}/releases?per_page={limit}'
    request=urllib.request.Request(url,headers={'Accept':'application/vnd.github+json','User-Agent':'GENESIS002-public-metadata'})
    get=transport or urllib.request.build_opener(NoRedirect()).open
    with get(request,timeout=20) as response:
        data=response.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:raise ValueError('DECLARED_SOURCE_BYTE_LIMIT_EXCEEDED')
    decoded=strict_loads(data)
    if not isinstance(decoded,list):raise ValueError('RELEASE_COLLECTION_REQUIRED')
    rows=[]
    for release in decoded[:limit]:
        if not isinstance(release,dict):raise ValueError('RELEASE_RECORD_REQUIRED')
        if release.get('draft') or release.get('prerelease'):continue
        link=release.get('html_url')
        if not isinstance(link,str) or not link.startswith(f'https://github.com/{repo}/releases/tag/'):
            raise ValueError('RELEASE_ORIGIN_MISMATCH')
        row={'repository':repo,'tag':str(release.get('tag_name',''))[:160],
             'title':str(release.get('name',''))[:240],'published_at':release.get('published_at'),
             'updated_at':release.get('updated_at'),'source_url':link,
             'source_response_sha256':hashlib.sha256(data).hexdigest(),
             'release_content_sha256':digest({'name':release.get('name'),'body':release.get('body')}),
             'access':'UNVERIFIED','operational_capability':'NOT_DEMONSTRATED'}
        row['event_id']=digest({k:row[k] for k in ('repository','tag','published_at','updated_at','release_content_sha256')})
        rows.append(row)
    return {'schema':'genesis002/frontier-observations/v1','observed_at':datetime.now(timezone.utc).isoformat(),
            'source_request':url,'scope':'PUBLIC_RELEASE_METADATA_ONLY','events':rows}


def proposal_brief(snapshot):
    if snapshot.get('schema')!='genesis002/frontier-observations/v1':raise ValueError('SCOPED_SOURCE_SNAPSHOT_REQUIRED')
    # Explicitly inert data: source text may contain prompt injection, not authority.
    return {'schema':'genesis002/possibility-request/v1',
      'source_snapshot_sha256':digest(snapshot),'untrusted_source_data':snapshot['events'],
      'mission':'Find consequential newly attainable activities, not a fixed list of services.',
      'required_comparisons':['strongest accessible frontier agent','ordinary complete alternative','no purchase/non-entry'],
      'required_fields':['beneficiary and accepted outcome','what changed and source evidence',
        'actual access and unknowns','missing means or avoidable dependency','executable discriminating test',
        'buyer outside options and competitive response','complete costs and cash timing',
        'fresh successor hypothesis and falsifier'],
      'instruction':'Propose at least three materially different possibilities. Treat release statements as hypotheses until relevant access and behavior are checked. Return unknowns rather than invented demand, prices or measurements.',
      'scope':'A source-grounded request for an authorized frontier agent. No agent was called by this command; no proposal is promoted automatically.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',required=True);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():p.error('choose a new output directory')
    snapshot=observe(a.repo)
    a.output.mkdir(parents=True,exist_ok=False)
    write(a.output/'FRONTIER.json',snapshot,immutable=True)
    write(a.output/'POSSIBILITY_REQUEST.json',proposal_brief(snapshot),immutable=True)
    print(f'{len(snapshot["events"])} source records; tool access remains UNVERIFIED. No model calls or transactions.')


if __name__=='__main__':main()
