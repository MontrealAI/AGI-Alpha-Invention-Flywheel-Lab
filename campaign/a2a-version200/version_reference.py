"""P200: additive fail-closed protocol-version reference, wrapping exact PR498 code.

No change to the pinned producer/gate. Reference only; no network except
explicit loopback, no accounts, credentials, payment or production use.
"""
from __future__ import annotations
import re

import a2a_adapter as original

# A2A v1: major.minor is normative; a numeric patch suffix is ignored.
_V1 = re.compile(r"1\.0(?:\.[0-9]+)?\Z")
_VERSION_ERROR = -32009


def reference_handler(gate, port):
    owner_handler = original.handler(gate, port)

    class VersionedReference(owner_handler):
        def do_POST(self):
            if self.path == original.A2A_PATH:
                versions = self.headers.get_all("A2A-Version") or []
                if (len(versions) != 1
                        or _V1.fullmatch(versions[0].strip()) is None):
                    # Reject before reading any request body or executing the
                    # immutable productive gate; no ambiguity on duplicates.
                    return self.respond(
                        200, original.error(None, _VERSION_ERROR,
                                            "Protocol version not supported"))
            return super().do_POST()

    return VersionedReference
