# SPDX-License-Identifier: Apache-2.0
"""Prepare a bounded French version-floor check from two authenticated repository objects."""
import argparse
from hashlib import sha1, sha256
import json
from pathlib import Path
import re


AMBITION = ("Créez un contrôle réutilisable indiquant combien des deux versions finales de CPython satisfont "
            "le minimum 3.13.4, à partir des deux en-têtes officiels autorisés.")
FLOOR = (3, 13, 4)
SOURCES = {
    "alpha": ("55fee9cf216abe4ec0d1139f94b1930fbd0c7644", "45b770003cb854f1d412f398e21c06dc75a40ce8",
              "6d09cebdb07346b76b8f9176f5d23773c8c8dd12605eabdbfd0a7461ec86c408"),
    "bravo": ("6cb20a219a860eaf687b2d968b41c480c7461909", "7447c0b19d8612b53d9abcbcd6c7a75a18020d2f",
              "d539cfabe79088f3e418b9498389e1143da2cf797368b6cf6bdd31d21eb3ff9b"),
}
CLAIM = "eligible_releases"


def prepare(directory):
    snapshots, values, references = {}, {}, {}
    for key, (commit, blob, digest) in SOURCES.items():
        raw = (directory / f"{key}.h").read_bytes()
        if sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() != blob or sha256(raw).hexdigest() != digest:
            raise ValueError(f"Source differs from the registered public object: {key}")
        text = raw.decode()
        if not re.search(r"^#define\s+PY_RELEASE_LEVEL\s+PY_RELEASE_LEVEL_FINAL\s*$", text, re.M):
            raise ValueError("Only final releases are in the comparison scope")
        for part in ("major", "minor", "micro"):
            field = re.search(rf"^#define\s+PY_{part.upper()}_VERSION\s+(\d+)\s*$", text, re.M)
            values[f"{key}_{part}"] = int(field.group(1))
        official = re.search(r'^#define\s+PY_VERSION\s+"(\d+\.\d+\.\d+)"\s*$', text, re.M).group(1)
        references[key] = tuple(map(int, official.split(".")))
        snapshots[key] = {"url": f"https://github.com/python/cpython/blob/{commit}/Include/patchlevel.h", "version": commit,
                          "sha256": digest, "content_type": "text/plain", "text": text,
                          "acquisition": "Authorized GitHub connector, exact commit and Git blob verified"}
    version = "".join(record["sha256"] for record in snapshots.values())
    version = sha256(version.encode()).hexdigest()
    facts = {"floor": list(FLOOR), "release_level": "final", "pinned_headers": list(SOURCES)}
    values.update(zip(("floor_major", "floor_minor", "floor_micro"), FLOOR))
    value_bytes = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    expected = sum(version_tuple >= FLOOR for version_tuple in references.values())
    record = {"kind": "values", "origin": "VERIFIED_EXTERNAL_SOURCE", "sha256": sha256(value_bytes).hexdigest(),
              "version": version, "facts": facts, "values": values,
              "source": "Numeric version macros from two exact public CPython header objects"}
    claim = {"id": CLAIM, "dataset": "cpython_versions", "tool": "run_instrument", "locator": ["output", "count"],
             "unit": "versions", "dimension": "release_count", "version": version, "requires": facts,
             "required_fields": [[field] for field in values],
             "reference": {"value": str(expected), "source": "Separate Python tuple comparisons of PY_VERSION strings"}}
    manifest = {
        "schema": "frontier/local-mission-input-v1", "ambition": AMBITION, "language": "fr",
        "context": ("Les versions alpha et bravo sont finales. Les observations chiffrées *_major, *_minor, *_micro, ainsi que le seuil "
                    "floor_major, floor_minor, floor_micro, sont déjà extraites des en-têtes. Comparez les trois composantes de chaque version "
                    "lexicographiquement et fournissez le nombre de versions admissibles dans la sortie count. Construisez versions.json puis "
                    "exécutez-le avec input:{dataset:'cpython_versions'} et la revendication eligible_releases. Les captures alpha et bravo "
                    "sont lisibles avec l’outil approuvé et ses décalages d’octets. Le contrôle porte sur la version déclarée."),
        "tools": ["construct_instrument", "run_instrument", "read_source_snapshot"],
        "requirements": {"evidence": {"inputs": {"cpython_versions": record}, "claims": [claim]}, "source_snapshots": snapshots,
                         "outcome": {"deliverable": "Contrôle numérique réutilisable du seuil de version finale.", "required_claims": [CLAIM],
                                     "criteria": ["Compter les deux versions selon l’ordre majeur, mineur, correctif."],
                                     "constraints": ["Périmètre limité aux déclarations de version finale."],
                                     "verification": "Comparer séparément les chaînes PY_VERSION officielles.",
                                     "alternatives": ["Comparer des triplets d’entiers avec Python."]}},
    }
    receipt = {"sources": {key: {field: value for field, value in row.items() if field != "text"}
                            for key, row in snapshots.items()}, "floor": FLOOR, "exact_versions": references,
               "independent_count": expected, "binding_sha256": record["sha256"]}
    return manifest, receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sources", type=Path, help="Directory containing the two exact publisher objects alpha.h and bravo.h")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest, receipt = prepare(args.sources)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
