#!/usr/bin/env python3
"""Independent CSV recount and bounded-claim verification, without importing generator."""
from __future__ import annotations
import csv
import hashlib
import json
import math
from pathlib import Path

SCHEMA = 'agi-alpha/public-need117/sampled-perception-audit/v1'
COLUMNS = ('case_id', 'period', 'group', 'label', 'model_output')
COUNTS = ('total', 'unlabeled', 'abstained', 'scored', 'tp', 'tn', 'fp', 'fn')
FIELDS = {'schema', 'input_sha256', 'input_filename', 'rows', 'evidence_role',
          'label_review_status', 'population_frame_status', 'status', 'groups',
          'population_prevalence_estimate', 'population_bias_certification',
          'commercial_acceptance', 'actual_revenue_usd', 'limitations'}


def _no_duplicate_pairs(pairs):
    d = {}
    for key, value in pairs:
        if key in d:
            raise ValueError('DUPLICATE_RECEIPT_FIELD')
        d[key] = value
    return d


def _interval(errors: int, total: int):
    if total == 0:
        return None
    p = errors / total
    z = 1.959963984540054
    d = 1 + z * z / total
    middle = (p + z*z/(2*total)) / d
    half_width = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total))/d
    return [round(max(0.0, middle-half_width), 6), round(min(1.0, middle+half_width), 6)]


def verify(csv_path: Path, report_path: Path) -> bool:
    raw_report = report_path.read_bytes()
    if len(raw_report) > 4_000_000:
        raise ValueError('BOUNDED_REPORT_REQUIRED')
    report = json.loads(raw_report, object_pairs_hook=_no_duplicate_pairs,
                        parse_constant=lambda _s: (_ for _ in ()).throw(ValueError('NONFINITE_RECEIPT')))
    if not isinstance(report, dict) or set(report) != FIELDS or report['schema'] != SCHEMA:
        raise ValueError('EXACT_SCHEMA_REQUIRED')
    if (report['input_filename'] != csv_path.name
            or hashlib.sha256(csv_path.read_bytes()).hexdigest() != report['input_sha256']):
        raise ValueError('ORIGINAL_INPUT_CHANGED')
    if report['evidence_role'] not in ('EXPOSED_DEMO', 'FROZEN_HELDOUT') or report['label_review_status'] not in ('UNVERIFIED', 'INDEPENDENTLY_REVIEWED') or report['population_frame_status'] not in ('UNKNOWN','DOCUMENTED'):
        raise ValueError('INVALID_EVIDENCE_DECLARATION')
    expected_status = ('BOUNDED_HELDOUT_DIAGNOSTIC' if report['evidence_role'] == 'FROZEN_HELDOUT' and report['label_review_status'] == 'INDEPENDENTLY_REVIEWED' else 'UNQUALIFIED_DEMONSTRATION')
    if report['status'] != expected_status:
        raise ValueError('UNSUPPORTED_EVIDENCE_PROMOTION')
    if not isinstance(report['limitations'], list) or len(report['limitations']) != 5 or not all(isinstance(s, str) and s for s in report['limitations']):
        raise ValueError('EXPLICIT_LIMITATIONS_REQUIRED')
    with csv_path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError('EXACT_SOURCE_COLUMNS_REQUIRED')
        records = list(reader)
    if type(report['rows']) is not int or not 1 <= report['rows'] <= 20000 or len(records) != report['rows']:
        raise ValueError('ROW_COUNT_CHANGED')
    count: dict[str, dict[str, int]] = {}
    seen: set[str] = set()
    for x in records:
        if set(x) != set(COLUMNS) or any(v is None for v in x.values()):
            raise ValueError('INVALID_SOURCE_ROW')
        if not x['case_id'] or x['case_id'] in seen:
            raise ValueError('REPEATED_CASE')
        seen.add(x['case_id'])
        if (not x['group'] or not x['period'] or x['label'] not in ('0', '1', 'NA')
                or x['model_output'] not in ('0', '1', 'ABSTAIN')):
            raise ValueError('INVALID_SOURCE_CLASS')
        g = count.setdefault(x['group'], {k: 0 for k in COUNTS})
        g['total'] += 1
        if x['label'] == 'NA':
            g['unlabeled'] += 1
        if x['model_output'] == 'ABSTAIN':
            g['abstained'] += 1
        if x['label'] in ('0', '1') and x['model_output'] in ('0', '1'):
            g['scored'] += 1
            if x['label'] == '1':
                g['tp' if x['model_output'] == '1' else 'fn'] += 1
            else:
                g['tn' if x['model_output'] == '0' else 'fp'] += 1
    if not isinstance(report['groups'], dict) or set(count) != set(report['groups']):
        raise ValueError('GROUPS_CHANGED')
    for group, g in count.items():
        reported = report['groups'][group]
        if not isinstance(reported, dict) or set(reported) != set(COUNTS) | {'observed_error_rate','observed_error_wilson95','scored_fraction','total_not_equal_population'}:
            raise ValueError('GROUP_FIELDS_CHANGED:' + group)
        if any(type(reported.get(k)) is not int or reported[k] != g[k] for k in COUNTS):
            raise ValueError('COUNTS_CHANGED:' + group)
        denom = g['scored']
        errors = g['fp'] + g['fn']
        rate = round(errors / denom, 6) if denom else None
        if reported['observed_error_rate'] != rate:
            raise ValueError('ERROR_CHANGED:' + group)
        if reported['observed_error_wilson95'] != _interval(errors, denom):
            raise ValueError('INTERVAL_CHANGED:' + group)
        if reported['scored_fraction'] != round(denom / g['total'], 6):
            raise ValueError('DENOMINATOR_CHANGED:' + group)
        if reported['total_not_equal_population'] is not True:
            raise ValueError('POPULATION_INFERENCE_REFUSED:' + group)
    if any(report[k] is not None for k in ('population_prevalence_estimate','population_bias_certification','commercial_acceptance','actual_revenue_usd')):
        raise ValueError('UNSUPPORTED_CLAIM')
    return True


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--csv', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    verify(a.csv, a.report)
    print('INDEPENDENT_SAMPLE_REPLAY_ACCEPTED')
