#!/usr/bin/env python3
"""Blinded, release-vintaged diagnostic for timing variations in DR C histories."""

import argparse
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import time

import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.stats import median_abs_deviation

from covariance_study import FENCE, elements, group_epochs, observations, weighted

DAY = 86400.0
LEGACY_SOURCES = {
    'elements': '2f1e4a3ad9dd3cc9f78e38f25c3a1d1e0ead1604ea0a86f66cc752ff1a666033',
    'observations': '68231e16f2de416b2070570ec71085db6ee91622cc231ef942bb91cc747c8f09',
    'manifest': 'eb2d9ba5f9f0b329a83eb3c39c98ecd7e74a25d1d99d3f41fe43dc72686379d5',
}
PROTOCOL = {
    'timing_cutoff_bjd_tdb': str(FENCE),
    'epoch_association_max_abs_phase': 0.20,
    'reference_uncertainty': 'DR C published independent epoch and period marginals, plus historical median timing error',
    'historical_calibration': 'One latest timing per non-test system; predict from a preselected older prefix using an independent-marginals pseudo-ephemeris pivoted at its median epoch',
    'calibration_ratio_bands': ((0.0, 1.0, 0.75), (1.0, 2.0, 1.5), (2.0, 4.0, 3.0)),
    'minimum_calibration_systems': 30,
    'nominal_coverage': 0.90,
    'model': 'Generalized least-squares linear ephemeris plus a Matérn-3/2 process on the O−C residuals',
    'coherence_timescale_history_fraction': 0.50,
    'minimum_unique_training_epochs': 12,
    'minimum_rolling_training_epochs': 8,
    'minimum_residual_amplitude_to_reported_error': 2.5,
    'minimum_process_variance_reduction': 0.10,
    'maximum_lead_to_history_span': 1.00,
    'rolling_lead_ratio': (0.60, 1.40),
    'minimum_rolling_forecasts': 6,
    'minimum_rolling_blocks': 3,
    'validation_block_width_lead_ratio': 0.20,
    'max_ttv_to_linear_median_block_error': 0.80,
    'minimum_fraction_blocks_improved': 2 / 3,
    'conditional_uncertainty_multiplier': 'Maximum standardized historical rolling residual, floored at 1.645',
}


def verified_input(path, role):
    data = path.read_bytes()
    if sha256(data).hexdigest() != LEGACY_SOURCES[role]:
        raise ValueError(f'Frozen {role} bytes mismatch')
    return data


def system_name(name):
    return re.sub(r'(?:\.[0-9]+|[b-z])$', '', name)


def rows_as_floats(rows):
    return [(n, float(d), float(s)) for n, d, s in rows]


def linear(rows, target):
    fit = weighted(rows, [s**-2 for _, _, s in rows])
    x, y, sq, total, slope = fit
    noise_sq = float(np.median([s for _, _, s in rows]))**2
    mean = y + (target - x) * slope
    full_sd = math.sqrt(noise_sq + 1 / total + (target - x)**2 / sq)
    pivot = float(np.median([n for n, _, _ in rows]))
    diagonal_sd = math.sqrt(noise_sq + 1 / total + ((pivot - x)**2 + (target - pivot)**2) / sq)
    return mean, full_sd, diagonal_sd


def whole_epoch(ephemeris, date_start, date_stop):
    reference, _, period, _ = ephemeris
    left, right = Decimal(str(date_start)), Decimal(str(date_stop))
    max_oc = Decimal(str(PROTOCOL['epoch_association_max_abs_phase'])) * period
    earliest = int(((left - max_oc - reference) / period).to_integral_value(rounding=ROUND_CEILING))
    latest = int(((right + max_oc - reference) / period).to_integral_value(rounding=ROUND_FLOOR))
    count = max(0, latest - earliest + 1)
    return (earliest if count == 1 else None), count, float(max_oc)


