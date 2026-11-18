"""Independently check released CSVs against printed TeX or the control XHTML."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET

HERE=Path(__file__).resolve().parent
TEX=HERE.parents[2]/"docs/research/enterprise-011/enterprise-011.tex"
TEX_ID="3e763727cbaf19013255ea69e249825c798dc29bb6d1d6da1f7d4312c97a8961"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def independent(key):
    if key=="publication":
        if sha(TEX)!=TEX_ID: raise ValueError("Different printed-table source")
        body=TEX.read_text().split(r"\toprule ",1)[1].split(r"\bottomrule",1)[0]
        text=body.replace(r"\midrule","").replace(r"\%","%").replace(r"\$","$")
        return [[cell.strip() for cell in line.split("&")] for line in text.split(r"\\") if line.strip()],[]
    # The two grouped XHTML bodies are expanded by their declared authored structure.
    raw=(HERE/"calibration.html").read_text()
    doc=ET.fromstring("<body>"+raw.split("<body>",1)[1].split("</body>",1)[0]+"</body>")
    def cells(r): return ["".join(c.itertext()).strip() for c in r]
    head=cells(doc.find(".//thead/tr"))
    matrix=[head]
    for row in doc.findall(".//tbody/tr"):
        values=cells(row)
        if len(values)==len(head):
            span=row[0].attrib.get("rowspan")
            if span!="2": raise ValueError("Unregistered authored control span")
            group=values[0]
        elif len(values)==len(head)-1:
            values.insert(0,group)
        else: raise ValueError("Malformed authored control row")
        matrix.append(values)
    note=doc.find(".//p[@id='table-note']").text
    return matrix,[note,note]


def audit(outdir):
    observed=json.loads((outdir/"RESULTS.json").read_text())
    if set(observed["tables"])!={"publication","calibration"}:
        raise ValueError("Missing registered table")
    ids=json.loads((HERE/"inputs.json").read_text())
    verified={}
    for key,arms in observed["tables"].items():
        if set(arms)!={"direct","native","ocr","model"}: raise ValueError("Incomplete arms")
        gold,notes=independent(key)
        verified[key]={}
        for arm,result in arms.items():
            target=outdir/f"{key}-{arm}"
            if result["accepted"]:
                with (target/"table.csv").open(newline="",encoding="utf-8") as f:
                    actual=list(csv.reader(f))
                metadata=json.loads((target/"provenance.json").read_text())
                if (actual!=gold or metadata["qualifying_notes"]!=notes
                    or result["csv_sha256"]!=sha(target/"table.csv") or metadata["csv_sha256"]!=result["csv_sha256"]
                    or metadata["source_pdf_sha256"]!=ids[key]["pdf_sha256"]
                    or metadata["source_html_sha256"]!=ids[key]["html_sha256"]
                    or metadata["physical_pages"]!=[p["page"] for p in ids[key]["pages"]]):
                    raise ValueError(f"Independent receiver rejected {key}/{arm}")
                verified[key][arm]={"independently_matched_cells":sum(map(len,gold)),"qualifying_notes":len(notes)}
            else:
                if target.exists(): raise ValueError("Unqualified delivery exists")
                verified[key][arm]={"withheld":True}
    return verified


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("output",type=Path)
    print(json.dumps(audit(p.parse_args().output),indent=2))
