"""Independently recompute the site planning claims from the actual CMR and ASF response bytes."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sqlite3


SQL = '''
WITH RECURSIVE
catalog(item) AS (SELECT value FROM json_each(:source, '$.items')),
records AS (
   SELECT json_extract(item, '$.umm.GranuleUR') AS granule,
          json_extract(item, '$.umm.InputGranules[0]') AS observation_0,
          json_extract(item, '$.umm.InputGranules[1]') AS observation_1,
          item
   FROM catalog
),
attributes AS (
   SELECT granule, observation_0, observation_1,
          MAX(CASE WHEN json_extract(a.value, '$.Name')='STACK_ID'
                   THEN json_extract(a.value, '$.Values[0]') END) AS stack,
          MAX(CASE WHEN json_extract(a.value, '$.Name')='FULL_FRAME'
                   THEN json_extract(a.value, '$.Values[0]') END) AS full_frame,
          MAX(CASE WHEN json_extract(a.value, '$.Name')='REFERENCE_ZERO_DOPPLER_START_TIME'
                   THEN julianday(json_extract(a.value, '$.Values[0]')) END) AS reference_time,
          MAX(CASE WHEN json_extract(a.value, '$.Name')='SECONDARY_ZERO_DOPPLER_START_TIME'
                   THEN julianday(json_extract(a.value, '$.Values[0]')) END) AS secondary_time
   FROM records JOIN json_each(item, '$.umm.AdditionalAttributes') AS a
   GROUP BY granule, observation_0, observation_1
),
ready AS (
   SELECT * FROM attributes
   WHERE full_frame='TRUE' AND reference_time >= julianday(:start)
     AND secondary_time <= julianday(:end) AND secondary_time > reference_time
     AND observation_0 IS NOT NULL AND observation_1 IS NOT NULL
),
chains(stack, last_input, last_time, links) AS (
   SELECT stack, observation_1, secondary_time, 1 FROM ready
   UNION ALL
   SELECT c.stack, r.observation_1, r.secondary_time, c.links+1
   FROM chains c JOIN ready r ON c.stack=r.stack AND c.last_input=r.observation_0
   WHERE r.secondary_time > c.last_time
)
SELECT stack, MAX(links) FROM chains GROUP BY stack ORDER BY stack
'''


def independently_check(directory):
    report = json.loads((directory / 'CATALOG-COMPARISON.json').read_bytes())
    start, end = report['interval']
    final = {}
    with sqlite3.connect(':memory:') as db:
        for city, summary in report['site_results'].items():
            observed = {}
            for label, suffix in [('nisar_cmr', 'nisar-cmr'), ('nisar_asf', 'nisar-asf'),
                                  ('opera_sentinel_cmr', 'opera-cmr')]:
                raw = (directory / f'{city}-{suffix}.json').read_bytes()
                receipt = summary['acquisition_observations'][label]
                assert sha256(raw).hexdigest() == receipt['sha256'] and len(raw) == receipt['bytes']
                observed[label] = raw.decode()
            chains = dict(db.execute(SQL, {'source': observed['nisar_cmr'], 'start': start, 'end': end}))
            retained = {row['stack']: len(row['same_input_links'])
                        for row in summary['exact_in_window_acquisition_chains']}
            catalog = set(db.execute('''SELECT json_extract(value, '$.umm.GranuleUR')
                                         FROM json_each(?, '$.items')''', (observed['nisar_cmr'],)))
            secondary = set(db.execute('''SELECT json_extract(value, '$.granuleName') g
                                           FROM json_each(?, '$[0]')
                                           WHERE json_extract(value, '$.processingLevel')='GUNW'
                                             AND instr(g, '_P05036_')>0''', (observed['nisar_asf'],)))
            early, = db.execute('''SELECT COUNT(*) FROM json_each(?, '$.items') i
                                   JOIN json_each(i.value, '$.umm.AdditionalAttributes') a
                                   WHERE json_extract(a.value, '$.Name')='REFERENCE_ZERO_DOPPLER_START_TIME'
                                     AND julianday(json_extract(a.value, '$.Values[0]')) < julianday(?)''',
                                (observed['nisar_cmr'], start)).fetchone()
            incumbent, = db.execute('SELECT COUNT(*) FROM json_each(?, \'$.items\')',
                                     (observed['opera_sentinel_cmr'],)).fetchone()
            assert chains == retained and catalog == secondary
            assert len(catalog) == summary['nisar_validated_cmr'] and early == summary['pre_window_reference_count']
            assert incumbent == summary['opera_displacement_control_count']
            final[city] = {'count': len(catalog), 'pre_window_reference_count': early,
                           'max_chain_links': max(chains.values(), default=0), 'incumbent_count': incumbent}
    return {'sqlite_version': sqlite3.sqlite_version, 'scoped_observations': final,
            'acceptance': 'INDEPENDENT_IMPLEMENTATION_REPLAY_SAME_PUBLIC_ARCHIVE'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result_directory', type=Path)
    args = parser.parse_args()
    print(json.dumps(independently_check(args.result_directory), indent=2))


if __name__ == '__main__':
    main()
