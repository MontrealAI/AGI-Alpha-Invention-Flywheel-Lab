"""Direct relational acceptance rule. It has no constructor or check-order dependency."""

from contextlib import closing
import json
import sqlite3


def outcomes(cases):
    with closing(sqlite3.connect(":memory:")) as db:
        query = """
            WITH projected AS (
                SELECT json_extract(value, '$.id') AS id,
                       json_extract(value, '$.observed.scope') =
                           json_extract(value, '$.required.scope') AS scope_ok,
                       json_extract(value, '$.observed.chronology') <=
                           json_extract(value, '$.required.chronology') AS time_ok,
                       json_extract(value, '$.observed.role') =
                           json_extract(value, '$.required.role') AS role_ok,
                       json_extract(value, '$.observed.qualification') =
                           json_extract(value, '$.required.qualification') AS quality_ok
                FROM json_each(?)
            )
            SELECT id, CASE scope_ok AND time_ok AND role_ok AND quality_ok
                WHEN 1 THEN 'supported'
                WHEN 0 THEN 'inapplicable'
                ELSE 'insufficient'
            END FROM projected
        """
        result = dict(db.execute(query, [json.dumps(cases, sort_keys=True)]))
        if len(result) != len(cases):
            raise ValueError("Duplicate case identity")
    return result
