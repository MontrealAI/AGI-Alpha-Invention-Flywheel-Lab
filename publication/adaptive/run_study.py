"""Run construction and matched transfer without opening confirmation."""

import argparse
from pathlib import Path
from types import SimpleNamespace

from pages import canonical, digest
from research import ARMS, main


def run(cohort, workspace, config, model, representation):
    workspace.mkdir(mode=0o700,parents=True,exist_ok=True)
    runs={}

    def execute(label,mode,event,arm,prior=None,attempts=1):
        result=main(SimpleNamespace(workspace=workspace/label,config=config,model=model,mode=mode,event=event,
                                   arm=arm,prior=prior,attempts=attempts,history=cohort/'fit.json',
                                   development=cohort/'development.json',provider='localhost-inference',
                                   budget=512*attempts,request_tokens=512,representation=representation))
        runs[label]=result
        (workspace/'runs.json').write_bytes(canonical(runs)+b'\n')
        print(label,result['status'],[(x['status'],x.get('score'),x.get('diagnosis'),x.get('reason'))
                                      for x in result['events']],flush=True)
        return result

    first=execute('push-first','construct','push','original',attempts=2)
    parent=workspace/'parent.json'
    parent.write_bytes(canonical({'first':first['result'],'run_sha256':digest(first)})+b'\n')
    learned=execute('method','learn','push','original',prior=parent)
    prior=None
    if learned['result']:
        prior=workspace/'reuse.json'
        prior.write_bytes(canonical(learned['result'])+b'\n')
    for label in ARMS if prior else ('original',):
        execute(label,'construct','pull_request',label,prior=prior if label!='original' else None)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('cohort','workspace','config'):
        parser.add_argument(field,type=Path)
    parser.add_argument('model')
    parser.add_argument('--representation',choices=('expression','stack','wat'),default='expression')
    args=parser.parse_args()
    run(args.cohort,args.workspace,args.config,args.model,args.representation)