def calibration(histories, test_systems):
    scores = defaultdict(dict)
    bands = PROTOCOL['calibration_ratio_bands']
    for name, rows in histories.items():
        system = system_name(name)
        if system in test_systems or len(rows) < 5:
            continue
        expected_epoch, observed_oc, _ = rows[-1]
        first_epoch = rows[0][0]
        for index, (lower, upper, typical) in enumerate(bands):
            options = []
            for count in range(4, len(rows)):
                origin = rows[count - 1][0]
                lead_to_span = (expected_epoch - origin) / (origin - first_epoch)
                if lower < lead_to_span <= upper:
                    options.append((abs(math.log(lead_to_span / typical)), -count, count))
            if not options:
                continue
            count = min(options)[-1]
            forecast, full_sd, marg_sd = linear(rows[:count], expected_epoch)
            error = abs(forecast - observed_oc)
            scores[index].setdefault(system, {})[name] = (error / full_sd, error / marg_sd)
    result = {}
    for index in range(len(bands)):
        # Retain one predetermined planet per stellar system in each horizon band.
        groups = [group[min(group)] for group in scores[index].values()]
        rank = math.ceil(PROTOCOL['nominal_coverage'] * (len(groups) + 1))
        result[index] = {'systems': len(groups), 'rank_1_indexed': rank}
        if len(groups) >= PROTOCOL['minimum_calibration_systems'] and rank <= len(groups):
            result[index]['weighted_multiplier'] = sorted(x[0] for x in groups)[rank - 1]
            result[index]['released_marginals_multiplier'] = sorted(x[1] for x in groups)[rank - 1]
    return result


def calibration_band(lead_to_span, bands):
    for index, (lower, upper, _) in enumerate(PROTOCOL['calibration_ratio_bands']):
        if lower < lead_to_span <= upper:
            return index, bands[index]
    return None, {}


def matern32(distance):
    x = math.sqrt(3.0) * np.abs(distance)
    return (1.0 + x) * np.exp(-x)


def timing_variation(rows, target):
    epochs, residual, sigma = np.asarray(rows, dtype=float).T
    span = epochs[-1] - epochs[0]
    pivot = (epochs[-1] + epochs[0]) / 2.0
    coordinate = (epochs - pivot) / span
    x = np.column_stack((np.ones(epochs.size), coordinate))
    noise = float(np.median(sigma))
    initial = np.linalg.lstsq(x / sigma[:, None], residual / sigma, rcond=None)[0]
    scatter = float(median_abs_deviation(residual - x @ initial, scale='normal'))
    amplitude = math.sqrt(max(0.0, scatter**2 - noise**2))
    diagnostics = {'history_noise_s': noise * DAY, 'residual_process_amplitude_s': amplitude * DAY}
    if amplitude < PROTOCOL['minimum_residual_amplitude_to_reported_error'] * noise:
        return None, diagnostics
    timescale = span * PROTOCOL['coherence_timescale_history_fraction']
    kernel = amplitude**2 * matern32((epochs[:, None] - epochs[None, :]) / timescale)
    kernel[np.diag_indices_from(kernel)] += sigma**2
    factor = cho_factor(kernel, lower=True)
    cinv_x = cho_solve(factor, x)
    trend_factor = cho_factor(x.T @ cinv_x, lower=True)
    trend = cho_solve(trend_factor, cinv_x.T @ residual)
    xstar = np.array([1.0, (target - pivot) / span])
    partial = amplitude**2 * matern32((epochs - target) / timescale)
    conditional = cho_solve(factor, partial)
    prediction = float(xstar @ trend + conditional @ (residual - x @ trend))
    trend_projection = xstar - x.T @ conditional
    variance_trend = trend_projection @ cho_solve(trend_factor, trend_projection)
    variance_reduction = float(np.clip(partial @ conditional / amplitude**2, 0.0, 1.0))
    deviation = math.sqrt(noise**2 + amplitude**2 * (1.0 - variance_reduction) + variance_trend)
    diagnostics.update({'coherence_timescale_epochs': timescale, 'process_variance_reduction': variance_reduction})
    return (prediction, deviation), diagnostics


