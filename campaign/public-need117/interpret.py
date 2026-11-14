#!/usr/bin/env python3
"""Offline *sample-level* perception classifier audit; never a population estimator."""
from __future__ import annotations
import argparse
import csv
import hashlib
import html
import json
import math
from pathlib import Path

HEADERS = ('case_id', 'period', 'group', 'label', 'model_output')
SCHEMA = 'agi-alpha/public-need117/sampled-perception-audit/v1'


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def wilson(success: int, total: int) -> list[float] | None:
    if not total:
        return None
    z = 1.959963984540054
    center = (success / total + z*z/(2*total))/(1+z*z/total)
    spread = z*math.sqrt((success/total)*(1-success/total)/total+z*z/(4*total*total))/(1+z*z/total)
    return [round(max(0.0, center-spread), 6), round(min(1.0, center+spread), 6)]


def load(path: Path) -> tuple[list[dict[str, str]], str]:
    if path.stat().st_size > 4_000_000:
        raise ValueError('BOUNDED_CSV_REQUIRED')
    raw = path.read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        raise ValueError('BOM_REFUSED')
    raw.decode('utf-8')
    with path.open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames is None or tuple(reader.fieldnames) != HEADERS:
            raise ValueError('EXACT_SAMPLE_COLUMNS_REQUIRED')
        rows = list(reader)
    if not 1 <= len(rows) <= 20000:
        raise ValueError('NONEMPTY_BOUNDED_SAMPLE_REQUIRED')
    seen = set()
    for row in rows:
        if set(row) != set(HEADERS):
            raise ValueError('INVALID_SAMPLE_SHAPE')
        if any(value is None or '\x00' in value for value in row.values()):
            raise ValueError('INVALID_SAMPLE_VALUE')
        if not row['case_id'] or len(row['case_id']) > 128 or row['case_id'] in seen:
            raise ValueError('UNIQUE_CASE_ID_REQUIRED')
        seen.add(row['case_id'])
        if not row['period'] or len(row['period']) > 64 or not row['group'] or len(row['group']) > 64:
            raise ValueError('BOUNDED_GROUP_PERIOD_REQUIRED')
        if row['label'] not in ('0', '1', 'NA') or row['model_output'] not in ('0', '1', 'ABSTAIN'):
            raise ValueError('EXACT_LABEL_AND_MODEL_OUTPUT_REQUIRED')
    return rows, sha(raw)


def metrics(rows: list[dict[str, str]]) -> dict:
    groups: dict[str, dict[str, int]] = {}
    for row in rows:
        g = groups.setdefault(row['group'], {k: 0 for k in ('total', 'unlabeled', 'abstained', 'scored', 'tp', 'tn', 'fp', 'fn')})
        g['total'] += 1
        if row['label'] == 'NA':
            g['unlabeled'] += 1
        if row['model_output'] == 'ABSTAIN':
            g['abstained'] += 1
        if row['label'] in ('0', '1') and row['model_output'] in ('0', '1'):
            g['scored'] += 1
            key = {('1','1'): 'tp', ('0','0'): 'tn', ('0','1'): 'fp', ('1','0'): 'fn'}[(row['label'], row['model_output'])]
            g[key] += 1
    out = {}
    for group, g in sorted(groups.items()):
        denominator = g['scored']
        errors = g['fp'] + g['fn']
        out[group] = dict(g, observed_error_rate=round(errors/denominator, 6) if denominator else None,
                          observed_error_wilson95=wilson(errors, denominator),
                          scored_fraction=round(denominator/g['total'], 6),
                          total_not_equal_population=True)
    return out


