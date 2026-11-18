"""Standalone conventional converter, equivalent on the registered JSONL workload."""
import json
import re
import sqlite3
import sys

FIELDS = ("author_date", "author_hour", "author_minute", "committer_date", "committer_hour", "committer_minute")
PROJECTION = """select :author_date as written_date, cast(:author_hour as integer) as written_hour,
cast(:author_minute as integer) as written_minute, :committer_date as landed_date,
cast(:committer_hour as integer) as landed_hour, cast(:committer_minute as integer) as landed_minute"""


def convert(db, row):
    if type(row) is not dict or not set(FIELDS) <= row.keys():
        raise ValueError("missing_field")
    if set(FIELDS) != row.keys():
        raise ValueError("extra_field")
    for field in FIELDS:
        value = row[field]
        if field.endswith("_date"):
            if type(value) is not str:
                raise ValueError("invalid_value")
        elif not (type(value) is int and abs(value) < 2**53 or
                  type(value) is str and len(value) <= 17 and re.fullmatch(r"0|-?[1-9][0-9]*", value)
                  and abs(int(value)) < 2**53):
            raise ValueError("invalid_value")
    return dict(db.execute(PROJECTION, row).fetchone())


def uniq(pairs):
    row = dict(pairs)
    if len(row) != len(pairs):
        raise ValueError("duplicate field")
    return row


if __name__ == "__main__":
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        for line in sys.stdin:
            print(json.dumps(convert(connection, json.loads(line, object_pairs_hook=uniq)), ensure_ascii=False))
    except (ValueError, sqlite3.Error) as err:
        print(str(err), file=sys.stderr)
        sys.exit(2)
