"""ALPHA Economic Engine CLI: demo, doctor, run, serve, submit, status and audit."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import signal
import threading
import json
from .core import read,save,sign
from .agents import HarnessAgent,AuthoredFixtureAgent
from .commerce import SimulatedBuyer,HTTPBuyer,Stripe
from .runtime import Engine,default_policy
from .store import State


def secret(name):
    value=os.environ.get(name,'') if isinstance(name,str) else ''
    if len(value)<32:raise ValueError('MISSING_EXPLICIT_SECRET_ENVIRONMENT_VARIABLE')
    return value


def build(root,config):
    if not isinstance(config,dict) or config.get('schema')!='alpha-economic/config/v1':raise ValueError('EXACT_CONFIG_VERSION_REQUIRED')
    keys={buyer:secret(env).encode() for buyer,env in config['buyer_key_env'].items()}
    mode=config['policy']['scope']
    if config['agent'].get('kind')=='authored-fixture':
        if mode!='SIMULATED':raise ValueError('FIXTURE_AGENT_ONLY_FOR_SIMULATION')
        agent=AuthoredFixtureAgent()
    else:agent=HarnessAgent(config['agent'])
    if mode=='SIMULATED':return Engine(root,config['policy'],agent,SimulatedBuyer(keys),keys)
    from .gateway import TreasuryGateway
    from .live import LiveEngine
    stripe_cfg=config['stripe'];t=config['treasury'];b=config['buyers']
    stripe=Stripe(secret(stripe_cfg['key_env']),secret(stripe_cfg['webhook_secret_env']),mode=stripe_cfg['mode'],authorized=stripe_cfg.get('authorized') is True)
    treasury=TreasuryGateway(t['url'],secret(t['request_key_env']).encode(),secret(t['response_key_env']).encode(),t['account'],enabled=t.get('authorized') is True,mode=stripe_cfg['mode'])
    buyer=HTTPBuyer(b['endpoints'],keys,enabled=b.get('authorized') is True)
    return LiveEngine(root,config['policy'],agent,buyer,keys,treasury,stripe,success_url=stripe_cfg['success_url'],cancel_url=stripe_cfg['cancel_url'],authorized=config.get('external_execution_authorized') is True)


def doctor(config):
    """Offline readiness: does not retrieve credentials, ping providers or spend."""
    problems=[]
    try:
        if config.get('schema')!='alpha-economic/config/v1':problems.append('unsupported configuration schema')
        mode=config['policy']['scope']
        for env in config.get('buyer_key_env',{}).values():
            if len(os.environ.get(env,''))<32:problems.append('buyer authentication environment variable missing: '+env)
        kind=config.get('agent',{}).get('kind')
        if kind=='authored-fixture':problems.append('authored fixture is not model inference')
        if mode!='SIMULATED':
            if config.get('external_execution_authorized') is not True:problems.append('external execution not authorized')
            for key in ('stripe','treasury','buyers'):
                if not config.get(key,{}).get('authorized'):problems.append(key+' not configured and authorized')
            problems.append('real treasury gateway implementation and provider qualification must be supplied; not included in this package')
    except (KeyError,TypeError):problems.append('configuration incomplete')
    return {'offline_readiness':not problems,'issues':problems,'network_calls':0,
            'live_commercial_qualification':'NOT_ESTABLISHED','credentials_displayed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('./alpha-engine'))
    p.add_argument('--config',type=Path)
    sub=p.add_subparsers(dest='command',required=True)
    d=sub.add_parser('demo');d.add_argument('--output',type=Path,required=True)
    sub.add_parser('example-config');sub.add_parser('doctor');sub.add_parser('status');sub.add_parser('audit')
    for command in ('run','serve'):
        r=sub.add_parser(command);r.add_argument('--poll',type=float,default=1.0)
        if command=='run':r.add_argument('--watch',action='store_true')
        else:r.add_argument('--port',type=int,default=8765);r.add_argument('--token-env',default='ALPHA_CONTROL_TOKEN')
    s=sub.add_parser('submit');s.add_argument('--envelope',type=Path,required=True)
    args=p.parse_args()
    if args.command=='demo':
        from .demo import run
        result=run(args.output)
    elif args.command=='example-config':
        result={'schema':'alpha-economic/config/v1','policy':default_policy(),
                'agent':{'kind':'authored-fixture'},'buyer_key_env':{'buyer-demo':'ALPHA_BUYER_DEMO_KEY'}}
    else:
        if args.config is None:p.error('--config is required')
        config=read(args.config)
        if args.command=='doctor':result=doctor(config)
        elif args.command=='status':result=State(args.root,config['policy']).summary()
        else:
            engine=build(args.root,config)
            if args.command=='submit':result={'job':engine.submit(read(args.envelope))}
            elif args.command=='audit':
                with engine.state.lock():
                    try:engine._open();result=engine.report()
                    finally:engine.close()
            else:
                stop=threading.Event()
                signal.signal(signal.SIGTERM,lambda *_:stop.set());signal.signal(signal.SIGINT,lambda *_:stop.set())
                server=None;thread=None
                try:
                    if args.command=='serve':
                        from .server import make_server
                        server=make_server(engine,secret(args.token_env),args.port,stripe=getattr(engine,'stripe',None))
                        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                    result=engine.run(watch=args.command=='serve' or args.watch,poll=args.poll,stop=stop)
                finally:
                    if server:server.shutdown();server.server_close();thread.join()
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__=='__main__':main()
