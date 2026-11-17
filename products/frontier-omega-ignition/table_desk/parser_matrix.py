"""Receive two registered visual parser outputs and check their plain-text table."""
import argparse
import json
from pathlib import Path
import re

from table_desk import compare, digest, export, reference, registration, write_json

HERE = Path(__file__).resolve().parent
TABLE = re.compile(r"\\begin\{tabular\}\{([clr]+)\}(.*?)\\end\{tabular\}", re.S)
HEADER = re.compile(r"\\thead\{([^{}]*)\}")


def parse_fragment(raw):
    tables = TABLE.findall(raw)
    if len(tables) != 1:
        raise ValueError("The page must contain exactly one supported tabular environment.")
    columns, body = tables[0]
    rows = []
    for line in body.split(r"\\"):
        if not line.strip():
            continue
        row = []
        for cell in line.split("&"):
            value = cell.strip()
            wrapped = HEADER.fullmatch(value)
            value = wrapped[1] if wrapped else value
            if not value or any(char in value for char in "\\{}$"):
                raise ValueError("Unsupported markup in candidate cell.")
            row.append(value)
        if len(row) != len(columns):
            raise ValueError("Column data differ from declared table geometry.")
        rows.append(row)
    if len(rows) < 2:
        raise ValueError("Missing header or data row.")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--observation", type=Path, required=True)
    ap.add_argument("--author", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    obs = json.loads((args.observation / "observation.json").read_text())
    pin = json.loads((HERE / "parser-model.json").read_text())
    receipt = {"registration_sha256": digest(HERE / "cycle-001.json"),
               "observation_sha256": digest(args.observation / "observation.json"),
               "adapter_sha256": digest(Path(__file__)), "verdict": "withheld"}
    try:
        if (obs.get("status") != "completed" or len(obs["crops"]) != 2
                or obs["revision"] != pin["revision"] or obs["model_sha256"] != pin["sha256"]["model.safetensors"]):
            raise ValueError("Incomplete or different model observation.")
        matrix = []
        for page, crop in enumerate(obs["crops"], 1):
            raw = args.observation / f"page-{page}.txt"
            if (crop["page"] != page or crop["raw_sha256"] != digest(raw) or
                    crop["image_sha256"] != digest(HERE / "evidence" / f"page-{page}.png")):
                raise ValueError("Page or output identity differs from observation.")
            rows = parse_fragment(raw.read_text(encoding="utf-8"))
            if matrix and matrix[0] != rows[0]:
                raise ValueError("Printed continuation header differs.")
            matrix.extend(rows[1:] if matrix else rows)
        verdict = compare(matrix, reference(args.author, registration(HERE / "cycle-001.json")))
        receipt.update(verdict)
        if verdict["accepted"]:
            export(args.output, matrix)
            receipt.update(verdict="accepted", csv_sha256=digest(args.output / "table.csv"))
    except (ValueError, KeyError, OSError) as exc:
        receipt["reason"] = str(exc)
    write_json(args.output / "receipt.json", receipt)
    print(json.dumps(receipt))
    if receipt["verdict"] != "accepted":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
