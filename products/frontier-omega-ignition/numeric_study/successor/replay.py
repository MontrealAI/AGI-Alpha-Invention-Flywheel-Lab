"""Independently check the two archived ND02-S deliveries without new inference."""
import argparse
import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
sys.path.insert(0,str(STUDY))
from audit import independent
from prepare import file_sha


def replay(output):
    output.mkdir(parents=True,exist_ok=False)
    result=json.loads((HERE/"COMPARISON.json").read_text())
    spec=json.loads((STUDY/"inputs.json").read_text())["calibration"]
    for path,expected in ((HERE/"PROTOCOL.md",result["protocol_sha256"]),
                          (HERE/"run.py",result["runner_sha256"]),(STUDY/"recover.py",result["decoder_sha256"]),
                          (STUDY/"calibration.html",spec["html_sha256"])):
        if file_sha(path)!=expected:raise ValueError(f"Changed source: {path.name}")
    old=STUDY/"model_observation"
    expected,notes=independent("calibration")
    with tempfile.TemporaryDirectory() as tmp:
        fresh=Path(tmp)
        shutil.copy(HERE/"fresh-observation.json",fresh/"observation.json")
        observation=json.loads((fresh/"observation.json").read_text())
        if len(observation["calls"])!=2:raise ValueError("Unexpected inference count")
        for i,(page,call) in enumerate(zip(spec["pages"],observation["calls"])):
            name=f'page-{page["crop"]}.txt'
            source=HERE/("fresh-"+name)
            if not source.exists():source=old/name
            if (call["png_sha256"]!=page["png_sha256"] or call["raw_sha256"]!=file_sha(source)
                or call["raw_sha256"]!=result["arms"]["fresh"]["source_raw_sha256"][i]):
                raise ValueError("Different observed generation")
            shutil.copy(source,fresh/name)
        for name,archive,count in (("reuse",old,0),("fresh",fresh,2)):
            dest=output/name
            arm=result["arms"][name]
            if arm["additional_model_calls"]!=count: raise ValueError("Mismatched arm")
            delivery=subprocess.run([sys.executable,"-B",STUDY/"recover.py","--observation",archive,
                                     "--output",dest],check=False)
            if delivery.returncode!=0:
                if arm["accepted"] or (dest/"table.csv").exists():raise ValueError("Unreproducible rejection")
                continue
            with (dest/"table.csv").open(newline="",encoding="utf-8") as f:
                if list(csv.reader(f))!=expected:raise ValueError("Independent cell check failed")
            receipt=json.loads((dest/"RECOVERY.json").read_text())
            if (file_sha(dest/"table.csv")!=arm["csv_sha256"] or receipt["observed_footnotes"]!=notes
                    or not arm["accepted"] or receipt["source_pdf_sha256"]!=spec["pdf_sha256"]):
                raise ValueError("Source, delivered content or notes differ")
    print(json.dumps({k:a["accepted"] for k,a in result["arms"].items()}))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,required=True)
    replay(p.parse_args().output)
