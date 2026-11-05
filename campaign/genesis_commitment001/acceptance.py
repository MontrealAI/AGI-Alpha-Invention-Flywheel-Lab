"""Independent acceptance of bounded synthetic SQLite deliverables.

This checker reads the delivered database itself. It never imports a producer,
accepts a producer's success flag, or treats a simulated buyer as a real customer.
The fixed schema and finite input limits are this experiment's attack surface;
they are not a general database recovery or production-security guarantee.
"""
from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
import re
import sqlite3

REQUEST_SCHEMA = "genesis-commitment001/request/v1"
DELIVERY_SCHEMA = "genesis-commitment001/delivery/v1"
MAX_DATABASE_BYTES = 1_000_000
MAX_ENCODED_BYTES = 2_000_000
_ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z", re.ASCII)

_TABLE_SQL = {
    "accounts": "CREATE TABLE accounts(account_id TEXT PRIMARY KEY,name TEXT NOT NULL,balance_cents INTEGER NOT NULL)",
    "customers": "CREATE TABLE customers(customer_id TEXT PRIMARY KEY,name TEXT NOT NULL)",
    "invoices": "CREATE TABLE invoices(invoice_id TEXT PRIMARY KEY,customer_id TEXT NOT NULL REFERENCES customers(customer_id),amount_cents INTEGER NOT NULL)",
}
_COLUMNS = {
    "accounts": [(0, "account_id", "TEXT", 0, None, 1),
                 (1, "name", "TEXT", 1, None, 0),
                 (2, "balance_cents", "INTEGER", 1, None, 0)],
    "customers": [(0, "customer_id", "TEXT", 0, None, 1),
                  (1, "name", "TEXT", 1, None, 0)],
    "invoices": [(0, "invoice_id", "TEXT", 0, None, 1),
                 (1, "customer_id", "TEXT", 1, None, 0),
                 (2, "amount_cents", "INTEGER", 1, None, 0)],
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _identifier(value):
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError("COMMITMENT_VALID_IDENTIFIER_REQUIRED")


def _name(value):
    if type(value) is not str or not 1 <= len(value) <= 128 or "\x00" in value:
        raise ValueError("COMMITMENT_BOUNDED_NAME_REQUIRED")
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise ValueError("COMMITMENT_VALID_UNICODE_REQUIRED") from error


def _money(value):
    if type(value) is not int or not 0 <= value <= 10**12:
        raise ValueError("COMMITMENT_EXACT_BOUNDED_CENTS_REQUIRED")


def validate_request(request):
    """Validate the complete frozen requirement; return an isolated JSON value."""
    if (type(request) is not dict or
            set(request) != {"schema", "id", "kind", "records"} or
            request["schema"] != REQUEST_SCHEMA or
            type(request["kind"]) is not str or
            request["kind"] not in {"restore", "migration"}):
        raise ValueError("COMMITMENT_EXACT_REQUEST_REQUIRED")
    _identifier(request["id"])
    records = request["records"]
    if type(records) is not list or not 1 <= len(records) <= 1024:
        raise ValueError("COMMITMENT_BOUNDED_RECORDS_REQUIRED")
    seen = set()
    customers = {}
    for record in records:
        if request["kind"] == "restore":
            if type(record) is not dict or set(record) != {"account_id", "name", "balance_cents"}:
                raise ValueError("COMMITMENT_EXACT_RESTORE_RECORD_REQUIRED")
            ident = record["account_id"]
            _identifier(ident)
            _name(record["name"])
            _money(record["balance_cents"])
        else:
            if type(record) is not dict or set(record) != {
                    "invoice_id", "customer_id", "customer_name", "amount_cents"}:
                raise ValueError("COMMITMENT_EXACT_MIGRATION_RECORD_REQUIRED")
            ident = record["invoice_id"]
            _identifier(ident)
            _identifier(record["customer_id"])
            _name(record["customer_name"])
            _money(record["amount_cents"])
            previous = customers.setdefault(record["customer_id"], record["customer_name"])
            if previous != record["customer_name"]:
                raise ValueError("COMMITMENT_CONFLICTING_CUSTOMER_NAMES")
        if ident in seen:
            raise ValueError("COMMITMENT_DUPLICATE_RECORD_ID")
        seen.add(ident)
    if len(_canonical(request)) > 1_000_000:
        raise ValueError("COMMITMENT_BOUNDED_REQUEST_REQUIRED")
    return copy.deepcopy(request)


def _normalized_sql(sql):
    return re.sub(r"\s+", "", sql).lower().rstrip(";")


def _check_database(request, raw):
    if not raw.startswith(b"SQLite format 3\x00"):
        raise ValueError("COMMITMENT_SQLITE_DATABASE_REQUIRED")
    db = sqlite3.connect(":memory:")
    try:
        db.enable_load_extension(False)
        for name, limit in (("SQLITE_LIMIT_LENGTH", MAX_DATABASE_BYTES),
                            ("SQLITE_LIMIT_SQL_LENGTH", 65_536),
                            ("SQLITE_LIMIT_COLUMN", 32),
                            ("SQLITE_LIMIT_EXPR_DEPTH", 32),
                            ("SQLITE_LIMIT_COMPOUND_SELECT", 8),
                            ("SQLITE_LIMIT_ATTACHED", 0)):
            db.setlimit(getattr(sqlite3, name), limit)
        calls = 0

        def progress():
            nonlocal calls
            calls += 1
            return int(calls > 2000)

        db.set_progress_handler(progress, 100)
        db.deserialize(raw)
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("PRAGMA query_only=ON")
        tables = {"accounts"} if request["kind"] == "restore" else {"customers", "invoices"}
        objects = db.execute("SELECT type,name,tbl_name,sql FROM sqlite_schema ORDER BY type,name").fetchall()
        expected_objects = {(kind, name) for table in tables
                            for kind, name in (("table", table), ("index", "sqlite_autoindex_" + table + "_1"))}
        if {(kind, name) for kind, name, _, _ in objects} != expected_objects or len(objects) != len(expected_objects):
            raise ValueError("COMMITMENT_EXACT_DATABASE_OBJECTS_REQUIRED")
        for kind, name, table, sql in objects:
            if table not in tables:
                raise ValueError("COMMITMENT_UNEXPECTED_DATABASE_OBJECT")
            if kind == "table":
                if name != table or type(sql) is not str or _normalized_sql(sql) != _normalized_sql(_TABLE_SQL[table]):
                    raise ValueError("COMMITMENT_EXACT_TABLE_SCHEMA_REQUIRED")
            elif sql is not None or name != "sqlite_autoindex_" + table + "_1":
                raise ValueError("COMMITMENT_AUTOMATIC_PRIMARY_INDEX_REQUIRED")
        for table in sorted(tables):
            # table comes exclusively from the fixed set above, never user SQL.
            if db.execute("PRAGMA table_info(" + table + ")").fetchall() != _COLUMNS[table]:
                raise ValueError("COMMITMENT_COLUMN_SCHEMA_CHANGED")
            foreign = db.execute("PRAGMA foreign_key_list(" + table + ")").fetchall()
            expected_foreign = [(0, 0, "customers", "customer_id", "customer_id", "NO ACTION", "NO ACTION", "NONE")] if table == "invoices" else []
            if foreign != expected_foreign:
                raise ValueError("COMMITMENT_FOREIGN_KEY_SCHEMA_CHANGED")
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("COMMITMENT_DATABASE_INTEGRITY_FAILED")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("COMMITMENT_FOREIGN_KEY_CHECK_FAILED")
        records = request["records"]
        if request["kind"] == "restore":
            expected = sorted((r["account_id"], r["name"], r["balance_cents"], "text", "text", "integer") for r in records)
            actual = db.execute("SELECT account_id,name,balance_cents,typeof(account_id),typeof(name),typeof(balance_cents) FROM accounts ORDER BY account_id").fetchall()
            if actual != expected:
                raise ValueError("COMMITMENT_RESTORED_DATA_MISMATCH")
        else:
            customer_map = {r["customer_id"]: r["customer_name"] for r in records}
            expected_customers = sorted((ident, name, "text", "text") for ident, name in customer_map.items())
            actual_customers = db.execute("SELECT customer_id,name,typeof(customer_id),typeof(name) FROM customers ORDER BY customer_id").fetchall()
            expected_invoices = sorted((r["invoice_id"], r["customer_id"], r["amount_cents"], "text", "text", "integer") for r in records)
            actual_invoices = db.execute("SELECT invoice_id,customer_id,amount_cents,typeof(invoice_id),typeof(customer_id),typeof(amount_cents) FROM invoices ORDER BY invoice_id").fetchall()
            if actual_customers != expected_customers or actual_invoices != expected_invoices:
                raise ValueError("COMMITMENT_MIGRATED_DATA_MISMATCH")
    finally:
        db.close()


def verify(request, artifact):
    """Accept only source-matched database bytes with the exact required data."""
    try:
        request = validate_request(request)
        if type(artifact) is not dict or set(artifact) != {
                "schema", "request_sha256", "kind", "method", "output_database_b64",
                "output_sha256", "operation"}:
            raise ValueError("COMMITMENT_EXACT_DELIVERY_REQUIRED")
        if artifact["schema"] != DELIVERY_SCHEMA or artifact["kind"] != request["kind"]:
            raise ValueError("COMMITMENT_DELIVERY_KIND_CHANGED")
        if type(artifact["method"]) is not str or artifact["method"] not in {"retained", "direct"}:
            raise ValueError("COMMITMENT_DECLARED_METHOD_REQUIRED")
        operation = "restore-from-backup" if request["kind"] == "restore" else "normalize-legacy-invoices"
        if artifact["operation"] != operation or artifact["request_sha256"] != _digest(request):
            raise ValueError("COMMITMENT_SOURCE_REQUIREMENT_CHANGED")
        encoded = artifact["output_database_b64"]
        if type(encoded) is not str or len(encoded) > MAX_ENCODED_BYTES:
            raise ValueError("COMMITMENT_BOUNDED_DATABASE_ENCODING_REQUIRED")
        raw = base64.b64decode(encoded, validate=True)
        if not 512 <= len(raw) <= MAX_DATABASE_BYTES or base64.b64encode(raw).decode("ascii") != encoded:
            raise ValueError("COMMITMENT_CANONICAL_BOUNDED_DATABASE_REQUIRED")
        if artifact["output_sha256"] != hashlib.sha256(raw).hexdigest():
            raise ValueError("COMMITMENT_DATABASE_HASH_CHANGED")
        _check_database(request, raw)
        return {"accepted": True, "errors": []}
    except (ValueError, TypeError, KeyError, sqlite3.Error, binascii.Error, UnicodeError, OverflowError) as error:
        return {"accepted": False, "errors": [str(error)]}
