"""Audit whether stated measurement boxes admit one common slope."""

import argparse
from fractions import Fraction
import json
from pathlib import Path


def rows(problem):
    if type(problem) is not dict or set(problem)!={'points'} or type(problem['points']) is not list:
        raise ValueError('CALIBRATION_CONTRACT')
    ids = set()
    for row in problem['points']:
        if type(row) is not list or len(row)!=5:
            raise ValueError('CALIBRATION_ROW')
        key, x, tolerance_x, y, tolerance_y = row
        if (type(key) is not str or not key or key in ids
                or any(type(value) is not int for value in row[1:])
                or not (x > tolerance_x >= 0 and y > 0 and tolerance_y >= 0)):
            raise ValueError('CALIBRATION_UNITS')
        ids.add(key)
    if not ids:
        raise ValueError('EMPTY_CALIBRATION')
    return problem['points']


def exact(problem):
    measurements = rows(problem)
    best, witness = Fraction(0), []
    for i, x_i, ex_i, y_i, ey_i in measurements:
        for j, x_j, ex_j, y_j, ey_j in measurements:
            low_x, high_x = x_i + ex_i, x_j - ex_j
            necessary = Fraction((y_i-ey_i)*high_x-(y_j+ey_j)*low_x, y_i*high_x+y_j*low_x)
            if necessary > best or (necessary==best and best>0 and [i,j]<witness):
                best, witness = necessary, [i,j]
    return {'slack':[best.numerator,best.denominator],'witness':witness}


def interval(measurements, delta):
    lower = max([0]+[Fraction(y-ey-delta*y,x+ex) for _,x,ex,y,ey in measurements])
    upper = min(Fraction(y+ey+delta*y,x-ex) for _,x,ex,y,ey in measurements)
    return lower,upper


def validate(problem, output):
    """Check attainable and minimal with an independent interval calculation."""
    measurements = rows(problem)
    delta = Fraction(*output['slack'])
    witness = output['witness']
    lower, upper = interval(measurements, delta)
    if delta<0 or lower>upper or [delta.numerator,delta.denominator]!=output['slack']:
        return False
    if delta==0:
        return witness==[]
    if type(witness) is not list or len(witness)!=2:
        return False
    close = (lower==upper)
    left = min((key for key,x,ex,y,ey in measurements if Fraction(y-ey-delta*y,x+ex)==lower),default=None)
    right = min((key for key,x,ex,y,ey in measurements if Fraction(y+ey+delta*y,x-ex)==upper),default=None)
    return close and left is not None and right is not None and witness==[left,right]


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    args=parser.parse_args()
    with args.input.open('rb') as stream:
        value=stream.read(256_001)
    if len(value)>256_000:
        parser.error('Calibration file exceeds the transfer bound.')
    problem=json.loads(value)
    answer=exact(problem)
    if not validate(problem, answer):
        raise ValueError('CALIBRATION_CONTROLS_DIVERGE')
    print(json.dumps(answer,sort_keys=True))
