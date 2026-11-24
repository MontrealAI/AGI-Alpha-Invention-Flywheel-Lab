"""Fit on development-side data and independently challenge recorded candidates."""

import argparse
import json
from pathlib import Path

from learning import BASELINES, conventional, eligible, examples, forecasts, train
from pages import EVENTS, canonical, digest


def read(path):
    with path.open('rb') as stream:
        data = stream.read(2_000_001)
    if len(data)>2_000_000:
        raise ValueError('INPUT_SIZE')
    return json.loads(data)


def part(root, commitments, name, low, high):
    rows = read(root/f'{name}.json')
    if (digest(rows)!=commitments[name] or any(not low<r['number']<=high or r['completed'] is None for r in rows)
            or len({r['id'] for r in rows})!=len(rows)):
        raise ValueError('PARTITION_DRIFT')
    return rows


def fit(root):
    registration = read(root/'inputs.json')
    a,b,_ = registration['cutoffs']
    raw = part(root,registration['commitments'],'fit',0,a)
    dev = part(root,registration['commitments'],'development',a,b)
    cases = examples(raw)
    model, resources = train(cases)
    compare = forecasts(examples(dev,raw),model)
    best = min(BASELINES,key=lambda arm:(compare[arm]['mae_seconds'],compare[arm]['p90_seconds'],arm))
    return {'schema':'frontier/adaptive-training-v1','dataset':digest(registration),'model':model,
            'training':resources,'development':compare,'selected_baseline':best}


def forecast_verdict(model, held, baseline):
    results = forecasts(held,model)
    a,b = results['trained'],results[baseline]
    good = a['mae_seconds'] <= .9*b['mae_seconds'] and a['p90_seconds'] <= b['p90_seconds']
    return {'reference':baseline,'verdict':'QUALIFIED' if good else 'REJECTED','comparisons':results}


def transfer_check(runs, development, history):
    from research import ARMS, development_items, previews

    cohort=[runs[label] for label in ARMS if label in runs]
    strategy=runs.get('method',{}).get('result')
    if len(cohort)!=len(ARMS) or strategy is None:
        return {'state':'ABSTAIN','reason':'INCOMPLETE_TRANSFER','runs':len(cohort)}
    control=cohort[0]
    if any((run['model'],run['config_sha256'],run['output_budget']) !=
           (control['model'],control['config_sha256'],control['output_budget']) for run in cohort):
        raise ValueError('UNMATCHED_TRANSFER')
    cases=[c for c in examples(development,history) if c['event']=='pull_request']
    rows,_=development_items(cases)
    comparison={}
    for label,run in zip(ARMS,cohort):
        prior=None if label=='original' else strategy
        if run['binding']['prior_sha256']!=(digest(prior) if prior else None) or run['binding']['arm']!=label:
            raise ValueError('TRANSFER_LINEAGE')
        _, expected=previews(rows,label,prior)
        if any(event['selection']!=expected for event in run['events']):
            raise ValueError('TRANSFER_SELECTION')
        comparison[label]=dict(expected,attempted=len(run['events']))
    return {'state':'COMPARED','method_sha256':digest(strategy),'observed_selection':comparison}


def check(root, experiment, runs=None):
    inputs = read(root/'inputs.json')
    fit_no,dev_no,end_no = inputs['cutoffs']
    bound = inputs['commitments']
    raw = part(root,bound,'fit',0,fit_no)
    dev = part(root,bound,'development',fit_no,dev_no)
    held = part(root,bound,'confirmation',dev_no,end_no)
    model = experiment['model']
    audit = fit(root)
    if (experiment['dataset']!=digest(inputs) or audit['model']!=model or
            audit['selected_baseline']!=experiment['selected_baseline']):
        raise ValueError('MODEL_OR_REFERENCE_DRIFT')
    held_cases = examples(held,[*raw,*dev])
    verdict = forecast_verdict(model,held_cases,experiment['selected_baseline'])
    reports = {}
    transfer = transfer_check(runs,dev,raw) if runs else None
    if runs:
        from research import policy_monitor
        for event in EVENTS:
            cases = [case for case in held_cases if case['event']==event]
            if not cases:
                reports[event] = {'availability':'NO_ELIGIBLE_CONFIRMATION'}
                continue
            baselines = conventional(cases)
            best = min((key for key in baselines if eligible(baselines[key])),key=lambda k:baselines[k]['reads'])
            report = {'incumbent':best,'references':baselines,'candidates':{}}
            reports[event] = report
            for label, run in runs.items():
                if run['binding']['event']!=event or run['binding']['kind']!='adaptive-construct':
                    continue
                if run['binding']['development_sha256']!=bound['development']:
                    raise ValueError('CONSTRUCTOR_DEVELOPMENT_DRIFT')
                if run['binding']['history_sha256']!=bound['fit']:
                    raise ValueError('CONSTRUCTOR_HISTORY_DRIFT')
                try:
                    result = policy_monitor(run['result'],cases) if run['result'] else None
                except ValueError as error:
                    report['candidates'][label] = {'verdict':'REJECTED','reason':str(error)}
                    continue
                advance = (result is not None and eligible(result) and
                           result['reads']*10 <= baselines[best]['reads']*9 and run['status']=='SEALED')
                report['candidates'][label] = {'verdict':'QUALIFIED' if advance else 'REJECTED',
                                               'run_sha256':digest(run),'result':result}
    return {'schema':'frontier/adaptive-verification-v1','dataset':digest(inputs),'model_sha256':digest(model),
            'forecast':verdict,'monitoring':reports,'transfer':transfer,'public_cases':len(held_cases)}


if __name__=='__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('command',choices=('fit','verify'))
    cli.add_argument('cohort',type=Path)
    cli.add_argument('--training',type=Path)
    cli.add_argument('--runs',type=Path)
    args = cli.parse_args()
    if args.command=='fit':
        value = fit(args.cohort)
    else:
        if args.training is None:
            cli.error('verify needs --training')
        value = check(args.cohort,read(args.training),read(args.runs) if args.runs else None)
    print(canonical(value).decode())
