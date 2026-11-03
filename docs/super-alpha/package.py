import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
from verify import ROOT,PUBLIC,check

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise SystemExit('Choose a new output directory')
    check();manifest=json.loads((ROOT/'PUBLICATION.json').read_text());a.output.mkdir(parents=True)
    pdf=a.output/'SUPER_ALPHA.pdf';shutil.copyfile(PUBLIC,pdf)
    archive=a.output/'SUPER_ALPHA_SOURCE.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        entries={name:(ROOT/name).read_bytes() for name in [*manifest['source_files'],'PUBLICATION.json']}
        entries['SUPER_ALPHA.pdf']=pdf.read_bytes()
        for name,data in sorted(entries.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,11,3,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,data)
    (a.output/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in [pdf,archive]))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise ValueError('Archive integrity failure')
    print(json.dumps({'status':'PASS','output':str(a.output),'source_files':len(manifest['source_files'])+1}))
if __name__=='__main__':main()
