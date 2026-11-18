"""Build an intentionally false, evaluation-only manifest to replay negative evidence."""
from ignition import construction


def rejected_manifest(contract, proposal):
    if (contract["spec"]["kind"] != "manifest_audit" or proposal["kind"] != "manifest_audit"
            or proposal["program"] == contract["spec"]["definition"]):
        raise ValueError("A negative control needs a differing manifest")
    body = {"format": "ignition-artifact/1", "contract_sha256": contract["sha256"],
            "kind": "manifest_audit", "program": proposal["program"]}
    return {**body, "sha256": construction.fingerprint(body)}
