"""Reproduce RR-02's complete author-edition comparison."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from xml.etree import ElementTree as ET

from lxml import etree

from annotate import HERE, MARK, PRODUCER, XHTML, anchors, read_markup
from compare import tokens
from run import KEY, ROOT, digest, run_arm, source_material


KEY_007 = ([1]*9 + [None] + [2]*11 + [3]*13 + [4]*9 + [None] + [5]*12
           + [None] + [6]*7 + [7]*7)


def adjudicate(author_bytes, artifact, gold, pdf, recipient_pdf):
    original = ET.fromstring(author_bytes)
    edition = ET.fromstring(artifact.read_bytes())
    projection = []
    for parent in edition.iter():
        for child in list(parent):
            marker = child.get(MARK)
            if marker is None:
                continue
            if marker == "policy":
                assert child.tag == XHTML + "meta" and child.get("http-equiv") == "Content-Security-Policy"
            else:
                assert child.tag == XHTML + "a"
                idx = int(marker)
                link = child.get("href")
                page = int(link.removeprefix("source.pdf#page="))
                projection.append((idx,page,link == f"source.pdf#page={page}"))
            parent.remove(child)
    encode = lambda root: ET.canonicalize(ET.tostring(root, encoding="unicode"))
    preserved = encode(original) == encode(edition)
    unique = len(projection) == len({idx for idx, _, _ in projection})
    correct = [idx for idx, page, ok in projection if ok and 1 <= idx <= len(gold) and gold[idx-1] == page]
    source_ok = digest(pdf) == digest(recipient_pdf)
    return {"correct": len(correct), "wrong": len(projection)-len(correct),
            "total": len(gold), "all_existing_markup_preserved": preserved, "same_pdf": source_ok,
            "indices": correct, "accepted": bool(projection) and unique and len(correct) == len(projection)
            and preserved and source_ok}


def conventional(source, pdf, folder):
    folder.mkdir()
    pages = subprocess.check_output(["pdftotext", "-enc", "UTF-8", str(pdf), "-"]).decode().split("\f")
    pages = [" "+tokens(p)+" " for p in pages]
    material = source_material(source)[0]
    rows = []
    for i, (_, passage) in enumerate(material, 1):
        needle = " " + tokens(passage) + " "
        choices = [page for page,text in enumerate(pages,1) if needle in text]
        rows.append({"index": i, "text": passage, "page": choices[0] if len(choices)==1 else None})
    (folder/"annotated-author.html").write_bytes(anchors(source.read_bytes(), rows))
    shutil.copyfile(pdf, folder/"source.pdf")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--direct", type=Path, nargs=3, metavar=("HTML", "PDF", "NEW_DIR"),
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.direct:
        conventional(*args.direct)
        return
    out = args.output.resolve()
    out.mkdir()
    results = {}
    for name,gold in (("cycle-001", KEY), ("cycle-007", KEY_007)):
        folder = out/name
        folder.mkdir()
        source, pdf = (ROOT/"docs/research"/f"{name}.{ext}" for ext in ("html","pdf"))
        assert len(source_material(source)[0]) == len(gold)
        candidate, direct, mupdf = (folder/arm for arm in ("candidate","direct","mupdf"))
        commands = {
            "reader": [sys.executable, str(PRODUCER), "--source", str(source), "--pdf", str(pdf),
                       "--output", str(candidate)],
            "annotated": [sys.executable, str(HERE/"annotate.py"), "--edition", str(candidate)],
            "direct": [sys.executable, str(HERE/"successor.py"), "--output", str(folder),
                       "--direct", str(source), str(pdf), str(direct)],
            "mupdf": [sys.executable, str(HERE/"compare.py"), str(source), str(pdf), str(mupdf)]
        }
        telemetry = {label: run_arm(cmd, folder) for label,cmd in commands.items()}
        arms = {}
        for label,d in [("annotated",candidate), ("direct",direct)]:
            artifact = d/"annotated-author.html"
            arms[label] = adjudicate(source.read_bytes(), artifact, gold, pdf, d/"source.pdf") if artifact.is_file() else {"accepted":False}
            if artifact.is_file():
                arms[label]["html_sha256"] = digest(artifact)
        links = json.loads((mupdf/"links.json").read_text()) if (mupdf/"links.json").is_file() else []
        score = [(row["page"], gold[row["index"]-1]) for row in links if row["page"]]
        arms["mupdf"] = {"correct":sum(p==g for p,g in score), "wrong":sum(p!=g for p,g in score),
                         "total":len(gold)}
        tests = {}
        for mutate,message in (("source","Publication or instrument identity differs"),
                               ("receipt","Received evidence differs")):
            tmp = folder/f"altered-{mutate}"
            tmp.mkdir()
            for filename in ("manuscript.original.txt", "source.pdf", "receipt.json"):
                shutil.copyfile(candidate/filename,tmp/filename)
            if mutate == "source":
                with (tmp/"manuscript.original.txt").open("ab") as fh: fh.write(b"<!--changed-->")
            else:
                path = tmp/"receipt.json"
                r = json.loads(path.read_text())
                row = next(b for b in r["blocks"] if b["page"])
                row["page"] += 1
                path.write_text(json.dumps(r))
            obs = run_arm([sys.executable, str(HERE/"annotate.py"), "--edition", str(tmp)], folder)
            tests[mutate] = obs["exit_code"] != 0 and message in obs["stderr"] and not (tmp/"annotated-author.html").exists()
            telemetry["altered_"+mutate] = obs
        stats = source_material(source)[1]
        results[name] = {"source_html_sha256":digest(source),"source_pdf_sha256":digest(pdf),
                         "source_structures":stats,"received_receipt_sha256":digest(candidate/"receipt.json"),
                         "verdicts":arms,"negative_controls":tests,"process_costs":telemetry}
    report = {"study":"RR-02","results":results,
              "files_sha256":{p.name:digest(p) for p in (PRODUCER,HERE/"annotate.py",HERE/"successor.py",HERE/"compare.py",HERE/"run.py")},
              "interpretation":"Source-to-page correspondence on two pinned public editions. No human productivity, newly available AI capability, generalization, economic or causal process advantage measured."}
    (out/"SUCCESSOR_RESULTS.json").write_text(json.dumps(report, indent=2)+"\n")
    for name,r in results.items():
        print(name,{k:(v.get("correct"),v.get("wrong")) for k,v in r["verdicts"].items()},r["negative_controls"])


if __name__ == "__main__":
    main()
