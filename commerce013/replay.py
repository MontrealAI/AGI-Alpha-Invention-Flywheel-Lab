"""Restore exact deterministic synthetic service evidence and replay a frozen holdout."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from commerce013.experiment import (SCHEMA,CONFIRMATION_SEEDS,FAMILIES,base_config,
                                    canonical,sha,world_row)
from enterprise.services import prepare_services

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'campaign/commerce-013'
FIXTURE='commerce013-fixture-6inwxctn/qualified'


def restore_source(root=ROOT):
    root=Path(root)
    frozen=json.loads((root/'campaign/commerce-013/FROZEN.json').read_text())
    recorded=json.loads((root/'campaign/commerce-013/SERVICE_MANIFEST.json').read_text())
    if frozen['manifest_sha256']!=sha(recorded):
        raise ValueError('FROZEN_SYNTHETIC_MANIFEST_CHANGED')
    identity=json.loads((root/'campaign/commerce-013/SOURCE_IDENTITIES.json').read_text())
    for rel,record in identity.items():
        if not isinstance(record,dict) or 'sha256' not in record:
            continue
        expected=record['sha256'];path=root/rel
        if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('EXACT_SOURCE_MISMATCH:'+rel)
    created=prepare_services(root,FIXTURE)
    for key in recorded:
        if key=='resource_receipt':
            continue
        if created.get(key)!=recorded[key]:
            raise ValueError('SYNTHETIC_SERVICE_EVIDENCE_DRIFT:'+key)
    return recorded


def replay_seed(root,manifest,seed):
    if type(seed) is not int or seed not in CONFIRMATION_SEEDS:
        raise ValueError('FROZEN_CONFIRMATION_SEED_REQUIRED')
    recorded=json.loads((Path(root)/'campaign/commerce-013/CONFIRMATION.json').read_text())
    selected=json.loads((Path(root)/'campaign/commerce-013/DECISION.json').read_text())['selected']
    expected={(row['family'],row['arm']):row for row in recorded if row['seed']==seed}
    if len(expected)!=len(FAMILIES)*2:
        raise ValueError('INCOMPLETE_FROZEN_CONFIRMATION')
    verified=[]
    for fam in FAMILIES:
        for arm in ('retain_existing_channel',selected):
            row=world_row(root,manifest,base_config(),seed,fam,arm)
            if row!=expected[(fam,arm)]:
                raise ValueError('HELDOUT_NATIVE_REPLAY_DIFFERS:'+fam+':'+arm)
            verified.append(row)
    return {'schema':'agi-alpha/commerce013-source-reproduction/v1',
            'seed':seed,'native_worlds_verified':len(verified),
            'recorded_world_sha256':sha(verified),
            'recorded_raw_manifest_sha256':sha(manifest),
            'scope':'EXACT_SYNTHETIC_NATIVE_REPLAY_NOT_REAL_COMMERCE',
            'actual_revenue_usd':0,'pass':True}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--seed',required=True,type=int)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError('PRESERVE_EXISTING_RECEIPTS')
    m=restore_source(ROOT)
    r=replay_seed(ROOT,m,a.seed)
    a.output.write_bytes(canonical(r)+b'\n')
    print('EXACT_SOURCE_NATIVE_REPLAY_VERIFIED',r['native_worlds_verified'])

if __name__=='__main__':main()
