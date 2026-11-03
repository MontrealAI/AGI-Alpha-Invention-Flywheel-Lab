import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from verify_publication import ROOT, verify


def package(output):
    verify()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    pdf = ROOT / 'AGI_ALPHA_FLYWHEEL.pdf'
    if not pdf.exists():
        pdf = ROOT.parent / 'research/agi-alpha-flywheel-20261102.pdf'
    published = output / 'AGI_ALPHA_FLYWHEEL.pdf'
    if pdf.resolve() != published:
        shutil.copyfile(pdf, published)
    manifest = json.loads((ROOT / 'PUBLICATION.json').read_text())
    archive = output / 'AGI_ALPHA_FLYWHEEL_SOURCE.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(list(manifest['source_sha256']) + ['PUBLICATION.json']):
            entry = zipfile.ZipInfo(name, date_time=(2026, 11, 2, 0, 0, 0))
            entry.external_attr = 0o644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(entry, (ROOT / name).read_bytes(), compresslevel=9)
        entry = zipfile.ZipInfo(published.name, date_time=(2026, 11, 2, 0, 0, 0))
        entry.external_attr = 0o644 << 16
        entry.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(entry, published.read_bytes(), compresslevel=9)
    sums = ''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in (published, archive))
    (output / 'SHA256SUMS').write_text(sums)
    print(json.dumps({'pdf': str(published), 'source': str(archive), 'checksums': str(output / 'SHA256SUMS')}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    package(parser.parse_args().output)
