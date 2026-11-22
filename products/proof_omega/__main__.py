import argparse
import json
from pathlib import Path
from .checker import bundle, verify, load_json, Rejected
from .provider import repair

def main():
    p=argparse.ArgumentParser(description='PROOF Ω: verify pure integer kernels under an explicit frozen contract')
    sub=p.add_subparsers(dest='command',required=True)
    for name in ('check','repair'):
        q=sub.add_parser(name); q.add_argument('--source',required=True); q.add_argument('--contract',required=True); q.add_argument('--output',required=True)
        if name=='repair':
            q.add_argument('--model'); q.add_argument('--attempts',type=int,default=3)
            q.add_argument('--request-seconds',type=int,default=600)
            q.add_argument('--authorize-model-sharing',action='store_true',help='Explicitly authorize sharing these source/contract bytes with your authenticated Codex provider')
    q=sub.add_parser('verify'); q.add_argument('bundle')
    a=p.parse_args()
    try:
        if a.command=='verify': result=verify(a.bundle)
        else:
            source=Path(a.source).read_text(); c=load_json(a.contract)
            if a.command=='check': result=bundle(source,c,a.output)
            else:
                if not a.authorize_model_sharing: raise Rejected('model sharing requires explicit --authorize-model-sharing')
                result=repair(source,c,a.output,a.model,a.attempts,a.request_seconds)
        print(json.dumps(result,indent=2))
        return 0 if result['status']=='PROVED_SCOPED' else 2
    except (ValueError,OSError,Rejected) as e:
        print(json.dumps({'status':'REJECTED','reason':str(e)})); return 2

if __name__=='__main__': raise SystemExit(main())
