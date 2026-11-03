import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
from verify import PUBLIC
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise SystemExit('Use a new output directory')
    subprocess.run(['python3',str(ROOT/'verify.py')],check=True)
    manifest=json.loads((ROOT/'PUBLICATION.json').read_text());a.output.mkdir(parents=True)
    pdf=a.output/'AGI_ALPHA_FLYWHEEL_2026_11_02_REPORT.pdf';shutil.copyfile(PUBLIC,pdf)
    archive=a.output/'AGI_ALPHA_FLYWHEEL_2026_11_02_REPORT_SOURCE.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in sorted([*manifest['source_files'],'PUBLICATION.json']):
            info=zipfile.ZipInfo(name,date_time=(2026,11,3,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,(ROOT/name).read_bytes())
        info=zipfile.ZipInfo(pdf.name,date_time=(2026,11,3,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o644<<16;z.writestr(info,pdf.read_bytes())
    sums=a.output/'SHA256SUMS';sums.write_text(''.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+x.name+'\n' for x in [pdf,archive]))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(json.dumps({'status':'PASS','output':str(a.output),'source_files':len(manifest['source_files'])+1}))
if __name__=='__main__':main()
