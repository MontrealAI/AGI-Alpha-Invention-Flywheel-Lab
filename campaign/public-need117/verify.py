#!/usr/bin/env python3
"""Independent source binding and confusion-count reviewer, not a model auditor."""
from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path


def verify(csv_path: Path, report_path: Path) -> bool:
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if report.get('schema') != 'agi-alpha/public-need117/sampled-perception-audit/v1':
        raise ValueError('SCHEMA_MISMATCH')
    if hashlib.sha256(csv_path.read_bytes()).hexdigest() != report.get('input_sha256'):
        raise ValueError('ORIGINAL_INPUT_CHANGED')
    with csv_path.open(encoding='utf-8', newline='') as stream:
        records = list(csv.DictReader(stream, strict=True))
    if len(records) != report.get('rows'):
        raise ValueError('ROW_COUNT_CHANGED')
    count = {}
    seen = set()
    for x in records:
        if x['case_id'] in seen:
            raise ValueError('REPEATED_CASE')
        seen.add(x['case_id'])
        g = count.setdefault(x['group'], {'total':0,'unlabeled':0,'abstained':0,'scored':0,'tp':0,'tn':0,'fp':0,'fn':0})
        g['total'] += 1
        if x['label'] == 'NA': g['unlabeled'] += 1
        if x['model_output'] == 'ABSTAIN': g['abstained'] += 1
        if x['label'] in ('0','1') and x['model_output'] in ('0','1'):
            g['scored'] += 1
            if x['label'] == '1': g['tp' if x['model_output']=='1' else 'fn'] += 1
            else: g['tn' if x['model_output']=='0' else 'fp'] += 1
    if set(count) != set(report['groups']):
        raise ValueError('GROUPS_CHANGED')
    for k,c in count.items():
        if any(report['groups'][k].get(field) != value for field,value in c.items()):
            raise ValueError('COUNTS_CHANGED:'+k)
        denom = c['scored']
        error = round((c['fn']+c['fp'])/denom, 6) if denom else None
        if report['groups'][k].get('observed_error_rate') != error:
            raise ValueError('ERROR_CHANGED:'+k)
    if any(report.get(k) is not None for k in ('population_prevalence_estimate','population_bias_certification','commercial_acceptance','actual_revenue_usd')):
        raise ValueError('UNSUPPORTED_CLAIM')
    if report['status'] not in ('UNQUALIFIED_DEMONSTRATION','BOUNDED_HELDOUT_DIAGNOSTIC'):
        raise ValueError('INVALID_STATUS')
    if report['status'] == 'BOUNDED_HELDOUT_DIAGNOSTIC' and (report['evidence_role'] != 'FROZEN_HELDOUT' or report['label_review_status'] != 'INDEPENDENTLY_REVIEWED'):
        raise ValueError('UNAUTHORIZED_QUALIFICATION')
    return True


if __name__ == '__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--csv',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    args=p.parse_args();verify(args.csv,args.report);print('INDEPENDENT_SAMPLE_REPLAY_ACCEPTED')
