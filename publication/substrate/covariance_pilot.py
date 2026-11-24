"""Reproduce the preregistered, retrospective public transit-timing readiness check."""

import argparse
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from science_substrate import calculate, canonical, exact, problem, source_records


ARCHIVE = '0c17105ad6a7b4f50281c15f1ed61170163f008f00451c30bb25e39e83ef80e8'
EARLY = 'e79d5ab1dcce58ddd11a9ae2c1eca71958d4d5109c0e35773c99b9ec5294cf7d'
SPLIT = Fraction('2460000.5')


def flagged(paper):
    for name, witness, values in source_records(paper.read_bytes(), 'paper'):
        case = problem(name, witness, 'BJD_TDB', '2462502.5', values)
        result = calculate(case)
        if result['decision'] != 'COVARIANCE_SENSITIVE':
            continue
        _, s0, _, sp, duration = map(exact, values)
        if s0**2+(sp*result['epoch'])**2 <= (duration/288)**2:
            yield name, witness


def original_times(raw):
    lines = raw.decode().splitlines()
    if [field.strip() for field in lines[0].split('\t')][:4] != ['Tmid (BJD_TDB)','Tmid unc.','source','ID']:
        raise ValueError('TIMING_CATALOGUE_SCHEMA')
    rows = []
    for line in lines[1:]:
        observed, sigma, source, witness = (v.strip() for v in line.split('\t'))
        observed, sigma = exact(observed), exact(sigma)
        if sigma <= 0 or not source or not witness:
            raise ValueError('TIMING_CATALOGUE_ROW')
        rows.append((observed,sigma,source,witness))
    return rows


def epoch_groups(rows, midpoint, period):
    selected = {}
    for observed, sigma, source, witness in rows:
        epoch = round((observed-midpoint)/period)
        if abs(observed-midpoint-period*epoch) >= period/8:
            raise ValueError('EPOCH_ASSIGNMENT')
        # Keep one strict match per epoch for both arms.
        value = (sigma,witness,observed,source)
        if epoch not in selected or value<selected[epoch]:
            selected[epoch] = value
    return [(epoch,row[2],row[0]) for epoch,row in sorted(selected.items())]


def fitted(rows):
    weights = [(n,y,1/u**2) for n,y,u in rows]
    total = sum(w for _,_,w in weights)
    center = sum(w*n for n,_,w in weights)/total
    mean = sum(w*y for _,y,w in weights)/total
    sxx = sum(w*(n-center)**2 for n,_,w in weights)
    slope = sum(w*(n-center)*(y-mean) for n,y,w in weights)/sxx
    intercept = mean-slope*center
    v0, vp, cov = 1/total+center**2/sxx, 1/sxx, -center/sxx
    determinant = total*sum(w*n*n for n,_,w in weights)-sum(w*n for n,_,w in weights)**2
    if cov != -sum(w*n for n,_,w in weights)/determinant:
        raise ValueError('MATRIX_COVARIANCE_DISAGREEMENT')
    return intercept,slope,v0,vp,cov


def analyze(rows, early):
    base = {'raw_observations':len(rows),'raw_before':sum(row[0]<SPLIT for row in rows)}
    if early is None:
        return {**base,'decision':'ABSTAIN_NO_EARLIER_EPOCH_SOURCE'}
    epochs = epoch_groups(rows,*early)
    train, held = ([r for r in epochs if r[1]<SPLIT], [r for r in epochs if r[1]>=SPLIT])
    base.update(fit_epochs=len(train),held_epochs=len(held))
    if len(train)<3:
        return {**base,'decision':'ABSTAIN_FEW_FIT_EPOCHS'}
    intercept,slope,v0,vp,cov = fitted(train)
    successes = {'with_covariance':0,'zero_covariance':0}
    total_variance = dict(successes)
    for epoch, observed, sigma in held:
        independent = v0+epoch**2*vp+sigma**2
        for arm,var in (('with_covariance',independent+2*epoch*cov),('zero_covariance',independent)):
            successes[arm] += (observed-intercept-epoch*slope)**2 <= Fraction('1.96')**2*var
            total_variance[arm] += var
    return {**base,'decision':'RETROSPECTIVE_REPLAY' if held else 'ABSTAIN_NO_HELD_EPOCHS',
            'covariance_day2':float(cov),'held_95pct_count':successes,
            'held_total_predictive_variance_s2':{key:float(value*86400**2) for key,value in total_variance.items()}}


def work(paper, early, timings):
    early_bytes = early.read_bytes()
    if sha256(early_bytes).hexdigest()!=EARLY or sha256(timings.read_bytes()).hexdigest()!=ARCHIVE:
        raise ValueError('ORIGINAL_OBSERVATION_DIGEST')
    selected = dict(flagged(paper))
    if len(selected)!=5:
        raise ValueError('PILOT_POPULATION')
    prior = {line[:14].strip():(exact(line[15:30].strip()),exact(line[41:53].strip()))
             for line in early_bytes.decode('ascii').splitlines() if line[:14].strip() in selected}
    with ZipFile(timings) as archive:
        results = {}
        for name, witness in selected.items():
            raw = archive.read('by_planet/'+name+'.txt')
            results[name] = {'paper_witness':witness,'timings_sha256':sha256(raw).hexdigest(),
                             **analyze(original_times(raw),prior.get(name))}
    return {'cutoff_bjd_tdb':str(float(SPLIT)), 'ephemerides_early_sha256':EARLY,
            'observation_archive_sha256':ARCHIVE,'targets':results,
            'scope':'Retrospective data readiness. One point per epoch, independent reported errors assumed, no added jitter, no telescope allocation.'}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for filename in ('paper','earlier','timings'):
        parser.add_argument(filename,type=Path)
    options = parser.parse_args()
    print(canonical(work(options.paper,options.earlier,options.timings)).decode())
