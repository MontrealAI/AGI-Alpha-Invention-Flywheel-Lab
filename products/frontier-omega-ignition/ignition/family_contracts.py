"""Data interfaces of the installed builders and independently supplied manifest witnesses."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

from . import construction


_FAMILIES = {
    "record_migration": {
        "inputs": ["flat_json_rows"],
        "operations": ["project_fields", "join_text_fields", "split_text_field", "convert_scalar_type",
                       "enforce_extra_field_policy"],
        "outputs": ["mapped_json_rows"],
        "semantics": "Each input row yields one output row, in input order. Project a field, join two to four "
                     "text fields of the same row, or split one text field. The column checks or converts to "
                     "text, integer or boolean. The definition selects drop or reject for extra fields. "
                     "A lookup in another table or a remote system requires a different worker.",
        "recipient_input": "A JSON batch with a rows array, or one input row per line using migrate-jsonl.",
    },
    "manifest_audit": {
        "inputs": ["trusted_sha256_manifest", "named_file_bytes"],
        "operations": ["compare_sha256_by_path"],
        "outputs": ["path_discrepancy_report"],
        "semantics": "Compare named input bytes with independently supplied SHA-256 digests at those logical "
                     "paths. Emit ok and sorted lists of matched, changed, missing and unexpected paths. "
                     "The comparison cannot emit transformed rows, resolve names or fetch missing data.",
        "recipient_input": "A files object of relative names and canonical base64 bytes, or a selected stable "
                           "unpacked POSIX directory using audit-directory.",
    },
}


def catalog():
    """Return JSON data for research turns; candidate edits cannot change the checker."""
    return deepcopy(_FAMILIES)


def _valid_manifest(mapping):
    try:
        construction._manifest({"manifest": mapping})
    except construction.ConstructionError:
        return False
    return True


def _ids(items):
    return (isinstance(items, list) and bool(items) and all(isinstance(i, str) and i for i in items)
            and len(set(items)) == len(items))


def assess(kind, mechanics, *, requested_output=None, public_spec=None, authorized_manifest=None):
    """Check declared input/output mechanics, independently of the prose and the model's fit verdict.

    public_spec is the operator's builder-visible contract. authorized_manifest, when supplied,
    is caller-owned evidence. Neither argument may come from the candidate being reviewed.
    A supported result only establishes fit of the declared interface and operations.
    """
    family = _FAMILIES.get(kind) if isinstance(kind, str) else None
    if family is None:
        return {"status": "unsupported", "reason": "No installed data-only builder has this family."}
    if requested_output is not None:
        requested = [requested_output] if isinstance(requested_output, str) else requested_output
        if not _ids(requested) or not set(requested) <= set(family["outputs"]):
            return {"status": "unsupported", "reason": "The installed family cannot emit the requested output."}
    if public_spec and (not isinstance(public_spec, dict) or public_spec.get("kind") != kind):
        return {"status": "unsupported", "reason": "The proposed worker differs from the supplied contract family."}
    if mechanics is None:
        return {"status": "unassessed", "reason": "The proposal has no declared input, operation and output interface."}
    axes = ("inputs", "operations", "outputs")
    if not isinstance(mechanics, dict) or set(mechanics) != set(axes) or not all(_ids(mechanics[k]) for k in axes):
        return {"status": "unsupported", "reason": "Declare distinct input, operation and output identifiers in each list."}
    if set(mechanics["inputs"]) != set(family["inputs"]):
        return {"status": "unsupported", "reason": "The proposed inputs differ from the inputs the installed worker requires."}
    if not set(mechanics["operations"]) <= set(family["operations"]):
        return {"status": "unsupported", "reason": "An operation in the proposed route is unavailable in this worker."}
    if set(mechanics["outputs"]) != set(family["outputs"]):
        return {"status": "unsupported", "reason": "The declared output differs from the installed worker's output."}
    if kind == "manifest_audit":
        definition = public_spec.get("definition") if public_spec else {"manifest": authorized_manifest}
        if not isinstance(definition, dict) or set(definition) != {"manifest"} or not _valid_manifest(definition["manifest"]):
            return {"status": "unsupported", "reason": "A manifest audit needs independently supplied named SHA-256 digests."}
    return {"status": "supported", "reason": "The declared inputs, operations and output match this worker's bounded interface."}


class _Pairs(list):
    """Distinguish JSON objects from arrays and retain duplicate keys before building a map."""


def _entries(text):
    if text.lstrip().startswith("{"):
        try:
            doc = json.loads(text, object_pairs_hook=_Pairs)
        except (ValueError, RecursionError):
            return []
        if (not isinstance(doc, _Pairs) or len(doc) != 1 or doc[0][0] != "manifest"
                or not isinstance(doc[0][1], _Pairs)):
            return []
        pairs = doc[0][1]
        return pairs if _valid_manifest(dict(pairs)) and all(_valid_manifest({p: h}) for p, h in pairs) else []
    entries = []
    for line in text.splitlines():
        digest, marker, path = line.partition("  ")
        if marker and _valid_manifest({path: digest}):
            entries.append((path, digest))
    return entries


def extracted_manifest(signals):
    """Read exact checksum records from eligible, operator-entered research signals.

    Each source must already be normalized by research._signals. This reads only the
    supplied excerpt. Returning an inventory identifies its origin for operator review;
    it neither authenticates a publisher nor grants authority to access any file.
    A conflict anywhere withholds the combined inventory.
    """
    inventory, provenance, conflicts = {}, [], set()
    for signal in signals:
        if (signal.get("origin") != "operator-supplied excerpt" or signal.get("acquisition")
                or signal.get("status") != "active" or signal.get("access") != "available"
                or signal.get("current_observation") is not True or signal.get("event_pending") is not False
                or signal.get("excerpt_truncated") or not signal.get("rights")
                or signal["rights"] == "Unknown; citation and local evaluation only."):
            continue
        text = signal.get("text")
        if not isinstance(text, str) or sha256(text.encode()).hexdigest() != signal.get("sha256"):
            continue
        entries = _entries(text)
        if entries:
            provenance.append({"id": signal["id"], "url": signal["url"], "sha256": signal["sha256"],
                               "paths": sorted({path for path, _ in entries})})
        for path, digest in entries:
            if path in inventory and inventory[path] != digest:
                conflicts.add(path)
            inventory[path] = digest
    return {"manifest": inventory if not conflicts and _valid_manifest(inventory) else {},
            "sources": provenance, "conflicts": sorted(conflicts)}
