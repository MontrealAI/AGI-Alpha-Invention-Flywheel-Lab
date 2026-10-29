import argparse,hashlib,json,os,pathlib,shutil,subprocess,sys

def probe(root,output):
    root=pathlib.Path(root).resolve();output=pathlib.Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    manifest='campaign/cycle-001/CLOSURE.json'
    closure=json.loads((root/manifest).read_text())
    paths=set(closure)|{manifest,'reproduce.py','research/pglib_opf_case14_ieee.m','research/pglib_opf_case30_ieee.m'}
    for name in paths:
        target=output/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target)
    shutil.copyfile(root/'reproduce.py',output/'reproduce.original.txt')
    candidate=output/'grid_screen/__init__.py'
    candidate.write_text(candidate.read_text()+"\nfrom pathlib import Path as _P\n_P(__file__).with_name('IMPORT_SIDE_EFFECT.txt').write_text('harmless verifier marker\\n')\n")
    (output/'output').mkdir()
    result=subprocess.run([sys.executable,'-I',str(output/'reproduce.py'),'--worker','--output',str(output/'output')],capture_output=True,text=True,timeout=10,env={'PATH':os.defpath,'OPENBLAS_NUM_THREADS':'1','OMP_NUM_THREADS':'1'})
    record={'runner_sha256':hashlib.sha256((output/'reproduce.original.txt').read_bytes()).hexdigest(),'returncode':result.returncode,'identity_mismatch_reported':'SOURCE_IDENTITY_MISMATCH' in result.stderr,'import_side_effect_before_refusal':(output/'grid_screen/IMPORT_SIDE_EFFECT.txt').exists(),'stdout':result.stdout,'stderr':result.stderr,'scope':'Temporary trusted verifier copy; harmless marker; original source untouched'}
    record['passed']=record['returncode']!=0 and record['identity_mismatch_reported'] and not record['import_side_effect_before_refusal']
    (output/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--output',required=True);a=p.parse_args();r=probe(a.root,a.output);print(json.dumps({k:v for k,v in r.items() if k not in ('stdout','stderr')}));sys.exit(0 if r['passed'] else 1)
