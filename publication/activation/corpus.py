"""Freeze evidence packet requests and their public byte identities."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from zipfile import ZipFile

from inventory import BASE, ROOT
from packets import PACKS, allowed
from pages import PAGES, REPO, canonical, digest

HARNESS='39e76570c851b3527d78a526053a9ea2a611a993'
GROUPS={
    'learning-replay': (PACKS[3], (
        ('receipt',3,'check.py reproduce.py study/verification.json'),
        ('model',3,'learning.py study/training.json study/cohort/inputs.json'),
        ('fit',4,'check.py learning.py study/cohort/fit.json study/cohort/inputs.json'),
        ('operate',3,'operate.py pages.py study/operation.json'),
        ('construct',4,'research.py wasm_policy.py study/runs.json requirements-linux.txt'),
        ('diagnose',2,'research.py study/verification.json study/runs.json'),
        ('validation',5,'check.py self_test.py study/cohort/development.json study/cohort/confirmation.json study/training.json'),
        ('runtime',4,'provider.py research.py study.py wasm_policy.py bridge/adapters.py'),
        ('learning-history',5,'study/cohort/fit.json study/cohort/development.json study/cohort/inputs.json study/cohort/confirmation.json'),
        ('policy-study',4,'study/run_study.py study/runs.json research.py wasm_policy.py'),
        ('portable-policy',3,'wasm_policy.py research.py requirements-linux.txt'),
        ('public-witness',2,'study/operation.json study/verification.json pages.py'),
    )),
    'local-runner': (PACKS[1], (
        ('local-provider',2,'provider.py local.example.json'),
        ('instrument',3,'harness-engine.js formulas.py foundry-core.mjs'),
        ('study-bridge',3,'provider.py study.py study-cli.mjs'),
        ('portable-packet',4,'foundry-study.mjs study-seal.mjs outcome-receipt.mjs study-cli.mjs'),
        ('handoff',2,'bridge/adapters.py bridge/instruments.py bridge/streaming.py provider.py'),
        ('noaa-replay',2,'retained/noaa-cases.json retained/noaa-window.json retained/qualification.json'),
        ('strict-provider',4,'bridge/adapters.py bridge/output_schema.py bridge/streaming.py local.example.json'),
        ('baseline-program',3,'provider.py formulas.py harness-engine.js'),
        ('study-proof',3,'successor-study/cases.json successor-study/report.json successor-study/source.json'),
        ('fresh-proof',3,'successor-followup/cases.json successor-followup/report.json successor-followup/source.json'),
        ('evaluation-runtime',4,'foundry-study.mjs study-seal.mjs study.py study-cli.mjs outcome-receipt.mjs'),
        ('independent-workshop',4,'foundry-core.mjs foundry-cli.mjs formulas.py local.example.json provider.py'),
    )),
    'inventor-audit': (PACKS[2], (
        ('base-trial',3,'inventor_verify.py study/evidence.json study/reproduction.json'),
        ('runtime',4,'inventor.py relational.py provider.py local.example.json'),
        ('diagnostic-cases',2,'study/diagnostic-evidence.json study/diagnostic-reproduction.json'),
        ('independent',3,'relational.py inventor_verify.py reproduce.py'),
        ('trace',2,'study/evidence.json study/reproduction.json study/protocol.py'),
        ('stronger-model',3,'study/larger-evidence.json study/larger-reproduction.json reproduce.py'),
        ('protected-challenge',4,'study/run_pilot.py study/protocol.py inventor_verify.py study/reproduction.json'),
        ('failure-replay',4,'study/diagnostic-evidence.json study/diagnostic-reproduction.json reproduce.py relational.py'),
        ('calibration-switch',3,'study/RESOURCE-FOLLOWUP.md local.example.json provider.py study.py'),
        ('larger-shared',5,'study/larger-evidence.json study/larger-reproduction.json study/run_pilot.py inventor.py inventor_verify.py'),
        ('negative-result',3,'study/REPORT.md study/larger-evidence.json study/diagnostic-evidence.json'),
        ('lowest-footprint',2,'study/REGISTRATION.md study/protocol.py'),
    )),
}


def repository(*args):
    return subprocess.check_output(('git',*args),cwd=ROOT)


def read_public(public):
    raw=(public/'atlas-release.json').read_bytes()
    release=json.loads(raw)
    if release['source_commit']!=BASE:
        raise ValueError('RELEASE_SOURCE')
    catalogue={}
    manifests={}
    counts={}
    for name in PACKS:
        path=public/name
        body=path.read_bytes()
        binding=sha256(body).hexdigest()
        if binding!=release['foundry_sha256'][name]:
            raise ValueError('RELEASE_PACKAGE_DRIFT')
        with ZipFile(path) as zip_:
            manifest=json.loads(zip_.read('manifest.json'))['file_sha256']
            for key,hash_ in manifest.items():
                data=zip_.read(key)
                if sha256(data).hexdigest()!=hash_:
                    raise ValueError('ARCHIVE_FILE_DRIFT')
                counts[hash_]=len(data)
        key='a:'+name
        manifests[name]=manifest
        catalogue[key]={'url':PAGES+name,'kind':'archive','bytes':len(body),'sha256':binding,
                        'supplies':sorted(set(manifest.values()))}
    return catalogue,manifests,counts,sha256(raw).hexdigest()


def pinned_sources(target,catalogue):
    scopes=((BASE,('products/frontier-member-tools','publication/inventor','publication/adaptive',
                   'publication/frontier-foundry')),
            (HARNESS,('products/alpha-genesis-harness/bridge','products/alpha-genesis-harness/LICENSE',
                      'products/alpha-genesis-harness/NOTICE')))
    found={}
    for sha,roots in scopes:
        entries=repository('ls-tree','-r','--name-only',sha,'--',*roots).decode().splitlines()
        for name in entries:
            raw=repository('show',f'{sha}:{name}')
            fingerprint=sha256(raw).hexdigest()
            if fingerprint in target and fingerprint not in found:
                source={'url':f'https://raw.githubusercontent.com/{REPO}/{sha}/{name}',
                        'kind':'direct','sha256':fingerprint,'bytes':len(raw),'supplies':[fingerprint]}
                if allowed(source):
                    found[fingerprint]=source
    for fingerprint,source in found.items():
        catalogue['d:'+fingerprint]=source
    return len(found)


def build(public):
    sources,manifests,sizes,release=read_public(public)
    cases={}
    all_targets=set()
    for name,(archive,groups) in GROUPS.items():
        split={'development':[],'confirmation':[]}
        for number,(slug,cap,names) in enumerate(groups):
            files=names.split()
            identifiers=[manifests[archive][file] for file in files]
            all_targets.update(identifiers)
            split['development' if number<6 else 'confirmation'].append({
                'id':name+'/'+slug,'objective':name,'cap':cap,'archive':'a:'+archive,
                'required':identifiers,'files':dict(zip(files,identifiers)),
                'required_bytes':sum(sizes[k] for k in identifiers)})
        cases[name]=split
    distinct=pinned_sources(all_targets,sources)
    if distinct<16:
        raise ValueError('INSUFFICIENT_PINNED_DIRECT_SOURCES')
    return {'schema':'frontier/public-packet-corpus-v1','base':BASE,'release_sha256':release,
            'catalogue':sources,'families':cases}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('public',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    value=build(args.public)
    args.output.mkdir(mode=0o700,parents=True,exist_ok=True)
    data={'catalogue':value['catalogue'],**value['families']}
    parts={'catalogue':data.pop('catalogue')}
    for name,split in data.items():
        for label,rows in split.items():
            parts[f'{name}-{label}']=rows
    for label,part in parts.items():
        (args.output/f'{label}.json').write_bytes(canonical(part)+b'\n')
    receipt={k:v for k,v in value.items() if k not in ('catalogue','families')}
    receipt['commitments']={label:digest(part) for label,part in parts.items()}
    (args.output/'commitments.json').write_bytes(canonical(receipt)+b'\n')
    print({label:len(part) for label,part in parts.items()})
