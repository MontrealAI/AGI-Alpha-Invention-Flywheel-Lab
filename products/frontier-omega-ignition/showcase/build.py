"""Render the public, read-only Pairing Lab using only repository-owned, public inputs."""
import argparse
import base64
import csv
import hashlib
import html
import io
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parent
if str(PRODUCT) not in sys.path:
    sys.path.insert(0, str(PRODUCT))
from flagship import package

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def csp_hash(source):
    return "'sha256-" + base64.b64encode(hashlib.sha256(source.encode()).digest()).decode() + "'"

def policy(document):
    match = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', document)
    if not match:
        raise ValueError("Missing public showcase policy")
    return html.unescape(match[1])

def render():
    receipt = json.loads((PRODUCT / "flagship/receipt.json").read_text())
    raw = (PRODUCT / "flagship/runs.csv").read_bytes()
    if sha(raw) != receipt["study"]["data_sha256"] or sha(raw) != "c60d0b58ab109ba900e36465a0ffadaaeb4c8a2743abc744eb17f3f596842118":
        raise ValueError("Public runs do not match the registered archive")
    for name, expected in receipt["study"]["source_sha256"].items():
        if name not in package.FILES or sha((PRODUCT / "flagship" / name).read_bytes()) != expected:
            raise ValueError(f"Public recipient source changed: {name}")
    archive = io.BytesIO()
    package.build(archive)
    record = json.loads((PRODUCT / "frontier_study/record.json").read_text())
    atlas_raw = (PRODUCT / "frontier_study/atlas.json").read_bytes()
    atlas = json.loads(atlas_raw)
    if sha(atlas_raw) != record["atlas_sha256"]:
        # Study identities use canonical JSON, see frontier_study.digest.
        canonical = json.dumps(atlas, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        if sha(canonical) != record["atlas_sha256"]:
            raise ValueError("Evidence map changed since registration")
    ids = {row["task"] for row in csv.DictReader(io.StringIO(raw.decode()))}
    ranked = sorted(ids, key=lambda t: (sha(("pairing-lab-v1/" + t).encode()), t))
    split = 3 * len(ranked) // 5
    ref = receipt["arms"]["2000000/2"]["split"]
    if sha("\n".join(ranked[:split]).encode()) != ref["calibration_ids_sha256"] or sha("\n".join(ranked[split:]).encode()) != ref["audit_ids_sha256"]:
        raise ValueError("Split identities changed")
    payload = {"csv": raw.decode(), "tasks": ranked, "split": split, "receipt": receipt,
               "options": record["candidates"] + record["challengers"],
               "sources": {item["id"]: item["url"] for item in atlas["sources"]},
               "winner": record["decision"]["candidate_id"],
               "copy": json.loads((HERE / "copy.json").read_text()),
               "archive": base64.b64encode(archive.getvalue()).decode(),
               "archive_sha256": sha(archive.getvalue())}
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).replace("<", r"\u003c").replace(">", r"\u003e").replace("&",r"\u0026")
    sheet, script = [(HERE / name).read_text() for name in ("style.css", "app.js")]
    security = "default-src 'none'; connect-src 'none'; object-src 'none'; img-src data:; base-uri 'none'; form-action 'none'; script-src " + csp_hash(script) + "; style-src " + csp_hash(sheet)
    document = (HERE / "page.html").read_text()
    for marker, value in [("<!--POLICY-->", security), ("/*STYLE*/", sheet), ("<!--PAYLOAD-->", encoded), ("/*APP*/", script)]:
        if document.count(marker) != 1:
            raise ValueError("Missing or duplicate public renderer marker")
        document = document.replace(marker, value)
    return document

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    out = p.parse_args().output
    out.write_text(render(), encoding="utf-8")
    print(f"{out}: {sha(out.read_bytes())}")
