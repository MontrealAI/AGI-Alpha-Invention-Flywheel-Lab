"""Observe a finite, public release registry and preserve auditable opportunity candidates."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.parse import quote

from .__main__ import BridgeError, dump, retrieve_source, through_egress_proxy
from .lean_delta import EXPERIMENT as LEAN_EXPERIMENT, FEATURE as LEAN_FEATURE, VERSIONS as LEAN_VERSIONS

HOSTS = frozenset({'api.github.com'})
SCHEMA = 'frontier-omega-alpha/release-observations-v1'
SOURCES = {
    'formal_verification': ('leanprover/lean4', 'verification'),
    'local_models_and_quantization': ('ggml-org/llama.cpp', 'local inference'),
    'serving_cost': ('vllm-project/vllm', 'serving performance'),
    'hardware_runtime': ('ROCm/rocm-systems', 'accelerator compatibility'),
    'model_distribution': ('ollama/ollama', 'model portability'),
    'scientific_computing': ('scipy/scipy', 'scientific computation'),
}
TAG = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.+\-]{0,99}\Z')
SHA = re.compile(r'[a-f0-9]{64}\Z')


def fetch_release(url, transport):
    result = transport(url, HOSTS)
    release = json.loads(result['text'])
    tag = release.get('tag_name')
    if not isinstance(tag, str) or not TAG.fullmatch(tag) or type(release.get('id')) is not int or release['id'] < 1:
        raise ValueError('Invalid release identity')
    if release.get('draft') is not False or release.get('prerelease') is not False:
        raise ValueError('Unreleased source cannot become an observation')
    published = datetime.fromisoformat(release['published_at'].replace('Z', '+00:00'))
    if not published.tzinfo or published > datetime.now(timezone.utc):
        raise ValueError('Invalid publication time')
    if not SHA.fullmatch(result['sha256']):
        raise ValueError('Invalid document digest')
    return {'tag': tag, 'id': release['id'], 'published_at': published.isoformat(),
            'url': url, 'retrieved_at': result['retrieved_at'], 'sha256': result['sha256']}


def proposal(repo, facet, before, after):
    candidate = {
        'kind': 'reported_release_hypothesis',
        'newly_worth_attempting': f'Replay a matched {facet} experiment with the newly published {repo} release {after["tag"]}.',
        'why_earlier_was_harder': f'The recorded predecessor was {before["tag"]}. The new version and its exact feature delta require qualification.',
        'action': 'Choose one acceptance metric from the release’s primary documentation and preregister a before/after comparison.',
        'beneficiary': 'MONTREAL.AI operators with a reproducible workload in this category.',
        'existing_alternative': f'The exact preceding published release {before["tag"]} on the same workload.',
        'requirements': 'An approved release checksum, compatible runtime and bounded local or standard GitHub compute.',
        'falsification': 'A separately implemented reference test fails to reproduce an improvement beyond the registered tolerance.',
        'retained_asset': 'A version-pinned reproducer, the matched baseline and a reusable acceptance rule.',
        'technical_verification': 'pending',
        'beneficiary_acceptance': 'unproven',
        'payment': 'unproven',
        'net_economic_benefit': 'unproven',
    }
    if repo == 'leanprover/lean4' and (before['tag'], after['tag']) == tuple('v' + version for version in LEAN_VERSIONS):
        candidate.update(
            newly_worth_attempting='Verify that the new bv_decide +uf mode checks whether two calculations make equivalent calls to an abstract function.',
            why_earlier_was_harder='Lean 4.35 had no +uf mode. Compare against its existing grind and explicit congruence proofs.',
            action='Run the registered Lean release comparison on approved local toolchains.',
            beneficiary='MONTREAL.AI operators verifying fixed-width compiler or hardware transformations behind abstract interfaces.',
            existing_alternative='Lean 4.35 grind and explicit congruence proved with the established bv_decide tactic.',
            falsification='Lean 4.36 fails either true workload or accepts a false workload with an independently enumerated witness.',
            retained_asset='A parameterized proof pattern on both function arities and a finite independent reference.',
            registered_experiment=LEAN_EXPERIMENT,
            release_notes=LEAN_FEATURE,
        )
    return candidate


def observe_releases(previous, transport=retrieve_source):
    def check(item):
        ident, (repository, facet) = item
        base = f'https://api.github.com/repos/{repository}/releases'
        prior = previous.get(ident, {}).get('observed')
        try:
            latest = fetch_release(base + '/latest', transport)
            pointed = fetch_release(base + '/tags/' + quote(latest['tag'], safe=''), transport)
            fields = ('tag', 'id', 'published_at')
            if tuple(latest[key] for key in fields) != tuple(pointed[key] for key in fields):
                raise ValueError('Latest and version-pinned records disagree')
        except (BridgeError, ValueError, KeyError, AttributeError, TypeError):
            return ident, {'state': 'unavailable', 'observed': prior,
                           'uncertainty': 'The source was unavailable or its named release could not be verified.'}
        if not prior:
            state = 'first_observation'
        elif any(latest[field] != prior[field] for field in ('id', 'tag')):
            state = 'published_version_changed'
        elif latest['sha256'] != prior['sha256']:
            state = 'metadata_changed'
        else:
            state = 'unchanged'
        evidence = {'state': state, 'observed': latest, 'pinned': pointed, 'preceding': prior,
                    'uncertainty': 'This evidence verifies a publisher record. Capability and economic effects require experiments.'}
        if state == 'published_version_changed':
            evidence['opportunity'] = proposal(repository, facet, prior, latest)
        return ident, evidence

    with ThreadPoolExecutor(max_workers=3) as pool:
        return dict(pool.map(check, SOURCES.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--environment-egress', action='store_true')
    args = parser.parse_args()
    previous = {}
    if args.previous:
        if args.previous.is_symlink() or args.previous.stat().st_size > 64 * 1024:
            raise ValueError('Invalid release checkpoint')
        checkpoint = json.loads(args.previous.read_text())
        if checkpoint['schema'] != SCHEMA or set(checkpoint['sources']) != set(SOURCES):
            raise ValueError('Unexpected previous release registry')
        previous = checkpoint['sources']
    records = observe_releases(previous, through_egress_proxy if args.environment_egress else retrieve_source)
    if all(record['state'] == 'unavailable' for record in records.values()):
        raise SystemExit('Primary release sources unavailable. Prior checkpoint retained.')
    if previous and all(record['state'] == 'unchanged' for record in records.values()):
        return
    dump({'schema': SCHEMA, 'sources': records}, args.output)


if __name__ == '__main__':
    main()
