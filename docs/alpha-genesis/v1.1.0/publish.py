#!/usr/bin/env python3
"""Prepare versioned source and a static publication site. Never uploads or deploys."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import shutil
import sys
import zipfile
from release_tools import source_files,check_html_links
from verify import run_checks

ROOT=Path(__file__).resolve().parent
EDITION='1.1.0'
NAME='ALPHA_GENESIS_FLYWHEEL_OMEGA'
SITE_FILES=[f'{NAME}.pdf',f'{NAME}.tex','README.md','DEPLOYMENT.md','REVIEW_NOTES.md',
            'RELEASE_STATUS.json','CITATION.cff','assets/site.css','assets/explorer.js',
            'assets/successor_reference.png','study/TEST_RESULTS.txt','study/results/results.json',
            'source/CLAIM_REGISTER.md','source/FRONTIER_RECHECK.json','source/WEB_SOURCES.json']


def archive(output: Path,root: Path,paths: list[str]) -> None:
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for relative in sorted(paths):
            info=zipfile.ZipInfo(relative,date_time=(2026,11,4,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,(root/relative).read_bytes(),compresslevel=9)


def write_manifest(root: Path) -> None:
    lines=[hashlib.sha256(p.read_bytes()).hexdigest()+'  '+rel for rel,p in sorted(source_files(root).items())]
    (root/'SHA256SUMS').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def prepare(output: Path,full:bool=False) -> dict:
    output=output.resolve()
    if output.exists() or output.is_relative_to(ROOT):
        raise ValueError('Choose a NEW directory outside the source package.')
    run_checks(full)
    output.mkdir(parents=True,exist_ok=False)
    source_name=f'{NAME}_v{EDITION}_SOURCE.zip'
    archive(output/source_name,ROOT,list(source_files(ROOT))+['SHA256SUMS'])
    site=output/'site';site.mkdir()
    for relative in SITE_FILES:
        dest=site/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/relative,dest)
    html=(ROOT/'START_HERE.html').read_text(encoding='utf-8')
    html=html.replace('<a class="button" href="#reproduce">Reproduce the studies</a>',
        f'<a class="button" href="{source_name}" download>Download the research package</a>')
    (site/'index.html').write_text(html,encoding='utf-8')
    (site/'.nojekyll').write_text('',encoding='utf-8')
    shutil.copy2(output/source_name,site/source_name)
    write_manifest(site)
    links=check_html_links(site)
    archive(output/f'{NAME}_v{EDITION}_WEBSITE.zip',site,list(source_files(site))+['SHA256SUMS'])
    shutil.copy2(ROOT/f'{NAME}.pdf',output/f'{NAME}_v{EDITION}.pdf')
    shutil.copy2(ROOT/f'{NAME}.tex',output/f'{NAME}_v{EDITION}.tex')
    deliverables=[p for p in output.iterdir() if p.is_file()]
    (output/'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(deliverables)),encoding='utf-8')
    return {'output':str(output),'site':str(site),'local_links':links,'uploaded':False}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--full',action='store_true',help='Rebuild the paper as part of preflight.')
    args=parser.parse_args()
    try:
        import json
        print(json.dumps(prepare(args.output,args.full),indent=2));return 0
    except (OSError,ValueError,RuntimeError) as exc:
        print(f'Publication preparation failed: {exc}',file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
