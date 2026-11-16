"""P0-188 experimental immutable CAS closure transport.

Read-only independent research primitive. Snapshot bytes are not a source
transition, account authorization, financial audit or writer lease.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from commercial.ledger import digest
from connected_enterprise import transition_evidence as te


_MAX_TICKETS = 64
_MAX_NODES = 150_000


@dataclass(frozen=True)
class HistoryEvidenceSnapshot:
    root_ticket_digest: str
    closure_digest: str
    ticket_count: int
    blobs: Mapping[str, bytes]

    @contextmanager
    def evidence(self):
        """A fresh, hash-verified in-memory proof scope, not live account authority."""
        with te.evidence_scope(dict(self.blobs)):
            yield


def _nested_tickets(resolved, remaining):
    """Walk all historical fields, including nested source-transition tickets."""
    stack = [resolved.get("prior_record"),
             resolved.get("prior_envelope"),
             resolved.get("operating")]
    found = []
    while stack:
        remaining -= 1
        if remaining < 0:
            raise ValueError("HISTORY_SNAPSHOT_NODE_BOUND")
        item = stack.pop()
        if isinstance(item, dict):
            if (set(item) == {"body", "signature"}
                    and isinstance(item["body"], dict)
                    and item["body"].get("schema") in {te.V1, te.V2}):
                found.append(item)
            else:
                stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return found, remaining


def capture_historical_evidence(ticket):
    """Capture a complete immutable V2 evidence closure in a trusted caller scope.

    No ticket-supplied path is opened. The caller must already have bound a
    trusted evidence_directory/evidence_scope and authenticated the ticket
    *separately*. This does not establish a linearizable finance checkpoint or
    guard against an uncooperative writer changing the live store after capture.
    """
    pending = [ticket]
    seen = set()
    verified_tickets = []
    blobs = {}
    total_bytes = 0
    remaining = _MAX_NODES
    while pending:
        current = pending.pop()
        if not isinstance(current, dict) or set(current) != {"body", "signature"}:
            raise ValueError("EXACT_HISTORY_SNAPSHOT_TICKET_REQUIRED")
        marker = digest(current)
        if marker in seen:
            continue
        seen.add(marker)
        if len(seen) > _MAX_TICKETS:
            raise ValueError("HISTORY_SNAPSHOT_TICKET_BOUND")
        # Existing resolver checks schema, canonical JSON, hash/length, budget,
        # and recursively references only in the explicit current evidence scope.
        resolved = te.ticket_body(current)
        if current["body"].get("schema") == te.V2:
            refs = current["body"]["evidence"]
            for ref in refs.values():
                name = ref["sha256"]
                raw = te.read_evidence_blob(name)
                if len(raw) != ref["bytes"]:
                    raise ValueError("HISTORY_SNAPSHOT_REFERENCE_CHANGED")
                if name not in blobs:
                    blobs[name] = raw
                    total_bytes += len(raw)
                    if (len(blobs) > te.MAX_BUNDLE_FILES
                            or total_bytes > te.MAX_BUNDLE_BYTES):
                        raise ValueError("HISTORY_SNAPSHOT_BUNDLE_BOUND")
                elif blobs[name] != raw:
                    raise ValueError("HISTORY_SNAPSHOT_SOURCE_CHANGED")
        verified_tickets.append(current)
        descendants, remaining = _nested_tickets(resolved, remaining)
        pending.extend(descendants)

    # Independently verify the complete capture without any live directory.
    # This is the defining condition distinguishing a closed snapshot from an
    # old cached receipt carrying no evidence bytes.
    with te.evidence_scope(blobs):
        for current in verified_tickets:
            te.ticket_body(current)

    root_digest = digest(ticket)
    inventory = [{"sha256": name, "bytes": len(raw)}
                 for name, raw in sorted(blobs.items())]
    closure_digest = digest({"root_ticket": root_digest, "blobs": inventory})
    return HistoryEvidenceSnapshot(root_ticket_digest=root_digest,
                                   closure_digest=closure_digest,
                                   ticket_count=len(verified_tickets),
                                   blobs=MappingProxyType(dict(sorted(blobs.items()))))
