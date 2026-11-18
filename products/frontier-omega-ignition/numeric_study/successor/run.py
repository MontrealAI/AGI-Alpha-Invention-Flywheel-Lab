"""Matched comparison of a retained versus freshly regenerated observation."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
sys.path.insert(0,str(STUDY))
from audit import independent
from observe_model import DRIVER_SHA
from prepare import file_sha

DECODER_SHA="9e8d696802b4978bd6fc38dbe9c894dad0754f1274d0f3049b43ef38f961c629"


def write(path,data):
    path.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")


def timed(command,log,env=None):
    start=time.monotonic()
    with log.open("wb") as stream:
        proc=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,env=env)
        _,status,usage=os.wait4(proc.pid,0)
        proc.returncode=os.waitstatus_to_exitcode(status)
    return {"exit":proc.returncode,"wall_seconds":round(time.monotonic()-start,6),
            "cpu_seconds":round(usage.ru_stime+usage.ru_utime,6),
            "largest_process_rss_kib_linux":usage.ru_maxrss}


def fresh(crops,source,python,out):
    manifest=json.loads((STUDY.parent/"table_desk/parser-model.json").read_text())
    expected={**manifest["sha256"],"run_transformers_inference.py":DRIVER_SHA}
    receipt={"repository":manifest["repository"],"revision":manifest["revision"],
            "model_sha256":expected["model.safetensors"],"driver_sha256":DRIVER_SHA,
            "registration_sha256":file_sha(STUDY/"inputs.json"),"device":"cpu","dtype":"float32",
            "threads":4,"max_new_tokens":2048,"greedy":True,"calls":[]}
    out.mkdir()
    env={**os.environ,"OMP_NUM_THREADS":"4","MKL_NUM_THREADS":"4","HF_HUB_OFFLINE":"1",
         "HF_HUB_DISABLE_TELEMETRY":"1","TOKENIZERS_PARALLELISM":"false"}
    deps=("torch","torchvision","transformers","timm","pillow","tokenizers")
    probe="import json,importlib.metadata as m;print(json.dumps({n:m.version(n) for n in "+repr(deps)+"}))"
    receipt["versions"]=json.loads(subprocess.check_output([python,"-c",probe],text=True,env=env))
    with tempfile.TemporaryDirectory() as td:
        model=Path(td)/"nd02_model";model.mkdir()
        for name,digest in expected.items():
            src=(source/name).resolve(strict=True)
            with src.open("rb") as f:
                if hashlib.file_digest(f,"sha256").hexdigest()!=digest:
                    raise ValueError(f"Wrong model or driver file: {name}")
            (model/name).symlink_to(src)
        for pg in json.loads((STUDY/"inputs.json").read_text())["calibration"]["pages"]:
            image=crops/f'page-{pg["crop"]}.png'
            if file_sha(image)!=pg["png_sha256"]:raise ValueError("Changed registered crop")
            raw=out/image.with_suffix(".txt").name
            start=time.monotonic()
            # Preserve stdout as raw generation, separately from provider logs.
            err=out/(image.stem+".log")
            with raw.open("wb") as output,err.open("wb") as errors:
                proc=subprocess.Popen([python,"-I",model/"run_transformers_inference.py","--model",model,
                    "--image",image,"--device","cpu","--max-new-tokens","2048","--local-files-only"],
                    stdout=output,stderr=errors,env=env)
                _,status,usage=os.wait4(proc.pid,0);proc.returncode=os.waitstatus_to_exitcode(status)
            receipt["calls"].append({"crop":image.name,"png_sha256":file_sha(image),
                "raw_sha256":file_sha(raw),"exit":proc.returncode,
                "wall_seconds":round(time.monotonic()-start,6),"cpu_seconds":round(usage.ru_stime+usage.ru_utime,6),
                "largest_process_rss_kib_linux":usage.ru_maxrss})
            write(out/"observation.json",receipt)


def delivery(args):
    args.output.mkdir()
    if file_sha(STUDY/"recover.py")!=DECODER_SHA:raise ValueError("Different decoder")
    archive=STUDY/"model_observation" if args.arm=="reuse" else args.output/"fresh"
    if args.arm=="fresh":fresh(args.crops,args.model,args.python,archive)
    observation=json.loads((archive/"observation.json").read_text())
    pages=json.loads((STUDY/"inputs.json").read_text())["calibration"]["pages"]
    for p in pages:
        if file_sha(args.crops/f'page-{p["crop"]}.png')!=p["png_sha256"]:raise ValueError("Source differs")
    meta=timed([sys.executable,"-B",STUDY/"recover.py","--observation",archive,
                "--output",args.output/"delivery"],args.output/"decoder.log")
    out=args.output/"delivery";decision=json.loads((out/"RECOVERY.json").read_text())
    accepted=False
    if meta["exit"]==0 and decision["accepted"]:
        with (out/"table.csv").open(newline="",encoding="utf-8") as f:
            actual=list(csv.reader(f))
        wanted,notes=independent("calibration")
        accepted=(actual==wanted and decision["observed_footnotes"]==notes
                  and file_sha(out/"table.csv")==decision["csv_sha256"])
    if not accepted and (out/"table.csv").exists():raise ValueError("Unsafe delivery")
    selected=[c for c in observation["calls"] if c["crop"] in {f'page-{p["crop"]}.png' for p in pages}]
    result={"accepted":accepted,"csv_sha256":decision.get("csv_sha256"),"notes":decision.get("observed_footnotes"),
            "correct_cells":decision.get("correct_cells"),"additional_model_calls":0 if args.arm=="reuse" else len(selected),
            "source_raw_sha256":[c["raw_sha256"] for c in selected],"decoder":meta}
    write(args.output/"arm.json",result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--model",type=Path)
    parser.add_argument("--python",type=Path)
    parser.add_argument("--arm",choices=("reuse","fresh"))
    parser.add_argument("--crops",type=Path)
    args=parser.parse_args()
    if args.arm:return delivery(args)
    if not args.model or not args.python:parser.error("--model and --python are required for fresh inference")
    args.output.mkdir(parents=True,exist_ok=False)
    crops=args.output/"crops"
    # Both counterfactuals receive the same registered crop acquisition.
    prep=timed([sys.executable,"-B",STUDY/"prepare.py",crops],args.output/"preparation.log")
    if prep["exit"]:raise ValueError("Shared source preparation failed")
    result={"study":"ND02-S","protocol_sha256":file_sha(HERE/"PROTOCOL.md"),
            "runner_sha256":file_sha(Path(__file__)),"decoder_sha256":DECODER_SHA,
            "shared_preparation":prep,"arms":{}}
    for arm in ("reuse","fresh"):
        out=args.output/arm
        use=timed([sys.executable,"-B",Path(__file__),"--arm",arm,"--crops",crops,"--model",args.model,
                   "--python",args.python,"--output",out],args.output/(arm+".log"))
        arm_result=json.loads((out/"arm.json").read_text()) if (out/"arm.json").exists() else {"accepted":False}
        arm_result["timed_delivery"]=use
        arm_result["wall_with_shared_preparation"]=round(use["wall_seconds"]+prep["wall_seconds"],6)
        result["arms"][arm]=arm_result
    r,f=result["arms"].values()
    same=(r["accepted"] and f["accepted"] and r["csv_sha256"]==f["csv_sha256"] and r["notes"]==f["notes"])
    result["equal_accepted_delivery"]=same
    result["byte_identical_generations"]=r.get("source_raw_sha256")==f.get("source_raw_sha256")
    result["observed_marginal_wall_saving_seconds"]=round(f["timed_delivery"]["wall_seconds"]-r["timed_delivery"]["wall_seconds"],6) if same else None
    write(args.output/"COMPARISON.json",result)
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
