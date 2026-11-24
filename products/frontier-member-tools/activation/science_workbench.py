"""Replay the published scientific environments with their independent checks."""

import argparse
from pathlib import Path

import calibration_environment as calibration
import route_environment as endpoint
from science_reference import verified
from science_substrate import calculate, canonical, exact, read_json


LABS = {
    'ephemeris': {
        'file': 'study/substrate/CASE.json',
        'scope': 'Linear ephemeris; model standard deviation over unknown covariance. Observing authorization: ABSTAIN.',
        'units': {'anchor': 'BJD_TDB', 'sigma_s': 'seconds', 'duration_hour': 'hours'},
    },
    'endpoint': {
        'file': 'study/amplification/trial.json',
        'scope': 'Published measured capacity on distinct systems. Operational adoption: ABSTAIN.',
        'units': {'rate_min': 'tokens per second per user', 'latency_max': 'milliseconds', 'load': 'concurrent queries'},
    },
    'calibration': {
        'file': 'study/amplification/calibration-trial.json',
        'scope': 'Feasibility of one common slope under declared measurement intervals.',
        'units': {'slack': 'unitless fraction [numerator, denominator]'},
    },
}


def replay(name, case):
    lab = LABS[name]
    if name == 'ephemeris':
        result = calculate(case)
        if result != verified(case):
            raise ValueError('EPHEMERIS_REFERENCE_DIVERGENCE')
        if result['decision'] in {'WITHIN', 'EXCEEDS', 'COVARIANCE_SENSITIVE'}:
            limit = 300 * exact(case['ephemeris']['duration_hour'])
            result['target_limit_s'] = [limit.numerator, limit.denominator]
    elif name == 'endpoint':
        result = endpoint.conventional(case)
        if result != endpoint.independent(case):
            raise ValueError('ENDPOINT_REFERENCE_DIVERGENCE')
    else:
        result = calibration.exact(case)
        if not calibration.validate(case, result):
            raise ValueError('CALIBRATION_REFERENCE_DIVERGENCE')
    return {'environment': name, 'scope': lab['scope'], 'units': lab['units'], 'result': result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=('list', *LABS))
    parser.add_argument('input', type=Path, nargs='?')
    args = parser.parse_args()
    if args.environment == 'list':
        output = LABS
    else:
        path = args.input or Path(__file__).resolve().parent / LABS[args.environment]['file']
        output = replay(args.environment, read_json(path))
    print(canonical(output).decode())


if __name__ == '__main__':
    main()
