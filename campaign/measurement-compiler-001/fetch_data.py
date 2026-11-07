"""Retrieve the two registered public archives; verify before accepting bytes."""
import argparse
import hashlib
from pathlib import Path
from urllib.request import urlopen

SOURCES={
 'Codes_Python.zip':'330d76f3c7148d2840f7f207cd90d7a98eb1d972867b70188096043c9e3261a2',
 'EvaluationData_full.zip':'85c47f91c0cd15889a96108b389550edafd8bba46b40fd84447e63a62534ce42'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    for name,digest in SOURCES.items():
        dest=a.output/name
        if dest.exists():
            if hashlib.sha256(dest.read_bytes()).hexdigest()!=digest:
                raise ValueError(f'Existing archive does not match registered bytes: {name}')
            print(f'Verified existing {name}');continue
        url=f'https://zenodo.org/records/10986692/files/{name}?download=1'
        with urlopen(url,timeout=60) as response:data=response.read(10_000_001)
        if len(data)>10_000_000 or hashlib.sha256(data).hexdigest()!=digest:
            raise ValueError(f'Size or hash mismatch: {name}')
        dest.write_bytes(data);print(f'Verified {name}: {len(data)} bytes')

if __name__=='__main__':main()
