"""Experimental v2 evidence resolution; explicit trusted in-memory bundle only.

Not a production storage/publication implementation. No paths from signed or
unsigned tickets are ever opened. Wire descriptors are owner-authenticated;
immutable canonical blobs are checked at every resolution, never cached mutable.
"""
import contextvars
import copy
import hashlib
import hmac
import json
from contextlib import contextmanager
from types import MappingProxyType

V1 = 'agi-alpha/native-source-transition/v1'
V2 = 'agi-alpha/native-source-transition/v2-cas'
DOMAIN = b'native-source-transition\n'
MAX_TICKET_BYTES = 16_000_000
MAX_BLOB_BYTES = 64_000_000
MAX_BUNDLE_BYTES = 512 * 1024 * 1024
MAX_BUNDLE_FILES = 10_000
_store = contextvars.ContextVar('explicit_transition_evidence', default=None)
FIELDS = {'schema','id','account_path','from_source','to_source','counter',
          'expected_state_digest','day','historical_root','verifier_files'}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def evidence_scope(blobs):
    """Caller explicitly supplies trusted storage bytes, not ticket-selected paths.

    Aggregate bounds are shared with, not additional to, a future archive's
    source and other evidence budget. This prototype counts these blobs only.
    """
    if not isinstance(blobs, dict) or len(blobs)>MAX_BUNDLE_FILES:
        raise ValueError('BOUNDED_TRANSITION_BUNDLE_REQUIRED')
    total=0; verified={}
    for name,raw in blobs.items():
        if not isinstance(name,str) or len(name)!=64 or any(c not in '0123456789abcdef' for c in name):
            raise ValueError('EXACT_TRANSITION_CONTENT_ADDRESS_REQUIRED')
        if type(raw) is not bytes or len(raw)>MAX_BLOB_BYTES:
            raise ValueError('BOUNDED_TRANSITION_BLOB_REQUIRED')
        total+=len(raw)
        if total>MAX_BUNDLE_BYTES or _sha(raw)!=name:
            raise ValueError('TRANSITION_BUNDLE_BOUND_OR_HASH_CHANGED')
        verified[name]=raw
    token=_store.set(MappingProxyType(verified))
    try: yield
    finally: _store.reset(token)


def externalize(body, blobs):
    """Owner-side construction only; caller signs NEW body after complete checks.

    Existing prior tickets remain byte-equivalent nested values. New prior
    records reference their existing v2 tickets instead of recursively embedding
    all resolved history. Blob insertion is content-deduplicating and atomic at
    this in-memory mapping boundary, not a durable storage claim.
    """
    evidence={'prior_record','prior_envelope'}
    if not isinstance(body,dict) or body.get('schema')!=V1 or set(body) not in [FIELDS|evidence,FIELDS|evidence|{'operating'}]:
        raise ValueError('EXACT_V1_TRANSITION_BODY_REQUIRED')
    pending={}; refs={}
    for field in sorted(evidence|({'operating'} if 'operating' in body else set())):
        raw=canonical(body[field]); sha=_sha(raw)
        if len(raw)>MAX_BLOB_BYTES: raise ValueError('BOUNDED_TRANSITION_BLOB_REQUIRED')
        pending[sha]=raw; refs[field]={'sha256':sha,'bytes':len(raw)}
    combined={**blobs,**pending}
    with evidence_scope(combined): pass
    result={k:copy.deepcopy(body[k]) for k in FIELDS};result['schema']=V2
    result['evidence']=refs
    if len(canonical({'body':result,'signature':'0'*64}))>MAX_TICKET_BYTES:
        raise ValueError('BOUNDED_SOURCE_TRANSITION_REQUIRED')
    blobs.update(pending)
    return result



def _parse_budget(raw):
    # Scan bytes before object construction. Strings cannot smuggle braces;
    # escaped quotes do not terminate strings. Canonical validation follows.
    depth=0; nodes=0; quoted=False; escaped=False; primitive=False
    for byte in raw:
        if quoted:
            if escaped:escaped=False
            elif byte==92:escaped=True
            elif byte==34:quoted=False
            continue
        if byte==34:
            quoted=True;nodes+=1;primitive=False
        elif byte in (91,123):
            depth+=1;nodes+=1;primitive=False
        elif byte in (93,125):depth-=1;primitive=False
        elif byte in (32,9,10,13,44,58):primitive=False
        elif not primitive:nodes+=1;primitive=True
        if depth>128 or nodes>2_000_000:
            raise ValueError('TRANSITION_JSON_DEPTH_OR_NODE_BUDGET')
    if quoted or depth!=0:raise ValueError('INVALID_TRANSITION_JSON')


