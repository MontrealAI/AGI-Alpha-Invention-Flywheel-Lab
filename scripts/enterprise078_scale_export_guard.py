"""Stage only allowlisted, source-bound public scale artifacts; never publish raw diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

WORLD = re.compile(r"[a-z][a-z0-9_]{0,47}\Z")
SUCCESS_FILES = (
    ("enterprise078-scale-keyfree.zip", "keyfree.zip"),
    ("PUBLIC_PACKAGE.json", "PUBLIC_PACKAGE.json"),
    ("public/CAMPAIGN.json", "CAMPAIGN.json"),
)
FORBIDDEN = {"private", "credentials", "secrets", ".ssh", ".git", "__pycache__"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regular(path: Path) -> Path:
    if any(part.is_symlink() for part in (path, *path.parents)) or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("EXPORT_INPUT_NOT_REGULAR")
    return path


def zip_paths_safe(archive: Path) -> None:
    with zipfile.ZipFile(archive) as z:
        names = set()
        for member in z.infolist():
            path = PurePosixPath(member.filename)
            parts = path.parts
            if tuple(member.filename.split("/")) != parts or member.is_dir():
                raise ValueError("UNSAFE_PUBLIC_ARCHIVE_MEMBER")
            if (member.filename.startswith("/") or "\\" in member.filename
                    or not parts or parts[0] not in {"source", "public"}
                    or len(parts) < 2 or any(x in FORBIDDEN or x in {".", ".."} for x in parts)
                    or member.filename in names):
                raise ValueError("UNSAFE_PUBLIC_ARCHIVE_MEMBER")
            mode = (member.external_attr >> 16) & 0o170000
            if mode and mode not in {stat.S_IFDIR, stat.S_IFREG}:
                raise ValueError("UNSAFE_PUBLIC_ARCHIVE_FILE_TYPE")
            names.add(member.filename)


def checked_out_source_sha() -> str:
    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1],
            text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("CHECKED_OUT_SOURCE_IDENTITY_UNAVAILABLE") from exc
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("INVALID_CHECKED_OUT_SOURCE_IDENTITY")
    return head


def prepare(output: Path, upload: Path, stdout: Path, stderr: Path, code: int, world: str) -> dict:
    if not WORLD.fullmatch(world):
        raise ValueError("INVALID_REGISTERED_WORLD")
    if code < 0 or code > 255:
        raise ValueError("INVALID_EXIT_STATUS")
    if upload.exists() or upload.is_symlink():
        raise ValueError("FRESH_UPLOAD_DIRECTORY_REQUIRED")
    if any(part.is_symlink() for part in upload.parents):
        raise ValueError("PUBLIC_EXPORT_PARENT_SYMLINK_REFUSED")
    if output.resolve() == upload.resolve() or output.resolve() in upload.resolve().parents:
        raise ValueError("PUBLIC_EXPORT_MUST_BE_SEPARATE")
    logs = (regular(stdout), regular(stderr))
    os.umask(0o077)
    receipt = {
        "schema": "enterprise078-scale/sanitized-public-export/v1",
        "world": world,
        "subprocess_exit_code": code,
        "status": "SUCCESSFUL_SOURCE_BOUND_PUBLIC_EXPORT" if code == 0 else "FAILED_PRIVATE_DIAGNOSTICS_RETAINED_LOCALLY",
        "stdout_sha256": sha(logs[0]),
        "stderr_sha256": sha(logs[1]),
        "stdout_bytes": logs[0].stat().st_size,
        "stderr_bytes": logs[1].stat().st_size,
        "raw_logs_uploaded": False,
        "original_historical_failures_reclassified": False,
        "export_guard_sha256": sha(Path(__file__)),
        "checked_out_source_sha": checked_out_source_sha(),
        "github_event_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
    }
    if code == 0:
        manifest = json.loads(regular(output / "PUBLIC_PACKAGE.json").read_text())
        archive = regular(output / "enterprise078-scale-keyfree.zip")
        if manifest.get("archive") != archive.name or manifest.get("sha256") != sha(archive) or manifest.get("bytes") != archive.stat().st_size or manifest.get("private_state_included") is not False:
            raise ValueError("PUBLIC_PACKAGE_HASH_OR_PRIVACY_MISMATCH")
        zip_paths_safe(archive)
        campaign = json.loads(regular(output / "public/CAMPAIGN.json").read_text())
        rows = campaign.get("results")
        if (campaign.get("requested_worlds") != [world] or not isinstance(rows, list)
                or len(rows) != 1 or rows[0].get("case") != world
                or rows[0].get("status") != "NATIVE_AND_OPERATING_REPLAY_PASSED"
                or any(k in rows[0] for k in ("stderr_tail", "stdout", "stderr", "error"))):
            raise ValueError("PUBLIC_CAMPAIGN_NOT_SUCCESSFUL_OR_REDACTED")
        paths = SUCCESS_FILES + (
            (f"public/{world}/result.json", f"{world}.result.json"),
            (f"public/{world}/review.json", f"{world}.review.json"),
        )
        for src, _ in paths:
            regular(output / src)
        # The verified archive is canonical; standalone financial receipts must
        # be exactly the same bytes, not post-packaging lookalikes.
        with zipfile.ZipFile(archive) as z:
            for src, _ in paths:
                if not src.startswith("public/"):
                    continue
                standalone = regular(output / src)
                member = z.getinfo(src)
                if member.file_size != standalone.stat().st_size or hashlib.sha256(z.read(src)).hexdigest() != sha(standalone):
                    raise ValueError("PUBLIC_STANDALONE_AND_ARCHIVE_MISMATCH")
    # An incomplete staging directory must never be a public upload path.
    with tempfile.TemporaryDirectory(prefix=".e078-private-stage-", dir=upload.parent) as temporary:
        stage = Path(temporary) / "approved"
        stage.mkdir(mode=0o700)
        if code == 0:
            for src, dest in paths:
                shutil.copyfile(regular(output / src), stage / dest)
            receipt["files_sha256"] = {dest: sha(stage / dest) for _, dest in paths}
        (stage / "SAFE_EXPORT_RECEIPT.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        if upload.exists() or upload.is_symlink():
            raise ValueError("FRESH_UPLOAD_DIRECTORY_REQUIRED")
        os.rename(stage, upload)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--upload-root", type=Path, required=True)
    parser.add_argument("--stdout", type=Path, required=True)
    parser.add_argument("--stderr", type=Path, required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--world", required=True)
    a = parser.parse_args()
    receipt = prepare(a.output_root, a.upload_root, a.stdout, a.stderr, a.exit_code, a.world)
    print(json.dumps({"status": receipt["status"], "world": receipt["world"], "subprocess_exit_code": receipt["subprocess_exit_code"]}))


if __name__ == "__main__":
    main()
