"""Explicit opt-in download of hash-bound public originals; never model inference."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
HOST = 'usgs-nims-images.s3.amazonaws.com'


def download(url, expected_sha256, destination):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc != HOST:
        raise ValueError('Only the declared public USGS image host is allowed')
    destination = destination.resolve()
    if not destination.is_relative_to(ROOT):
        raise ValueError('Destination must remain inside this instrument directory')
    if destination.exists():
        content = destination.read_bytes()
    else:
        with urlopen(url, timeout=30) as response:
            if urlparse(response.url).netloc != HOST:
                raise ValueError('Unexpected redirect host')
            content = response.read(10_000_001)
        if len(content) > 10_000_000:
            raise ValueError('Image exceeds 10 MB bound')
    if hashlib.sha256(content).hexdigest() != expected_sha256:
        raise ValueError(f'Source hash mismatch: {destination.name}')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=['water', 'canopy', 'all'], required=True)
    args = parser.parse_args()
    count = 0
    for cohort, folder in [('water', ROOT), ('canopy', ROOT / 'v3_canopy')]:
        if args.cohort not in [cohort, 'all']:
            continue
        for row in json.loads((folder / 'manifest.json').read_text()):
            if 'error' in row:
                continue
            if Path(row['filename']).name != row['filename']:
                raise ValueError('Expected a filename, not a path')
            download(row['url'], row['sha256'], folder / 'images' / row['filename'])
            count += 1
        if cohort == 'canopy':
            for row in json.loads((folder / 'probes/proposal.json').read_text())['probes']:
                download(row['url'], row['sha256'], folder / row['file'])
                count += 1
    print(f'Verified {count} public original images; no model inference.')


if __name__ == '__main__':
    main()
