"""Run the pinned model's official CPU reader once per frozen ND02 image."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile
import time

from prepare import HERE, SPEC, file_sha, prepare

DRIVER_SHA="fc3568bb3e9cf48dbcb8ce0cd4e25ee7360cec9fa9da331141497ecee5dcea41"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path, help="pinned model environment interpreter")
    parser.add_argument("--output", required=True, type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    start=time.monotonic()
    pin=json.loads((HERE.parent/"table_desk/parser-model.json").read_text())
    manifest={**pin["sha256"],"run_transformers_inference.py":DRIVER_SHA}
    receipt={"repository":pin["repository"],"revision":pin["revision"],
             "model_sha256":manifest["model.safetensors"],"driver_sha256":DRIVER_SHA,
             "registration_sha256":file_sha(SPEC),"device":"cpu","dtype":"float32",
             "threads":4,"max_new_tokens":2048,"greedy":True,"calls":[]}
    with tempfile.TemporaryDirectory() as td:
        tmp=Path(td)
        prepare(tmp/"crops")
        model=tmp/"nd02_model"
        model.mkdir()
        for name,expected in manifest.items():
            source=(args.model/name).resolve(strict=True)
            with source.open("rb") as stream:
                if hashlib.file_digest(stream,"sha256").hexdigest()!=expected:
                    raise ValueError(f"Unregistered provider file: {name}")
            (model/name).symlink_to(source)
        env={**os.environ,"OMP_NUM_THREADS":"4","MKL_NUM_THREADS":"4","HF_HUB_OFFLINE":"1",
             "HF_HUB_DISABLE_TELEMETRY":"1","TOKENIZERS_PARALLELISM":"false"}
        deps=("torch","torchvision","transformers","timm","pillow","tokenizers")
        probe="import json,importlib.metadata as m;print(json.dumps({n:m.version(n) for n in "+repr(deps)+"}))"
        receipt["versions"]=json.loads(subprocess.check_output([args.python,"-c",probe],text=True,env=env))
        for image in sorted((tmp/"crops").glob("page-*.png")):
            mark=time.monotonic()
            prev=resource.getrusage(resource.RUSAGE_CHILDREN)
            run=subprocess.run([args.python,"-I",model/"run_transformers_inference.py","--model",model,
                "--image",image,"--device","cpu","--max-new-tokens","2048","--local-files-only"],
                capture_output=True,env=env)
            after=resource.getrusage(resource.RUSAGE_CHILDREN)
            raw=args.output/(image.stem+".txt")
            raw.write_bytes(run.stdout)
            item={"crop":image.name,"png_sha256":file_sha(image),"raw_sha256":file_sha(raw),
                 "exit":run.returncode, "wall_seconds":round(time.monotonic()-mark,4),
                 "cpu_seconds":round(after.ru_utime+after.ru_stime-prev.ru_utime-prev.ru_stime,4)}
            if run.returncode: item["failure"]=run.stderr.decode(errors="replace")[-1400:]
            receipt["calls"].append(item)
            receipt["wall_seconds"]=round(time.monotonic()-start,4)
            receipt["max_child_rss_kib_linux"]=after.ru_maxrss
            (args.output/"observation.json").write_text(json.dumps(receipt,indent=2)+"\n")


if __name__=="__main__":
    main()
