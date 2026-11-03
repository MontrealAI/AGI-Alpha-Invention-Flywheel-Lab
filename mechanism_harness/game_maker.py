"""Strict source-bound entry point for the preserved finite economic kernel."""
import argparse
import hashlib
import json
from pathlib import Path
from ._game_maker_v1 import *
from . import _game_maker_v1 as kernel
from .game_input import read_input,decode,source_hashes


def binding(raw,spec):
    return {'schema':'omega/raw-and-executable-provenance/v1',
            'raw_input_sha256':hashlib.sha256(raw).hexdigest(),
            'parsed_spec_sha256':digest(spec),'source_files':source_hashes()}


def rederive(spec,report,raw_bytes=None):
    payload={k:v for k,v in report.items() if k not in ('replay','input_binding')}
    kernel.rederive(spec,payload)
    if 'input_binding' in report:
        if raw_bytes is None:raise ValueError('RAW_INPUT_BYTES_REQUIRED_FOR_FILE_AUDIT')
        if decode(raw_bytes)!=spec or report['input_binding']!=binding(raw_bytes,spec):
            raise ValueError('RAW_INPUT_OR_EXECUTABLE_SOURCE_CHANGED')
    receipt={'accepted':True,'spec_sha256':digest(spec),'report_sha256':digest(payload),
             'scope':'DETERMINISTIC_REDERIVATION_NOT_INDEPENDENT_ECONOMIC_VERIFICATION'}
    if 'input_binding' in report:receipt['input_binding_sha256']=digest(report['input_binding'])
    if 'replay' in report and report['replay']!=receipt:raise ValueError('SOURCE_BOUND_REPLAY_RECEIPT_CHANGED')
    return receipt


def audit_file(path,report):
    if 'input_binding' not in report:raise ValueError('RAW_FILE_BINDING_REQUIRED')
    raw,spec=read_input(path)
    return rederive(spec,report,raw)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('spec',type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args(argv)
    raw,spec=read_input(a.spec);result=invent(spec)
    result['input_binding']=binding(raw,spec)
    result['replay']=rederive(spec,result,raw)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.output.is_symlink() or any(x.is_symlink() for x in a.output.parents):
        raise ValueError('REGULAR_OUTPUT_REQUIRED')
    with a.output.open('xb') as stream:stream.write(canonical(result)+b'\n')
    print(json.dumps({'status':result['status'],'winner':result['winner'],'report':str(a.output)},indent=2))

if __name__=='__main__':main()
