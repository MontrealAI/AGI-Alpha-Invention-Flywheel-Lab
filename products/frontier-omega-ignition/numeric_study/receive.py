"""Receive structured numeric tables, applying separately sourced references."""
import argparse
import csv
import json
from pathlib import Path
import re
import resource
import subprocess
import tempfile
import time

import fitz
from lxml import html
from PIL import Image
from prepare import HERE, RESEARCH, SPEC, file_sha, prepare


def clean(value):
    return " ".join(value.split())


def reference(key, spec):
    path=RESEARCH/"enterprise-011.html" if key=="publication" else HERE/"calibration.html"
    if file_sha(path)!=spec["html_sha256"]: raise ValueError("Reference has changed")
    doc=html.fromstring(path.read_bytes())
    table=doc.xpath("//table")[0]
    matrix=[]
    pending={}
    for row in table.xpath(".//tr"):
        cells=[]
        for cell in row.xpath("./td|./th"):
            while len(cells) in pending:
                cells.append(pending.pop(len(cells)))
            text=clean(cell.text_content())
            if cell.get("rowspan"):
                if cell.get("rowspan")!="2" or cell.get("colspan"):
                    raise ValueError("Unregistered source span")
                pending[len(cells)]=text
            cells.append(text)
        matrix.append(cells)
    if pending: raise ValueError("Unresolved rowspan")
    if key=="publication":
        required=["Regime","Passed / runs","Success","Mean complete-cost profit","Cash survival"]
        if matrix[0]!=required: raise ValueError("Unexpected source headings")
        matrix=[["Regime","Passed","Mean profit","Survival"]]+[
            [r[0].replace("_"," "),r[1],r[3],r[4]] for r in matrix[1:]]
        return matrix,[]
    return matrix,[clean(doc.get_element_by_id("table-note").text_content())]*len(spec["pages"])


def combine(key, pages):
    """Restore only the declared group at row 2; ambiguous geometry is refused."""
    joined=[]
    notes=[]
    for grid,note in pages:
        if not grid: raise ValueError("Missing table")
        if key=="calibration":
            if len(grid)!=3 or any(len(r)!=5 for r in grid):
                raise ValueError("Missing control rows, cells or repeat header")
            if not grid[1][0] or grid[2][0] not in ("",grid[1][0]):
                raise ValueError("Conflicting or missing two-row span anchor")
            grid[2][0]=grid[1][0]
            notes.append(note)
        if joined and grid[0]!=joined[0]: raise ValueError("Repeated header differs")
        joined.extend(grid[1:] if joined else grid)
    return joined,notes


def conventional(key, spec, pdf, crops, mode):
    pages=[]
    with fitz.open(pdf) as doc, tempfile.TemporaryDirectory() as td:
        tmp=Path(td)/"cell.png"
        for item in spec["pages"]:
            page=doc[item["page"]-1]
            with Image.open(crops/f'page-{item["crop"]}.png') as pic:
                def read(rect):
                    if mode=="native":
                        return clean(page.get_textbox(fitz.Rect(*rect)))
                    x,y=item["box"][:2]
                    crop=pic.crop(tuple((n-(x if i%2==0 else y))*4 for i,n in enumerate(rect)))
                    crop.save(tmp)
                    run=subprocess.run(["tesseract",str(tmp),"stdout","-l","eng","--psm","7"],
                                       capture_output=True,text=True,check=True)
                    return clean(run.stdout)
                rows=[[read((a,top,b,bottom)) for a,b in zip(item["cols"],item["cols"][1:])]
                      for top,bottom in zip(item["rows"],item["rows"][1:])]
                pages.append((rows,read(item["note"]) if "note" in item else None))
    return combine(key,pages)


TABULAR=re.compile(r"\\begin\{tabular\}\{[|clr ]+\}(.*?)\\end\{tabular\}",re.S)
WRAP=re.compile(r"\\(?:thead|textbf|textnormal|mathrm|text)\{([^{}]*)\}")
SPAN=re.compile(r"\\multirow\{2\}\{\*\}\{([^{}]*)\}")
TOKEN=re.compile(r"</?s>|<x_[0-9.]+>|<y_[0-9.]+>|<class_[A-Za-z_]+>|<predict_[A-Za-z_]+>|<output_markdown>")
IGNORE_RULE=re.compile(r"\\(?:toprule|midrule|bottomrule|hline)\b")


def tex_text(value):
    value=SPAN.sub(r"\1",value)
    value=WRAP.sub(r"\1",value)
    value=value.replace(r"\%","%").replace(r"\$","$").replace(r"\_","_")
    if any(c in value for c in r"\{}"): raise ValueError("Unrecognized cell markup")
    return clean(value)


