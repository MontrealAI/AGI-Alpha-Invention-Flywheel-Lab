import argparse, hashlib, json, stat, zipfile
from pathlib import Path, PurePosixPath

def restore(manifest_path, destination):
    index=Path(manifest_path);meta=json.loads(index.read_bytes());archive=index.parent/meta['archive'];root=Path(destination).resolve()
    if meta.get('schema')!='agi-alpha/next009-lossless-evidence-archive/v1':raise ValueError('ARCHIVE_SCHEMA')
    raw=archive.read_bytes()
    if len(raw)!=meta['archive_bytes'] or hashlib.sha256(raw).hexdigest()!=meta['archive_sha256']:raise ValueError('ARCHIVE_BYTES')
    restored=[]
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist())!=len(set(z.namelist())) or set(z.namelist())!=set(meta['entries']):raise ValueError('ARCHIVE_MEMBERS')
        if sum(i.file_size for i in z.infolist())>256*1024*1024:raise ValueError('ARCHIVE_EXPANSION_LIMIT')
        for info in z.infolist():
            name=PurePosixPath(info.filename)
            if name.is_absolute() or '..' in name.parts or stat.S_ISLNK(info.external_attr>>16):raise ValueError('UNSAFE_ARCHIVE_PATH')
            expected=meta['entries'][info.filename];data=z.read(info)
            if len(data)!=expected['bytes'] or hashlib.sha256(data).hexdigest()!=expected['sha256']:raise ValueError('MEMBER_IDENTITY')
            path=root.joinpath(*name.parts)
            if any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('SYMLINK_DESTINATION')
            path.parent.mkdir(parents=True,exist_ok=True)
            if path.exists():
                if path.read_bytes()!=data:raise ValueError('UNIQUE_EVIDENCE_WOULD_BE_OVERWRITTEN')
            else:
                with path.open('xb') as f:f.write(data)
            restored.append(info.filename)
    return {'archive':archive.name,'members_verified':len(restored),'destination':str(root),'overwrite_policy':'Existing byte-identical files only; differing originals refused.'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifests',nargs='+');p.add_argument('--destination',required=True);a=p.parse_args()
    for m in a.manifests:print(json.dumps(restore(m,a.destination)))
