import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def export(source, output):
    source, output = Path(source).resolve(), Path(output).absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise FileExistsError(output)
    databases = sorted(source.glob('*.sqlite'))
    if not databases or len(databases) > 20:
        raise ValueError('BOUNDED_NATIVE_DATABASES_REQUIRED')
    records = []
    for path in databases:
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        connection.row_factory = sqlite3.Row
        try:
            tables = {table: [dict(r) for r in connection.execute('SELECT * FROM ' + table + ' ORDER BY rowid')] for table in ['config', 'wallets', 'source_receipts', 'events', 'journal', 'investments', 'investment_events']}
        finally:
            connection.close()
        after = hashlib.sha256(path.read_bytes()).hexdigest()
        if after != before:
            raise AssertionError('READ_ONLY_EXPORT_CHANGED_DATABASE')
        records.append({'file': path.name, 'sha256': before, 'bytes': path.stat().st_size, 'tables': tables})
    output.mkdir(parents=True, exist_ok=False)
    record = {'schema': 'agi-alpha/next009-native-event-export/v1', 'scope': 'Read-only export of authored local-provider simulations; no real customer or payment data.', 'exporter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'databases': records, 'all_database_bytes_unchanged': True}
    (output / 'NATIVE_EVENTS.json').write_text(json.dumps(record, indent=2) + '\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = export(args.source, args.output)
    print(json.dumps({'databases_exported': len(result['databases']), 'bytes_unchanged': result['all_database_bytes_unchanged']}))