def rolling_comparison(rows, lead):
    lower, upper = PROTOCOL['rolling_lead_ratio']
    training_minimum = PROTOCOL['minimum_rolling_training_epochs']
    block_width = max(3, math.ceil(PROTOCOL['validation_block_width_lead_ratio'] * lead))
    blocks = defaultdict(list)
    validation = []
    for index in range(training_minimum, len(rows)):
        target, outcome, _ = rows[index]
        origins = []
        for origin in range(training_minimum - 1, index):
            rolled_lead = target - rows[origin][0]
            if lead * lower <= rolled_lead <= lead * upper:
                origins.append((abs(math.log(rolled_lead / lead)), -origin, origin))
        if not origins:
            continue
        prefix = rows[:min(origins)[-1] + 1]
        fit, _ = timing_variation(prefix, target)
        if fit is None:
            continue
        time_varying_mean, time_varying_sd = fit
        linear_mean, _, _ = linear(prefix, target)
        varying_error = abs(time_varying_mean - outcome)
        linear_error = abs(linear_mean - outcome)
        block = (target - rows[0][0]) // block_width
        blocks[block].append((varying_error, linear_error))
        validation.append((target, prefix[-1][0], varying_error / time_varying_sd))
    diagnostics = {
        'rolling_forecasts': len(validation), 'rolling_blocks': len(blocks),
        'rolling_origin_target_epochs': [[origin, target] for target, origin, _ in validation],
    }
    if not validation:
        return False, diagnostics
    median_blocks = np.array([np.median(block, axis=0) for block in blocks.values()])
    time_varying, conventional = np.median(median_blocks, axis=0)
    wins = float(np.mean(median_blocks[:, 0] < median_blocks[:, 1]))
    multiplier = max(1.645, max(item[2] for item in validation))
    diagnostics.update({
        'ttv_median_block_absolute_error_s': float(time_varying * DAY),
        'linear_median_block_absolute_error_s': float(conventional * DAY),
        'fraction_blocks_improved': wins,
        'rolling_uncertainty_multiplier': multiplier,
    })
    supported = (
        len(validation) >= PROTOCOL['minimum_rolling_forecasts'] and len(blocks) >= PROTOCOL['minimum_rolling_blocks']
        and conventional > 0 and time_varying <= PROTOCOL['max_ttv_to_linear_median_block_error'] * conventional
        and wins >= PROTOCOL['minimum_fraction_blocks_improved']
    )
    return supported, diagnostics


def result_forecast(pivot, correction, sigma, factor):
    return {
        'mid_bjd_tdb': float(pivot + Decimal(str(correction))),
        'sigma_s': sigma * DAY,
        'calibration_multiplier': factor,
        'nominal_90_halfwidth_s': sigma * factor * DAY if factor is not None else None,
    }


