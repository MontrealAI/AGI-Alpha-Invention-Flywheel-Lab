"""P0-202 read-only positive source-closure reference.

NOT an Account, JournalAccount, upgrader, HMAC signer or financial verifier.
A prospective owner port must use the real canonical authorization and audit.
"""
from __future__ import annotations

from pathlib import Path

from connected_enterprise.finance import source_identity


def target_identity_before_and_after(root: Path, manifest: dict, signing_boundary=None) -> dict:
    """Demonstrate correct selected-source checks around a hypothetical signer.

    `signing_boundary` is a *test-only* callback that cannot sign tickets.
    The owner must transplant the two manifest arguments into the real guarded
    authorization after composing with current main's manifest-aware resolver.
    """
    if not isinstance(manifest, dict) or not isinstance(manifest.get("schema"), str):
        raise ValueError("EXPLICIT_SELECTED_SERVICE_MANIFEST_REQUIRED")
    root = Path(root).absolute()
    selected = source_identity(root, manifest)
    if signing_boundary is not None:
        signing_boundary()
    if source_identity(root, manifest) != selected:
        raise ValueError("SELECTED_TARGET_CHANGED_DURING_AUTHORIZATION")
    return selected
