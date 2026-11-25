from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re

import numpy as np


HERE = Path(__file__).resolve().parent


def fits_header(raw, offset):
    keys = {}
    pos = offset
    while pos + 80 <= len(raw):
        card = raw[pos:pos + 80].decode('ascii')
        pos += 80
        name = card[:8].strip()
        if name == 'END':
            return keys, ((pos + 2879) // 2880) * 2880
        if card[8:10] == '= ':
            content = card[10:].lstrip()
            keys[name] = (content.split("'")[1].strip() if content.startswith("'")
                          else content.split('/')[0].strip())
    raise ValueError('No FITS END card')


def tess_table(raw):
    primary, offset = fits_header(raw, 0)
    assert primary['NAXIS'] == '0'
    header, offset = fits_header(raw, offset)
    assert header['XTENSION'] == 'BINTABLE'
    assert header['EXTNAME'] == 'LIGHTCURVE'
    formats = {'B': '>u1', 'I': '>i2', 'J': '>i4', 'K': '>i8', 'E': '>f4', 'D': '>f8'}
    columns = []
    for i in range(1, int(header['TFIELDS']) + 1):
        count, letter = re.fullmatch(r'(\d*)([BIJKED])', header[f'TFORM{i}']).groups()
        count = int(count or '1')
        columns.append((header[f'TTYPE{i}'], formats[letter], (count,)) if count > 1
                       else (header[f'TTYPE{i}'], formats[letter]))
    dtype = np.dtype(columns)
    assert dtype.itemsize == int(header['NAXIS1'])
    return primary, header, np.frombuffer(raw, dtype=dtype, offset=offset, count=int(header['NAXIS2']))


def utc_stamp(jd):
    return (datetime(1970, 1, 1, tzinfo=timezone.utc)
            + timedelta(days=float(jd) - 2440587.5)).isoformat()


def possible_tess_dip(t, f, err, nominal):
    local = np.abs(t - nominal) <= 0.65
    t, f, err = t[local], f[local], err[local]
    if len(t) < 50:
        return None
    f, err = f / np.median(f), err / np.median(f)
    w = 1 / err
    x = t - nominal
    base = np.column_stack((np.ones(len(x)), x))
    y = f * w
    fit, *_ = np.linalg.lstsq(base * w[:, None], y, rcond=None)
    no_dip = float(np.sum((y - (base @ fit) * w) ** 2))
    best = None
    for center in np.arange(-0.45, 0.451, 0.001):
        separation = np.abs(x - center)
        for duration in (0.15, 0.20, 0.25, 0.30):
            for ingress in (0.025, 0.050, 0.075):
                shape = np.clip((duration / 2 - separation) / ingress, 0, 1)
                design = np.column_stack((base, -shape))
                coefficients, *_ = np.linalg.lstsq(design * w[:, None], y, rcond=None)
                if coefficients[2] <= 0 or np.count_nonzero(shape > 0) < 15:
                    continue
                improvement = no_dip - float(np.sum((y - (design @ coefficients) * w) ** 2))
                if best is None or improvement > best['delta_chi2']:
                    best = {'approximate_center_bjd_tdb': float(nominal + center),
                            'depth_relative': float(coefficients[2]), 'duration_d': duration,
                            'ingress_d': ingress, 'delta_chi2': improvement,
                            'interior_and_contacts_samples': int(np.count_nonzero(shape > 0)),
                            'purpose': 'Exploratory ordinary grid fit, conditional shape, not an independent ground timing.'}
    return best


def main():
    with (HERE / 'exofop-74164.source').open(newline='') as src:
        ground = list(csv.DictReader(src, delimiter='\t'))
    page = (HERE / 'exofop-target.source').read_text()
    candidates = [json.loads(hit.group()) for hit in re.finditer(r'\{[^{}]+\}', page)
                  if '"tsdate":"2020-07-26"' in hit.group() and '"tstag":28725' in hit.group()]
    observation, = candidates
    primary, header, values = tess_table((HERE / 'tess-s27.fits').read_bytes())
    assert primary['TICID'] == '55652896' and primary['SECTOR'] == '27'
    assert header['TIMESYS'] == 'TDB' and header['BJDREFI'] == '2457000'
    time = values['TIME'] + float(header['BJDREFI']) + float(header['BJDREFF'])
    flux = values['PDCSAP_FLUX'].astype(float)
    error = values['PDCSAP_FLUX_ERR'].astype(float)
    good = np.isfinite(time) & np.isfinite(flux) & np.isfinite(error) & (error > 0) & (values['QUALITY'] == 0)
    jd = np.array([float(r['JD_UTC']) for r in ground])
    bjd = np.array([float(r['BJD_TDB']) for r in ground])
    gflux = np.array([float(r['rel_flux_T1']) for r in ground])
    gsigma = np.array([float(r['rel_flux_err_T1']) for r in ground])
    margins = 15 / 1440
    neighborhood = good & (time >= jd.min() - margins) & (time <= jd.max() + margins)
    dip = possible_tess_dip(time[good], flux[good], error[good], float(np.median(jd)))
    extent = None
    if dip:
        center = dip['approximate_center_bjd_tdb']
        stop = center + dip['duration_d'] / 2
        extent = {'approximate_tess_dip_end_bjd_tdb': stop,
                  'minimum_ground_start_later_than_tess_end_s_with_15_min_scale_margin':
                      float((jd.min() - margins - stop) * 86400),
                  'paired_ground_exposures_at_candidate_even_with_15_min_scale_margin':
                      int(np.count_nonzero(np.abs(jd - center) <= dip['duration_d'] / 2 + margins))}
    output = {'ground': {'observation_id': observation['tsobid'], 'target': observation['tsplname'],
                         'archive_coverage': observation['tstcov'], 'instrument': observation['tstel'],
                         'camera': observation['tscam'], 'filter': observation['tsfilt'], 'rows': len(ground),
                         'jd_utc_range': [float(jd.min()), float(jd.max())],
                         'utc_range_approximate': [utc_stamp(jd.min()), utc_stamp(jd.max())],
                         'bjd_tdb_values': dict(Counter(map(float, bjd))), 'valid_published_bjd_tdb_rows':
                             int(np.count_nonzero(np.isfinite(bjd) & (bjd > 2400000))),
                         'raw_flux_relative_min_median_max': [float(gflux.min()), float(np.median(gflux)), float(gflux.max())],
                         'raw_flux_error_median': float(np.median(gsigma))},
              'tess': {'tic': primary['TICID'], 'sector': primary['SECTOR'], 'telescope': primary['TELESCOP'],
                       'timesys': header['TIMESYS'], 'bjdrefi': header['BJDREFI'], 'bjdreff': header['BJDREFF'],
                       'total_cadences': len(values), 'quality_zero_finite_cadences': int(np.count_nonzero(good)),
                       'quality_zero_finite_range_bjd_tdb': [float(time[good].min()), float(time[good].max())],
                       'cadences_near_ground_utc_with_15_min_scale_margin': int(np.count_nonzero(neighborhood)),
                       'ordinary_grid_dip': dip}, 'approximate_overlap_diagnostic': extent}
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
