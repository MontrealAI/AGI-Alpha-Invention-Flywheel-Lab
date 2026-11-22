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
    label = ' '.join(request['model'].casefold().split())
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


def direct_process(db, request, protocol):
    label, exclusion = normalized_for_lookup(request)
    catalog = protocol['catalog']
    return db.execute('''
        WITH inputs(label, excluded_label, use_kind, nozzle, requested_chamber, installed, sheet, review) AS
          (VALUES (?, ?, ?, ?, ?, ?, ?, ?))
        SELECT CASE WHEN use_kind != 'non_safety_critical' THEN 'external-review-required'
          WHEN EXISTS (SELECT 1 FROM excluded WHERE label = excluded_label) THEN 'unsupported-configuration'
          WHEN equipment.model IS NULL THEN 'need-model-evidence'
          WHEN nozzle > ? THEN 'no-documented-path'
          WHEN installed = 'unknown' OR (nozzle > ? AND installed <> 'retrofit') THEN 'installed-configuration-unverified'
          WHEN chamber IS NULL THEN 'need-chamber-evidence'
          WHEN requested_chamber > chamber THEN 'outside-chamber-envelope'
          WHEN sheet <> ? THEN 'accessory-evidence-required'
          WHEN review <> 'approved-evidence' THEN 'site-evidence-required'
          ELSE 'documented-process-envelope' END
        FROM inputs LEFT JOIN equipment ON equipment.label = inputs.label
        ''', (label, exclusion, request['use'], request['nozzle_requirement_c'], request['required_chamber_c'],
              request['claimed_installed'], request['sheet'], request['site_review'], catalog['retrofit_nozzle_c'],
              catalog['standard_nozzle_c'], catalog['successor_sheet'])).fetchone()[0]


def ordinary_process(db, request, protocol):
    """Ordinary composition with the incumbent lookup and the same published facts."""
    fit = compatibility(db, request, protocol, protocol['after'])
    if fit not in ('existing-envelope', 'retrofit-candidate'):
        return fit
    label, _ = normalized_for_lookup(request)
    chamber = db.execute('SELECT chamber FROM equipment WHERE label = ?', (label,)).fetchone()[0]
    installed = request['claimed_installed']
    constraints = (
        (installed == 'unknown' or (fit == 'retrofit-candidate' and installed != 'retrofit'), 'installed-configuration-unverified'),
        (chamber is None, 'need-chamber-evidence'),
        (chamber is not None and request['required_chamber_c'] > chamber, 'outside-chamber-envelope'),
        (request['sheet'] != protocol['catalog']['successor_sheet'], 'accessory-evidence-required'),
        (request['site_review'] != 'approved-evidence', 'site-evidence-required'),
    )
    return next((verdict for failed, verdict in constraints if failed), 'documented-process-envelope')
