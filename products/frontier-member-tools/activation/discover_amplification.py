"""Choose an experiment from an operator-authorized operating brief."""

import argparse
import json
from pathlib import Path
import signal

from model_step import brief, object_schema, step


SCHEMA = object_schema({key:brief(bound) for key,bound in (
    ('objective',220),('beneficiary',100),('observed_limit',220),('intervention',240),
    ('strong_control',180),('decisive_test',240),('why_this_now',200))})


def choose(args):
    with args.brief.open('rb') as stream:
        raw=stream.read(12_001)
    if not 0<len(raw)<=12_000:
        raise ValueError('OPERATING_BRIEF_SIZE')
    evidence=raw.decode('utf-8')
    prompt=(
        'Identify the next consequential research action for MONTREAL.AI from the operating evidence below. '
        'You may identify an objective absent from the brief. Explain the concrete limitation, the value of '
        'removing it, and a decisive independent test versus a capable existing alternative. Treat the evidence '
        'as observations and hypotheses. Respect stated resources and operational scope. Claim only established outcomes.\n'
        + evidence
    )
    return step(args.workspace,args.config,args.model,SCHEMA,prompt,'amplification-next-investigation',
                args.tokens,attempts=2,deadline=args.until)


def interrupt(_signum,_frame):
    raise KeyboardInterrupt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ('brief','workspace','config'):
        parser.add_argument('--'+flag,type=Path,required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--until',type=int,required=True)
    parser.add_argument('--tokens',type=int,default=640)
    signal.signal(signal.SIGTERM,interrupt)
    args=parser.parse_args()
    try:
        print(json.dumps(choose(args),ensure_ascii=False,indent=2))
    except KeyboardInterrupt:
        parser.exit(130,'Paused. Reuse the same workspace, brief, and model configuration.\n')
