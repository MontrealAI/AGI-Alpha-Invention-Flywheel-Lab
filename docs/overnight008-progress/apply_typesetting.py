"""Apply one recorded line-break-only repair to the generated LaTeX artifact.

The source-frozen paper builder, registry, facts and all experiment inputs are
unchanged. Re-run after a fresh exact-source build, not over a repaired artifact.
"""
import argparse
import datetime as dt
import difflib
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import time


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True, type=Path)
    args = parser.parse_args()
    out = args.directory.resolve()
    resource.setrlimit(resource.RLIMIT_CPU, (580, 580))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    start = time.monotonic()
    source = json.loads((out / "SOURCE_SHA256.json").read_text())
    tex_path = out / "AGI_ALPHA_Progress_008.tex"
    before = tex_path.read_bytes()
    target = r"FULL120\_MODEL\_OBSTRUCTION\_VERIFIED"
    replacement = r"FULL120\_\allowbreak{}MODEL\_\allowbreak{}OBSTRUCTION\_\allowbreak{}VERIFIED"
    text = before.decode()
    if text.count(target) != 1 or replacement in text:
        raise ValueError("Expected exactly one original status label; refusing repair")
    archive = out / "tmp" / "source_generated"
    archive.mkdir(parents=True, exist_ok=False)
    for suffix in ["tex", "pdf", "log"]:
        original = out / ("AGI_ALPHA_Progress_008." + suffix)
        (archive / original.name).write_bytes(original.read_bytes())
    after = text.replace(target, replacement).encode()
    tex_path.write_bytes(after)
    patch = "".join(difflib.unified_diff(text.splitlines(keepends=True), after.decode().splitlines(keepends=True), fromfile="source-generated.tex", tofile="line-break-repaired.tex"))
    (out / "TYPESETTING_PATCH.diff").write_text(patch)
    command = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(out), str(tex_path)]
    for i in range(2):
        result = subprocess.run(command, cwd=out, capture_output=True)
        (out / ("TYPESETTING_BUILD_" + str(i + 1) + ".log")).write_bytes(result.stdout + b"\n" + result.stderr)
        if result.returncode:
            raise RuntimeError("LATEX_TYPESETTING_REBUILD_FAILED")
    own = resource.getrusage(resource.RUSAGE_SELF)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {"operation":"OUTPUT_ONLY_TYPESETTING_REPAIR", "source_ref":source["source_ref"], "snapshot_sha256":source["snapshot_sha256"],
        "original_generated_tex_sha256":sha(before), "repaired_tex_sha256":sha(after),
        "original_generated_pdf_sha256":sha((archive / "AGI_ALPHA_Progress_008.pdf").read_bytes()),
        "repaired_pdf_sha256":sha((out / "AGI_ALPHA_Progress_008.pdf").read_bytes()),
        "repair_script_sha256":sha(Path(__file__).read_bytes()), "patch_sha256":sha((out / "TYPESETTING_PATCH.diff").read_bytes()),
        "reason":"One unbreakable status label overflowed its table cell by97.87025pt. Insert allowbreak commands after its three underscores.",
        "source_builder_and_registry_unchanged":True, "words_numbers_and_experiment_inputs_unchanged":True,
        "scope":"The final PDF/LaTeX are an explicitly recorded typesetting derivative of the exact-source build. HTML/Markdown/source manifest remain original builder outputs. This is not a new experiment.",
        "wall_seconds":time.monotonic()-start, "cpu_seconds_self_plus_waited_children":own.ru_utime+own.ru_stime+child.ru_utime+child.ru_stime,
        "peak_self_rss_kib":own.ru_maxrss,"peak_child_rss_kib":child.ru_maxrss,"created_utc":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "complete_monetary_cost":"UNKNOWN", "resource_scope":"Within remaining original600CPU paper reservation; no renewal."}
    (out / "TYPESETTING_REPAIR.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
