"""Strict contracts, bounded content and shared source identities. No money ledger."""
from __future__ import annotations
import hashlib
import hmac
import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import uuid

SCHEMA = 'alpha-economic/contract/v1'
HEX = re.compile(r'[a-f0-9]{64}\Z')
ID = re.compile(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,95}\Z')
COST_FIELDS = ('acquisition', 'research', 'construction_per_attempt', 'verification',
               'delivery', 'support', 'maintenance', 'tax_provision')
CONTRACT_FIELDS = {'schema','buyer','purpose','domain','inputs','training','confirmation',
                   'ordinary','price_microUSD','buyer_budget_microUSD','outside_option_microUSD',
                   'costs_microUSD','reinvestment_microUSD','reuse_benefit_microUSD',
                   'max_attempts','max_operations','scope_key','conditions','rights',
                   'residual_microUSD','claim_window_hours','expires_at','nonce'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def filehash(path):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def parse(raw):
    def pairs(items):
        out={}
        for k,v in items:
            if k in out: raise ValueError('DUPLICATE_JSON_KEY')
            out[k]=v
        return out
    def bad(_): raise ValueError('NONFINITE_JSON')
    if len(raw)>2_000_000: raise ValueError('BOUNDED_JSON_REQUIRED')
    result=json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    canonical(result)
    return result


def safe(path):
    p=Path(os.path.abspath(path))
    if any(x.is_symlink() for x in (p,*p.parents)): raise ValueError('SYMLINK_REFUSED')
    if p.exists() and p.is_file() and p.stat().st_nlink != 1: raise ValueError('HARDLINK_REFUSED')
    return p


def child(root,relative):
    if not isinstance(relative,str) or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('RELATIVE_PATH_REQUIRED')
    return safe(Path(root)/relative)


def read(path): return parse(safe(path).read_bytes())


def atomic(path,data):
    p=safe(path); p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    temp=p.with_name('.'+uuid.uuid4().hex+'.tmp')
    try:
        fd=os.open(temp,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(temp,p)
        fd=os.open(p.parent,os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally: temp.unlink(missing_ok=True)


def save(path,value): atomic(path,canonical(value))


def immutable(path,value):
    p=safe(path); data=canonical(value)
    if p.exists():
        if p.read_bytes()!=data: raise ValueError('IMMUTABLE_RECORD_CHANGED')
        return
    atomic(p,data)


def money(value,positive=False):
    if type(value) is not int or value < int(positive): raise ValueError('EXACT_NONNEGATIVE_INTEGER_MONEY_REQUIRED')
    return value


def harness(name):
    package='alpha_engine_harness'
    base=Path(__file__).resolve().parents[2]/'products/alpha-genesis-harness/bridge'
    if package not in sys.modules:
        spec=importlib.util.spec_from_file_location(package,base/'__init__.py',submodule_search_locations=[str(base)])
        module=importlib.util.module_from_spec(spec); sys.modules[package]=module; spec.loader.exec_module(module)
    return importlib.import_module(package+'.'+name)


def contract(value):
    if not isinstance(value,dict) or set(value)!=CONTRACT_FIELDS or value['schema']!=SCHEMA:
        raise ValueError('EXACT_ECONOMIC_CONTRACT_REQUIRED')
    if value['domain']!='bounded-json-instrument': raise ValueError('UNREGISTERED_EXECUTION_DOMAIN')
    for k in ('buyer','scope_key','nonce'):
        if not isinstance(value[k],str) or not ID.fullmatch(value[k]): raise ValueError('BOUNDED_IDENTIFIER_REQUIRED')
    for k in ('purpose','conditions','rights'):
        if not isinstance(value[k],str) or not 0<len(value[k])<=8000: raise ValueError('EXPLICIT_PURPOSE_CONDITIONS_RIGHTS_REQUIRED')
    for k in ('price_microUSD','buyer_budget_microUSD','outside_option_microUSD','reinvestment_microUSD','reuse_benefit_microUSD','residual_microUSD','expires_at'):
        money(value[k])
    if value['price_microUSD']<200_000: raise ValueError('NATIVE_PRICE_FLOOR_200000_MICROUSD')
    if type(value['max_attempts']) is not int or not 1<=value['max_attempts']<=20:
        raise ValueError('DECLARED_ATTEMPT_LIMIT_REQUIRED')
    if type(value['max_operations']) is not int or not 1<=value['max_operations']<=1_000_000:
        raise ValueError('DECLARED_OPERATION_LIMIT_REQUIRED')
    if type(value['claim_window_hours']) is not int or not 2<=value['claim_window_hours']<=87600:
        raise ValueError('DECLARED_CLAIM_WINDOW_REQUIRED')
    if value['residual_microUSD']>value['price_microUSD']+200_000: raise ValueError('RESIDUAL_EXCEEDS_EXPOSURE')
    costs=value['costs_microUSD']
    if not isinstance(costs,dict) or set(costs)!=set(COST_FIELDS): raise ValueError('COMPLETE_DECLARED_COST_CATEGORIES_REQUIRED')
    for v in costs.values(): money(v)
    inputs=value['inputs']
    if not isinstance(inputs,list) or not inputs or len(inputs)>64 or any(not isinstance(k,str) for k in inputs) or len(set(inputs))!=len(inputs):
        raise ValueError('DECLARED_UNIQUE_INPUT_FIELDS_REQUIRED')
    if any(not isinstance(k,str) or not ID.fullmatch(k) for k in inputs): raise ValueError('INPUT_IDENTIFIER_REQUIRED')
    for group in ('training','confirmation'):
        cases=value[group]
        if not isinstance(cases,list) or not 1<=len(cases)<=256: raise ValueError('BOUNDED_NONEMPTY_ACCEPTANCE_CASES_REQUIRED')
        for case in cases:
            if not isinstance(case,dict) or set(case)!={'input','expected'} or not isinstance(case['input'],dict) or set(case['input'])!=set(inputs) or not isinstance(case['expected'],dict):
                raise ValueError('EXACT_ACCEPTANCE_CASE_REQUIRED')
            harness('instruments').finite(case)
    if {digest(c['input']) for c in value['training']} & {digest(c['input']) for c in value['confirmation']}:
        raise ValueError('TRAINING_CONFIRMATION_INPUTS_MUST_BE_DISJOINT')
    if not isinstance(value['ordinary'],dict): raise ValueError('COMPETENT_ORDINARY_ALTERNATIVE_REQUIRED')
    canonical(value)
    return value


def identifier(c): return 'a-'+digest(contract(c))


def worst_cost(c):
    return sum(c['costs_microUSD'].values())+(c['max_attempts']-1)*c['costs_microUSD']['construction_per_attempt']


def signature(envelope,key):
    if not isinstance(key,bytes) or len(key)<32: raise ValueError('AUTHENTICATION_KEY_AT_LEAST_32_BYTES')
    return hmac.new(key,b'alpha-economic-v1\n'+canonical(envelope),hashlib.sha256).hexdigest()


def sign(body,key): return {'body':body,'signature':signature(body,key)}


def authenticate(envelope,key,*,kind,now):
    if not isinstance(envelope,dict) or set(envelope)!={'body','signature'}:
        raise ValueError('EXACT_SIGNED_ENVELOPE_REQUIRED')
    body=envelope['body']
    if not isinstance(body,dict) or body.get('kind')!=kind or type(body.get('expires_at')) is not int or body['expires_at']<now:
        raise ValueError('MESSAGE_TYPE_OR_EXPIRY_INVALID')
    if not isinstance(envelope['signature'],str) or not hmac.compare_digest(signature(body,key),envelope['signature']):
        raise ValueError('AUTHENTICATION_FAILED')
    return body
