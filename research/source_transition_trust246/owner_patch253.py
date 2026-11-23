"""P0-253: source-pinned, owner-reviewable signer repair proposal only.

Returns a patched COPY of immutable historical source. No account, key,
successor source, filesystem or active financial signer is accessed.
"""
import ast
import hashlib

OWNER_UPGRADES_BLOB = "9866d004c412fc05c9f6292cf898307f177359df"
REPLACEMENTS = (
    (
        "                'operating': operating, 'evidence_dir': str(Path(evidence_dir).absolute()) if evidence_dir else None,\n                'codec_source': (target_root/'connected_enterprise/transition_evidence.py').read_text() if evidence_dir else None}",
        "                'operating': operating, 'evidence_dir': str(Path(evidence_dir).absolute()) if evidence_dir else None}",
    ),
    (
        "   codec={};exec(p['codec_source'],codec);blobs={}",
        "   from connected_enterprise.transition_evidence import externalize, preflight_storage, persist_evidence\n   blobs={}",
    ),
    ("   body=codec['externalize'](body,blobs)", "   body=externalize(body,blobs)"),
    ("   codec['preflight_storage'](unsigned,r,old)", "   preflight_storage(unsigned,r,old)"),
    ("   codec['persist_evidence'](p['evidence_dir'],blobs)", "   persist_evidence(p['evidence_dir'],blobs)"),
)

def git_blob_id(raw):
    if type(raw) is not bytes:
        raise TypeError("PINNED_OWNER_BYTES_REQUIRED")
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw).hexdigest()

def patch_historical_owner(raw):
    """Fail closed on drift; remove only the known untrusted codec flow."""
    if git_blob_id(raw) != OWNER_UPGRADES_BLOB:
        raise ValueError("HISTORICAL_OWNER_SOURCE_BLOB_CHANGED")
    source = raw.decode("utf-8")
    for old, new in REPLACEMENTS:
        if source.count(old) != 1:
            raise ValueError("OWNER_PATCH_ANCHOR_NOT_UNIQUE")
        source = source.replace(old, new, 1)
    ast.parse(source, filename="proposed_owner_upgrades.py")
    if ("codec_source" in source or "exec(p[" in source
            or "target_root/'connected_enterprise/transition_evidence.py'" in source):
        raise ValueError("SUCCESSOR_EXECUTION_REMAINS_IN_SIGNER")
    fixed = "from connected_enterprise.transition_evidence import externalize, preflight_storage, persist_evidence"
    if source.count(fixed) != 1:
        raise ValueError("PINNED_OWNER_CODEC_IMPORT_MISSING")
    return source.encode("utf-8")
