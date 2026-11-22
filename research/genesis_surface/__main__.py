"""Generate and audit digital research geometry; no network or account access."""
import argparse
import json
from .build import build, audit

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['build','audit','mesh'])
    p.add_argument('--request',default='campaign/genesis-surface/REQUEST.json')
    p.add_argument('--out',required=True)
    p.add_argument('--design',help='Existing audited design directory for mesh export')
    p.add_argument('--step-mm',type=float,default=.1)
    a=p.parse_args()
    if a.command=='mesh':
        if not a.design:p.error('--design is required for mesh')
        from .mesh import export_mesh
        r=export_mesh(a.design,a.out,a.step_mm)
    else:r=build(a.request,a.out) if a.command=='build' else audit(a.out)
    print(json.dumps(r,sort_keys=True,allow_nan=False))

if __name__=='__main__':main()
