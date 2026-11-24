"""Replay the shipped evidence, or requalify and apply one recorded instrument."""

import argparse
from pathlib import Path
import sys

from inventor import compact, digest, load, proposals, require
from inventor_verify import grade
from relational import check, evaluate


def replay_trace(run, sample, arm, prior, observations):
    require(run['binding']['prior_sha256'] == (digest(prior) if prior else None), 'PRIOR')
    previous = []
    seen_usage = 0
    for event in run['events']:
        _, selection = proposals(sample['development'], previous, arm, prior['method'] if prior else None, observations)
        require(event['selection'] == selection, 'METHOD_TRACE')
        seen_usage += event['used_output']
        if 'candidate' in event:
            previous = check(sample['mission'], sample['development'], event['candidate']['sql'])
            require(previous == event['checks'] and sum(x['pass'] for x in previous) == event['matches'], 'DEVELOPMENT_TRACE')
    require(seen_usage == run['spent_output'] and seen_usage <= run['output_budget'], 'USAGE')


def replay(evidence, reproduction):
    registration = reproduction['registration']
    require(evidence['registration_sha256'] == digest(registration), 'REGISTRATION')
    require(digest(reproduction['opportunities']) == registration['opportunities'], 'OPPORTUNITIES')
    choice = evidence['runs']['opportunity']
    if 'opportunity_run_sha256' in registration:
        require(digest(choice) == registration['opportunity_run_sha256'], 'OPPORTUNITY_SELECTION')
    if choice['status'] == 'SELECTED':
        require(evidence['first_mission'] == choice['result']['choice'], 'OPPORTUNITY_SELECTION')
    prior = evidence['runs'].get('method', {}).get('result')
    if prior:
        first = evidence['runs']['first']
        require(prior['first'] == first['result'] and prior['lineage']['first_run_sha256'] == digest(first) and
                prior['lineage']['method_sha256'] == digest(prior['method']), 'LINEAGE')
    for name, sample in reproduction['missions'].items():
        require(digest(sample['development']) == registration['commitments'][name]['development'], 'DEVELOPMENT')
    verified = {}
    for label, recorded in evidence['assessments'].items():
        expected = recorded['assessment']
        name, arm = expected['mission'], expected['arm']
        sample = reproduction['missions'][name]
        candidate = sample['incumbent'] if arm == 'conventional' else evidence['runs'][label]
        if arm != 'conventional':
            replay_trace(candidate,sample,arm,None if arm == 'original' else prior,bool(registration.get('development_feedback')))
        result = grade(registration, sample['mission'], sample['confirmation'], candidate, arm)
        require(result['assessment'] == expected and result['sha256'] == recorded['sha256'], 'ASSESSMENT')
        verified[label] = {'matched':expected['matched'],'total':expected['total'],'verdict':expected['verdict']}
    return verified


def main(args):
    root = Path(__file__).resolve().parent
    prefix = 'larger-' if args.larger else 'diagnostic-' if args.diagnostic else ''
    evidence, reproduction = (load(root/'study'/f'{prefix}{name}.json') for name in ('evidence','reproduction'))
    verified = replay(evidence, reproduction)
    if args.apply:
        label, path = args.apply
        require(label in verified and verified[label]['verdict'] == 'MATCHED', 'CANDIDATE_QUALIFICATION')
        scope = evidence['assessments'][label]['assessment']
        sample = reproduction['missions'][scope['mission']]
        candidate = sample['incumbent'] if scope['arm'] == 'conventional' else evidence['runs'][label]['result']
        return {'result':evaluate(sample['mission']['tables'],load(path),candidate['sql']), 'scope':scope['mission']}
    return {'schema':'frontier/inventor-replay-v1','registration_sha256':evidence['registration_sha256'],
            'evidence_sha256':digest(evidence),'comparisons':verified}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    cohort = parser.add_mutually_exclusive_group()
    cohort.add_argument('--diagnostic',action='store_true',help='Replay the separately registered diagnostic-feedback trial')
    cohort.add_argument('--larger',action='store_true',help='Replay the separately registered larger-model construction test')
    parser.add_argument('--apply',nargs=2,metavar=('ARM','INPUT'))
    try:
        print(compact(main(parser.parse_args())))
    except (ValueError,OSError,KeyError,TypeError,RecursionError):
        print('Replay refused. Check the original receipt, case sheet and input files.',file=sys.stderr)
        sys.exit(2)
