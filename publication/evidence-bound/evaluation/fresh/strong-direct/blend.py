#!/usr/bin/env python3
"""Exact blend balance. Pass a JSON file or '-' for standard input."""

import argparse
import json
import sys
from fractions import Fraction
from pathlib import Path


MASS_IN_MG = {'kg': 1000000, 'g': 1000, 'mg': 1, 'ug': Fraction(1, 1000),
              'ng': Fraction(1, 1000000)}
VOLUME_IN_L = {'kL': 1000, 'L': 1, 'dL': Fraction(1, 10),
               'cL': Fraction(1, 100), 'mL': Fraction(1, 1000),
               'uL': Fraction(1, 1000000), 'nL': Fraction(1, 1000000000)}


def balance(batches):
    masses, volumes, concentrations = [], [], []
    for batch in batches:
        concentration_unit = batch['concentration_unit'].replace('µ', 'u').replace('μ', 'u')
        mass_unit, denominator_unit = concentration_unit.split('/')
        volume_unit = batch['volume_unit'].replace('µ', 'u').replace('μ', 'u')
        concentration = (Fraction(batch['concentration']) * MASS_IN_MG[mass_unit]
                         / VOLUME_IN_L[denominator_unit])
        volume = Fraction(batch['volume']) * VOLUME_IN_L[volume_unit]
        concentrations.append(concentration)
        volumes.append(volume)
        masses.append(concentration * volume)

    total_volume, total_mass = sum(volumes), sum(masses)
    if total_volume <= 0:
        raise ValueError('A positive total blend volume is required')
    blend = sum(concentration * (volume / total_volume)
                for concentration, volume in zip(concentrations, volumes))
    if blend * total_volume != total_mass:
        raise ArithmeticError('The mass and volume balance does not close')

    return {
        'status': 'ok',
        'metrics': {
            'blend_concentration': exact(blend, 'mg/L'),
            'solute_mass': exact(total_mass, 'mg'),
            'blend_volume': exact(total_volume, 'L'),
        },
        'mass_volume_conserved': True,
    }


def exact(value, unit):
    return {'numerator': value.numerator, 'denominator': value.denominator, 'unit': unit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input')
    source = parser.parse_args().input
    raw = sys.stdin.read() if source == '-' else Path(source).read_text(encoding='utf-8')
    payload = json.loads(raw, parse_float=Fraction)
    if isinstance(payload, list) and payload and 'data' in payload[0]:
        payload, = [case for case in payload if 'batches' in case['data']]
    if isinstance(payload, dict):
        payload = payload.get('data', payload)['batches']
    print(json.dumps(balance(payload), sort_keys=True))


if __name__ == '__main__':
    main()
