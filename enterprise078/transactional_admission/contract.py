"""Bind actual SQL/CSV bytes to a distinct, immutable acceptance contract.

This is a delivery checker, not a JournalAccount catalogue migration. The
original laboratory manifest and all historical native source pins stay intact.
"""
import hashlib
import json
import re
import tempfile
from pathlib import Path

from enterprise078.transactional_data.acceptance import verify
from enterprise078.transactional_data.operator import validate

TYPE = 'enterprise078/transactional-database-and-derived-csv/v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def request(identity, events):
    if not isinstance(identity, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', identity):
        raise ValueError('EXPLICIT_TRANSACTIONAL_REQUEST_ID_REQUIRED')
    validate(events)
    return {'type': TYPE, 'id': identity, 'input_sha256': digest(events),
            'input_records': len(events), 'projection': 'group-sum-and-count',
            'csv_header': ['account', 'units', 'event_count'],
            'acceptance': 'exact-events-exact-totals-exact-csv-sqlite-integrity',
            'scope': 'synthetic nonfinancial records; no physical laboratory acceptance'}


def accept(contract, events, database, csv_path):
    if contract != request(contract.get('id', ''), events):
        raise ValueError('EXACT_TYPED_REQUEST_REQUIRED')
    database, csv_path = Path(database), Path(csv_path)
    for path in (database, csv_path):
        if not path.is_file() or path.is_symlink():
            raise ValueError('REGULAR_DELIVERY_REQUIRED')
    # A live WAL database is not a portable single-file delivery. Snapshot it
    # with SQLite's backup API first; do not hash an incomplete main file.
    wal = database.with_name(database.name + '-wal')
    if wal.exists() and wal.stat().st_size:
        raise ValueError('CHECKPOINTED_STANDALONE_DATABASE_REQUIRED')
    db_bytes, csv_bytes = database.read_bytes(), csv_path.read_bytes()
    # Validate exactly the bytes being committed. Concurrent source changes
    # cannot make the receipt attest different inspected bytes.
    with tempfile.TemporaryDirectory(prefix='transactional-acceptance-') as tmp:
        db_copy, csv_copy = Path(tmp)/'delivery.sqlite', Path(tmp)/'derived.csv'
        db_copy.write_bytes(db_bytes)
        csv_copy.write_bytes(csv_bytes)
        result = verify(db_copy, events, csv_path=csv_copy)
    return {'schema': 'enterprise078/typed-delivery-receipt/v1',
            'request_sha256': digest(contract), 'type': TYPE,
            'database_sha256': hashlib.sha256(db_bytes).hexdigest(),
            'database_bytes': len(db_bytes),
            'csv_sha256': hashlib.sha256(csv_bytes).hexdigest(),
            'csv_bytes': len(csv_bytes), 'acceptance': result,
            'accepted': result['accepted'], 'native_catalog_admitted': False}
