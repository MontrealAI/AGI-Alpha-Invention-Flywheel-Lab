import argparse, hashlib, json, zipfile
from pathlib import Path

def sha(data):return hashlib.sha256(data).hexdigest()

def package(root, output, paths):
    root=Path(root).resolve();output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise FileExistsError(output)
    entries={}
    for name in paths:
        p=root/name
        if not p.exists():raise FileNotFoundError(p)
        candidates=[p] if p.is_file() else sorted(p.rglob('*'))
        for path in candidates:
            if path.is_symlink():raise ValueError('SYMLINK_EVIDENCE')
            if not path.is_file() or path.name.endswith('.lock') or '__pycache__' in path.parts:continue
            rel=path.relative_to(root).as_posix()
            if rel in entries:continue
            raw=path.read_bytes();entries[rel]={'sha256':sha(raw),'bytes':len(raw)}
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name,meta in sorted(entries.items()):
            raw=(root/name).read_bytes()
            if sha(raw)!=meta['sha256']:raise ValueError('EVIDENCE_CHANGED_DURING_PACKAGE')
            info=zipfile.ZipInfo(name,date_time=(2026,10,30,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    manifest={'schema':'agi-alpha/next009-lossless-evidence-archive/v1','archive':output.name,'archive_sha256':sha(output.read_bytes()),'archive_bytes':output.stat().st_size,'entries':entries,'scope':'Exact original evidence bytes; archive timestamps normalized. No missing array is reconstructed or assigned a predecessor identity.'}
    index=output.with_suffix('.manifest.json');index.write_text(json.dumps(manifest,indent=2)+'\n')
    with zipfile.ZipFile(output) as z:
        for name,meta in entries.items():
            raw=z.read(name)
            if len(raw)!=meta['bytes'] or sha(raw)!=meta['sha256']:raise ValueError('ARCHIVE_ROUNDTRIP_MISMATCH')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--output',required=True);p.add_argument('paths',nargs='+');a=p.parse_args();r=package(a.root,a.output,a.paths)
    print(json.dumps({k:r[k] for k in ['archive','archive_sha256','archive_bytes']}|{'files':len(r['entries'])}))