def predict(case, ephemeris, rows, calibration_bands):
    entry = {'id': case['id'], 'target': case['target'], 'older_epochs': len(rows)}
    if ephemeris is None:
        return {**entry, 'epoch': None, 'verdict': 'ABSTAIN_MISSING_RELEASED_EPHEMERIS'}
    epoch, count, phase_range = whole_epoch(ephemeris, case['search_start_bjd_tdb'], case['search_stop_bjd_tdb'])
    entry.update({'epoch': epoch, 'candidate_epochs': count, 'max_assumed_absolute_oc_days': phase_range})
    if epoch is None:
        return {**entry, 'verdict': 'ABSTAIN_AMBIGUOUS_EPOCH' if count else 'ABSTAIN_NO_EPOCH_IN_RANGE'}
    if len(rows) < 4:
        return {**entry, 'verdict': 'ABSTAIN_FEW_PRE_CUTOFF_EPOCHS'}
    reference, epoch_sd, period, period_sd = ephemeris
    nominal = reference + epoch * period
    lead = epoch - rows[-1][0]
    span = rows[-1][0] - rows[0][0]
    band, factors = calibration_band(lead / span, calibration_bands)
    noise = float(np.median([s for _, _, s in rows]))
    released_sd = math.sqrt(float(epoch_sd**2 + (epoch * period_sd)**2) + noise**2)
    weighted_mean, weighted_sd, _ = linear(rows, epoch)
    entry.update({
        'lead_days': float(lead * period), 'historical_span_days': float(span * period),
        'calibration_band': band, 'calibration_systems': factors.get('systems', 0),
        'released_marginals': result_forecast(nominal, 0.0, released_sd, factors.get('released_marginals_multiplier')),
        'weighted_linear': result_forecast(nominal, weighted_mean, weighted_sd, factors.get('weighted_multiplier')),
        'ttv': None,
    })
    if len(rows) < PROTOCOL['minimum_unique_training_epochs']:
        return {**entry, 'verdict': 'ABSTAIN_TTV_FEW_PRE_CUTOFF_EPOCHS'}
    if not 0 < lead <= PROTOCOL['maximum_lead_to_history_span'] * span:
        return {**entry, 'verdict': 'ABSTAIN_TTV_LEAD_OUTSIDE_HISTORICAL_SPAN'}
    proposal, diagnostics = timing_variation(rows, epoch)
    entry['diagnostics'] = diagnostics
    if proposal is None:
        return {**entry, 'verdict': 'ABSTAIN_TTV_RESIDUAL_AMPLITUDE_UNRESOLVED'}
    mean, sigma = proposal
    if abs(mean) > phase_range:
        return {**entry, 'verdict': 'ABSTAIN_TTV_PREDICTED_PHASE_OUTSIDE_ASSOCIATION_RANGE'}
    validated, comparison = rolling_comparison(rows, lead)
    diagnostics.update(comparison)
    if diagnostics['process_variance_reduction'] < PROTOCOL['minimum_process_variance_reduction']:
        return {**entry, 'verdict': 'ABSTAIN_TTV_WEAK_HISTORICAL_LEVERAGE'}
    if len(comparison['rolling_origin_target_epochs']) < PROTOCOL['minimum_rolling_forecasts'] or comparison['rolling_blocks'] < PROTOCOL['minimum_rolling_blocks']:
        return {**entry, 'verdict': 'ABSTAIN_TTV_INSUFFICIENT_MATCHED_LEAD_VALIDATION'}
    if not validated:
        return {**entry, 'verdict': 'ABSTAIN_TTV_NO_VALIDATED_GAIN_OVER_LINEAR'}
    entry['ttv'] = result_forecast(nominal, mean, sigma, comparison['rolling_uncertainty_multiplier'])
    return {**entry, 'verdict': 'DIAGNOSTIC_TTV_FORECAST'}


def run(args):
    began = time.perf_counter()
    ephemerides = elements(verified_input(args.elements, 'elements'))
    old_observations = observations(verified_input(args.observations, 'observations'), True)
    if any(row[0] >= FENCE for rows in old_observations.values() for row in rows):
        raise ValueError('Post-cutoff training observation')
    cases = [row for row in json.loads(verified_input(args.manifest, 'manifest'))['cases'] if row['cohort'] == 'held']
    if len(cases) != 11:
        raise ValueError('Unexpected number of held date bands')
    test_systems = {system_name(row['target']) for row in cases}
    histories = {
        target: rows_as_floats(group_epochs(old_observations.get(target, []), ephem[0], ephem[2]))
        for target, ephem in ephemerides.items()
    }
    calibrators = calibration(histories, test_systems)
    forecasts = [predict(case, ephemerides.get(case['target']), histories.get(case['target'], []), calibrators) for case in cases]
    return {
        'protocol': PROTOCOL, 'sha256': {**LEGACY_SOURCES, 'script': sha256(Path(__file__).read_bytes()).hexdigest()},
        'calibration': calibrators, 'verdict_counts': dict(Counter(row['verdict'] for row in forecasts)),
        'events': forecasts, 'wall_time_s': time.perf_counter() - began,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('elements', 'observations', 'manifest', 'output'):
        parser.add_argument('--' + argument, type=Path, required=True)
    args = parser.parse_args()
    result = run(args)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    temporary.replace(args.output)


if __name__ == '__main__':
    main()
