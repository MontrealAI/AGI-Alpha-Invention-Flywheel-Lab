"""Diagnose an observed instrument failure and resume a new registered design."""

import argparse
import json
from pathlib import Path
import signal

from amplify import CODE, canonical, development, proposed_instrument, read
from model_step import step
from native_experiment import run
from study import atomic


def refine(args):
    plan, scope = read(args.registration)
    repair, repair_sha = read(args.repair)
    previous, prior_sha = read(args.instrument)
    if (previous['registration_sha256'] != scope or repair['previous_instrument_sha256'] != prior_sha
            or repair['parent_registration_sha256'] != scope or repair['model'] != args.model):
        raise ValueError('REFINEMENT_BINDING')
    examples = development(args.development, plan['development_sha256'])
    prior_request = {'contract':plan['contract'],'examples':examples,'feedback':[]}
    prior_run = run(previous['result']['source'], prior_request)
    transient = {key:prior_run[key] for key in ('result','error') if key in prior_run}
    prompt = ('''A previously proposed tool meant to help scientists construct correct software failed its own
development interface test. Use the actual error below to diagnose the failure. Then construct an improved
independent diagnostic instrument, not a solver for just this worked data and not a copy of the expected output.
Use the named JSON structure. The contract is prose supplied as one full string, not an encoded mapping.
An experiment can use other input fields in another scientific domain. Explicitly check semantics before using
columns. Use pure Python in a worker that has no external filesystem, subprocesses, or network. Return JSON
with a short hypothesis and Python source. Source must define solve(request) returning a nonempty list of at
most 12 short strings of at most 240 characters each. The strings should help a model avoid actual semantic
confusion using the supplied contract and data. Each reader also receives the original examples.\n'''
              + canonical({'refinement':repair_sha, 'request':prior_request,'previous':previous['result'],
                           'observed':transient}))
    record=step(args.workspace,args.config,args.model,CODE,prompt,'instrument-refinement',repair['request_tokens'],
                attempts=repair['attempts'],deadline=args.until)
    if record['status']=='SEALED':
        revised=record['result']
        check=proposed_instrument(revised, plan['contract'], examples, [])
        atomic(args.workspace/'instrument.json',{'registration_sha256':scope,'result':revised,'revision':repair_sha,
            'parent':prior_sha,'observed_original':transient,'development_diagnostics':check})
    return record


def interrupt(_signal, _frame):
    raise KeyboardInterrupt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('registration','repair','instrument','development','config','workspace'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--until',type=int,required=True)
    signal.signal(signal.SIGTERM,interrupt)
    try:
        print(json.dumps(refine(parser.parse_args()),ensure_ascii=False,indent=2))
    except KeyboardInterrupt:
        parser.exit(130,'Paused. Resume using the same experiment binding.\n')
