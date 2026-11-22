"""Recorded document-only repair of the frozen late builder's missing xcolor.

This changes one LaTeX dependency declaration, not scientific text, code or data.
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


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument("--directory",required=True,type=Path);a=p.parse_args();out=a.directory.resolve()
    resource.setrlimit(resource.RLIMIT_CPU,(575,575));resource.setrlimit(resource.RLIMIT_AS,(2147483648,2147483648))
    start=time.monotonic();manifest=json.loads((out/"SOURCE_SHA256.json").read_text())
    source=out/"AGI_ALPHA_Late_008.tex";before=source.read_bytes();text=before.decode()
    needle=r"\usepackage[breaklinks=true,colorlinks=true,urlcolor=blue!55!black,linkcolor=black]{hyperref}"
    if text.count(needle)!=1 or r"\usepackage{xcolor}" in text:raise ValueError("Expected exact unpatched dependency declaration")
    failed_log=(out/"AGI_ALPHA_Late_008.log").read_text()
    if "Undefined color `blue!55!black'" not in failed_log:raise ValueError("Expected preserved xcolor failure")
    archive=out/"typesetting_original";archive.mkdir(exist_ok=False)
    (archive/source.name).write_bytes(before)
    (archive/"AGI_ALPHA_Late_008.log.txt").write_text(failed_log)
    (archive/"BUILD_PASS_1.log.txt").write_bytes((out/"BUILD_PASS_1.log").read_bytes())
    after=text.replace(needle,r"\usepackage{xcolor}"+"\n"+needle).encode();source.write_bytes(after)
    patch="".join(difflib.unified_diff(text.splitlines(keepends=True),after.decode().splitlines(keepends=True),fromfile="source-generated.tex",tofile="dependency-repaired.tex"))
    (out/"TYPESETTING_PATCH.diff").write_text(patch)
    command=["pdflatex","-interaction=nonstopmode","-halt-on-error","-output-directory",str(out),str(source)]
    for i in range(2):
        r=subprocess.run(command,cwd=out,capture_output=True);(out/("TYPESETTING_BUILD_"+str(i+1)+".log")).write_bytes(r.stdout+b"\n"+r.stderr)
        if r.returncode:raise RuntimeError("Typesetting dependency rebuild failed")
    own,child=resource.getrusage(resource.RUSAGE_SELF),resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt={"operation":"LATE_OUTPUT_ONLY_TYPESETTING_DEPENDENCY_REPAIR","source_ref":manifest["source_ref"],"source_inputs":manifest["consumed_files"],"snapshot_sha256":manifest["snapshot_sha256"],"original_generated_tex_sha256":sha(before),"repaired_tex_sha256":sha(after),"pdf_sha256":sha((out/"AGI_ALPHA_Late_008.pdf").read_bytes()),"script_sha256":sha(Path(__file__).read_bytes()),"patch_sha256":sha((out/"TYPESETTING_PATCH.diff").read_bytes()),"scientific_words_numbers_inputs_builder_registry_unchanged":True,"reason":"Frozen builder requests mixed xcolor link color but omits xcolor package; add exactly one package declaration.","failure_preserved":True,"initial_failed_build_CPU_seconds":None,"initial_failed_build_CPU_unknown_is_not_zero":True,"cpu_seconds_self_plus_waited_children":own.ru_utime+own.ru_stime+child.ru_utime+child.ru_stime,"wall_seconds":time.monotonic()-start,"peak_self_rss_kib":own.ru_maxrss,"peak_child_rss_kib":child.ru_maxrss,"created_utc":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),"scope":"Explicit document-only derivative. No numerical experiment, source edit, physical or commercial qualification; original600CPU paper reservation unchanged.","complete_monetary_cost":"UNKNOWN"}
    (out/"TYPESETTING_REPAIR.json").write_text(json.dumps(receipt,indent=2)+"\n");print(json.dumps(receipt))


if __name__=="__main__":main()
