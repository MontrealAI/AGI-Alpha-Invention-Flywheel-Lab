#!/usr/bin/env python3
"""Create a small public research package; never copy private originals or fonts."""
import argparse,hashlib,shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def source_files():
    files=[p for p in ROOT.rglob('*') if p.is_file() and p.suffix in {'.tex','.py','.md','.json','.txt','.html'}
        and '__pycache__' not in p.parts and 'publication-output' not in p.parts]
    return sorted(files)

def package(output):
    out=Path(output).absolute()
    if out.exists():raise ValueError('Choose a fresh output directory')
    out.mkdir(parents=True)
    pdf=ROOT/'SURF_THE_EXPONENTIAL.pdf'
    if not pdf.read_bytes().startswith(b'%PDF-'):raise ValueError('Build the manuscript first')
    shutil.copyfile(pdf,out/pdf.name)
    with zipfile.ZipFile(out/'SURF_THE_EXPONENTIAL_SOURCE.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in source_files():z.write(p,p.relative_to(ROOT))
        z.write(ROOT/'VERSION','VERSION')
    records=[]
    for p in sorted(out.iterdir()):records.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name)
    (out/'SHA256SUMS').write_text('\n'.join(records)+'\n')
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();print(package(a.output))
