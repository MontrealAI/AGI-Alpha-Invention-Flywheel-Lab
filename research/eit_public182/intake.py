"""Read-only public Zenodo *metadata* gate, NOT a physical-data experiment.

Pre-implementation registration: campaign/eit-public-observatory182/PROTOCOL.md
No credentials, archive downloads, or financial operations are used.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen

RECORD_ID = 24120439
API = f"https://zenodo.org/api/records/{RECORD_ID}"
MAX_METADATA_BYTES = 2_000_000
PHANTOMS = ("AgarCylinderPhantom", "AgarChestPhantom", "HeadPhantom")
CHECKSUM_RE = re.compile(r"^(md5:[0-9a-fA-F]{32}|sha256:[0-9a-fA-F]{64})$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.+() -]{1,180}$")


class IntakeRefusal(ValueError):
    """Fail closed without converting missing evidence into a scientific result."""


def unique_pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise IntakeRefusal("DUPLICATE_JSON_KEY")
        result[k] = v
    return result


def read_record(url: str = API) -> tuple[dict, str]:
    if url != API:
        raise IntakeRefusal("SOURCE_URL_CHANGED")
    request = Request(url, headers={"User-Agent": "AGI-ALPHA-public-EIT-metadata-gate/1.0", "Accept": "application/json"})
    with urlopen(request, timeout=25) as response:
        if urlparse(response.url).hostname not in {"zenodo.org", "www.zenodo.org"}:
            raise IntakeRefusal("SOURCE_HOST_CHANGED")
        raw = response.read(MAX_METADATA_BYTES + 1)
    if len(raw) > MAX_METADATA_BYTES:
        raise IntakeRefusal("METADATA_TOO_LARGE")
    try:
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_pairs)
    except (ValueError, UnicodeError) as exc:
        raise IntakeRefusal("INVALID_SOURCE_JSON") from exc
    if not isinstance(record, dict):
        raise IntakeRefusal("NOT_A_RECORD")
    return record, hashlib.sha256(raw).hexdigest()


def declared_license(metadata: dict) -> str:
    license_info = metadata.get("license")
    rights = metadata.get("rights")
    values = []
    if isinstance(license_info, dict):
        values += [license_info.get("id"), license_info.get("title")]
    elif isinstance(license_info, str):
        values.append(license_info)
    if isinstance(rights, list):
        for item in rights:
            if isinstance(item, dict):
                values += [item.get("id"), item.get("title"), item.get("identifier")]
    if isinstance(rights, dict):
        values += [rights.get("id"), rights.get("title")]
    return next((v for v in values if isinstance(v, str) and v.strip()), "")


def _file_entries(files):
    if isinstance(files, list):
        return files
    if isinstance(files, dict):
        return list(files.values())
    raise IntakeRefusal("NO_FILE_INVENTORY")


def validate(record: dict, raw_sha256: str) -> dict:
    if type(record.get("id")) is not int or record["id"] != RECORD_ID:
        raise IntakeRefusal("WRONG_RECORD_ID")
    metadata = record.get("metadata")
    if not isinstance(metadata, dict):
        raise IntakeRefusal("MISSING_RECORD_METADATA")
    doi = record.get("doi") or metadata.get("doi") or ""
    if not isinstance(doi, str) or f"zenodo.{RECORD_ID}" not in doi:
        raise IntakeRefusal("DOI_NOT_BOUND_TO_RECORD")
    title = metadata.get("title")
    if not isinstance(title, str) or "impedance tomography" not in title.lower():
        raise IntakeRefusal("WRONG_DATASET_TITLE")
    license_declared = declared_license(metadata)
    if not license_declared:
        raise IntakeRefusal("DATASET_LICENSE_UNVERIFIED")

    inventory = []
    names = set()
    for entry in _file_entries(record.get("files")):
        if not isinstance(entry, dict):
            raise IntakeRefusal("BAD_FILE_DESCRIPTOR")
        name = entry.get("key") or entry.get("filename")
        if not isinstance(name, str) or not SAFE_NAME_RE.fullmatch(name) or name in {".", ".."}:
            raise IntakeRefusal("UNSAFE_OR_MISSING_FILENAME")
        if name.casefold() in names:
            raise IntakeRefusal("DUPLICATE_FILE_DESCRIPTOR")
        names.add(name.casefold())
        size = entry.get("size")
        if type(size) is not int or size < 0:
            raise IntakeRefusal("INVALID_DECLARED_SIZE")
        checksum = entry.get("checksum")
        if not isinstance(checksum, str) or not CHECKSUM_RE.fullmatch(checksum):
            raise IntakeRefusal("INVALID_DECLARED_CHECKSUM")
        links = entry.get("links", {})
        link = links.get("self") or links.get("content") if isinstance(links, dict) else None
        parsed = urlparse(link) if isinstance(link, str) else None
        if parsed is None or parsed.scheme != "https" or parsed.hostname not in {"zenodo.org", "www.zenodo.org"}:
            raise IntakeRefusal("UNTRUSTED_FILE_URL")
        inventory.append({"name": name, "declared_bytes": size, "declared_checksum": checksum.lower(), "url": link})

    missing = [p for p in PHANTOMS if not any(p.casefold() in f["name"].casefold() for f in inventory)]
    if missing:
        raise IntakeRefusal("MISSING_REGISTERED_PHANTOM_CLASS:" + ",".join(missing))
    return {
        "schema": "blue-sky-182-public-metadata-v1",
        "record_id": RECORD_ID,
        "api": API,
        "doi": doi,
        "title": title,
        "license_as_declared_by_source": license_declared,
        "metadata_response_sha256": raw_sha256,
        "files": sorted(inventory, key=lambda d: d["name"]),
        "phantom_classes_present": list(PHANTOMS),
        "archive_bytes_independently_hashed": False,
        "physical_measurements_analyzed": False,
        "clinical_or_commercial_claim": False,
        "decision": "METADATA_ONLY_PASS__HOLD_NO_DEPLOY",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="New public-only metadata receipt JSON path")
    args = parser.parse_args(argv)
    out = Path(args.out)
    if out.exists() or out.is_symlink():
        raise IntakeRefusal("OUTPUT_ALREADY_EXISTS")
    record, raw_sha = read_record()
    receipt = validate(record, raw_sha)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"decision": receipt["decision"], "manifest": str(out), "metadata_sha256": raw_sha,
                      "files": len(receipt["files"]), "bytes_downloaded_from_archives": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (IntakeRefusal, OSError) as error:
        print(json.dumps({"decision": "REFUSE__HOLD_NO_DEPLOY", "error": str(error)}), file=sys.stderr)
        sys.exit(2)