def model_table(key,spec,archive):
    observation=json.loads((archive/"observation.json").read_text())
    pin=json.loads((HERE.parent/"table_desk/parser-model.json").read_text())
    if observation["model_sha256"]!=pin["sha256"]["model.safetensors"] or observation["revision"]!=pin["revision"]:
        raise ValueError("Unregistered model")
    if observation["registration_sha256"]!=file_sha(SPEC): raise ValueError("Different registration")
    pages=[]
    for page in spec["pages"]:
        name=f'page-{page["crop"]}'
        calls=[c for c in observation["calls"] if c["crop"]==name+".png"]
        if len(calls)!=1 or calls[0]["exit"]!=0 or calls[0]["png_sha256"]!=page["png_sha256"]:
            raise ValueError("Missing or mismatched model call")
        raw=archive/(name+".txt")
        if file_sha(raw)!=calls[0]["raw_sha256"]: raise ValueError("Model output identity changed")
        output=raw.read_text()
        hits=list(TABULAR.finditer(output))
        if len(hits)!=1: raise ValueError("Expected one plain tabular region")
        body=IGNORE_RULE.sub("",hits[0].group(1))
        grid=[[tex_text(cell) for cell in row.split("&")] for row in body.split(r"\\") if row.strip()]
        tail=clean(TOKEN.sub("",output[hits[0].end():]))
        pages.append((grid,tex_text(tail) if key=="calibration" else None))
    return combine(key,pages)


def compare(candidate,gold):
    rows,notes=candidate
    target,required=gold
    errors=[]
    correct=0
    for ri,row in enumerate(target):
        for ci,wanted in enumerate(row):
            got=rows[ri][ci] if ri<len(rows) and ci<len(rows[ri]) else None
            if got==wanted: correct+=1
            else: errors.append({"row":ri+1,"column":ci+1,"expected":wanted,"observed":got})
    shape=[len(row) for row in rows]==[len(row) for row in target]
    return {"accepted":shape and correct==sum(map(len,target)) and notes==required,
            "correct_cells":correct,"total_cells":sum(map(len,target)),
            "dimensions_match":shape,"footnotes_match":notes==required,"errors":errors,
            "observed_footnotes":notes}


def process(output,archive):
    output.mkdir(parents=True,exist_ok=False)
    spec=json.loads(SPEC.read_text())
    with tempfile.TemporaryDirectory() as td:
        crops=Path(td)/"crops"
        prepare(crops)
        report={"study":"ND02","inputs_sha256":file_sha(SPEC),"receiver_sha256":file_sha(Path(__file__)),
                "crop_preparer_sha256":file_sha(HERE/"prepare.py"),"model_observation_sha256":file_sha(archive/"observation.json"),
                "execution":{"pymupdf":fitz.VersionBind,"ocr":subprocess.check_output(["tesseract","--version"],text=True).splitlines()[0]},
                "scope":"Transcription of one simulated-outcome publication and one synthetic calibration table","tables":{}}
        for key,record in spec.items():
            gold=reference(key,record)
            table=report["tables"][key]={}
            for arm in ("direct","native","ocr","model"):
                before=time.monotonic()
                try:
                    if arm=="direct": data=reference(key,record)
                    elif arm=="model": data=model_table(key,record,archive)
                    else:
                        pdf=RESEARCH/"enterprise-011.pdf" if key=="publication" else crops/"calibration.pdf"
                        data=conventional(key,record,pdf,crops,arm)
                    result=compare(data,gold)
                    if result["accepted"]:
                        target=output/f"{key}-{arm}"
                        target.mkdir()
                        with (target/"table.csv").open("w",newline="",encoding="utf-8") as fh:
                            csv.writer(fh,lineterminator="\n").writerows(data[0])
                        result["csv_sha256"]=file_sha(target/"table.csv")
                        metadata={"source_pdf_sha256":record["pdf_sha256"],"source_html_sha256":record["html_sha256"],
                                  "physical_pages":[p["page"] for p in record["pages"]],
                                  "qualifying_notes":data[1],"csv_sha256":result["csv_sha256"]}
                        (target/"provenance.json").write_text(json.dumps(metadata,indent=2)+"\n")
                except (ValueError,subprocess.CalledProcessError) as exc:
                    result={"accepted":False,"reason":str(exc),"total_cells":sum(map(len,gold[0]))}
                result["receiver_wall_seconds"]=round(time.monotonic()-before,6)
                table[arm]=result
        (output/"RESULTS.json").write_text(json.dumps(report,indent=2)+"\n")
        return report


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-observation",type=Path,default=HERE/"model_observation")
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    verdict=process(args.output,args.model_observation)
    for table,arms in verdict["tables"].items():
        print(table,{k:v["accepted"] for k,v in arms.items()})
