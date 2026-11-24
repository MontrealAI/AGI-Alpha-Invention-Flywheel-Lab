"""Reproduce a sealed artifact against separately held, committed cases."""

import argparse
from pathlib import Path
import sys
from time import perf_counter_ns

from inventor import ARMS, SCHEMA, compact, digest, load, record, require, validate_mission
from relational import check


def grade(registration, mission, cases, artifact, arm):
    require(registration['schema'] == 'frontier/inventor-registration-v1', 'REGISTRATION')
    validate_mission(mission, cases)
    commitment = registration['commitments'][mission['id']]
    require(digest(mission) == commitment['mission'] and digest(cases) == commitment['confirmation'], 'COMMITMENT')
    if arm == 'conventional':
        require(digest(artifact) == commitment['incumbent'], 'INCUMBENT')
        candidate = artifact
        development_status = 'CONVENTIONAL'
    else:
        require(artifact['schema'] == SCHEMA and artifact['model'] == registration['model'], 'MODEL')
        binding = artifact['binding']
        require(binding['kind'] == 'construction' and binding['arm'] == arm and
                binding['mission_sha256'] == commitment['mission'] and
                binding['cases_sha256'] == commitment['development'], 'RUN_BINDING')
        candidate = artifact['result']
        development_status = artifact['status']
    require(development_status in ('CONVENTIONAL','SEALED','DEVELOPMENT_INCOMPLETE','ABSTAIN'), 'RUN_OPEN')
    started = perf_counter_ns()
    if candidate is None:
        results = [{'id':case['id'],'pass':False, 'error':'NO_ARTIFACT'} for case in cases]
    else:
        record(candidate, {'sql':6000,'hypothesis':600})
        results = check(mission, cases, candidate['sql'])
    wall_ns = perf_counter_ns() - started
    matched = sum(row['pass'] for row in results)
    verdict = 'MATCHED' if matched == len(cases) and development_status in ('CONVENTIONAL','SEALED') else 'REJECTED'
    result = {'schema':'frontier/inventor-assessment-v1','mission':mission['id'], 'arm':arm,
              'registration_sha256':digest(registration),'cases_sha256':digest(cases),
              'submitted_sha256':digest(artifact),'candidate_sha256':digest(candidate) if candidate else None,
              'completed_development':development_status, 'matched':matched, 'total':len(cases),
              'verdict':verdict,'checks':results}
    return {'assessment':result, 'sha256':digest(result),'observed_evaluator_wall_ns':wall_ns}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('registration',type=Path)
    parser.add_argument('mission',type=Path)
    parser.add_argument('cases',type=Path)
    parser.add_argument('artifact',type=Path)
    parser.add_argument('arm',choices=(*ARMS,'conventional'))
    args = parser.parse_args()
    try:
        print(compact(grade(load(args.registration),load(args.mission),load(args.cases),load(args.artifact),args.arm)))
    except (ValueError,OSError,KeyError,TypeError,RecursionError):
        print('Evaluation refused. Check the frozen commitments and submitted run.',file=sys.stderr)
        sys.exit(2)
