"""Explicit bounded retrieval of the pinned public authors' forward model."""
import argparse
import hashlib
import io
from pathlib import Path
import urllib.request
from zipfile import ZipFile
from .probe import AUTHOR_CODE_SHA256

URL='https://zenodo.org/api/records/22142148/files/Code.zip/content'
ARCHIVE_SHA256='5bfb83a1e0c9f048e44bf1dfbfa35f75bd09ffd18b2286f6b471b597a8ee9671'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if not args.output.is_absolute() or args.output.exists() or any(p.is_symlink() for p in [args.output,*args.output.parents]):raise ValueError('NEW_REGULAR_ABSOLUTE_OUTPUT_REQUIRED')
    with urllib.request.urlopen(URL,timeout=30) as response:raw=response.read(100_001)
    if len(raw)>100_000 or hashlib.sha256(raw).hexdigest()!=ARCHIVE_SHA256:raise ValueError('PINNED_PUBLIC_ARCHIVE_CHANGED')
    with ZipFile(io.BytesIO(raw)) as archive:
        names=[n for n in archive.namelist() if Path(n).name=='ga_bilinear_hr_friction_law_core.py']
        if len(names)!=1 or archive.getinfo(names[0]).file_size>50_000:raise ValueError('EXACT_BOUNDED_AUTHOR_MODEL_REQUIRED')
        code=archive.read(names[0])
    if hashlib.sha256(code).hexdigest()!=AUTHOR_CODE_SHA256:raise ValueError('PINNED_AUTHOR_MODEL_CHANGED')
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(code)
    print(str(args.output))


if __name__=='__main__':main()
