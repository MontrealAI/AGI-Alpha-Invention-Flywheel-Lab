"""Strict interpretation of a pinned, bounded RTS-GMLC slice."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN = ROOT / 'campaign/grid-service-envelope-20261104'


def read_csv(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def load_inputs(directory, day):
    directory = Path(directory)
    buses = read_csv(directory / 'bus.csv')
    lines = read_csv(directory / 'branch.csv')
    gens = read_csv(directory / 'gen.csv')
    if (len(buses), len(lines), len(gens)) != (73, 120, 158):
        raise ValueError('Unexpected pinned network dimensions')
    selected = {}
    for file in sorted(directory.glob('*_3days.csv')):
        rows = [r for r in read_csv(file) if f"{int(r['Year']):04}-{int(r['Month']):02}-{int(r['Day']):02}" == day]
        if [int(r['Period']) for r in rows] != list(range(1, 25)):
            raise ValueError(f'Missing or duplicate hours: {file.name} {day}')
        selected[file.name] = rows
    if len(selected) != 6:
        raise ValueError('Exactly six verified hourly series required')
    series = {key: np.array([float(r[key]) for r in rows]) for rows in selected.values() for key in rows[0] if key not in ('Year','Month','Day','Period')}
    area_total = {area: sum(float(r['MW Load']) for r in buses if r['Area'] == area) for area in ('1','2','3')}
    demand = np.array([series[r['Area']] * float(r['MW Load']) / area_total[r['Area']] + float(r['MW Shunt G']) for r in buses]).T
    lower, upper = [], []
    thermal = []
    for i, g in enumerate(gens):
        kind, uid = g['Unit Type'], g['GEN UID']
        pm = float(g['PMax MW'])
        if kind in ('CSP','STORAGE','SYNC_COND'):
            lo = hi = np.zeros(24)
        elif kind in ('RTPV','HYDRO','ROR'):
            if uid not in series:
                raise ValueError(f'Missing fixed output {uid}')
            lo = hi = series[uid]
        elif kind in ('PV','WIND'):
            lo, hi = np.zeros(24), np.minimum(pm, series[uid])
        else:
            thermal.append(i)
            lo, hi = np.full(24,float(g['PMin MW'])), np.full(24,pm)
        if np.any(lo < 0) or np.any(hi > pm + 1e-7) or np.any(lo > hi):
            raise ValueError(f'Invalid generator profile {uid}')
        lower.append(lo); upper.append(hi)
    return {'buses':buses,'lines':lines,'gens':gens,'load':demand,'lower':np.array(lower).T,'upper':np.array(upper).T,'thermal':thermal,'day':day}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def registration():
    r = json.loads((CAMPAIGN/'REGISTRATION.json').read_text())
    amendment = json.loads((CAMPAIGN/'AMENDMENT_01.json').read_text())
    for key, value in amendment['overrides'].items():
        if isinstance(value, dict):
            r[key].update(value)
        else:
            r[key] = value
    return r
