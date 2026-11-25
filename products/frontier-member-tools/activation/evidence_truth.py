"""Deterministic evidence adjudication on recorded public source projections."""

import argparse
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from itertools import combinations
from pathlib import Path
import re
from urllib.parse import urlsplit

from science_substrate import canonical, read_json


ROOT = Path(__file__).resolve().parent
STUDY = ROOT / 'study/factory'
HEX = re.compile(r'[0-9a-f]{64}\Z')
KEY = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.:+/-]{0,139}\Z')
STAMP = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z')
NUMBER = re.compile(r'-?(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,10})?\Z')
SCOPE = ('subject','quantity','unit','basis')
STAGE_ROLES = {
    'public_offer': ('manufacturer_offer','authorized_supplier_offer'),
    'software_support': ('first_party_release',),
    'machine_operation': ('observed_machine_run',),
    'fulfilled_order': ('observed_fulfillment',),
}
ROLES = {role for permitted in STAGE_ROLES.values() for role in permitted} | {'roadmap','media','documentation'}


def valid(condition, code):
    if not condition:
        raise ValueError(code)


def key(value):
    valid(type(value) is str and KEY.fullmatch(value) and '..' not in value.split('/'), 'IDENTITY')
    return value


def timestamp(value):
    valid(type(value) is str and STAMP.fullmatch(value), 'UTC_TIMESTAMP')
    datetime.fromisoformat(value)
    return value


def number(value):
    valid(type(value) is str and NUMBER.fullmatch(value), 'EXACT_NUMBER')
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise ValueError('EXACT_NUMBER') from error


def scope(data):
    return tuple(key(data[name]) for name in SCOPE)


def unique_map(rows, label):
    valid(type(rows) is list, label)
    result = {key(row['id']):row for row in rows}
    valid(len(result)==len(rows),label)
    return result


def sources(data):
    result = unique_map(data,'DUPLICATE_SOURCE')
    for item in result.values():
        url = urlsplit(item['url'])
        valid(url.scheme=='https' and url.hostname and not url.username and not url.password and not url.fragment,
              'PUBLIC_SOURCE_URI')
        proof = item['sha256']
        valid(type(proof) is str and HEX.fullmatch(proof), 'SOURCE_SHA256')
        valid(item['binding'] in ('source_bytes','verified_projection'), 'SOURCE_BINDING')
        timestamp(item['published_at'])
    return result


def root_sets(records, origins):
    """Each record retains the exact set of upstream evidence units it used."""
    roots = {}
    active = set()

    def resolve(name):
        if name in roots:
            return roots[name]
        valid(name not in active and len(active)<64, 'LINEAGE_CYCLE_OR_DEPTH')
        active.add(name)
        row = records[name]
        lineage = row['lineage']
        valid(type(lineage) is list and len(lineage)==len(set(lineage)), 'LINEAGE_DUPLICATE')
        parents = row['parents']
        valid(type(parents) is list and len(parents)==len(set(parents)), 'PARENT_DUPLICATE')
        valid(not (parents and lineage), 'AMBIGUOUS_LINEAGE')
        valid(all(root in origins for root in lineage) and all(parent in records for parent in parents),
              'LINEAGE_WITNESS_MISSING')
        resolved = frozenset(lineage)
        if parents:
            upstream = [resolve(parent) for parent in parents]
            # Missing evidence is contagious through aggregates.
            if all(upstream):
                resolved = frozenset().union(*upstream)
        active.remove(name)
        roots[name] = resolved
        return resolved

    for name in records:
        resolve(name)
    return roots


