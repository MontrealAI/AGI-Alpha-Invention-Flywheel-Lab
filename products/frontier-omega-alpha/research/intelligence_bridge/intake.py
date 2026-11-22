"""Validate, independently observe and stage a narrow public research finding."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from pathlib import Path
from subprocess import SubprocessError
from urllib.parse import quote

from .. import scheduled
from ..__main__ import BridgeError, through_egress_proxy
from ..economic_alpha import observations as alpha_sources, study as alpha_study
from ..reflective_gate import assess_source_groups
from . import adapter

CAPSULE = 'frontier-omega-alpha/public-finding-capsule-v2'
RECORD = 'frontier-omega-alpha/research-finding-v2'
LEGACY_RECORD = 'frontier-omega-alpha/research-finding-v1'
LEDGER = 'frontier-omega-alpha/finding-ledger-v1'
METHODS = ('interactive-connector', 'manual-export')
VERSION = re.compile(r'(?:v?|therock-)\d{1,6}(?:\.\d{1,6}){1,3}(?:-(?:rc|beta|alpha)\d{0,2})?\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')
GITHUB_SHA = re.compile(r'[0-9a-f]{40}\Z')
LOGIN = re.compile(r'[A-Za-z0-9-]{1,39}(?:\[bot\])?\Z')
STAMP = re.compile(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z')
DAY = re.compile(r'\d{4}-\d\d-\d\d\Z')
INBOX = 'products/frontier-omega-alpha/research/intelligence_bridge/inbox/'
PRUSA = ('release', 'upgrade', 'stock', 'large')
LEAN_NOTES = 'https://lean-lang.org/doc/reference/latest/releases/v4.36.0/'
HOLDS = {'source-insufficient', 'contradicted', 'invalidated', 'falsified', 'waiting'}
MAX_ENTRIES = 512


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def exported_capsule(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode()


def digest(value):
    return sha256(canonical(value)).hexdigest()


def utcstamp(now):
    return now.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def time_value(value):
    if not isinstance(value, str) or not STAMP.fullmatch(value):
        raise ValueError('Use UTC ISO time with whole seconds')
    return datetime.fromisoformat(value)


def distinct_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Ambiguous duplicate JSON key')
        result[key] = value
    return result


def load_json(raw, limit=4096):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= limit:
        raise ValueError('Unexpected payload size')
    return json.loads(raw, object_pairs_hook=distinct_object)


def capsule(raw, now=None):
    value = load_json(raw)
    if value is None:
        return None
    if (not isinstance(value, dict) or set(value) != {'schema', 'classification', 'profile',
            'source', 'version', 'baseline', 'created_at', 'observed_at', 'method'}
            or value['schema'] != CAPSULE or value['classification'] != 'public-evidence'
            or value['method'] not in METHODS):
        raise ValueError('Invalid or prohibited finding scope')
    created, observed = time_value(value['created_at']), time_value(value['observed_at'])
    now = now or datetime.now(timezone.utc)
    if observed > created or created > now + timedelta(minutes=5):
        raise ValueError('Inconsistent finding times')
    if value['profile'] == 'prusa-retrofit':
        if tuple(value[key] for key in ('source', 'baseline', 'version')) != ('prusa', 'stock-290', 'ht-400-2026-10-21'):
            raise ValueError('Unregistered OEM event and comparator')
    elif value['profile'] == 'hf-harness-adapter':
        if (value['source'] != 'qwen_harness_adapter' or value['baseline'] == value['version']
                or any(not isinstance(value[key], str) or not GITHUB_SHA.fullmatch(value[key])
                       for key in ('baseline', 'version'))):
            raise ValueError('Use the registered adapter and immutable GGUF revisions')
    elif value['profile'] in ('upstream-release', 'lean-bitvector'):
        if (not isinstance(value['source'], str) or value['source'] not in scheduled.SOURCES
                or any(not isinstance(value[key], str) or len(value[key]) > 40 or not VERSION.fullmatch(value[key])
                       for key in ('baseline', 'version'))
                or value['baseline'] == value['version']):
            raise ValueError('Unregistered publisher or tag')
        if value['profile'] == 'lean-bitvector' and tuple(value[key] for key in ('source', 'baseline', 'version')) != (
                'formal_verification', 'v4.35.0', 'v4.36.0'):
            raise ValueError('No registered Lean capability experiment for those versions')
    else:
        raise ValueError('Unknown public evidence profile')
    return value


def opportunity_id(value):
    return value['source']


def event_id(value):
    # A dated release has one identity across declared methods, timestamps and profile upgrades.
    return digest({key: value[key] for key in ('schema', 'source', 'version')})


def fetch_evidence(value, transport=through_egress_proxy, oem=alpha_sources.observe_source):
    if value['profile'] == 'hf-harness-adapter':
        return adapter.observe(value['baseline'], value['version'], transport), None, adapter.RELEASE_DAY, True
    if value['profile'] == 'prusa-retrofit':
        protocol = alpha_study.named('protocol.json')
        with ThreadPoolExecutor(max_workers=4) as pool:
            sources = dict(pool.map(oem, ((name, protocol['sources'][name]) for name in PRUSA)))
        observed = {'acquired_utc': utcstamp(datetime.now(timezone.utc)), 'sources': sources}
        alpha_sources.assert_observation(observed, protocol)
        rows = [{'id': key, 'url': item['url'], 'sha256': item['sha256'], 'publisher': 'prusa',
                 'version': value['version'], 'published_on': protocol['after'] if key == 'release' else None,
                 'effective_on': protocol['after'], 'evidence_location': item['identity']} for key, item in sources.items()]
        return rows, observed, protocol['after'], True
    repo, _ = scheduled.SOURCES[value['source']]
    endpoints = {key: f'https://api.github.com/repos/{repo}/releases/tags/' + quote(value[key], safe='')
                 for key in ('baseline', 'version')}
    old = scheduled.fetch_release(endpoints['baseline'], transport)
    new = scheduled.fetch_release(endpoints['version'], transport)
    published = datetime.fromisoformat(new['published_at'])
    if old['tag'] != value['baseline'] or new['tag'] != value['version'] or old['id'] == new['id'] or published <= datetime.fromisoformat(old['published_at']):
        raise ValueError('The publisher did not confirm an ordered version change')
    rows = [{'id': key, 'url': r['url'], 'sha256': r['sha256'], 'publisher': repo,
             'version': r['tag'], 'published_on': r['published_at'][:10], 'effective_on': r['published_at'][:10],
             'evidence_location': 'Release tag, release ID, and publication timestamp'}
            for key, r in (('baseline', old), ('current', new))]
    if value['profile'] == 'lean-bitvector':
        notes = transport(LEAN_NOTES, frozenset({'lean-lang.org'}))
        if (not HASH.fullmatch(notes['sha256']) or not all(term in notes['text'].casefold()
                for term in ('bv_decide', 'uninterpreted functions', '+uf'))):
            raise ValueError('The pinned upstream notes no longer support the registered feature')
        rows.append({'id': 'feature', 'url': LEAN_NOTES, 'sha256': notes['sha256'], 'publisher': repo,
                     'version': new['tag'], 'published_on': new['published_at'][:10], 'effective_on': new['published_at'][:10],
                     'evidence_location': 'Uninterpreted Functions in bv_decide'})
    return rows, None, new['published_at'][:10], value['profile'] == 'lean-bitvector'


def history(raw):
    ledger = load_json(raw, 512 * 1024)
    if not isinstance(ledger, dict) or set(ledger) != {'schema', 'entries'} or ledger['schema'] != LEDGER:
        raise ValueError('Invalid bridge ledger')
    if not isinstance(ledger['entries'], list) or len(ledger['entries']) > MAX_ENTRIES:
        raise ValueError('Invalid or full bridge ledger')
    for row in ledger['entries']:
        if (not isinstance(row, dict) or set(row) != {'id', 'scope', 'version', 'phase', 'effective_on', 'at', 'digest'}
                or not isinstance(row['id'], str) or not HASH.fullmatch(row['id'])
                or not isinstance(row['digest'], str) or not HASH.fullmatch(row['digest'])
                or row['scope'] not in {*scheduled.SOURCES, 'prusa', 'qwen_harness_adapter'}
                or not isinstance(row['version'], str) or (not VERSION.fullmatch(row['version'])
                    and not GITHUB_SHA.fullmatch(row['version']) and row['version'] != 'ht-400-2026-10-21')
                or (row['effective_on'] is not None and not DAY.fullmatch(row['effective_on']))
                or row['phase'] not in HOLDS | {'detected', 'experiment-prepared', 'technically-verified'}):
            raise ValueError('Invalid history entry')
        time_value(row['at'])
    return ledger


def ledger_change(ledger, row):
    if len(ledger['entries']) >= MAX_ENTRIES:
        raise ValueError('The reviewed ledger requires archival rollover')
    return {'schema': LEDGER, 'entries': ledger['entries'] + [row]}


def append_record(ledger, record):
    return ledger_change(ledger, {'id': record['finding_id'], 'scope': record['scope'], 'phase': record['status'],
                                  'version': record['change']['current'],
                                  'effective_on': record['effective_on'], 'at': record['reception']['received_at'],
                                  'digest': digest(record)})


def observe_again(ledger, finding, phase, now):
    if phase not in HOLDS - {'source-insufficient'}:
        raise ValueError('Only a documented hold or invalidation is permitted as a manual review')
    old = next((row for row in reversed(ledger['entries']) if row['id'] == finding), None)
    if not old or old['phase'] == phase:
        raise ValueError('No changed review decision for the requested finding')
    return ledger_change(ledger, {**old, 'phase': phase, 'at': utcstamp(now)})


def experiment_plan(value):
    if value['profile'] == 'hf-harness-adapter':
        return {'id': 'local-gguf-harness-adapter-matched-trial',
                'command': None,
                'comparison': 'Same pinned base, harness, settings and resources with and without the adapter, plus the best authorized incumbent',
                'acceptance': 'An independent task checker verifies 12–20 fresh maintenance tasks. Compare all costs, retries and human work.',
                'falsifier': 'Local load, acceptance, resource economy or strongest alternative defeats the proposed benefit',
                'purpose': 'Test whether an already trained adapter makes a local coding workflow more productive on authorized work',
                'asset_contract': 'Pinned weights, harness configuration and independent acceptance evidence',
                'successor': 'Transfer the matched process to a different authorized software task family',
                'bounded_runner': False}
    if value['profile'] == 'prusa-retrofit':
        return {'id': 'alpha-1-retrofit-replay', 'command': 'python3 -m research.economic_alpha qualify',
                'comparison': 'Same supported device, requirement and authorized data before and after the documented retrofit',
                'acceptance': 'The separately implemented SQL baseline reproduces each registered decision',
                'falsifier': 'The fitted route is unavailable or the hold/valid cases disagree',
                'purpose': 'Find supported retrofit paths for an installed platform with a binding nozzle limit',
                'asset_contract': 'Structured inquiry to source-grounded equipment-envelope decision',
                'successor': 'Qualify a distinct installed process with configuration, chamber and site evidence',
                'bounded_runner': True}
    if value['profile'] == 'lean-bitvector':
        return {'id': 'lean-4.36-black-box-bit-vector-congruence', 'command': 'python3 -m research.lean_delta',
                'comparison': 'Both pinned local toolchains, explicit congruence and grind on identical statements',
                'acceptance': 'New mode proves both valid cases and rejects the false case checked by enumeration',
                'falsifier': 'A valid case fails or the independent counterexample is accepted',
                'purpose': 'Verify fixed-width transformations behind an abstract function interface',
                'asset_contract': 'Two proof workloads and an independently enumerated false mutation',
                'successor': 'A different multi-stage obligation under the same complete alternative',
                'bounded_runner': False}
    return {'id': None, 'command': None, 'comparison': 'The named preceding release on identical inputs',
            'acceptance': None, 'falsifier': None, 'purpose': 'Investigate a source-linked release change',
            'asset_contract': None, 'successor': None, 'bounded_runner': False}


def check_reception(reception):
    if not isinstance(reception, dict) or set(reception) != {'submitted_at', 'submitter', 'github_pr', 'commit_sha', 'authenticated_by'}:
        raise ValueError('Unexpected reception metadata')
    if reception['authenticated_by'] == 'github-rest':
        if (not isinstance(reception['submitter'], str) or not LOGIN.fullmatch(reception['submitter'])
                or type(reception['github_pr']) is not int or reception['github_pr'] <= 0
                or not isinstance(reception['commit_sha'], str) or not GITHUB_SHA.fullmatch(reception['commit_sha'])):
            raise ValueError('Invalid authenticated GitHub reception')
    elif reception['authenticated_by'] != 'local-only' or any(reception[key] is not None for key in ('submitter', 'github_pr', 'commit_sha')):
        raise ValueError('Local preview cannot claim GitHub authentication')


def receive(raw, ledger, reception, now=None, evidence=fetch_evidence, run_registered=False):
    now = now or datetime.now(timezone.utc)
    value = capsule(raw, now)
    if value is None:
        return {'disposition': 'no-finding', 'record': None, 'ledger': ledger}
    check_reception(reception)
    finding = event_id(value)
    scope = opportunity_id(value)
    # Previously approved records used a different ID. Deduplicate on the public release across schemas.
    previous = next((item for item in reversed(ledger['entries'])
                     if item['scope'] == scope and item['version'] == value['version']), None)
    advance = previous and ((previous['phase'] == 'experiment-prepared' and run_registered and value['profile'] == 'prusa-retrofit')
                            or (previous['phase'] == 'detected' and value['profile'] == 'lean-bitvector'))
    if previous and previous['phase'] != 'source-insufficient' and not advance:
        return {'disposition': 'duplicate', 'record': None, 'ledger': ledger}
    observed = time_value(value['observed_at'])
    submitted = time_value(reception['submitted_at'])
    if time_value(value['created_at']) > submitted or submitted > now + timedelta(minutes=5):
        raise ValueError('Finding times are inconsistent with submission')
    try:
        sources, inputs, effective, material = evidence(value)
        if observed.date().isoformat() < effective:
            raise ValueError('Finding predates the verified public change')
    except (BridgeError, KeyError, OSError, ValueError, SubprocessError):
        sources, inputs, effective, material = [], None, None, False
    status = 'source-insufficient' if not sources else 'experiment-prepared' if material else 'detected'
    if previous and not sources:
        return {'disposition': 'source-insufficient-repeat', 'record': None, 'ledger': ledger}
    old = next((entry for entry in reversed(ledger['entries']) if entry['scope'] == scope and entry['effective_on']
                and entry['version'] == value['baseline']), None)
    reopened = bool(old and old['phase'] in HOLDS and effective and effective > old['effective_on'] and material)
    plan = experiment_plan(value)
    experiment = None
    if run_registered and status == 'experiment-prepared' and plan['bounded_runner']:
        try:
            tested = alpha_study.qualify(inputs)
            experiment = {key: tested[key] for key in ('verification', 'cost_observations', 's1_asset_sha256')}
            status = 'technically-verified'
        except ValueError:
            experiment = {'verdict': 'registered comparison falsified or source freeze mismatched'}
            status = 'falsified'
    record = {
        'schema': RECORD, 'finding_id': finding, 'scope': scope, 'profile': value['profile'],
        'classification': 'public-evidence', 'created_at': value['created_at'], 'observed_at': value['observed_at'],
        'effective_on': effective, 'status': status, 'reopened': reopened, 'source_evidence': sources,
        'reception': {**reception, 'declared_method': value['method'], 'received_at': utcstamp(now),
                      'task_origin': 'operator-declared, task authorship unverified'},
        'change': {'publisher_profile': value['source'], 'prior': value['baseline'], 'current': value['version'],
                   'material_constraint_link': material, 'reported_improvement': None,
                   'independently_measured': experiment['verification'] if status == 'technically-verified' else None,
                   'access_and_license': ('Pinned public Apache-2.0 GGUF records. Local capacity and task authority remain to be qualified.'
                                          if value['profile'] == 'hf-harness-adapter' else 'Verify on approved source and actual permitted deployment'),
                   'uncertainty': 'A publisher record alone cannot establish capability or independent commercial evidence'},
        'opportunity': {'purpose': plan['purpose'], 'binding_condition': plan['comparison'], 'missing_means': plan['id'],
                        'structural_transfer': None, 'beneficiary': None, 'payer': None,
                        'permissions': 'Owner approval for deployment, private data, payments and publication',
                        'existing_alternative': plan['comparison']},
        'evaluation': {**plan, 'input_lock': [item['artifact'] for item in sources if 'artifact' in item],
            'identical_inputs_and_authority': True, 'independence': assess_source_groups(
            item['publisher'] for item in sources), 'complete_cost_categories': alpha_study.named('protocol.json')['cost_categories'],
            'resources': 'Only reviewed local or standard GitHub compute', 'experiment_receipt': experiment},
        'asset': {'verified_identity': experiment['s1_asset_sha256'] if status == 'technically-verified' else None,
                  'contract': plan['asset_contract'], 'reuse_benefit': None, 'successor': plan['successor'],
                  'rejection_condition': plan['falsifier']},
        'economics': {key: None for key in ('hypothesized_value', 'technical_improvement', 'beneficiary_acceptance',
                                           'funds_collected', 'complete_cost_net', 'incremental_advantage', 'repeatability', 'causal_successor')},
        'production_authority': False,
    }
    return {'disposition': status, 'record': record, 'ledger': append_record(ledger, record)}


def public_projection(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
        raise ValueError('Use a local reviewed public capsule')
    with path.open('rb') as stream:
        return stream.read(4097)
