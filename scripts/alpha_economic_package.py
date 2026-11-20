#!/usr/bin/env python3
"""Create a source-identified engine kit. Never include runtime accounts or secrets."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from connected_enterprise.finance import source_paths_for_manifest
from connected_enterprise.alpha_economic.service import SCHEMA


def paths():
    names=set(source_paths_for_manifest({'schema':SCHEMA}))
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('test_alpha_economic*.py'))
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'scripts').glob('alpha_economic*.py'))
    names.update(p.relative_to(ROOT).as_posix() for p in (ROOT/'docs/alpha-economic-engine').glob('*') if p.is_file())
    # Include local imports of the approved source closure; no runtime directory scan.
    todo=list(names);seen=set()
    while todo:
        name=todo.pop()
        if name in seen:continue
        seen.add(name);p=ROOT/name
        if p.suffix!='.py' or not p.is_file():continue
        parts=list(Path(name).with_suffix('').parts)
        for i in range(1,len(parts)):
            init='/'.join(parts[:i])+'/__init__.py'
            if (ROOT/init).is_file() and init not in names:names.add(init);todo.append(init)
        try:tree=ast.parse(p.read_text())
        except SyntaxError:continue
        for node in ast.walk(tree):
            modules=[]
            if isinstance(node,ast.Import):modules=[n.name for n in node.names]
            elif isinstance(node,ast.ImportFrom):
                prefix=parts[:-node.level] if node.level else []
                module=prefix+(node.module.split('.') if node.module else [])
                modules=['.'.join(module)]+['.'.join(module+[n.name]) for n in node.names]
            for module in modules:
                for candidate in (module.replace('.','/')+'.py',module.replace('.','/')+'/__init__.py'):
                    if (ROOT/candidate).is_file() and candidate not in names:names.add(candidate);todo.append(candidate)
    return sorted(n for n in names if (ROOT/n).is_file())


def build(output):
    output=Path(output)
    if output.exists():raise ValueError('NEW_PACKAGE_PATH_REQUIRED')
    files={n:(ROOT/n).read_bytes() for n in paths()}
    lic=ROOT/'products/alpha-genesis-harness/LICENSE'
    if lic.is_file():files['products/alpha-genesis-harness/LICENSE']=lic.read_bytes()
    elif Path('/usr/share/common-licenses/Apache-2.0').exists():files['products/alpha-genesis-harness/LICENSE']=Path('/usr/share/common-licenses/Apache-2.0').read_bytes()
    try:revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    except subprocess.CalledProcessError:revision=None
    manifest={'schema':'alpha-economic/source-kit/v1','git_revision':revision,
              'scope':'BOUNDED_ENGINE_SOURCE_AND_TESTS_NOT_LIVE_DEPLOYMENT_OR_FULL_REPOSITORY',
              'files':{n:hashlib.sha256(b).hexdigest() for n,b in files.items()}}
    files['ENGINE-SOURCE-MANIFEST.json']=json.dumps(manifest,sort_keys=True,indent=2).encode()
    files['START-HERE.txt']=b'ALPHA Economic Engine 0.2.0\n\nRead docs/alpha-economic-engine/README.md first.\nRun: python3 -m connected_enterprise.alpha_economic demo --output ./my-demo\n\nThe native monetary demonstration is SIMULATED. External treasury integration is unfinished.\nNo real customer, profit, deployment or general autonomous invention is certified.\n'
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,11,16,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,data)
    return {'archive':str(output),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'bytes':output.stat().st_size,'files':len(files),'git_revision':revision}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path);a=p.parse_args();print(json.dumps(build(a.output),indent=2))
