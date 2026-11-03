"""Strict economic inputs and raw/executable provenance. Standard library only."""
import hashlib
import json
import math
from pathlib import Path

MAX_BYTES=1_000_000


def decode(raw):
    if type(raw) is not bytes or len(raw)>MAX_BYTES:
        raise ValueError('BOUNDED_RAW_INPUT_BYTES_REQUIRED')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('DUPLICATE_JSON_MEMBER:'+key)
            result[key]=value
        return result
    def constant(value):raise ValueError('NONFINITE_JSON_NUMBER:'+value)
    try:
        value=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=constant)
    except (UnicodeError,RecursionError) as e:
        raise ValueError('INVALID_JSON_ENCODING_OR_DEPTH') from e
    stack=[(value,0)];visited=0
    while stack:
        node,depth=stack.pop();visited+=1
        if type(node) is float and not math.isfinite(node):raise ValueError('NONFINITE_JSON_NUMBER')
        if depth>32 or visited>100_000:raise ValueError('BOUNDED_JSON_STRUCTURE_REQUIRED')
        if type(node) is dict:stack.extend((v,depth+1) for v in node.values())
        elif type(node) is list:stack.extend((v,depth+1) for v in node)
    return value


def read_input(path):
    path=Path(path)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents) or not path.is_file():
        raise ValueError('REGULAR_INPUT_FILE_REQUIRED')
    with path.open('rb') as f:raw=f.read(MAX_BYTES+1)
    return raw,decode(raw)


def source_hashes():
    root=Path(__file__).resolve().parents[1]
    names=('mechanism_harness/game_maker.py','mechanism_harness/_game_maker_v1.py',
           'mechanism_harness/game_input.py','mechanism_harness/core.py')
    return {n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in names}
