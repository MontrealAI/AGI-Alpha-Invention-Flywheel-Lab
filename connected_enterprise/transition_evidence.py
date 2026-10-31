"""Experimental v2 evidence resolution; explicit trusted in-memory bundle only.

Not a production storage/publication implementation. No paths from signed or
unsigned tickets are ever opened. Wire descriptors are owner-authenticated;
immutable canonical blobs are checked at every resolution, never cached mutable.
"""
from collections import OrderedDict
import threading
import contextvars
import uuid
import re
from contextlib import nullcontext
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
_directory = contextvars.ContextVar('explicit_transition_directory', default=None)
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


_decoded_cache=OrderedDict()
_decoded_bytes=0
_decoded_lock=threading.RLock()


def _decoded(raw):
    # Cache only validated immutable byte strings. Every resolver still reads and
    # hashes the referenced content, and returns a detached copy to its caller.
    global _decoded_bytes
    with _decoded_lock:
        if raw in _decoded_cache:
            _decoded_cache.move_to_end(raw)
            return _decoded_cache[raw]
        _parse_budget(raw)
        value=json.loads(raw)
        if not isinstance(value,dict) or canonical(value)!=raw:
            raise ValueError('CANONICAL_TRANSITION_EVIDENCE_REQUIRED')
        while _decoded_cache and (len(_decoded_cache)>=12 or _decoded_bytes+len(raw)>64_000_000):
            previous,_=_decoded_cache.popitem(last=False);_decoded_bytes-=len(previous)
        _decoded_cache[raw]=value;_decoded_bytes+=len(raw)
        return value


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
        resolved[field]=copy.deepcopy(_decoded(raw))
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


def _artifact(name):
    return re.fullmatch(r'\.(?:stage|orphan)-[0-9a-f]{32}-[0-9a-f]{64}', name) is not None


