"""Execute the registered public pilot from a staged inventor companion."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

from protocol import MISSIONS, canonical, digest


def load(path):
    return json.loads(path.read_bytes())


def main(study, companion, config):
    registration = load(study/'registration.json')
    constructor, evaluator = study/'constructor', study/'evaluator'
    output = study/'observed'
    output.mkdir(mode=0o700, exist_ok=True)
    blocks = output/'runs'
    assessments = {}

    def execute(script, *arguments):
        command = [sys.executable,str(companion/script),*map(str,arguments)]
        return json.loads(subprocess.run(command, check=True, stdout=subprocess.PIPE).stdout)

    def construct(kind, label, meeting, budget, *arguments):
        return execute('inventor.py',kind,'--workspace',blocks/label,'--input',meeting,
                       '--config',config,'--provider','localhost-inference','--model',registration['model'],
                       '--budget',budget,*arguments)

    def assess(name, label, candidate, arm):
        result = execute('inventor_verify.py',study/'registration.json',constructor/f'{name}.json',
                         evaluator/f'{name}-confirmation.json',candidate,arm)
        assessments[label] = result
        r = result['assessment']
        print(f'{label} · {r["verdict"]} {r["matched"]}/{r["total"]}',flush=True)
        return result

    observed = {'registration_sha256':digest(registration),'source':registration['source'],'runs':{},
                'assessments':assessments,'complete_cost':None,'realized_member_value':None,'paid_inference_usd':0}
    runs = observed['runs']
    budgets = registration['output_budgets']
    if 'opportunity_run_sha256' in registration:
        choice = load(constructor/'fixed-opportunity.json')
        if digest(choice) != registration['opportunity_run_sha256']:
            raise ValueError('Registered opportunity choice changed.')
        runs['opportunity'] = choice
    else:
        runs['opportunity'] = construct('choose','opportunity',constructor/'opportunities.json',budgets['opportunity'])
    if runs['opportunity']['status'] != 'SELECTED':
        (output/'receipt.json').write_bytes(canonical(observed)+b'\n')
        return
    first = runs['opportunity']['result']['choice']
    observed['first_mission'] = first
    dev = constructor/f'{first}-development.json'
    runs['first'] = construct('construct','first',constructor/f'{first}.json',budgets['construction'], '--development', dev)
    assess(first,'first',blocks/'first/run.json','original')
    for name in MISSIONS:
        assess(name,f'{name}-conventional',evaluator/f'{name}-incumbent.json','conventional')
    if runs['first']['result'] is not None:
        runs['method'] = construct('learn','method',blocks/'first/run.json',budgets['method'],'--development',dev)
        if runs['method']['status'] == 'SEALED':
            prior = output/'prior.json'
            retained = canonical(runs['method']['result'])+b'\n'
            if prior.exists() and prior.read_bytes() != retained:
                raise ValueError('Prior differs from the retained method.')
            prior.write_bytes(retained)
            arms = ['original','ordinary','augmented','withdrawn']
            for index,name in enumerate(k for k in MISSIONS if k != first):
                for arm in (arms if index == 0 else reversed(arms)):
                    label = f'{name}-{arm}'
                    options = ['--development',constructor/f'{name}-development.json','--arm',arm]
                    if arm != 'original':
                        options += ['--prior', prior]
                    runs[label] = construct('construct',label,constructor/f'{name}.json',budgets['construction'],*options)
                    assess(name,label,blocks/f'{label}/run.json',arm)
    (output/'receipt.json').write_bytes(canonical(observed)+b'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study',type=Path)
    parser.add_argument('companion',type=Path)
    parser.add_argument('config',type=Path)
    args = parser.parse_args()
    main(args.study.resolve(), args.companion.resolve(), args.config.resolve())
