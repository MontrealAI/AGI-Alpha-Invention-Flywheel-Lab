"""Refit the public model and reproduce the independent confirmation."""

import argparse
from pathlib import Path

from check import check, read
from pages import canonical, digest


def stable_result(value):
    if isinstance(value,dict):
        return {k:stable_result(v) for k,v in value.items() if k not in ('wall_ns','cpu_ns','measured_ns')}
    if isinstance(value,list):
        return [stable_result(x) for x in value]
    return value


def replay(root,full):
    stored=read(root/'verification.json')
    training=read(root/'training.json')
    calculated=check(root/'cohort',training,read(root/'runs.json') if full else None)
    if not full:
        stored['monitoring']={}
        stored['transfer']=None
    if stable_result(calculated)!=stable_result(stored):
        raise ValueError('VERIFICATION_DRIFT')
    results=calculated['forecast']
    return {'case_count':calculated['public_cases'],'model_sha256':calculated['model_sha256'],
            'trained_parameters':len(training['model']['weights']),
            'parameters_changed':sum(a!=b for a,b in zip(training['model']['init'],training['model']['weights'])),
            'forecast_verdict':results['verdict'],'reference':results['reference'],
            'mean_error_seconds':{k:v['mae_seconds'] for k,v in results['comparisons'].items()},
            'monitoring':{event:{label:r['verdict'] for label,r in group.get('candidates',{}).items()}
                          for event,group in calculated['monitoring'].items()},
            'transfer':calculated['transfer'],
            'confirmation_sha256':digest(stable_result(calculated))}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full',action='store_true')
    args=parser.parse_args()
    print(canonical(replay(Path(__file__).resolve().parent/'study',args.full)).decode())