def ticket_body(ticket, *, key=None):
    if not isinstance(ticket,dict) or set(ticket)!={'body','signature'}:
        raise ValueError('EXACT_SOURCE_TRANSITION_AUTHORIZATION_REQUIRED')
    if len(canonical(ticket))>MAX_TICKET_BYTES: raise ValueError('BOUNDED_SOURCE_TRANSITION_REQUIRED')
    body=ticket['body']
    if not isinstance(body,dict):raise ValueError('EXACT_SOURCE_TRANSITION_BODY_REQUIRED')
    if key is not None:
        expected=hmac.new(key,DOMAIN+canonical(body),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,str(ticket['signature'])):
            raise ValueError('SOURCE_TRANSITION_SIGNATURE_MISMATCH')
    if body.get('schema')==V1:return body
    if body.get('schema')!=V2 or set(body)!=FIELDS|{'evidence'}:
        raise ValueError('EXACT_V2_TRANSITION_BODY_REQUIRED')
    if type(body['counter']) is not int or not 1<=body['counter']<=4:
        raise ValueError('SOURCE_TRANSITION_COUNTER_AND_CLOCK_REQUIRED')
    refs=body['evidence'];required={'prior_record','prior_envelope'}
    if not isinstance(refs,dict) or set(refs) not in [required,required|{'operating'}]:
        raise ValueError('EXACT_TRANSITION_REFERENCES_REQUIRED')
    store=_store.get()
    if store is None:raise ValueError('EXPLICIT_TRANSITION_EVIDENCE_SCOPE_REQUIRED')
    resolved={k:copy.deepcopy(body[k]) for k in FIELDS};resolved['schema']=V1
    for field,ref in refs.items():
        if (not isinstance(ref,dict) or set(ref)!={'sha256','bytes'} or type(ref['bytes']) is not int
            or not 0<ref['bytes']<=MAX_BLOB_BYTES or not isinstance(ref['sha256'],str)
            or len(ref['sha256'])!=64 or any(c not in '0123456789abcdef' for c in ref['sha256'])):
            raise ValueError('EXACT_BOUNDED_TRANSITION_REFERENCE_REQUIRED')
        raw=store.get(ref['sha256'])
        if raw is None or len(raw)!=ref['bytes'] or _sha(raw)!=ref['sha256']:
            raise ValueError('TRANSITION_EVIDENCE_MISSING_OR_CHANGED')
        # Resource qualification of stdlib parsing remains explicitly outstanding.
        # No compression and no recursive reference following are performed.
        _parse_budget(raw)
        value=json.loads(raw)
        if not isinstance(value,dict) or canonical(value)!=raw:
            raise ValueError('CANONICAL_TRANSITION_EVIDENCE_REQUIRED')
        resolved[field]=value
    return resolved

# Explicit caller-selected store I/O. This is not automatic account path discovery.
import os
import fcntl
import stat
from pathlib import Path


def _open_directory(path):
    """Open each absolute component without following symlinks; pin directory fd."""
    path=Path(path).absolute()
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            if part in {'.','..'}:raise ValueError('EXACT_EVIDENCE_DIRECTORY_REQUIRED')
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=child
        return fd
    except BaseException:
        os.close(fd);raise


def _name(name):
    return isinstance(name,str) and len(name)==64 and all(c in '0123456789abcdef' for c in name)


class _DirectoryStore:
    def __init__(self, fd):
        self.fd=fd
        names=os.listdir(fd)
        if len(names)>MAX_BUNDLE_FILES:raise ValueError('BOUNDED_TRANSITION_BUNDLE_REQUIRED')
        total=0
        for name in names:
            if not _name(name):raise ValueError('EXACT_TRANSITION_CONTENT_ADDRESS_REQUIRED')
            info=os.stat(name,dir_fd=fd,follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_BLOB_BYTES:
                raise ValueError('BOUNDED_REGULAR_TRANSITION_BLOB_REQUIRED')
            total+=info.st_size
        if total>MAX_BUNDLE_BYTES:raise ValueError('BOUNDED_TRANSITION_BUNDLE_REQUIRED')
    def get(self, name):
        if not _name(name):raise ValueError('EXACT_TRANSITION_CONTENT_ADDRESS_REQUIRED')
        try: fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=self.fd)
        except FileNotFoundError:return None
        try:
            info=os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_BLOB_BYTES:
                raise ValueError('BOUNDED_REGULAR_TRANSITION_BLOB_REQUIRED')
            chunks=[];remaining=MAX_BLOB_BYTES+1
            while remaining:
                data=os.read(fd,min(1024*1024,remaining))
                if not data:break
                chunks.append(data);remaining-=len(data)
            raw=b''.join(chunks)
            if len(raw)>MAX_BLOB_BYTES or len(raw)!=info.st_size or _sha(raw)!=name:
                raise ValueError('TRANSITION_EVIDENCE_MISSING_OR_CHANGED')
            return raw
        finally:os.close(fd)


@contextmanager
def evidence_directory(path):
    """Trusted caller path only; never obtain this argument from a ticket field."""
    fd=_open_directory(path)
    try:
        fcntl.flock(fd,fcntl.LOCK_SH)
        store=_DirectoryStore(fd);token=_store.set(store)
        try:yield
        finally:_store.reset(token)
    finally:os.close(fd)


def persist_evidence(path,blobs):
    """Create-only verified content. Caller supplies an existing private directory.

    Partial writes fail closed by hash and are not referenced by any new ticket.
    No account/intent descriptor writes occur here. Caller must finish this step
    before signing or committing a ticket; crash consistency is not yet qualified.
    """
    with evidence_scope(blobs):pass
    fd=_open_directory(path)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        store=_DirectoryStore(fd)
        existing=set(os.listdir(fd)); total=sum(os.stat(n,dir_fd=fd,follow_symlinks=False).st_size for n in existing)
        new={n:r for n,r in blobs.items() if n not in existing}
        if len(existing|set(new))>MAX_BUNDLE_FILES or total+sum(map(len,new.values()))>MAX_BUNDLE_BYTES:
            raise ValueError('BOUNDED_TRANSITION_BUNDLE_REQUIRED')
        for name,raw in blobs.items():
            if name in existing:
                if store.get(name)!=raw:raise ValueError('TRANSITION_EVIDENCE_MISSING_OR_CHANGED')
                continue
            out=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
            try:
                with os.fdopen(out,'wb',closefd=False) as stream:stream.write(raw);stream.flush();os.fsync(out)
            finally:os.close(out)
        os.fsync(fd)
    finally:os.close(fd)
