"""Execute the frozen public-day evaluation; retain every rejection and timing."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import resource
import time

from production060.dispatch import DispatchConfig, rolling_schedule
from production060.acceptance import make_contract, verify


def run(root: Path, arm: str, output: Path, ids=None):
    frozen = json.loads((root / 'production060/evaluation.json').read_text())
    catalog = json.loads((root / 'production060/data/catalog.json').read_text())
    resources = json.loads((root / 'production060/data/resources.json').read_text())
    chosen = set(ids) if ids else {r['id'] for r in catalog if r['operating_data_complete']}
    cfg = DispatchConfig(time_limit_s=frozen['solver']['time_limit_s_per_day'],
                         window_size=frozen['solver']['window_size'],
                         candidate_trucks=frozen['solver']['candidate_trucks'])
    output.mkdir(parents=True, exist_ok=True)
    summary = {'schema': 'production060/executed-evaluation/v1', 'arm': arm,
               'evaluation_sha256': hashlib.sha256((root/'production060/evaluation.json').read_bytes()).hexdigest(),
               'config': asdict(cfg), 'rows': []}
    for row in catalog:
        if row['id'] not in chosen:
            continue
        day = json.loads((root/row['path']).read_text())
        contract = make_contract(day, resources, mode=arm, planning_scope='rolling', config=asdict(cfg))
        before = resource.getrusage(resource.RUSAGE_SELF)
        started = time.monotonic()
        try:
            artifact = rolling_schedule(resources, day, mode=arm, config=cfg)
            receipt = verify(day, resources, artifact, contract)
            (output/(row['id']+'.json')).write_text(json.dumps(artifact, separators=(',', ':'), allow_nan=False)+'\n')
            result = {'id': row['id'], 'accepted': receipt['accepted'], 'errors': receipt['errors'],
                      'kpis': receipt['kpis'], 'objective': artifact['objective'],
                      'driver_review_count': len(artifact['diagnostics']['driver_review_flags']),
                      'missing_mix_count': len(artifact['diagnostics']['missing_mix_order_ids']),
                      'clean_mix': row['mix_data_complete'],
                      'heldout': row['id'] in frozen['heldout_logistics_ids']}
            (output/(row['id']+'.receipt.json')).write_text(json.dumps(receipt, indent=2)+'\n')
            (output/(row['id']+'.contract.json')).write_text(json.dumps(contract, indent=2)+'\n')
        except Exception as exc:
            result = {'id': row['id'], 'accepted': False, 'errors': [type(exc).__name__+': '+str(exc)],
                      'clean_mix': row['mix_data_complete'],
                      'heldout': row['id'] in frozen['heldout_logistics_ids']}
        after = resource.getrusage(resource.RUSAGE_SELF)
        result['wall_s'] = time.monotonic()-started
        result['cpu_s'] = after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime
        result['peak_rss_kib'] = after.ru_maxrss
        summary['rows'].append(result)
        summary['completed'] = len(summary['rows'])
        summary['accepted'] = sum(x['accepted'] for x in summary['rows'])
        summary['cpu_s'] = sum(x['cpu_s'] for x in summary['rows'])
        summary['wall_s'] = sum(x['wall_s'] for x in summary['rows'])
        (output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
        if len(summary['rows']) % 20 == 0 or not result['accepted']:
            print(json.dumps({'completed': summary['completed'], 'accepted': summary['accepted'],
                              'latest': result['id'], 'errors': result['errors'][:3]}), flush=True)
    return summary


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path('.'))
    ap.add_argument('--arm', choices=['ordinary','retained','cold'], default='ordinary')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--ids', nargs='*')
    args = ap.parse_args()
    answer = run(args.root, args.arm, args.output, args.ids)
    print(json.dumps({k: answer[k] for k in ['arm','completed','accepted','cpu_s','wall_s']}))
