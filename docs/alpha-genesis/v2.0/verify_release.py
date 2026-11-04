#!/usr/bin/env python3
"""Verify declared file bytes. This does not certify scientific or commercial claims."""
from pathlib import Path
import hashlib
import sys
ROOT=Path(__file__).resolve().parent

def main():
    count=0;failed=[]
    for line in (ROOT/'SHA256SUMS').read_text().splitlines():
        if not line.strip():continue
        expected,name=line.split('  ',1)
        p=ROOT/name
        if len(expected)!=64 or p.is_symlink() or not p.is_file() or ROOT not in p.resolve().parents:
            failed.append(name+': missing or unsafe');continue
        if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:failed.append(name+': changed')
        count+=1
    if failed:
        print('\n'.join(failed));return 1
    print(f'PASS: {count} declared files match SHA-256. Byte identity is not semantic certification.')
    return 0
if __name__=='__main__':raise SystemExit(main())
