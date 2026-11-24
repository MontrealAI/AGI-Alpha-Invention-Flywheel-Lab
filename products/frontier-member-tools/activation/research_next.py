"""Ask the local investigator what the released failure evidence warrants next."""

import argparse
from pathlib import Path

from activate import read, reject_invalid
from model_step import brief, object_schema, step
from pages import canonical


def propose(args):
    evaluation=read(args.evaluation)
    previous=read(args.observed)['state']
    selected=previous['completed'].get('retain-rule',{}).get('result')
    primary=evaluation['primary']
    evidence={'objective':evaluation['objective'],
              'first':{k:primary[k] for k in ('cases','valid','exact','error','verdict')},
              'fresh':{arm:{k:v[k] for k in ('cases','valid','exact','error','verdict','selection')}
                       for arm,v in evaluation['fresh'].items()},'policy':selected,
              'scope':'MONTREAL.AI independent public evidence recovery. No deploy authority.'}
    limits=object_schema({'next':brief(180),'why':brief(180),'falsifier':brief(180),'alternative':brief(120)})
    prompt=('Investigate the most consequential bottleneck revealed by this completed invention experiment. '
            'Recommend one concrete next test, cite the failed outcome that motivates it, state what would disprove the idea, '
            'and name a strong alternative. Consider changing the research direction. Do not equate a program compiling with a win. '
            'Return only JSON.\n'+canonical(evidence).decode())
    return step(args.workspace,args.config,args.model,limits,prompt,'research-review',384,attempts=2,
                validate=lambda value:reject_invalid(value,limits['required']),deadline=args.until)


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','evaluation','observed','config'):
        cli.add_argument('--'+name,type=Path,required=True)
    cli.add_argument('--model',required=True)
    cli.add_argument('--until',type=int,required=True)
    print(canonical(propose(cli.parse_args())).decode())
