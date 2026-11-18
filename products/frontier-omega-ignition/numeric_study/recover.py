"""Replay the observed synthetic span syntax under the separate ND02-R rule."""
import argparse
import csv
import json
from pathlib import Path

from audit import independent
from prepare import HERE,SPEC,file_sha
from receive import TABULAR,IGNORE_RULE,TOKEN,SPAN,combine,compare,tex_text


def decode(output):
    matches=list(TABULAR.finditer(output))
    if len(matches)!=1: raise ValueError("Expected one tabular region")
    region=matches[0]
    raw=[[c.strip() for c in r.split("&")] for r in IGNORE_RULE.sub("",region[1]).split(r"\\") if r.strip()]
    if len(raw)!=3 or any(len(r)!=5 for r in raw): raise ValueError("Unexpected registered grid")
    if not SPAN.fullmatch(raw[1][0]) or not SPAN.fullmatch(raw[1][0])[1].strip():
        raise ValueError("Missing explicit two-row span anchor")
    for rownum,row in enumerate(raw):
        for col,value in enumerate(row):
            if value==r"\mbox{}":
                if (rownum,col)!=(2,0): raise ValueError("Empty box outside declared covered slot")
                row[col]=""
    return [[tex_text(c) for c in row] for row in raw],tex_text(TOKEN.sub("",output[region.end():]))


def reconstruct(archive):
    obs=json.loads((archive/"observation.json").read_text())
    if obs["registration_sha256"]!=file_sha(SPEC): raise ValueError("Different observation registration")
    pin=json.loads((HERE.parent/"table_desk/parser-model.json").read_text())
    if (obs["revision"],obs["model_sha256"])!=(pin["revision"],pin["sha256"]["model.safetensors"]):
        raise ValueError("Different provider identity")
    parts=[]
    for p in json.loads(SPEC.read_text())["calibration"]["pages"]:
        name=f'page-{p["crop"]}'
        found=[c for c in obs["calls"] if c["crop"]==name+".png"]
        if len(found)!=1: raise ValueError("Missing or duplicate call")
        call=found[0]
        path=archive/(name+".txt")
        if (call["exit"]!=0 or call["png_sha256"]!=p["png_sha256"] or call["raw_sha256"]!=file_sha(path)):
            raise ValueError("Unexpected input or output identity")
        parts.append(decode(path.read_text()))
    return combine("calibration",parts)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--observation",type=Path,default=HERE/"model_observation")
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    result={"study":"ND02-R","receiver_sha256":file_sha(Path(__file__)),
            "original_results_sha256":file_sha(HERE/"RESULTS.json"),
            "protocol_sha256":file_sha(HERE/"RECOVERY_PROTOCOL.md"),"observation_sha256":file_sha(args.observation/"observation.json"),
            "additional_model_calls":0}
    try:
        values,notes=reconstruct(args.observation)
        result.update(compare((values,notes),independent("calibration")))
        if result["accepted"]:
            dest=args.output/"table.csv"
            with dest.open("w",encoding="utf-8",newline="") as stream:
                csv.writer(stream,lineterminator="\n").writerows(values)
            result["csv_sha256"]=file_sha(dest)
            result["source_pdf_sha256"]=json.loads(SPEC.read_text())["calibration"]["pdf_sha256"]
    except ValueError as exc:
        result.update(accepted=False,reason=str(exc))
    (args.output/"RECOVERY.json").write_text(json.dumps(result,indent=2)+"\n")
    if not result["accepted"]: raise SystemExit("Recovered table was withheld.")


if __name__=="__main__":main()
