"""Read-only verification of an actual hosted release operation using public records.

Use provider.json containing the raw GitHub API objects under tag, release, run,
job, gate_artifact, and operation_artifact. The two ZIPs are provider downloads
of the matching workflow artifacts. Only a compact digest summary is printed.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from zipfile import ZipFile


REPO = "MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"
BASE_ASSETS = {
    "COMPOSED_PUBLICATION.json", "OMEGA_V4_QUALIFICATION.json", "PAPER.pdf", "PAPER.tex",
    "PDF_QA.json", "PUBLICATION.json", "QUALIFICATION.json", "RELEASE_MANIFEST.json",
    "RELEASE_NOTES.md", "REPORT.md", "SHA256SUMS.txt", "connected014-keyfree.zip",
    "connected014-source.zip", "index.html",
}
REACH_ENTRYPOINT = "mechanism_harness/reach_native.py"
STAGES = ["source-identity", "run", "audit", "resume"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_artifact(meta, path, run, prefix):
    name = f"{prefix}-{run['head_sha']}-attempt-{run['run_attempt']}"
    require(meta["name"] == name and meta["expired"] is False, "Artifact identity or expiry")
    binding = meta["workflow_run"]
    require(binding["id"] == run["id"] and binding["head_sha"] == run["head_sha"]
            and binding["head_branch"] == "main"
            and binding["repository_id"] == run["repository"]["id"], "Artifact run binding")
    require(Path(path).stat().st_size == meta["size_in_bytes"]
            and "sha256:" + file_hash(path) == meta["digest"], "Artifact ZIP bytes")


def checked_probe(native_map, command):
    # The published probe prints sorted JSON with Python's default separators.
    expected = (json.dumps(native_map, sort_keys=True) + "\n").encode()
    require(hashlib.sha256(expected).hexdigest() == command["stdout_sha256"],
            "Identity probe stdout differs from the exact checkout's full source map")


def checked_reach(receipt, source, expected_map, download_sha=None):
    """Independently check the public receipt against the exact native sources."""
    if expected_map is None:
        require(REACH_ENTRYPOINT not in source["files"] and "omega_reach_native_source" not in source
                and "paid_reach" not in receipt, "Unexpected paid-reach evidence or partial archive")
        return None
    nested = receipt.get("paid_reach")
    require(isinstance(nested, dict), "Nested paid-reach engineering receipt missing")
    require(source.get("omega_reach_native_source") == expected_map
            and all(source["files"].get(path) == sha for path, sha in expected_map.items()),
            "Paid-reach full native source map differs from the published checkout or archive")
    map_hash = hashlib.sha256(json.dumps(expected_map, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    require(nested["schema"] == "omega/packaged-paid-reach-qualification/v1"
            and nested["native_source_sha256"] == map_hash and nested["primary"] is False
            and nested["arm"] == "pilot" and nested["scenario"] == "central", "Paid-reach identity or account")
    require(all(nested[name] == receipt[name] for name in ("source_commit", "source_sha256", "source_archive_sha256"))
            and nested["actual_release_download"] is (download_sha is not None),
            "Paid-reach source, archive or download status")
    if download_sha is None:
        require("download_receipt_sha256" not in nested, "Clean receipt claimed a release download")
    else:
        require(nested["download_receipt_sha256"] == download_sha == receipt["download_receipt_sha256"],
                "Paid-reach binding to raw hosted RELEASE_DOWNLOAD.json")
    flags = ("accepted", "native_audit_accepted", "completed_resume_export_unchanged", "completed_resume_authority_unchanged")
    require(all(nested[name] is True for name in flags)
            and re.fullmatch(r"[0-9a-f]{64}", nested["native_export_sha256"]), "Paid-reach audit and resume invariants")
    rows = nested["commands"]
    require([row["stage"] for row in rows] == STAGES, "Four source/run/audit/resume commands required")
    python = receipt["commands"][0]["command"][0]
    cart_account = Path(receipt["commands"][1]["command"][-1])
    require(Path(python).is_absolute() and cart_account.is_absolute() and ".." not in cart_account.parts,
            "Absolute interpreter and cart account required")
    target = str(cart_account.parent / "paid-reach" / "engineering-account")
    module = "mechanism_harness.reach_native"
    probe = f"from {module} import source_identity; import json; print(json.dumps(source_identity(),sort_keys=True))"
    arguments = [
        [python, "-c", probe], [python, "-m", module, "run", target, "--arm", "pilot", "--scenario", "central"],
        [python, "-m", module, "audit", target], [python, "-m", module, "resume", target],
    ]
    for row, argv in zip(rows, arguments):
        require(set(row) == {"stage", "command", "returncode", "stdout_sha256", "stderr_sha256"}
                and row["command"] == argv and type(row["returncode"]) is int and row["returncode"] == 0
                and all(re.fullmatch(r"[0-9a-f]{64}", row[name]) for name in ("stdout_sha256", "stderr_sha256")),
                "Paid-reach command, account, return code or log digest")
    checked_probe(expected_map, rows[0])
    return {"actual_release_download": nested["actual_release_download"], "arm": nested["arm"],
            "scenario": nested["scenario"], "primary": nested["primary"], "native_source_files": len(expected_map),
            "native_source_sha256": map_hash, "native_export_sha256": nested["native_export_sha256"],
            "commands": STAGES, **{name: nested[name] for name in flags}}


def verify(args):
    root = Path(args.verifier_source).resolve()
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    require(head == args.commit, "Verifier checkout must match the published merge commit")
    subprocess.run(["git", "-C", str(root), "diff", "--quiet", "HEAD", "--"], check=True)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))
    from commercial.ledger import strict_json
    from scripts import release_connected014 as canonical
    from scripts.qualify_omega_release import validate_receipt
    from mechanism_harness.cart_native import source_identity as cart_identity

    provider = strict_json(Path(args.provider).read_bytes())
    tag, release, run, job = (provider[name] for name in ("tag", "release", "run", "job"))
    commit = canonical.commit(args.commit)
    release_tag = canonical.tag(commit)
    expected_url = f"https://github.com/{REPO}/releases/tag/{release_tag}"
    require(tag["ref"] == f"refs/tags/{release_tag}" and tag["object"]["type"] == "commit"
            and tag["object"]["sha"] == commit, "Published tag to commit")
    require(release["tag_name"] == release_tag and release["html_url"].lower() == expected_url.lower()
            and release["draft"] is False and release.get("published_at"), "Published release")
    require(run["repository"]["full_name"].lower() == REPO.lower()
            and run["head_sha"] == commit and run["head_branch"] == "main"
            and run["event"] == "push" and run["path"] == ".github/workflows/connected014-release.yml"
            and run["status"] == "completed" and run["conclusion"] == "success", "Main release workflow")
    require(job["run_id"] == run["id"] and job["name"] == "operate-published-release"
            and job["head_sha"] == commit and job["run_attempt"] == run["run_attempt"]
            and job["status"] == "completed" and job["conclusion"] == "success", "Released operation job")
    steps = {s["name"]: s["conclusion"] for s in job["steps"]}
    required_steps = (
        "Download the actual released bytes",
        "Run, resume and audit the actual downloaded implementation and evidence",
        "Operate V4 from the actual downloaded release source",
        "Attach compact V4 receipt to existing downloaded-operation evidence",
        "Retain successful downloaded operation",
    )
    require(all(steps.get(name) == "success" for name in required_steps), "Released operation steps")

    checked_artifact(provider["gate_artifact"], args.gate_zip, run, "connected014-publication-gate")
    checked_artifact(provider["operation_artifact"], args.operation_zip, run, "connected014-published-operation")
    assets = {item["name"]: item for item in release["assets"]}
    require(set(assets) == BASE_ASSETS | {"RELEASE_GATE.json"}
            and len(assets) == len(release["assets"]) and all(
        item["state"] == "uploaded" and re.fullmatch(r"sha256:[0-9a-f]{64}", item["digest"])
        for item in assets.values()), "Release asset names or provider digests")
    digests = {name: item["digest"].removeprefix("sha256:") for name, item in assets.items()}

    with ZipFile(args.gate_zip) as gate:
        names = canonical.checked_members(gate)
        require(set(names) == set(assets), "Publication gate artifact asset set")
        for name in names:
            require(gate.getinfo(name).file_size == assets[name]["size"], "Published asset size")
            with gate.open(name) as stream:
                require(hashlib.file_digest(stream, "sha256").hexdigest() == digests[name],
                        "Published asset digest for " + name)
        manifest = strict_json(gate.read("RELEASE_MANIFEST.json"))
        require(manifest["schema"] == "agi-alpha/connected014-release/v1" and manifest["source_commit"] == commit
                and manifest["tag"] == release_tag and manifest["files"] == {
                    name: sha for name, sha in digests.items() if name not in {"RELEASE_MANIFEST.json", "SHA256SUMS.txt"}},
                "Sealed release asset manifest")
        sums = [digests[name] + "  " + name for name in sorted(set(digests) - {"SHA256SUMS.txt"})]
        require(gate.read("SHA256SUMS.txt").decode().splitlines() == sums, "Sealed release checksums")
        gate_receipt = strict_json(gate.read("RELEASE_GATE.json"))
        require(gate_receipt["source_commit"] == commit and gate_receipt["branch"] == "main"
                and gate_receipt["event"] == "push" and int(gate_receipt["own_run_id"]) == run["id"],
                "Publication gate source")
        gates = gate_receipt["required_workflows"]
        applicability = gate_receipt["applicability"]
        expected_gates = canonical.applicable_workflows(applicability["changed_paths"], gates,
                                                         applicability["conservative_all_conditionals"])
        expected_gates.add("omega-economy-v4.yml")
        require(set(gates) == expected_gates and all(
            row["head_sha"] == commit and row["head_branch"] == "main" and row["event"] == "push"
            and row["conclusion"] == "success" and row["path"] == ".github/workflows/" + key
            for key, row in gates.items()), "Main qualification gates")
        source = canonical.archive_manifest(io.BytesIO(gate.read("connected014-source.zip")))
        for name, expected_hash in source["files"].items():
            member = root / name
            require(member.is_file() and not any(p.is_symlink() for p in (member, *member.parents))
                    and file_hash(member) == expected_hash, "Archive member differs from merge checkout " + name)
        source_sha = source["executing_source"]["sha256"]
        require(manifest["source_sha256"] == source_sha, "Release manifest source digest")
        archive_sha = digests["connected014-source.zip"]
        cart_map = cart_identity()
        require(source["omega_v4_native_source"] == cart_map, "V4 full native source map differs from merge checkout")
        require((root / REACH_ENTRYPOINT).is_file() == (REACH_ENTRYPOINT in source["files"]),
                "Archive and published checkout disagree about presence of paid reach")
        reach_map = None
        if REACH_ENTRYPOINT in source["files"]:
            from mechanism_harness.reach_native import source_identity as reach_identity
            reach_map = reach_identity()
        clean_v4 = strict_json(gate.read("OMEGA_V4_QUALIFICATION.json"))
        validate_receipt(clean_v4, source, archive_sha, commit)
        require(clean_v4["actual_release_download"] is False, "Clean qualification scope")
        checked_probe(cart_map, clean_v4["commands"][0])
        checked_reach(clean_v4, source, reach_map)

    with ZipFile(args.operation_zip) as operated:
        names = canonical.checked_members(operated)
        download_name = "RELEASE_DOWNLOAD.json"
        run_name = "downloaded-release-operation/DOWNLOADED_RELEASE_RUN.json"
        keyfree_name = "downloaded-release-operation/downloaded-operation-keyfree.zip"
        require(set(names) == {download_name, run_name, keyfree_name}, "Downloaded operation artifact set")
        raw_download = operated.read(download_name)
        download = strict_json(raw_download)
        require(download["schema"] == "agi-alpha/connected014-actual-release-download/v1"
                and download["actual_release_download"] is True and download["files"] == digests
                and download["source_commit"] == commit and download["source_sha256"] == source_sha
                and download["tag"] == release_tag and download["release_url"] == release["html_url"],
                "Hosted release download receipt")
        raw_operation = operated.read(run_name)
        operation = strict_json(raw_operation)
        require(operation["schema"] == "agi-alpha/connected014-downloaded-release-operation/v1"
                and operation["accepted"] is True and operation["actual_release_download"] is True
                and operation["source_commit"] == commit and operation["tag"] == release_tag
                and operation["source_sha256"] == source_sha and operation["completed_resume_financially_unchanged"] is True,
                "Hosted canonical operation")
        for name in ("native_and_operating_audit", "downloaded_operation_public_audit", "released_public_audit"):
            require(operation[name]["accepted"] is True, "Canonical audit " + name)
        with operated.open(keyfree_name) as stream:
            require(hashlib.file_digest(stream, "sha256").hexdigest() == operation["downloaded_operation_package"]["sha256"],
                    "Key-free operation package")
        v4 = operation["omega_v4_engineering_qualification"]
        validate_receipt(v4, source, archive_sha, commit)
        download_sha = hashlib.sha256(raw_download).hexdigest()
        require(v4["actual_release_download"] is True and v4["download_receipt_sha256"] == download_sha,
                "V4 actual release download binding")
        checked_probe(cart_map, v4["commands"][0])
        paid_reach = checked_reach(v4, source, reach_map, download_sha)
        return {"verified": True, "scope": "Hosted released-byte engineering operation",
                "source_commit": commit, "tag": release_tag, "release_url": release["html_url"],
                "run_id": run["id"], "run_attempt": run["run_attempt"], "job_id": job["id"],
                "qualification_asset_count": len(BASE_ASSETS), "asset_count_after_publication_gate": len(assets),
                "source_archive_sha256": archive_sha, "source_sha256": source_sha,
                "source_files_compared_to_merge_checkout": len(source["files"]),
                "release_download_receipt_sha256": download_sha,
                "downloaded_operation_receipt_sha256": hashlib.sha256(raw_operation).hexdigest(),
                "public_gate_artifact_sha256": provider["gate_artifact"]["digest"],
                "public_operation_artifact_sha256": provider["operation_artifact"]["digest"],
                "v4_actual_release_download": v4["actual_release_download"],
                "v4_native_source_files": len(v4["native_source"]), "v4_native_source_sha256": v4["native_source_sha256"],
                "v4_native_export_sha256": v4["native_export_sha256"], "v4_commands": [r["stage"] for r in v4["commands"]],
                "v4_primary": v4["primary"], "v4_actual_revenue_usd": v4["actual_revenue_usd"],
                "paid_reach": paid_reach}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("commit", "provider", "gate-zip", "operation-zip", "verifier-source"):
        parser.add_argument("--" + option, required=True)
    print(json.dumps(verify(parser.parse_args()), sort_keys=True, indent=2))
