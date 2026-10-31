"""Bounded current-source production experiment: direct specialist vs verified delta.

Numbers are local CPU telemetry and semantic work, never model billing or sales.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import sys
import time

from commercial import service, service_verifier, verified_delta as delta

PROTOCOL = {'schema':'agi-alpha/verified-delta-experiment/v1','seed':2610310044,
            'fixed_cases':[{'customers':12,'per_customer':3,'snapshots':30},
                           {'customers':80,'per_customer':5,'snapshots':30},
                           {'customers':100,'per_customer':5,'snapshots':50}],
            'scope':'PUBLIC_SYNTHETIC_EXPOSED_DEVELOPMENT_COMPARISON_NOT_FRESH_BLINDED_OR_COMMERCIAL',
            'case_selection':'The three sizes were chosen after preliminary exposed timing exploration, not prospectively preregistered.',
            'baseline':'Each snapshot current canonical service.reconcile + separate service_verifier.audit_delivery',
            'candidate':'Source-bound previous externally pinned per-customer proofs; fresh changed shard checks; full oracle after timed operation',
            'stopping_rule':'Exactly the registered three cases and snapshots; no outcome-based seed change.'}


def example(customers, per_customer):
    invoices,payments=[],[]
    for i in range(customers):
        for j in range(per_customer):
            identity=f'C{i:03d}-J{j:03d}'
            value=1000+17*i+13*j
            invoices.append({'id':'I-'+identity,'customer':f'C{i:03d}','amount_cents':value})
            payments.append({'id':'P-'+identity,'customer':f'C{i:03d}','amount_cents':value,'invoice_refs':['I-'+identity]})
    return {'scope':service.SCOPE,'currency':'USD','order_id':'VERIFIED-DELTA-044',
            'require_complete':True,'invoices':invoices,'payments':payments}


def case(spec):
    root=example(spec['customers'],spec['per_customer']);rng=random.Random(PROTOCOL['seed']+spec['customers'])
    snapshots=[copy.deepcopy(root)]
    for step in range(1,spec['snapshots']):
        i=rng.randrange(len(root['invoices']))
        root['invoices'][i]['amount_cents']+=step
        root['payments'][i]['amount_cents']+=step
        snapshots.append(copy.deepcopy(root))
    direct_result=[]
    start=time.process_time_ns()
    for current in snapshots:
        report=service.reconcile(current)
        checked=service_verifier.audit_delivery(current,report)
        if not checked['accepted'] or not report['accepted']:
            raise ValueError('CANONICAL_REFERENCE_NOT_ACCEPTED')
        direct_result.append(report)
    direct_cpu=time.process_time_ns()-start
    previous,pin=None,None
    audited_results=[];rows_checked=0;rows_scanned=0;reused=0
    start=time.process_time_ns()
    for current in snapshots:
        cert=delta.execute(current,previous,expected_previous_sha256=pin)
        checked=delta.verify(current,cert,previous,expected_previous_sha256=pin,full=False)
        if not checked['source_bound']:
            raise ValueError('UNVERIFIED_DELTA_OUTPUT')
        audited_results.append(cert['report'])
        rows_checked+=cert['semantic_rows_rechecked']
        rows_scanned+=cert['global_input_rows_scanned']
        reused+=cert['reused_groups']
        previous,pin=cert,delta.digest(cert)
    delta_cpu=time.process_time_ns()-start
    # A separately timed independent full oracle checks every output (cost excluded
    # from the candidate's steady-state measured operation, reported explicitly).
    confirm_start=time.process_time_ns()
    for index,current in enumerate(snapshots):
        independent=service_verifier.audit_delivery(current,audited_results[index])
        if direct_result[index] != audited_results[index] or not independent['accepted']:
            raise ValueError('DELTA_DISAGREES_WITH_STRONG_DIRECT_ORACLE')
    independent_cpu=time.process_time_ns()-confirm_start
    total=len(snapshots)*(len(root['invoices'])+len(root['payments']))
    return {'configuration':spec,'result':'ALL_BOUND_SYNTHETIC_OUTCOMES_EQUAL_AND_ACCEPTED',
            'direct_semantic_rows':total,'delta_semantic_rows':rows_checked,
            'global_validation_rows_delta':rows_scanned,
            'semantic_recheck_avoided_fraction':round(1-rows_checked/total,6),
            'reused_shard_observations':reused,
            'direct_cpu_ns':direct_cpu,'delta_cpu_ns':delta_cpu,
            'separately_charged_development_full_oracle_cpu_ns':independent_cpu,
            'candidate_to_direct_cpu_ratio':round(delta_cpu/direct_cpu,4),
            'conditional_preferred_method':'VERIFIED_DELTA' if delta_cpu<direct_cpu else 'DIRECT_SPECIALIST',
            'limitations':['Machine/ordering/load-specific CPU telemetry; not measured host billing.',
                           'Global input scan and hashing included in candidate time.',
                           'This is previously observed data with a deterministic authored update path.',
                           'Full independent oracle included in research, excluded from candidate production timing; production trust assumes verified pinned prior.']}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True)
    args=ap.parse_args();path=Path(args.output).absolute()
    if path.exists() or any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('NEW_NON_SYMLINK_PUBLIC_RECEIPT_REQUIRED')
    if not path.parent.is_dir():raise ValueError('EXISTING_RECEIPT_DIRECTORY_REQUIRED')
    rows=[case(spec) for spec in PROTOCOL['fixed_cases']]
    report={'protocol':PROTOCOL,'source_hashes':delta.sources(),
            'cases':rows,'actual_customers':0,'actual_collections':0,'actual_profit':None,
            'source_bound_product':True,'human_expert_forecast_comparator':'NOT_RUN',
            'new_discovery_policy_advantage':'NOT_ESTABLISHED',
            'scope':'CONDITIONAL_ENGINEERING_MECHANISM_NOT_BEYOND_HUMAN_SUPERIORITY',
            'next_experiment':'Cost actual production billing and compare strong partition-aware specialist under matched current-source customer workloads.'}
    path.write_bytes(delta.canonical(report))
    print(json.dumps({'output':str(path),'cases':rows,'source_hashes':report['source_hashes']},sort_keys=True))

if __name__=='__main__':main()
