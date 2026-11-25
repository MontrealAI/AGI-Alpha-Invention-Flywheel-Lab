"""Run the independently authored ordinary SQLite comparator on public inputs."""

import argparse
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
import sys
from time import perf_counter_ns, process_time_ns


OCCUPANCY = """SELECT CAST(SUM(j.occupied * j.minutes) AS TEXT) || '/' ||
       CAST(SUM(j.capacity * j.minutes) AS TEXT) AS occupancy
  FROM journeys AS j
  JOIN services AS s ON j.line_id = s.line_id
 WHERE j.state = 'operated' AND s.scope = 'regular'
HAVING SUM(j.capacity * j.minutes) > 0"""

FREIGHT = """WITH conversions AS (
    SELECT CASE u_charge WHEN 'kg' THEN charge WHEN 't' THEN charge * 1000 END AS kg,
           CASE u_trajet WHEN 'm' THEN trajet WHEN 'km' THEN trajet * 1000 END AS m
      FROM expeditions
)
SELECT CAST(SUM(kg * m) AS TEXT) || '/1000000' AS travail
  FROM conversions
HAVING COUNT(*) > 0 AND COUNT(kg) = COUNT(*) AND COUNT(m) = COUNT(*)"""

MISSING_PAIRS = """SELECT cycle, 'duree_s' AS field FROM mesures WHERE duree_s IS NULL
UNION ALL
SELECT cycle, 'energie_j' AS field FROM mesures WHERE energie_j IS NULL
ORDER BY cycle, field"""

FULL_POWER = """SELECT CAST(SUM(energie_j) AS TEXT) || '/' ||
       CAST(SUM(duree_s) AS TEXT) AS puissance
  FROM mesures
HAVING COUNT(*) > 0 AND COUNT(duree_s) = COUNT(*) AND COUNT(energie_j) = COUNT(*)
   AND SUM(duree_s) > 0"""


def quoted(name):
    if re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', name) is None:
        raise ValueError('unsupported SQLite identifier')
    return '"' + name + '"'


def load(connection, case):
    for name, fields in case['schema'].items():
        if set(fields.values()) - {'INTEGER', 'TEXT'}:
            raise ValueError('unsupported authorized column type')
        table = quoted(name)
        columns = ', '.join(f'{quoted(k)} {v}' for k, v in fields.items())
        connection.execute(f'CREATE TABLE {table} ({columns}) STRICT')
        placeholders = ', '.join('?' for _ in fields)
        connection.executemany(f'INSERT INTO {table} VALUES ({placeholders})',
                               [[row[column] for column in fields] for row in case['data'][name]])
    connection.commit()
    connection.execute('PRAGMA query_only=ON')


def query(connection, statement):
    wall, cpu = perf_counter_ns(), process_time_ns()
    cursor = connection.execute(statement)
    rows = cursor.fetchall()
    return rows, {'query_sha256': sha256(statement.encode()).hexdigest(),
                  'columns': [item[0] for item in cursor.description], 'rows': rows,
                  'wall_ns': perf_counter_ns() - wall, 'cpu_ns': process_time_ns() - cpu}


def answer(case, connection):
    ident = case['id']
    if ident == 'od-c01':
        statement = OCCUPANCY
        explanation = ('The numerator counts occupied seat-minutes and the denominator counts capacity '
                       'seat-minutes over the same operated journeys with regular service.')
    elif ident == 'od-c02':
        statement = FREIGHT
        explanation = ('Les charges sont converties en kg et les distances en m. La somme entière '
                       'des kg·m est divisée exactement par un million pour obtenir des t·km.')
    elif ident == 'od-c03':
        statement = FULL_POWER
        missing_rows, observed = query(connection, MISSING_PAIRS)
        if missing_rows:
            by_cycle = {row['cycle']: i for i, row in enumerate(case['data']['mesures'])}
            missing = [f'mesures[{by_cycle[key]}].{field}' for key, field in missing_rows]
            labels = ', '.join(f'{cycle}.{field}' for cycle, field in missing_rows)
            return {'id': ident, 'decision': 'ABSTAIN', 'queries': [MISSING_PAIRS], 'result': {},
                    'missing': missing, 'explanation': (f'Mesure requise manquante pour {labels}. '
                       'La puissance moyenne de tous les cycles est indéterminée.')}, [observed]
        explanation = 'La somme des énergies est divisée exactement par la somme des durées de tous les cycles.'
    else:
        raise ValueError('unknown registered case')

    rows, observed = query(connection, statement)
    if len(rows) != 1 or len(rows[0]) != 1 or len(case['metrics']) != 1:
        raise ValueError('expected exactly one rational metric')
    value = Fraction(rows[0][0])
    result = value.numerator if value.denominator == 1 else str(value)
    return {'id': ident, 'decision': 'ANSWER', 'queries': [statement], 'result': {case['metrics'][0][0]: result},
            'missing': [], 'explanation': explanation}, [observed]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('cases', type=Path)
    parser.add_argument('predictions', type=Path)
    parser.add_argument('execution', type=Path)
    args = parser.parse_args()
    source = args.cases.read_bytes()
    output, executions = [], []
    wall, cpu = perf_counter_ns(), process_time_ns()
    for case in json.loads(source):
        start, usage = perf_counter_ns(), process_time_ns()
        connection = sqlite3.connect(':memory:')
        try:
            load(connection, case)
            response, observations = answer(case, connection)
        finally:
            connection.close()
        output.append(response)
        executions.append({'id': case['id'], 'read_only_queries': observations,
                           'wall_ns': perf_counter_ns() - start, 'cpu_ns': process_time_ns() - usage})
    encoded = (json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()
    with args.predictions.open('xb') as stream:
        stream.write(encoded)
    receipt = {'cases_sha256': sha256(source).hexdigest(), 'predictions_sha256': sha256(encoded).hexdigest(),
               'python': sys.version.split()[0], 'sqlite': sqlite3.sqlite_version, 'executions': executions,
               'wall_ns': perf_counter_ns() - wall, 'cpu_ns': process_time_ns() - cpu}
    with args.execution.open('x') as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write('\n')


if __name__ == '__main__':
    main()
