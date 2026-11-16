"""Acquire strongest disclosed C1d prior under pinned source provenance."""
from pathlib import Path
from urllib.request import urlopen
import hashlib

URL = ('https://raw.githubusercontent.com/ArthurAnache/Hackathon-AI-Reasearch/'
       'c0f8d1837e65d9194350edb7c029897cf031908d/'
       'records/1d/autonomous/c006_31bbf628_int56.json')
EXPECTED = 'dbca822baa7c8a20d05451b56de2dd77c032e88fa945d4e243d0a785787202d3'

def main():
    with urlopen(URL, timeout=120) as r:
        payload = r.read(3_000_000)
    if len(payload)>2_000_000:
        raise ValueError('source unexpectedly large')
    digest=hashlib.sha256(payload).hexdigest()
    if digest!=EXPECTED:
        raise ValueError(f'pinned upstream SHA-256 mismatch: got {digest}')
    out=Path('upstream-c1d-incumbent.json');out.write_bytes(payload)
    print('PINNED_SOURCE_OK',len(payload),digest)

if __name__=='__main__':main()
