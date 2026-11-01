"""Create and recheck a single conditional cross-business deal certificate."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from commercial import possibility_exchange as exchange, possibility_audit

EXPECTED={'GAME.json','PROPOSAL.json','AUDIT.json','MANIFEST.json'}


def safe(path):
    path=Path(path).absolute()
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError('SYMLINK_PATH_REFUSED')
    return path


def read(path):
    raw=safe(path).read_bytes()
    if len(raw)>3_000_000:raise ValueError('BOUNDED_INPUT_SIZE_REQUIRED')
    def pairs(items):
        obj={}
        for k,v in items:
            if k in obj:raise ValueError('DUPLICATE_JSON_FIELD')
            obj[k]=v
        return obj
    return json.loads(raw,object_pairs_hook=pairs,
                      parse_constant=lambda _:(_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def build(input_path, output):
    spec=read(input_path);exchange.validate(spec)
    root=safe(output)
    if root.exists():raise FileExistsError('CREATE_ONLY_PROOF_DIRECTORY_REQUIRED')
    proposal=exchange.build(spec)
    audited=possibility_audit.verify(spec,proposal)
    root.mkdir(parents=True)
    for name,obj in [('GAME.json',spec),('PROPOSAL.json',proposal),('AUDIT.json',audited)]:
        (root/name).write_bytes(exchange.canonical(obj))
    hashes={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('GAME.json','PROPOSAL.json','AUDIT.json')}
    (root/'MANIFEST.json').write_bytes(exchange.canonical({'schema':exchange.SCHEMA,
                    'file_sha256':hashes,'scope':'SYNTHETIC_CONDITIONAL_PROPOSAL_NO_FINANCIAL_AUTHORITY'}))
    return verify(root)


def verify(output, *, expected_manifest_sha256=None):
    root=safe(output)
    if not root.is_dir() or {p.name for p in root.iterdir()}!=EXPECTED:
        raise ValueError('EXACT_PACKAGE_FILES_REQUIRED')
    for name in EXPECTED:
        if not safe(root/name).is_file():raise ValueError('REGULAR_PINNED_FILE_REQUIRED')
    spec,proposal,receipt,manifest=(read(root/name) for name in ('GAME.json','PROPOSAL.json','AUDIT.json','MANIFEST.json'))
    if expected_manifest_sha256 is not None:
        actual=hashlib.sha256((root/'MANIFEST.json').read_bytes()).hexdigest()
        if type(expected_manifest_sha256) is not str or expected_manifest_sha256!=actual:
            raise ValueError('EXTERNAL_PROPOSAL_MANIFEST_PIN_CHANGED')
    if not isinstance(manifest,dict) or set(manifest)!= {'schema','file_sha256','scope'} or manifest['schema']!=exchange.SCHEMA or manifest['scope']!='SYNTHETIC_CONDITIONAL_PROPOSAL_NO_FINANCIAL_AUTHORITY':
        raise ValueError('EXACT_MANIFEST_REQUIRED')
    if manifest['file_sha256']!={name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                                 for name in ('GAME.json','PROPOSAL.json','AUDIT.json')}:
        raise ValueError('PROOF_FILE_HASH_CHANGED')
    fresh=possibility_audit.verify(spec,proposal)
    if receipt!=fresh:raise ValueError('AUDIT_RECEIPT_NOT_RECONSTRUCTED')
    return {'verified':True,'proposal_status':proposal['status'],
            'participant_count':len(proposal['chosen']['buyer_ids']) if proposal['chosen'] else 0,
            'actual_revenue_cents':0,'actual_profit_cents':None,
            'conditional_provider_gain_cents':proposal['chosen']['conditional_provider_gain_cents'] if proposal['chosen'] else None,
            'manifest_sha256':hashlib.sha256((root/'MANIFEST.json').read_bytes()).hexdigest(),
            'scope':manifest['scope']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    create=sub.add_parser('build');create.add_argument('--input',required=True);create.add_argument('--output',required=True)
    check=sub.add_parser('verify');check.add_argument('--output',required=True);check.add_argument('--expected-manifest-sha256')
    args=p.parse_args()
    result=build(args.input,args.output) if args.command=='build' else verify(args.output,expected_manifest_sha256=args.expected_manifest_sha256)
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
