"""Execute all frozen worlds in independent accounts and export only public bytes."""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, zipfile
from pathlib import Path
from commercial.ledger import digest
from enterprise078.service import source_paths
from .operator import ROOT, load_protocol, read, save

def source_closure(root=ROOT):
    return sorted(set(source_paths(root)) | {p.relative_to(root).as_posix() for p in (root/'enterprise078_scale').iterdir()
                   if p.is_file() and p.suffix in {'.py','.md','.json'}})

def copy_source(target):
    target=Path(target)
    if target.exists():raise ValueError('NEW_FROZEN_SOURCE_DESTINATION_REQUIRED')
    hashes={}
    for name in source_closure():
        original=ROOT/name
        if original.is_symlink():raise ValueError('SOURCE_SYMLINK_REFUSED')
        dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,dest)
        hashes[name]=hashlib.sha256(dest.read_bytes()).hexdigest()
    save(target/'SOURCE.json',{'schema':'enterprise078-scale/source/v1','files':hashes,'sha256':digest(hashes)})
    return hashes

def bundle(output):
    output=Path(output);source=output/'source';public=output/'public'
    names=set(read(source/'SOURCE.json')['files']) | {'SOURCE.json'}
    for case in public.iterdir():
        if not case.is_dir():continue
        manifest=read(case/'manifest.json')
        for job in manifest['jobs']:
            names.add(job['profile_path'])
            if (source/job['delivery_path']).exists():names.add(job['delivery_path'])
    dest=output/'enterprise078-scale-keyfree.zip'
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):archive.write(source/name,'source/'+name)
        for file in sorted(public.rglob('*')):
            if file.is_file() and file.suffix in {'.json','.md'}:archive.write(file,'public/'+file.relative_to(public).as_posix())
    save(output/'PUBLIC_PACKAGE.json',{'archive':dest.name,'bytes':dest.stat().st_size,
         'sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'private_state_included':False,
         'scope':'PUBLIC_REPRODUCTION_NOT_ACCOUNT_CONTINUATION_AUTHORITY'})
    return dest

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--resume',action='store_true');parser.add_argument('--world',action='append')
    args=parser.parse_args();out=args.output.absolute();source=out/'source';p=load_protocol();os.umask(0o077)
    if not args.resume:
        if out.exists():raise ValueError('EXISTING_RUN_REQUIRES_RESUME')
        out.mkdir(parents=True);copy_source(source)
    else:
        frozen=read(source/'SOURCE.json')
        for n,h in frozen['files'].items():
            if hashlib.sha256((source/n).read_bytes()).hexdigest()!=h:raise ValueError('FROZEN_RUN_SOURCE_CHANGED')
    worlds=args.world or [w['id'] for w in p['worlds']]
    if len(set(worlds))!=len(worlds) or not set(worlds)<={w['id'] for w in p['worlds']}:raise ValueError('REGISTERED_UNIQUE_WORLDS_REQUIRED')
    status=[]
    for world in worlds:
        case=out/'public'/world;private=out/'private'/world
        command=[sys.executable,'-m','enterprise078_scale.operator','--output',str(out),'--world',world]
        if private.exists():command.append('--resume')
        try:
            execution=subprocess.run(command,cwd=source,check=True,text=True,capture_output=True)
            (out/(world+'.stdout')).write_text(execution.stdout)
            review=subprocess.run([sys.executable,'-m','enterprise078_scale.review',str(case)],cwd=source,check=True,text=True,capture_output=True)
            save(case/'review.json',json.loads(review.stdout))
            r=read(case/'result.json');status.append({'case':world,'status':'NATIVE_AND_OPERATING_REPLAY_PASSED',
                'profit_microUSD':r['summary']['profit'],'collected_outputs':r['collected_outputs'],'opening_microUSD':r['opening_microUSD']})
        except subprocess.CalledProcessError as exc:
            (out/(world+'.failure.txt')).write_text((exc.stdout or '')+'\n'+(exc.stderr or ''))
            status.append({'case':world,'status':'FAILED_RETAINED_NOT_OMITTED','error':str(exc),'stderr_tail':(exc.stderr or '')[-2000:]})
        save(out/'public'/'CAMPAIGN.json',{'protocol_sha256':digest(p),'registered_worlds':[w['id'] for w in p['worlds']],
             'requested_worlds':worlds,'results':status,'pooled_profit':None,'full_matrix_completed':len(status)==len(p['worlds']) and all(s['status']=='NATIVE_AND_OPERATING_REPLAY_PASSED' for s in status),
             'commercial_milestone_qualified':False,'original_account_continuation':False})
        print(json.dumps(status[-1]),flush=True)
    if all((out/'public'/w/'result.json').exists() for w in worlds):bundle(out)
    if any(s['status']!='NATIVE_AND_OPERATING_REPLAY_PASSED' for s in status):raise SystemExit(1)
if __name__=='__main__':main()
