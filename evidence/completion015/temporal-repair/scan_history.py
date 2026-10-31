import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from commercial.ledger import digest

parts_root = ROOT / 'artifacts/completion015-parts'
index_path = parts_root / 'INDEX.json'
index = json.loads(index_path.read_text())
parts = []
offset = 0
for part in index['parts']:
    raw = (parts_root / part['path']).read_bytes()
    assert part['offset'] == offset and len(raw) == part['bytes'] and hashlib.sha256(raw).hexdigest() == part['sha256']
    parts.append(raw); offset += len(raw)
raw = b''.join(parts)
assert len(raw) == index['archive_bytes'] and hashlib.sha256(raw).hexdigest() == index['archive_sha256']
with zipfile.ZipFile(io.BytesIO(raw)) as archive:
    assert archive.testzip() is None
    frozen = json.loads(archive.read('FROZEN.json'))
    expected = frozen.pop('sha256'); assert digest(frozen) == expected; frozen['sha256'] = expected
    assert frozen['source']['sha256'] == 'abc262bf80741f36db2872330c2d4f5166c48d313143c239d440e3cd2143b9a4'
    report = json.loads(archive.read('REPORT.json'))
    bound = {row['task']['id']: row['result_sha256'] for row in report['worlds_index']}
    worlds = []
    for name in sorted(archive.namelist()):
        if not name.startswith('worlds/') or not name.endswith('/RESULT.json'):
            continue
        result = json.loads(archive.read(name)); world = name.split('/')[1]
        assert digest(result) == bound[world] and result['source']['sha256'] == frozen['source']['sha256']
        cfg = result['config']; investments = {row['plan_id']: row for row in result['investments']}
        uses = []; bad_uses = []; changed = []
        for order in result['orders']:
            ident = order.get('capacity_source_plan_id')
            if ident:
                asset = investments[ident]
                valid = asset['activation_time'] <= order['qualified_time'] and order['production_time'] < asset['expiry_time']
                use = {'order_id': order['id'], 'asset': ident, 'qualification': order['qualified_time'],
                       'production': order['production_time'], 'activation': asset['activation_time'], 'expiry': asset['expiry_time'], 'valid': valid}
                uses.append(use)
                if not valid:
                    bad_uses.append(use)
        for event in result['events']:
            if event['kind'] == 'BUSINESS_DECISION':
                time = event['time']
                old = [row['plan_id'] for row in result['investments'] if row['kind'] == 'capacity' and row['activation_time'] <= time < row['expiry_time']]
                new = [row['plan_id'] for row in result['investments'] if row['kind'] == 'capacity' and row['activation_time'] <= time and time + cfg['production_hours'] < row['expiry_time']]
                if old != new:
                    changed.append({'time': time, 'old': old, 'new': new})
        total = cfg['production_hours'] + cfg['acceptance_hours'] + cfg['clearing_hours']
        worlds.append({'world': world, 'source_bound_result_sha256': digest(result), 'production_hours': cfg['production_hours'],
                       'acceptance_hours': cfg['acceptance_hours'], 'clearing_hours': cfg['clearing_hours'],
                       'deadline_hours': cfg['payment_deadline_hours'], 'complete_lifecycle_hours': total,
                       'lifecycle_valid': total <= cfg['payment_deadline_hours'], 'capacity_uses': uses,
                       'invalid_capacity_uses': bad_uses, 'plan_capacity_eligibility_changes': changed,
                       'plan_events_checked': sum(row['kind'] == 'BUSINESS_DECISION' for row in result['events'])})
assert len(worlds) == 8
result = {'schema': 'agi-alpha/completion015-temporal-historical-impact/v1',
          'scope': 'READ_ONLY_ORIGINAL_ABC_RECORD_SCAN; no regenerated history or new business experiment',
          'archive_sha256': index['archive_sha256'], 'parts_index_sha256': hashlib.sha256(index_path.read_bytes()).hexdigest(),
          'source_sha256': frozen['source']['sha256'], 'frozen_sha256': frozen['sha256'], 'worlds': worlds,
          'totals': {'worlds': len(worlds), 'plan_events_checked': sum(row['plan_events_checked'] for row in worlds),
                     'capacity_uses': sum(len(row['capacity_uses']) for row in worlds),
                     'invalid_lifecycle_configs': sum(not row['lifecycle_valid'] for row in worlds),
                     'invalid_capacity_uses': sum(len(row['invalid_capacity_uses']) for row in worlds),
                     'plan_capacity_eligibility_changes': sum(len(row['plan_capacity_eligibility_changes']) for row in worlds)},
          'conclusion': 'Original reported eight-world temporal outcomes unaffected iff all violation and change totals zero; retained at original source identity, not promoted to current-source qualification.'}
Path(__file__).with_name('HISTORICAL_IMPACT.json').write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
print(json.dumps({'source_sha256': result['source_sha256'], 'totals': result['totals']}, sort_keys=True))
