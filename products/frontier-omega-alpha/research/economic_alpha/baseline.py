"""Conventional SQL decisions on the same registered OEM inputs."""

import sqlite3
from contextlib import contextmanager


@contextmanager
def equipment(protocol):
    catalog = protocol['catalog']
    db = sqlite3.connect(':memory:')
    try:
        db.execute('CREATE TABLE equipment (label TEXT PRIMARY KEY, model TEXT NOT NULL, chamber INTEGER)')
        db.execute('CREATE TABLE excluded (label TEXT PRIMARY KEY)')
        db.executemany('INSERT INTO equipment VALUES (?, ?, ?)',
                       [(label, model, profile['chamber_limit_c'])
                        for model, profile in catalog['eligible'].items() for label in profile['labels']])
        db.executemany('INSERT INTO excluded VALUES (?)',
                       [(label,) for label in catalog['explicit_exclusions']])
        yield db
    finally:
        db.close()


def normalized_for_lookup(request):
    label = ' '.join(request['model'].lower().split())
    return label, label[6:] if label.startswith('prusa ') else label


def compatibility(db, request, protocol, observed_on):
    label, exclusion = normalized_for_lookup(request)
    standard = protocol['catalog']['standard_nozzle_c']
    limit = protocol['catalog']['retrofit_nozzle_c'] if observed_on >= protocol['after'] else standard
    return db.execute('''
        SELECT CASE WHEN ? != 'non_safety_critical' THEN 'external-review-required'
          WHEN EXISTS (SELECT 1 FROM excluded WHERE label = ?) THEN 'unsupported-configuration'
          WHEN NOT EXISTS (SELECT 1 FROM equipment WHERE label = ?) THEN 'need-model-evidence'
          WHEN ? <= ? THEN 'existing-envelope'
          WHEN ? <= ? THEN 'retrofit-candidate' ELSE 'no-documented-path' END
        ''', (request['use'], exclusion, label, request['nozzle_requirement_c'], standard,
              request['nozzle_requirement_c'], limit)).fetchone()[0]
