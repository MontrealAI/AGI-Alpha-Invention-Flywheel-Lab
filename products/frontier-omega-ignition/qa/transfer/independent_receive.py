"""Independently exercise the accepted packages on the remaining public receipt sources."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile


PRODUCT = Path(__file__).resolve().parents[2]
SUPPLEMENTAL = {
    "mwaskom__seaborn": "825cb57cf3ea905fc1efe81acd7c9e215cc7fdc477fca351c49192c87a63b95e",
    "psf__requests": "f4ff7babffdda9a9aa9123d942ac68bcc05cdc9123015d6885bedfedfd7efbdc",
    "pydata__xarray": "aa724ed0ae813700b52dc7da78d15be38b7770b6cb9e861fcf3c587fa77e946b",
    "pylint-dev__pylint": "6d0a11f9c201a1c7e96bb230acb0498dca18d4242f892f8e330d7895b5042069",
    "pytest-dev__pytest": "13ce613974b54fa64b658236a5c61449d73c17ec3f1066d8f6aeb99f08411cf5",
    "scikit-learn__scikit-learn": "ec4cae42c10631cf3050fbbda619256996a25f09241bccb20d862778cc3e2688",
    "sympy__sympy": "a4c3518fe2ebfa1b2f6a1f83f9d000819fd5ea0ed695d7a591a2378b674a6f6a",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def measure(package, trusted):
    manifest = package / "producer.json"
    check(digest(manifest) == trusted, "Wrong producer manifest")
    receipt = json.loads(manifest.read_bytes())
    sources = PRODUCT / "action_study" / "qualification_choice" / "sources"
    check(set(SUPPLEMENTAL).isdisjoint(set(receipt["heldout_git_blobs"]) | {"django__django"}),
          "Supplemental receiver requires separate data from the training and original holdouts")
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        for name in ("migration", "integrity"):
            archive = package / f"{name}.zip"
            check(digest(archive) == receipt[name]["package_sha256"], "Wrong executable archive")
            with ZipFile(archive) as bundle:
                bundle.extractall(work / name)
        for name, expected_digest in sorted(SUPPLEMENTAL.items()):
            source = sources / f"{name}.json"
            check(digest(source) == expected_digest, f"Changed supplemental data for {name}")
            data = json.loads(source.read_bytes())
            rows = [dict(zip(data["row_fields"], r, strict=True)) for r in data["rows"]]
            inputs = b"".join(json.dumps(r).encode() + b"\n" for r in rows)
            reference = [{"task": r["id"], "trace_bytes": int(r["B_content_range"].partition("/")[2]),
                          "observed": r["B_retrieved_utc"]} for r in rows]
            jq = '{task:.id,trace_bytes:(.B_content_range|split("/")|last|tonumber),observed:.B_retrieved_utc}'
            for command in ([sys.executable, "-IB", str(work / "migration/run.py"), "migrate-jsonl"],
                            ["jq", "-c", jq]):
                proc = subprocess.run(command, input=inputs, capture_output=True, check=True)
                check([json.loads(row) for row in proc.stdout.splitlines()] == reference,
                      f"Incorrect output for {source.name}")
            results.append({"source": source.stem, "rows": len(rows), "sha256": expected_digest})
        inbox = work / "synthetic-handoff"
        shutil.copytree(package / "queue", inbox)
        names = sorted(p.name for p in inbox.iterdir())
        (inbox / names[0]).unlink()
        (inbox / names[1]).write_bytes(b"")
        (inbox / "retry.txt").write_text("Synthetic later delivery")
        proc = subprocess.run([sys.executable, "-IB", str(work / "integrity/run.py"), "audit-directory", str(inbox)],
                              capture_output=True)
        expected = {"ok": False, "missing": names[:1], "changed": names[1:2],
                    "unexpected": ["retry.txt"], "matched": names[2:]}
        check(proc.returncode == 1 and json.loads(proc.stdout) == expected, "Combined receipt mismatch")
    return {"producer_sha256": trusted, "additional_sources": results,
            "rows_correct_for_candidate_jq_and_reference": sum(item["rows"] for item in results),
            "combined_missing_changed_unexpected": expected}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.package, args.manifest_sha256), indent=2))
