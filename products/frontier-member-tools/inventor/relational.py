"""Read-only table programs over bounded in-memory fixtures."""

import json
import re
import sqlite3
from contextlib import closing

IDENTIFIER = re.compile(r'[a-z][a-z0-9_]{0,31}\Z')
FUNCTIONS = frozenset({
    'abs', 'avg', 'coalesce', 'count', 'dense_rank', 'first_value', 'group_concat', 'ifnull',
    'instr', 'lag', 'lead', 'length', 'lower', 'ltrim', 'max', 'min', 'nullif', 'rank',
    'replace', 'round', 'row_number', 'rtrim', 'substr', 'sum', 'trim', 'typeof', 'upper',
})


class QueryRefused(ValueError):
    """A safe classification suitable for a development retry."""


def scalar(value):
    return (value is None or (type(value) is int and -(2**53) < value < 2**53) or
            (type(value) is str and len(value.encode('utf-8')) <= 512))


def validate_schema(schema):
    if not isinstance(schema, dict) or not 1 <= len(schema) <= 6:
        raise QueryRefused('SCHEMA')
    for table, columns in schema.items():
        if not IDENTIFIER.fullmatch(table) or not isinstance(columns, dict) or not 1 <= len(columns) <= 12:
            raise QueryRefused('SCHEMA')
        if any(not IDENTIFIER.fullmatch(key) or kind not in ('INTEGER','TEXT') for key, kind in columns.items()):
            raise QueryRefused('SCHEMA')


def authorize(schema, action, first, second, database, source):
    if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ and database == 'main' and first in schema and (second == '' or second in schema[first]):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and second in FUNCTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def evaluate(schema, tables, sql):
    validate_schema(schema)
    if not isinstance(tables, dict) or set(tables) != set(schema):
        raise QueryRefused('INPUT')
    if not isinstance(sql, str) or not 0 < len(sql.encode('utf-8')) <= 6000:
        raise QueryRefused('QUERY_SIZE')
    if not re.match(r'\s*(SELECT|WITH)\b', sql, re.IGNORECASE):
        raise QueryRefused('READ_ONLY')
    with closing(sqlite3.connect(':memory:', cached_statements=0)) as db:
        db.execute('PRAGMA trusted_schema=OFF')
        db.execute('PRAGMA temp_store=MEMORY')
        for table, columns in schema.items():
            rows = tables[table]
            if not isinstance(rows, list) or len(rows) > 512:
                raise QueryRefused('INPUT')
            values = []
            for row in rows:
                if not isinstance(row, dict) or set(row) != set(columns):
                    raise QueryRefused('INPUT')
                ordered = tuple(row[column] for column in columns)
                if any(not scalar(value) or (value is not None and type(value) is not {'TEXT':str,'INTEGER':int}[kind])
                       for value, kind in zip(ordered, columns.values())):
                    raise QueryRefused('INPUT')
                values.append(ordered)
            fields = ','.join(f'"{column}" {kind}' for column, kind in columns.items())
            slots = ','.join('?' for _ in columns)
            db.execute(f'CREATE TABLE "{table}" ({fields}) STRICT')
            db.executemany(f'INSERT INTO "{table}" VALUES ({slots})', values)
        db.execute('PRAGMA query_only=ON')
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 64 * 1024)
        db.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 6000)
        db.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, 24)
        db.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 40)
        db.setlimit(sqlite3.SQLITE_LIMIT_COMPOUND_SELECT, 12)
        db.setlimit(sqlite3.SQLITE_LIMIT_VDBE_OP, 12000)
        db.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)
        db.set_authorizer(lambda *args: authorize(schema, *args))
        remaining = 2000
        def budget():
            nonlocal remaining
            remaining -= 1
            return remaining == 0
        db.set_progress_handler(budget, 100)
        try:
            result = db.execute(sql).fetchmany(257)
        except MemoryError as error:
            raise QueryRefused('QUERY_LIMIT') from error
        except sqlite3.Error as error:
            code = getattr(error, 'sqlite_errorcode', None)
            if code in (sqlite3.SQLITE_INTERRUPT, sqlite3.SQLITE_TOOBIG, sqlite3.SQLITE_NOMEM):
                raise QueryRefused('QUERY_LIMIT') from error
            if code == sqlite3.SQLITE_AUTH:
                raise QueryRefused('READ_ONLY') from error
            raise QueryRefused('SQL_ERROR') from error
    if len(result) > 256 or any(not all(map(scalar, row)) for row in result):
        raise QueryRefused('OUTPUT_LIMIT')
    rows = [list(row) for row in result]
    if len(json.dumps(rows, ensure_ascii=False).encode('utf-8')) > 32 * 1024:
        raise QueryRefused('OUTPUT_LIMIT')
    return rows


def reference_key(rows):
    return sorted(json.dumps(row, ensure_ascii=False, separators=(',', ':')) for row in rows)


def check(mission, cases, sql):
    results = []
    for case in cases:
        try:
            actual = evaluate(mission['tables'], case['input'], sql)
            row = {'id':case['id'], 'pass':reference_key(actual) == reference_key(case['expected'])}
        except QueryRefused as error:
            row = {'id':case['id'], 'pass':False, 'error':str(error)}
        results.append(row)
    return results
