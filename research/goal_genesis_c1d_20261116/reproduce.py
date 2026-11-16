#!/usr/bin/env python3
"""Exact standard-library-only reproduction and frozen-verdict comparison."""
import argparse
import hashlib
import json
from pathlib import Path
from verify_exact import verify as kronecker
from verify_ntt import verify as ntt

HERE=Path(__file__).resolve().parent

def reproduce(output_dir:Path):
    if output_dir.exists():raise ValueError('refusing to overwrite an output directory')
    raw=(HERE/'certificate4800.json').read_bytes()
    cert=json.loads(raw)
    a=kronecker(cert)
    b=ntt(cert)
    a['certificate_sha256']=hashlib.sha256(raw).hexdigest()
    expected_a=json.loads((HERE/'verdict4800.json').read_text())
    expected_b=json.loads((HERE/'independent_ntt_verdict.json').read_text())
    if a != expected_a:raise AssertionError('reproduction differs from frozen Kronecker verdict')
    if b != expected_b:raise AssertionError('reproduction differs from frozen NTT verdict')
    if f"{a['new_bound_num']}/{a['new_bound_den']}"!=b['fraction']:
        raise AssertionError('independent methods disagree')
    output_dir.mkdir(parents=True)
    (output_dir/'kronecker.json').write_text(json.dumps(a,indent=2)+'\n')
    (output_dir/'ntt_crt.json').write_text(json.dumps(b,indent=2)+'\n')
    print(json.dumps({'result':'PASS_EXACT_REPLAY','bound':a['new_bound_decimal'],
                      'independent_proofs':2,'knots':a['all_knot_coefficients'],
                      'sha256':a['certificate_sha256']},indent=2))

def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();reproduce(a.output_dir)
if __name__=='__main__':main()
