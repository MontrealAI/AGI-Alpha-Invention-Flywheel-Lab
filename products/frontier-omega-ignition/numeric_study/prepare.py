"""Build registered synthetic print and render PNGs using the study renderer."""
import argparse
import hashlib
import json
from pathlib import Path
import fitz
from reportlab.pdfgen.canvas import Canvas

HERE = Path(__file__).resolve().parent
RESEARCH = HERE.parents[2] / "docs/research/enterprise-011"
SPEC = HERE / "inputs.json"


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calibration(path):
    # This rendering has its own data, geometry and line breaks. It never reads
    # the semantic ground truth used by the independent receiver.
    pages = (("Alpha", ("1", "-2.50", "+0.25", "4.00"), ("2", "+0.08", "-0.75", "4.00")),
             ("Beta", ("1", "-0.40", "+1.20", "3.50"), ("2", "+0.04", "-1.10", "3.50")))
    c = Canvas(str(path),pagesize=(420,190),invariant=1,pageCompression=0)
    c.setTitle("ND02 calibration control")
    for i, (name, first, second) in enumerate(pages,1):
        c.setFont("Helvetica",10)
        for x,y,text in [(20,167,"Instrument calibration"),(367,167,f"{i} / 2")]:
            c.drawString(x,y,text)
        cols = [20,101,159,245,325,401]
        for col in cols: c.line(col,67,col,145)
        for y in [145,119,67]: c.line(cols[0],y,cols[-1],y)
        c.line(cols[1],93,cols[-1],93)  # one spanning first-column cell
        c.setFont("Helvetica-Bold",10)
        for x,head in zip(cols,("Sensor","Run","Bias (mV)","Drift (%)","Limit* (mV)")):
            c.drawString(x+5,129,head)
        c.setFont("Helvetica",11)
        c.drawString(25,102,name)
        for y,row in [(103,first),(77,second)]:
            for x,value in zip(cols[1:],row): c.drawString(x+5,y,value)
        c.setFont("Helvetica",9);c.drawString(20,44,"* Limit applies only at 20 C.")
        c.showPage()
    c.save()


def prepare(output):
    spec=json.loads(SPEC.read_text())
    output.mkdir(parents=True,exist_ok=False)
    calibration(output/"calibration.pdf")
    for key, doc in spec.items():
        pdf=RESEARCH/"enterprise-011.pdf" if key=="publication" else output/"calibration.pdf"
        if file_sha(pdf)!=doc["pdf_sha256"]: raise ValueError("Unexpected PDF identity")
        with fitz.open(pdf) as source:
            for page in doc["pages"]:
                pix=source[page["page"]-1].get_pixmap(matrix=fitz.Matrix(4,4),
                    clip=fitz.Rect(*page["box"]),alpha=False)
                dest=output/f'page-{page["crop"]}.png'
                pix.save(dest)
                if file_sha(dest)!=page["png_sha256"]: raise ValueError("Unexpected crop identity")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("output",type=Path);prepare(p.parse_args().output)
