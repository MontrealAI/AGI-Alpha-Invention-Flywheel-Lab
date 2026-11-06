"""Actually execute bounded synthetic SQLite recovery and schema migration.

These are conventional database operations on authored records. They establish
neither recovery of an external application nor an autonomous invention advantage.
The verifier lives in acceptance.py and does not call these implementations.
"""
from __future__ import annotations

import base64
import hashlib
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from commercial.ledger import digest
from .acceptance import validate_request

SCHEMA = 'genesis-commitment001/delivery/v1'


def default_requests():
    """Small authored inputs, exposed as development fixtures, never market data."""
    return [
        {'schema': 'genesis-commitment001/request/v1', 'id': 'restore-first',
         'kind': 'restore', 'records': [
             {'account_id': 'acct-A', 'name': 'Synthetic Workshop', 'balance_cents': 125075},
             {'account_id': 'acct-B', 'name': 'Synthetic Library', 'balance_cents': 82004},
             {'account_id': 'acct-C', 'name': 'Synthetic Studio', 'balance_cents': 0}]},
        {'schema': 'genesis-commitment001/request/v1', 'id': 'migration-next',
         'kind': 'migration', 'records': [
             {'invoice_id': 'inv-101', 'customer_id': 'buyer-Q', 'customer_name': 'Synthetic Forge', 'amount_cents': 71125},
             {'invoice_id': 'inv-102', 'customer_id': 'buyer-R', 'customer_name': 'Synthetic Lab', 'amount_cents': 20010},
             {'invoice_id': 'inv-103', 'customer_id': 'buyer-Q', 'customer_name': 'Synthetic Forge', 'amount_cents': 19995}]},
    ]


def _restore(request, directory, method):
    live, backup = directory / 'application.sqlite', directory / 'backup.sqlite'
    with closing(sqlite3.connect(live)) as original:
        original.execute('CREATE TABLE accounts(account_id TEXT PRIMARY KEY, name TEXT NOT NULL, balance_cents INTEGER NOT NULL)')
        original.executemany('INSERT INTO accounts VALUES(?,?,?)',
                            [(r['account_id'], r['name'], r['balance_cents']) for r in request['records']])
        original.commit()
        with closing(sqlite3.connect(backup)) as saved:
            original.backup(saved)
    # Deliberately destroy this temporary synthetic live file. Only the declared
    # backup remains usable; no real user database or external path is opened.
    live.write_bytes(b'DESTROYED SYNTHETIC APPLICATION DATABASE\n')
    try:
        with closing(sqlite3.connect(live)) as corrupt:
            corrupt.execute('SELECT * FROM accounts').fetchall()
    except sqlite3.DatabaseError:
        pass
    else:
        raise ValueError('SYNTHETIC_DESTRUCTION_DID_NOT_OCCUR')
    live.unlink()
    if method == 'retained':
        with closing(sqlite3.connect(backup)) as saved, closing(sqlite3.connect(live)) as recovered:
            saved.backup(recovered)
    else:
        # Equally capable ordinary direct backup-file restoration.
        shutil.copyfile(backup, live)
    return live.read_bytes()


def _migrate(request, directory, method):
    legacy, output = directory / 'legacy.sqlite', directory / 'normalized.sqlite'
    with closing(sqlite3.connect(legacy)) as source:
        source.execute('CREATE TABLE legacy(invoice_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, customer_name TEXT NOT NULL, amount_cents INTEGER NOT NULL)')
        source.executemany('INSERT INTO legacy VALUES(?,?,?,?)',
                           [(r['invoice_id'], r['customer_id'], r['customer_name'], r['amount_cents']) for r in request['records']])
        source.commit()
    with closing(sqlite3.connect(output)) as target:
        target.execute('PRAGMA foreign_keys=ON')
        target.execute('CREATE TABLE customers(customer_id TEXT PRIMARY KEY, name TEXT NOT NULL)')
        target.execute('CREATE TABLE invoices(invoice_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL REFERENCES customers(customer_id), amount_cents INTEGER NOT NULL)')
        if method == 'retained':
            with closing(sqlite3.connect(legacy)) as source:
                customers = source.execute('SELECT DISTINCT customer_id,customer_name FROM legacy ORDER BY customer_id').fetchall()
                invoices = source.execute('SELECT invoice_id,customer_id,amount_cents FROM legacy ORDER BY invoice_id').fetchall()
            target.executemany('INSERT INTO customers VALUES(?,?)', customers)
            target.executemany('INSERT INTO invoices VALUES(?,?,?)', invoices)
        else:
            # A conventional SQL-only route receives the identical source.
            target.execute('ATTACH DATABASE ? AS source', (str(legacy),))
            target.execute('INSERT INTO customers SELECT DISTINCT customer_id,customer_name FROM source.legacy ORDER BY customer_id')
            target.execute('INSERT INTO invoices SELECT invoice_id,customer_id,amount_cents FROM source.legacy ORDER BY invoice_id')
        if target.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('MIGRATION_FOREIGN_KEY_FAILURE')
        target.commit()
    return output.read_bytes()


def produce(request, *, method='retained'):
    """Return real SQLite output bytes after executing the requested operation.

    Temporary files are owned by this call and removed after output capture.
    The artifact proves inspectable final data; it does not cryptographically
    attest the historical execution steps or certify a real recovery deadline.
    """
    request = validate_request(request)
    if method not in {'retained', 'direct'}:
        raise ValueError('DECLARED_DELIVERY_METHOD_REQUIRED')
    with tempfile.TemporaryDirectory(prefix='genesis-delivery-') as temp:
        directory = Path(temp)
        if request['kind'] == 'restore':
            raw = _restore(request, directory, method)
            operation = 'restore-from-backup'
        else:
            raw = _migrate(request, directory, method)
            operation = 'normalize-legacy-invoices'
    if len(raw) > 1_000_000:
        raise ValueError('BOUNDED_DATABASE_OUTPUT_REQUIRED')
    return {'schema': SCHEMA, 'request_sha256': digest(request),
            'kind': request['kind'], 'method': method,
            'output_database_b64': base64.b64encode(raw).decode('ascii'),
            'output_sha256': hashlib.sha256(raw).hexdigest(), 'operation': operation}