class _DirectoryStore:
    def __init__(self, fd):
        self.fd=fd
        self.inventory()

    def inventory(self):
        fd=self.fd
        names=os.listdir(fd)
        if len(names)>MAX_BUNDLE_FILES:raise ValueError('BOUNDED_TRANSITION_BUNDLE_REQUIRED')
        total=0
        for name in names:
            if not (_name(name) or _artifact(name)):raise ValueError('EXACT_TRANSITION_CONTENT_ADDRESS_REQUIRED')
            info=os.stat(name,dir_fd=fd,follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_size>MAX_BLOB_BYTES:
                raise ValueError('BOUNDED_REGULAR_TRANSITION_BLOB_REQUIRED')
            total+=info.st_size
        if total>MAX_BUNDLE_BYTES:raise ValueError('BOUNDED_TRANSITION_BUNDLE_REQUIRED')
        return names,total

    def get(self, name):
        fcntl.flock(self.fd,fcntl.LOCK_SH)
        try:
            self.inventory()
            return self._get(name)
        finally:fcntl.flock(self.fd,fcntl.LOCK_UN)

    def _get(self, name):
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
    """Pin a caller-selected directory; locks cover reads, never child processes."""
    fd=_open_directory(path)
    try:
        fcntl.flock(fd,fcntl.LOCK_SH)
        try:store=_DirectoryStore(fd)
        finally:fcntl.flock(fd,fcntl.LOCK_UN)
        token=_store.set(store);directory=_directory.set(str(Path(path).absolute()))
        try:yield
        finally:_directory.reset(directory);_store.reset(token)
    finally:os.close(fd)


def active_directory():
    return _directory.get()


def output_scope(output):
    # The public output argument is the trusted locator, never a ticket field.
    path=Path(output).absolute()/'TRANSITION_EVIDENCE'
    return evidence_directory(path) if path.exists() or path.is_symlink() else nullcontext()


def persist_evidence(path,blobs,*,failpoint=None):
    """Create-only immutable objects. Interrupted stages remain bounded evidence."""
    with evidence_scope(blobs):pass
    fd=_open_directory(path)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        store=_DirectoryStore(fd)
        for name,raw in blobs.items():
            names,total=store.inventory()
            if name in names:
                if store._get(name)!=raw:raise ValueError('TRANSITION_EVIDENCE_MISSING_OR_CHANGED')
                continue
            # Includes temporary publication's transient hard link and bytes.
            if len(names)+2>MAX_BUNDLE_FILES or total+2*len(raw)>MAX_BUNDLE_BYTES:
                raise ValueError('BOUNDED_TRANSITION_BUNDLE_REQUIRED')
            stage='.stage-'+uuid.uuid4().hex+'-'+name
            out=os.open(stage,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
            try:
                if failpoint:failpoint('stage_created',stage)
                with os.fdopen(out,'wb',closefd=False) as stream:
                    stream.write(raw);stream.flush();os.fsync(out)
                if failpoint:failpoint('stage_synced',stage)
            finally:os.close(out)
            os.link(stage,name,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False)
            os.fsync(fd)
            if failpoint:failpoint('object_published',stage)
            os.unlink(stage,dir_fd=fd);os.fsync(fd)
    finally:os.close(fd)


def recover_stages(path):
    """Owner calls under account authority. Preserve failed raw bytes, no deletion."""
    fd=_open_directory(path)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX);store=_DirectoryStore(fd)
        rows=[]
        for name in sorted(store.inventory()[0]):
            if _name(name):
                store._get(name)  # Corrupt published objects cannot be repaired here.
                continue
            dest=name.replace('.stage-','.orphan-',1)
            if dest!=name:os.rename(name,dest,src_dir_fd=fd,dst_dir_fd=fd)
            obj=os.open(dest,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
            try:
                raw=os.read(obj,MAX_BLOB_BYTES+1)
                if len(raw)!=os.fstat(obj).st_size:raise ValueError('TRANSITION_RECOVERY_READ_CHANGED')
            finally:os.close(obj)
            rows.append({'path':dest,'bytes':len(raw),'sha256':_sha(raw)})
        os.fsync(fd);return rows
    finally:os.close(fd)


def record_blobs(record):
    """Resolve only known transition ancestry, bounded to four unique tickets."""
    found={};seen={}
    def visit(current):
        for ticket in current.get('source_transitions',{}).values():
            ident=_sha(canonical(ticket))
            if ident in seen:continue
            seen[ident]=True
            if len(seen)>4:raise ValueError('BOUNDED_SOURCE_TRANSITION_ANCESTRY_REQUIRED')
            body=ticket_body(ticket)
            if ticket['body']['schema']==V2:
                for ref in ticket['body']['evidence'].values():
                    raw=_store.get().get(ref['sha256'])
                    if raw is None or len(raw)!=ref['bytes'] or _sha(raw)!=ref['sha256']:
                        raise ValueError('TRANSITION_EVIDENCE_MISSING_OR_CHANGED')
                    found[ref['sha256']]=raw
            visit(body['prior_record'])
    visit(record)
    with evidence_scope(found):pass
    return found


def publication_preflight(body, blobs, target_root, manifest):
    """Owner-side shared source/object/checkpoint budget before signing a new wire.

    The exact eventual export still enforces its guard. This preflight reserves a
    declared record margin for this checkpoint; it never promises unbounded future
    records or counts each historical version more than once.
    """
    objects={**record_blobs(body['prior_record']),**blobs}
    with evidence_scope(objects):pass
    files={};versions={};seen=set()
    def add_source(root,expected,prefix,inputs_root=None):
        expected=dict(expected);source_names=set(expected);input_names=set()
        for job in manifest['jobs']:
            for field in ['input','artifact','receipt']:
                name=job[field];bound=job[field+'_sha256']
                if name in expected and expected[name]!=bound:raise ValueError('HISTORICAL_SOURCE_INPUT_HASH_CONFLICT')
                expected[name]=bound
                if name not in source_names:input_names.add(name)
        for name,bound in sorted(expected.items()):
            relative=Path(name);path=Path(root)/relative
            # Normal preparation copies these exact bound job inputs only after
            # authorization. A bare target need not already contain them.
            if name in input_names and not path.exists() and not path.is_symlink() and inputs_root is not None:path=Path(inputs_root)/relative
            if (relative.is_absolute() or '..' in relative.parts or '\\' in name
                    or any('.sqlite' in part or part=='.git' or part.endswith(('.key','-key')) for part in relative.parts)):
                raise ValueError('RELATIVE_KEY_FREE_PUBLIC_SOURCE_REQUIRED')
            if not path.is_file() or any(p.is_symlink() for p in [path,*path.parents]):raise ValueError('REGULAR_PUBLIC_SOURCE_REQUIRED')
            size=path.stat().st_size
            if size>MAX_BUNDLE_BYTES:raise ValueError('SHARED_PUBLICATION_BUDGET_EXCEEDED')
            with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
            if actual!=bound:raise ValueError('PUBLIC_SOURCE_CHANGED_DURING_PREFLIGHT')
            public=prefix+name
            if public in files and files[public]!={'bytes':size,'sha256':bound}:raise ValueError('PUBLIC_SOURCE_PATH_CONFLICT')
            files[public]={'bytes':size,'sha256':bound}
            if len(files)>MAX_BUNDLE_FILES or sum(row['bytes'] for row in files.values())>MAX_BUNDLE_BYTES:
                raise ValueError('SHARED_PUBLICATION_BUDGET_EXCEEDED')
    def visit(resolved,ancestors=frozenset()):
        ident=resolved['from_source']['sha256']
        if ident in ancestors:raise ValueError('HISTORICAL_SOURCE_CYCLE_REFUSED')
        expected=dict(resolved.get('operating',{}).get('from_runtime',resolved['from_source'])['files'])
        for name,bound in resolved['verifier_files'].items():
            if name in expected and expected[name]!=bound:raise ValueError('HISTORICAL_VERIFIER_HASH_CONFLICT')
            expected[name]=bound
        if ident in versions and versions[ident]!=expected:raise ValueError('HISTORICAL_VERSION_INVENTORY_CHANGED')
        if ident not in versions:
            if len(versions)>=4:raise ValueError('BOUNDED_SOURCE_TRANSITION_ANCESTRY_REQUIRED')
            add_source(resolved['historical_root'],expected,'source/historical-source-versions/'+ident+'/')
            versions[ident]=expected
        for ticket in resolved['prior_record'].get('source_transitions',{}).values():
            key=_sha(canonical(ticket))
            if key in seen:continue
            seen.add(key)
            visit(ticket_body(ticket),ancestors|{ident})
    add_source(target_root,body.get('operating',{}).get('to_runtime',body['to_source'])['files'],'source/',inputs_root=body['historical_root'])
    visit(body)
    record_bytes=(len(canonical(body['prior_record']))
                  +2*len(canonical(body.get('operating',{}).get('prior_checkpoint',{})))
                  +2*len(canonical(manifest))+1_000_000)
    source_bytes=sum(row['bytes'] for row in files.values());object_bytes=sum(map(len,objects.values()))
    # Up to four owner admission receipts plus records, indexes and audit receipts.
    public_files=len(files)+len(objects)+12
    if public_files>MAX_BUNDLE_FILES or source_bytes+object_bytes+record_bytes>MAX_BUNDLE_BYTES:
        raise ValueError('SHARED_PUBLICATION_BUDGET_EXCEEDED')
    return {'schema':'agi-alpha/native-publication-preflight/v1','source_files':len(files),
            'source_bytes':source_bytes,'historical_versions':len(versions),'objects':len(objects),
            'object_bytes':object_bytes,'checkpoint_record_allowance_bytes':record_bytes,
            'planned_public_files':public_files,'planned_public_bytes':source_bytes+object_bytes+record_bytes,
            'source_inventory_sha256':_sha(canonical(files)),
            'limits':{'files':MAX_BUNDLE_FILES,'bytes':MAX_BUNDLE_BYTES},
            'scope':'Shared checkpoint publication preflight; final actual export retains exact guard; later growth may require another bounded transport'}
