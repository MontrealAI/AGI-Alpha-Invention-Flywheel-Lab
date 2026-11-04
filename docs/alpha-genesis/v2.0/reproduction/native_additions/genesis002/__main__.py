from __future__ import annotations
import argparse
import json
from pathlib import Path
from .common import read
from .engine import run, STRESSES
from .audit import audit


def main():
    parser=argparse.ArgumentParser(description='GENESIS Ω: native simulated execution; no paid API or real commerce.')
    parser.add_argument('command',choices=('plan','run','resume','audit'))
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--config',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--stress',choices=STRESSES,default='central')
    parser.add_argument('--max-cycles',type=int,help='Pause after this many additional completed cycles; no account reset.')
    args=parser.parse_args()
    try:
        if args.command=='plan':
            if args.config is None:parser.error('--config is required for plan')
            from .decision import startup_screen
            result=startup_screen(read(args.config))
        elif args.output is None:parser.error('--output is required for execution or audit')
        elif args.command=='audit':
            result=audit(args.repo,args.output)
        else:
            if args.command=='run' and args.config is None:parser.error('--config is required for a new account')
            result=run(args.repo,args.output,read(args.config) if args.config else None,
                       stress=args.stress,resume=args.command=='resume',max_cycles=args.max_cycles)
        print(json.dumps(result,indent=2,sort_keys=True,allow_nan=False))
    except (ValueError,OSError,KeyError) as exc:
        parser.exit(2,f'GENESIS refused operation: {exc}\n')


if __name__=='__main__':main()