def reconcile(case, approved):
    expected_scope = scope(case)
    cutoff = timestamp(case['as_of'])
    tolerance = number(case['tolerance'])
    valid(tolerance>=0, 'NEGATIVE_TOLERANCE')
    origins = {key(name):kind for name,kind in case['origins'].items()}
    valid(set(origins.values()) <= {'physical','documentary','derived'}, 'ORIGIN_KIND')
    records = unique_map(case['records'],'DUPLICATE_OBSERVATION')
    roots = root_sets(records,origins)
    active, skipped = {}, {}
    for name,row in records.items():
        witness = approved[row['source']]
        valid(all(scope(records[parent])==scope(row)
                  and approved[records[parent]['source']]['published_at']<=witness['published_at']
                  for parent in row['parents']), 'INCOMPATIBLE_PARENT_SCOPE_OR_VINTAGE')
        if scope(row)!=expected_scope:
            skipped[name]='SCOPE_MISMATCH'
            continue
        if witness['published_at']>cutoff:
            skipped[name]='AFTER_CUTOFF'
            continue
        if row['interval'] is None:
            skipped[name]='VALUE_MISSING'
            continue
        valid(type(row['interval']) is list and len(row['interval'])==2,'MEASUREMENT_INTERVAL')
        low,high = map(number,row['interval'])
        valid(low<=high, 'REVERSED_INTERVAL')
        active[name]=(low,high)
    amended = set()
    for name in active:
        previous = records[name].get('supersedes',[])
        valid(type(previous) is list and all(old in records for old in previous), 'REVISION_WITNESS_MISSING')
        for old in previous:
            valid(bool(roots[name]) and roots[old]==roots[name] and scope(records[old])==expected_scope
                  and approved[records[old]['source']]['published_at']<approved[records[name]['source']]['published_at'],
                  'REVISION_SCOPE_OR_VINTAGE')
            if old in active:
                amended.add(old)
    for name in amended:
        active.pop(name)
        skipped[name]='SUPERSEDED_RELEASE'
    confirmed, dependent, unproved, conflicts = [], [], [], []
    for left,right in combinations(sorted(active),2):
        a,b = active[left],active[right]
        if max(a[0],b[0])>min(a[1],b[1])+tolerance:
            conflicts.append([left,right])
            continue
        if roots[left] & roots[right]:
            dependent.append([left,right])
            continue
        root_union = roots[left] | roots[right]
        if roots[left] and roots[right] and all(origins[item]=='physical' for item in root_union):
            confirmed.append([left,right])
        else:
            unproved.append([left,right])
    if conflicts:
        verdict = 'AMBIGUOUS_CONFLICT'
    elif confirmed:
        verdict = 'PHYSICAL_AGREEMENT'
    elif len(active)<2:
        verdict = 'INSUFFICIENT_RECORDS'
    elif dependent and not unproved:
        verdict = 'SHARED_UPSTREAM'
    else:
        verdict = 'INDEPENDENCE_UNESTABLISHED'
    return {'id':case['id'],'verdict':verdict,'physical_pairs':confirmed,'shared_pairs':dependent,
            'unproved_pairs':unproved,'conflicts':conflicts,'excluded':skipped,
            'lineage':{name:sorted(roots[name]) for name in sorted(active)}}


def offer_by(case, approved):
    stage = case['stage']
    valid(stage in STAGE_ROLES, 'PRODUCT_STAGE')
    bound = timestamp(case['as_of'])
    asked = {key(name):key(value) for name,value in case['scope'].items()}
    valid({'product','feature'}<=asked.keys(), 'PRODUCT_SCOPE')
    records = unique_map(case['records'],'DUPLICATE_PRODUCT_RECORD')
    observations = []
    rejected = {}
    for name,row in sorted(records.items()):
        source = approved[row['source']]
        role = row['role']
        valid(role in ROLES, 'PRODUCT_SOURCE_ROLE')
        actual = {key(field):key(value) for field,value in row['scope'].items()}
        stamp = timestamp(row['verified_by'])
        valid(stamp>=source['published_at'], 'UNBOUND_PRODUCT_DATE')
        if stamp>bound:
            rejected[name]='AFTER_CUTOFF'
        elif any(actual.get(field)!=value for field,value in asked.items()):
            rejected[name]='SCOPE_MISMATCH'
        elif role not in STAGE_ROLES[stage]:
            rejected[name]='INSUFFICIENT_EVIDENCE_ROLE'
        else:
            observations.append((stamp,name,row['source']))
    if observations:
        stamp,name,source = min(observations)
        result = {'verdict':'DOCUMENTED_BY_CUTOFF','first_verified_by':stamp,'witness':name,'source':source}
    else:
        result = {'verdict':'ABSTAIN_UNESTABLISHED','first_verified_by':None,'witness':None,'source':None}
    return {'id':case['id'],'stage':stage,**result,'excluded':rejected,
            'onset_established':False,'continuity_established':False}


def evaluate(study):
    valid(study['schema']=='frontier/evidence-truth-v1','STUDY_TYPE')
    approved = sources(study['sources'])
    operations = {'measurement':reconcile,'product_stage':offer_by}
    cases = unique_map(study['cases'],'DUPLICATE_CASE')
    return {name:operations[case['kind']](case,approved) for name,case in cases.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document',type=Path,nargs='?',default=STUDY/'EVIDENCE.json')
    parser.add_argument('--case',action='append',help='Select a registered case by ID')
    parser.add_argument('--registry',action='store_true',help='Show the bundled operating contracts')
    opts = parser.parse_args()
    if opts.registry:
        print(canonical(read_json(STUDY/'FACTORY.json')['registry']).decode())
        return
    data = read_json(opts.document)
    if opts.case:
        cases=unique_map(data['cases'],'DUPLICATE_CASE')
        valid(all(name in cases for name in opts.case) and len(set(opts.case))==len(opts.case),'CASE_SELECTION')
        data={**data,'cases':[cases[name] for name in opts.case]}
    result = evaluate(data)
    print(canonical({'input_sha256':sha256(opts.document.read_bytes()).hexdigest(),'outcomes':result}).decode())


if __name__=='__main__':
    main()