def build(path: Path, *, sample_role: str, review_status: str, population_frame: str) -> dict:
    if sample_role not in ('EXPOSED_DEMO', 'FROZEN_HELDOUT') or review_status not in ('UNVERIFIED', 'INDEPENDENTLY_REVIEWED'):
        raise ValueError('EXACT_EVIDENCE_ROLE_REQUIRED')
    if population_frame not in ('UNKNOWN', 'DOCUMENTED'):
        raise ValueError('EXACT_POPULATION_FRAME_STATUS_REQUIRED')
    rows, checksum = load(path)
    grouped = metrics(rows)
    status = ('BOUNDED_HELDOUT_DIAGNOSTIC' if sample_role == 'FROZEN_HELDOUT' and review_status == 'INDEPENDENTLY_REVIEWED'
              else 'UNQUALIFIED_DEMONSTRATION')
    return {
        'schema': SCHEMA, 'input_sha256': checksum, 'input_filename': path.name, 'rows': len(rows),
        'evidence_role': sample_role, 'label_review_status': review_status,
        'population_frame_status': population_frame, 'status': status, 'groups': grouped,
        'population_prevalence_estimate': None, 'population_bias_certification': None,
        'commercial_acceptance': None, 'actual_revenue_usd': None,
        'limitations': [
            'Input role and independent label-review assertions are operator claims, not authenticated evidence.',
            'Wilson intervals condition on scored observed cases and do not remove selection or labeling bias.',
            'Unknown labels and abstentions are excluded from observed error denominators; counts remain visible.',
            'Documented sampling alone does not prove representativeness or causal population disparities.',
            'No government dataset, procurement submission, buyer acceptance or paid transaction was used.'
        ]
    }


def render(report: dict) -> str:
    cols = ('total','unlabeled','abstained','scored','fp','fn','observed_error_rate','observed_error_wilson95')
    head = ''.join(f'<th scope="col">{html.escape(x)}</th>' for x in ('group',*cols))
    trs=[]
    for group, vals in sorted(report['groups'].items()):
        cells = [html.escape(group)] + [html.escape(json.dumps(vals[c],sort_keys=True)) for c in cols]
        trs.append('<tr>'+''.join('<td>'+x+'</td>' for x in cells)+'</tr>')
    note='This is a sample-level diagnostic, not validated population estimation, bias certification, or buyer acceptance.'
    return ('<!doctype html>\n<html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Audited sample perception — cautious interpretation</title>'
            '<style>body{font:1rem/1.6 system-ui;max-width:70rem;margin:2rem auto;padding:0 1rem;color:#202735}'
            'table{border-collapse:collapse;display:block;overflow-x:auto}td,th{padding:.55rem;border:1px solid #9aa5b4;text-align:left}'
            'caption{text-align:left;font-weight:700}mark{background:#fff0bd}</style>'
            '<main><h1>Audited perception sample</h1><p><mark>'+html.escape(report['status'])+'</mark></p>'
            '<p>'+html.escape(note)+'</p><table><caption>Observed scored cases, per group</caption><thead><tr>'
            +head+'</tr></thead><tbody>'+''.join(trs)+'</tbody></table>'
            '<p>Unlabeled and abstained cases remain outside error-rate denominators; inspect the JSON receipt for full limits.</p>'
            '<p>Data SHA-256: <code>'+report['input_sha256']+'</code></p></main></html>\n')


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--role', choices=('EXPOSED_DEMO', 'FROZEN_HELDOUT'), required=True)
    p.add_argument('--label-review', choices=('UNVERIFIED', 'INDEPENDENTLY_REVIEWED'), required=True)
    p.add_argument('--population-frame', choices=('UNKNOWN','DOCUMENTED'), required=True)
    a = p.parse_args()
    if a.output.exists():
        p.error('NEW_OUTPUT_DIRECTORY_REQUIRED')
    report = build(a.csv, sample_role=a.role, review_status=a.label_review, population_frame=a.population_frame)
    a.output.mkdir(parents=True)
    (a.output/'RESULT.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
    (a.output/'dashboard.html').write_text(render(report))
    print(json.dumps({'status':report['status'],'rows':report['rows'],'groups':len(report['groups'])},sort_keys=True))


if __name__ == '__main__':
    main()
