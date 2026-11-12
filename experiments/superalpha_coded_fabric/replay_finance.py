import json
from pathlib import Path
import shutil
import tempfile

from connected_enterprise.finance import SOURCE_PATHS, audit_journal
from connected_enterprise.scale import trailing_profit
from enterprise.services import SOURCE_PATHS as SERVICE_PATHS, prepare_services

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def replay():
    record = json.loads((HERE / 'evidence/NATIVE_RECORD.json').read_text())
    manifest = json.loads((HERE / 'evidence/MANIFEST.json').read_text())
    with tempfile.TemporaryDirectory(prefix='coded-fabric-public-replay-') as tmp:
        source = Path(tmp)
        for name in sorted(set(SOURCE_PATHS) | set(SERVICE_PATHS)):
            target = source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        prepare_services(source, 'fixture_services')
        audit = audit_journal(record, root=source, manifest=manifest)
    observer = trailing_profit(record['ledger'], operating_end_hour=5, operating_complete=True)
    assert audit['accepted'] and audit['summary']['profit'] == -2_500_000_000
    assert not observer['complete_365_day_operating_history']
    assert observer['trailing_365_day_profit_microUSD'] is None
    return {'accepted': True, 'native_actions_sha256': audit['actions_sha256'],
            'opening_capital_usd': 100000, 'profit_usd': -2500, 'cash_usd': 97500,
            'observer': observer,
            'scope': 'READ_ONLY_ORIGINAL_PUBLIC_NATIVE_REPLAY_NO_NEW_FUNDED_ACCOUNT'}


if __name__ == '__main__':
    print(json.dumps(replay(), indent=2, sort_keys=True))
