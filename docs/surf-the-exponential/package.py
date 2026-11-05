#!/usr/bin/env python3
"""Verify the publication binding and export deterministic release assets.

python3 package.py --verify
python3 package.py --output-dir /absolute/release-directory
python3 package.py --verify --output-dir /absolute/release-directory

The last form also validates existing exported assets without rewriting them.
The manifest is never automatically refreshed after a source or PDF mismatch.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import sys
from datetime import datetime, timezone
import zipfile


ROOT = Path(__file__).resolve().parent
MANIFEST_NAME = "PUBLICATION.json"
PDF_NAME = "SURF_THE_EXPONENTIAL.pdf"
ZIP_NAME = "SURF_THE_EXPONENTIAL_SOURCE.zip"
SUMS_NAME = "SHA256SUMS"
BUNDLE_PDF = "canonical/" + PDF_NAME
SOURCE_SUFFIXES = {".py", ".md", ".tex", ".bib", ".json"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def reject_duplicates(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate manifest key: {key}")
        result[key] = value
    return result


def source_inventory(root: Path) -> list[str]:
    """Inventory publication sources; build output and caches are not inputs."""
    paths = {
        path for path in root.iterdir()
        if path.is_file() and path.suffix in SOURCE_SUFFIXES and path.name != MANIFEST_NAME
    }
    if (root / ".gitignore").exists():
        paths.add(root / ".gitignore")
    for dirname in ("evidence", "figures"):
        directory = root / dirname
        if directory.exists():
            paths.update(path for path in directory.rglob("*") if path.is_file())
    return sorted(path.relative_to(root).as_posix() for path in paths)


def compiled_inventory(root: Path) -> list[str]:
    """Match the declared input selection used by build.py."""
    paths = (set(root.glob("*.tex")) | set(root.glob("*.bib"))
             | set((root / "figures").rglob("*.tex"))
             | {root / "evidence/results_table.tex"})
    return sorted(path.relative_to(root).as_posix() for path in paths)


def source_path(root: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if (relative.is_absolute() or ".." in relative.parts or relative.as_posix() != name
            or not name or name == MANIFEST_NAME):
        raise ValueError(f"Invalid source path in manifest: {name}")
    path = root / name
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"Missing, linked or external source: {name}")
    return path


def check_blob(data: bytes, entry: dict, label: str) -> None:
    if len(data) != entry["bytes"] or digest(data) != entry["sha256"]:
        raise ValueError(f"Content identity mismatch: {label}")


def validated_content(root: Path = ROOT) -> tuple[dict, dict[str, bytes]]:
    """Return the verified manifest and an immutable-in-memory file snapshot."""
    raw_manifest = (root / MANIFEST_NAME).read_bytes()
    manifest = json.loads(raw_manifest, object_pairs_hook=reject_duplicates)
    if manifest["schema"] != "surf-publication/v1":
        raise ValueError("Unsupported publication manifest schema")
    entries = manifest["source_files"]
    names = [entry["path"] for entry in entries]
    if names != sorted(set(names)):
        raise ValueError("Source list must contain unique, sorted paths")
    if names != source_inventory(root):
        raise ValueError("Publication source inventory differs from the manifest")
    if digest(canonical_json(entries)) != manifest["source_tree_sha256"]:
        raise ValueError("Source-tree digest does not match its entries")
    snapshot = {}
    for entry in entries:
        data = source_path(root, entry["path"]).read_bytes()
        check_blob(data, entry, entry["path"])
        snapshot[entry["path"]] = data
    compiled_names = compiled_inventory(root)
    compiled = [entry for entry in entries if entry["path"] in compiled_names]
    if ([entry["path"] for entry in compiled] != compiled_names
            or compiled != manifest["compiled_inputs"]
            or digest(canonical_json(compiled)) != manifest["compiled_input_tree_sha256"]):
        raise ValueError("Compiled input binding differs from the current build inputs")
    pdf_entry = manifest["canonical_pdf"]
    if (pdf_entry["bundle_path"] != BUNDLE_PDF
            or pdf_entry["repository_relative_to_source"] != "../research/surf-the-exponential.pdf"):
        raise ValueError("Unexpected canonical PDF location")
    candidates = (root / BUNDLE_PDF, root / "../research/surf-the-exponential.pdf")
    pdf_path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if pdf_path is None:
        raise ValueError("Canonical PDF is missing from both the bundle and repository locations")
    pdf_data = pdf_path.read_bytes()
    check_blob(pdf_data, pdf_entry, "canonical PDF")
    if not pdf_data.startswith(b"%PDF-"):
        raise ValueError("Canonical asset is not a PDF")
    expected_assets = {
        "pdf": PDF_NAME, "source_archive": ZIP_NAME,
        "manifest": MANIFEST_NAME, "checksums": SUMS_NAME,
    }
    if manifest["release_assets"] != expected_assets:
        raise ValueError("Unexpected release asset names")
    epoch = manifest["build"]["source_date_epoch"]
    if isinstance(epoch, bool) or not isinstance(epoch, int):
        raise ValueError("The source epoch must be an integer")
    if not 1980 <= datetime.fromtimestamp(epoch, timezone.utc).year <= 2107:
        raise ValueError("Source epoch cannot be represented by a deterministic ZIP timestamp")
    snapshot[MANIFEST_NAME] = raw_manifest
    snapshot[BUNDLE_PDF] = pdf_data
    return manifest, snapshot


def archive_bytes(snapshot: dict[str, bytes], epoch: int) -> bytes:
    """Sorted, uncompressed ZIP entries avoid compression-version variability."""
    stamp = datetime.fromtimestamp(epoch, timezone.utc)
    timestamp = (stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute, stamp.second)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name in sorted(snapshot):
            info = zipfile.ZipInfo(filename=name, date_time=timestamp)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.create_version = 20
            info.extract_version = 20
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.extra = b""
            info.comment = b""
            archive.writestr(info, snapshot[name])
        archive.comment = b""
    return buffer.getvalue()


def release_payloads(manifest: dict, snapshot: dict[str, bytes]) -> dict[str, bytes]:
    assets = {
        PDF_NAME: snapshot[BUNDLE_PDF],
        ZIP_NAME: archive_bytes(snapshot, manifest["build"]["source_date_epoch"]),
        MANIFEST_NAME: snapshot[MANIFEST_NAME],
    }
    sums = "".join(f"{digest(data)}  {name}\n" for name, data in sorted(assets.items()))
    assets[SUMS_NAME] = sums.encode("ascii")
    return assets


def export_or_verify(output: Path, assets: dict[str, bytes], verify_only: bool) -> list[dict]:
    output = output.resolve()
    if output == ROOT or output.is_relative_to(ROOT):
        raise ValueError("Use an output directory outside the publication source directory")
    if not verify_only:
        output.mkdir(parents=True, exist_ok=True)
    report = []
    for name, data in sorted(assets.items()):
        destination = output / name
        if verify_only:
            if not destination.is_file() or destination.read_bytes() != data:
                raise ValueError(f"Exported asset is absent or differs: {name}")
        else:
            destination.write_bytes(data)
        report.append({"name": name, "bytes": len(data), "sha256": digest(data)})
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Validate source/PDF binding; with --output-dir also check existing release assets")
    parser.add_argument("--output-dir", type=Path, help="Export four release assets here, or verify them when combined with --verify")
    args = parser.parse_args()
    if not args.verify and args.output_dir is None:
        parser.error("supply --verify or --output-dir")
    try:
        manifest, snapshot = validated_content()
        report = {
            "status": "PASS", "source_files_verified": len(manifest["source_files"]),
            "compiled_inputs_verified": len(manifest["compiled_inputs"]),
            "canonical_pdf_sha256": manifest["canonical_pdf"]["sha256"],
            "canonical_pdf_bytes": manifest["canonical_pdf"]["bytes"],
            "canonical_pdf_pages_recorded": manifest["canonical_pdf"]["pages"],
            "scope": "Exact source and canonical PDF identity; scientific validity and build causality require their separate checks.",
        }
        if args.output_dir is not None:
            assets = release_payloads(manifest, snapshot)
            report["assets"] = export_or_verify(args.output_dir, assets, args.verify)
            report["operation"] = "verified_existing_assets" if args.verify else "exported_assets"
        else:
            report["operation"] = "verified_publication_binding"
        print(json.dumps(report, indent=2))
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Publication verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
