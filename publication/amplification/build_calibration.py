"""Prepare a new scientific challenge using a published calibration fixture."""

from decimal import Decimal, ROUND_HALF_EVEN
from hashlib import sha256
import json
from pathlib import Path
import sys

from build_cases import WEIGHTS, save
from calibration_environment import exact, validate


CONTRACT = '''Each row in input.points is [id, x, x_error, y, y_error], with positive x-x_error and y.
Let delta be a common nonnegative relative allowance. Each row permits x anywhere in [x-x_error,x+x_error]
and y anywhere in [y-y_error-delta*y,y+y_error+delta*y]. A slope k >= 0 is feasible if some permitted x and y
in every row satisfy y=k*x, with the same k for all rows. Return the smallest feasible delta as its fully reduced
nonnegative fraction. Output {"slack":[numerator,denominator],"witness":[lower_row_id,upper_row_id]}.
For positive delta, the witness rows must be tight at the attained common slope, one from below and one from above.
When several rows are tight, choose the smallest ID on each side. At zero slack output an empty witness list.
Programs may use Python integer arithmetic and fractions. Return exact values and do not fit a point estimate.'''
SOURCE = '7aedc8e4c3e7181e381055d3815378b3f5bfe7b5b9386fd5748803d495ab1ced'


def case(case_id, points):
    problem={'points':points}
    verified=exact(problem)
    if not validate(problem,verified):
        raise ValueError('CALIBRATION_CONTROLS_DIVERGED')
    return {'id':case_id,'input':problem,'expected':verified}


def scaled(value):
    return int((value*10**9).to_integral_value(rounding=ROUND_HALF_EVEN))


def create(source, root):
    root.mkdir(parents=True,exist_ok=False)
    data=source.read_bytes()
    if sha256(data).hexdigest()!=SOURCE:
        raise ValueError('CALIBRATION_SOURCE')
    fixture=json.loads(data,parse_float=Decimal,parse_int=Decimal)
    held=[]
    for family in fixture['calibration']:
        for phase, points in sorted(family['phases'].items()):
            if len(points['area_rows'])!=len(points['force_rows']):
                raise ValueError('CALIBRATION_PAIRING')
            held.append(case(f'{family["id"]}-{phase}',[
                [f'row-{i:02d}',scaled(area[0]),scaled(area[1]),scaled(force[2]),scaled(force[3])]
                for i,(area,force) in enumerate(zip(points['area_rows'],points['force_rows']),1)]))
    dev=[case('synthetic-conflict',[['a',2,0,2,0],['b',1,0,3,0]]),
         case('synthetic-fits',[['x',2,1,3,0],['y',4,0,6,1]])]
    written=save(root/'development.json',dev)
    sealed=save(root/'confirmation.json',held)
    name='qwen3-4b-instruct-2507-q4_k_m'
    save(root/'registration.json',{'schema':'frontier/amplification-registration-v1',
        'objective':'Obtain an exact witness for public calibration discrepancy', 'contract':CONTRACT,
        'development_sha256':written,'confirmation_sha256':sealed,'source_sha256':SOURCE,
        'source':'https://doi.org/10.5281/zenodo.22142148',
        'credit':'Li Fu, Djibril Gabriel Kashala, Davy Dalmas and Julien Scheibert. CC BY 4.0.',
        'scope':'Existing positive-area slope box with relative force uncertainty. Integer conversion to billionths. '
                'Results apply to the published numerical source; physical transfer is a separate study.',
        'design_tokens':850,'design_attempts':1,'weights':{name: WEIGHTS[name]},
        'comparisons':{name:{'arms':['harness','amplified'],'attempts':2,'request_tokens':850}},
        'materiality':'Probe whether the identical instrument produces applicable notes on a new shape. '
                      'Candidate testing may continue with staged context. No causal recursive claim from this probe.'})


if __name__=='__main__':
    create(Path(sys.argv[1]),Path(sys.argv[2]))
