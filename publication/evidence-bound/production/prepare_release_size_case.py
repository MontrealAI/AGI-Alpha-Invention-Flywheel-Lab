# SPDX-License-Identifier: Apache-2.0
"""Bind a French live archive-size check to the two downloaded Pages packages."""

from hashlib import sha256
import json
from pathlib import Path
import sys
from zipfile import ZipFile


AMBITION = ("Comparez la taille exacte des deux archives publiques de HARNESS, versions 1.0.0 et 1.1.0, "
            "et calculez de combien d’octets la version 1.1.0 est plus grande.")


def prepare(directory, revision):
    release = json.loads((directory / "atlas-release.json").read_bytes())
    if release["source_commit"] != revision:
        raise ValueError("The release receipt must bind the intended revision")
    verified = {}
    for version in ("1.0.0", "1.1.0"):
        name = f"frontier-harness-executor-{version}.zip"
        path = directory / name
        raw = path.read_bytes()
        fingerprint = sha256(raw).hexdigest()
        with ZipFile(path) as archive:
            about = json.loads(archive.read("manifest.json"))
        if fingerprint != release["universal_mission_sha256"][name] or about["version"] != version:
            raise ValueError("Archive bytes and version must match the release receipt")
        verified[version] = {"sha256": fingerprint, "bytes": path.stat().st_size, "source": about["source"]}

    values = {"previous_bytes": verified["1.0.0"]["bytes"], "current_bytes": verified["1.1.0"]["bytes"]}
    value_bytes = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    difference = values["current_bytes"] - values["previous_bytes"]
    facts = {"quantity": "archive_file_size", "old": verified["1.0.0"]["sha256"], "new": verified["1.1.0"]["sha256"]}
    record = {"kind": "values", "origin": "VERIFIED_EXTERNAL_SOURCE", "sha256": sha256(value_bytes).hexdigest(),
              "version": revision, "facts": facts, "values": values, "source": "Exact official Pages archives and release receipt"}
    claim = {"id": "archive_delta", "dataset": "release_sizes", "tool": "run_instrument",
             "locator": ["output", "difference"], "unit": "octets", "dimension": "file_size", "version": revision,
             "required_fields": [[key] for key in values], "requires": facts,
             "reference": {"value": str(difference), "source": "Separate os.stat size subtraction of two checked public archive files"}}
    manifest = {"schema": "frontier/local-mission-input-v1", "ambition": AMBITION, "language": "fr",
                "context": ("Les deux longueurs proviennent des archives publiques vérifiées. Calculez la différence "
                            "current_bytes moins previous_bytes avec le champ de sortie difference. "
                            "Rattachez le calcul à la revendication archive_delta et au jeu release_sizes."),
                "tools": ["construct_instrument", "run_instrument"],
                "requirements": {"evidence": {"inputs": {"release_sizes": record}, "claims": [claim]}}}
    return manifest, {"release_revision": revision, "archive_statistics": verified, "expected_delta_bytes": difference}


if __name__ == "__main__":
    packages, revision, output = sys.argv[1:]
    manifest, control = prepare(Path(packages), revision)
    Path(output).write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps(control, ensure_ascii=False, sort_keys=True))
