"""Actual runnable customer packages, deterministically hashed and locally delivered."""
import io
from pathlib import Path
import zipfile
from .core import canonical,digest,filehash,immutable,atomic,harness,safe
from .checker import verify


def package(c,artifact,target):
    verdict=verify(c,artifact)
    if not verdict['accepted']:raise ValueError('UNVERIFIED_DELIVERY_REFUSED')
    target=safe(target);target.mkdir(parents=True,exist_ok=True,mode=0o700)
    evaluator=Path(harness('instruments').__file__).read_bytes()
    files={'instrument.json':canonical(artifact['instrument']),
           'input-example.json':canonical(c['training'][0]['input']),
           'acceptance.json':canonical(verdict),'instruments.py':evaluator,
           'README.txt':('Verified bounded JSON instrument\n\nRun with Python 3.10+:\n  python3 instruments.py instrument.json input-example.json --max-operations '+str(c['max_operations'])+'\n\nAcceptance covers the supplied finite cases, not every possible input.\nThe supplied evaluator retains its Apache-2.0 SPDX license; see LICENSE-HARNESS.txt.\nNo payment, production-deployment or invention claim is made by this package.\n').encode()}
    license_path=Path(__file__).resolve().parents[2]/'products/alpha-genesis-harness/LICENSE'
    fallback=Path('/usr/share/common-licenses/Apache-2.0')
    if license_path.is_file():files['LICENSE-HARNESS.txt']=license_path.read_bytes()
    elif fallback.is_file():files['LICENSE-HARNESS.txt']=fallback.read_bytes()
    else:raise ValueError('EVALUATOR_LICENSE_TEXT_REQUIRED_FOR_DISTRIBUTION')
    import hashlib
    manifest={k:hashlib.sha256(v).hexdigest() for k,v in files.items()}
    files['MANIFEST.json']=canonical(manifest)
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            z.writestr(info,data)
    data=buf.getvalue();path=target/'solution.zip'
    if path.exists() and path.read_bytes()!=data:raise ValueError('DELIVERY_PACKAGE_CHANGED')
    if not path.exists():atomic(path,data)
    receipt={'artifact_sha256':digest(artifact),'package_sha256':hashlib.sha256(data).hexdigest(),
             'bytes':len(data),'files':manifest,'acceptance':verdict}
    immutable(target/'receipt.json',receipt)
    return receipt
