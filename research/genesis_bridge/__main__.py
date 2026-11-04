"""Offline numerical bridge. Fixture acceptance is synthetic, never physical certification."""
import argparse,json,pathlib
from .core import read,execute,accept
from .demo import run_demo
p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
d=s.add_parser('demo');d.add_argument('--out',type=pathlib.Path,required=True)
r=s.add_parser('run');r.add_argument('--request',type=pathlib.Path,required=True);r.add_argument('--fixture',type=pathlib.Path,required=True);r.add_argument('--out',type=pathlib.Path,required=True)
a=s.add_parser('audit');a.add_argument('--request',type=pathlib.Path,required=True);a.add_argument('--fixture',type=pathlib.Path,required=True);a.add_argument('--execution',type=pathlib.Path,required=True)
x=p.parse_args()
if x.cmd=='demo':result=run_demo(x.out);print(json.dumps({'summary':str(x.out/'SUMMARY.json'),'same_kernel_equal_outputs':result['same_kernel_equal_outputs']}))
elif x.cmd=='run':_,result=execute(read(x.request),x.out,read(x.fixture));print(json.dumps(result))
else:result=accept(read(x.request),read(x.execution),read(x.fixture));print(json.dumps(result))
if x.cmd!='demo' and result['status']=='FAIL':raise SystemExit(1)
