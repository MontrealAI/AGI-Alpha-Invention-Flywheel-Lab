import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import xml.etree.ElementTree as E
import zipfile

EXPECTED = "0e88487dfbce2643eb7ad43ecd15c87853d9d1c8cccd2e011be5efa90c43e3a7"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
SOURCE = "https://github.com/Bop2000/DAS-DAO/blob/2e57921bbf0bb113c6e645a6dc556458bca69c92/data/CPM-P_dataset.xlsx"


def inspect(raw):
    actual = hashlib.sha256(raw).hexdigest()
    if actual != EXPECTED:
        raise ValueError("PINNED_PUBLIC_DATASET_BYTES_REQUIRED")
    header, indices, populated = [], [], 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = E.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(node.itertext()) for node in shared.findall(NS + "si")]
        with archive.open("xl/worksheets/sheet1.xml") as stream:
            for _, node in E.iterparse(stream, events=("end",)):
                if node.tag != NS + "row":
                    continue
                cells = {}
                for cell in node.findall(NS + "c"):
                    value = cell.find(NS + "v")
                    inline = cell.find(NS + "is")
                    if value is None and inline is None:
                        continue
                    text = value.text if value is not None else "".join(inline.itertext())
                    text = strings[int(text)] if cell.get("t") == "s" else text
                    letters = re.match(r"[A-Z]+", cell.attrib["r"]).group()
                    column = 0
                    for letter in letters:
                        column = column * 26 + ord(letter) - 64
                    cells[column - 1] = text
                if cells:
                    populated += 1
                    if not header:
                        header = [cells.get(i) for i in range(max(cells) + 1)]
                    else:
                        indices.append(cells.get(0))
                node.clear()
    matches = [name for name in header if name and re.search(r"\b(heat|batch|lot|cast_id|date|timestamp|foundry|customer)\b", name, re.I)]
    return {"schema": "super-alpha/public-alloy-data-admissibility/v1", "scope": "POST_DECISIVE_EMPIRICAL_PIVOT_SOURCE_INSPECTION_ONLY", "source_url": SOURCE, "source_commit": "2e57921bbf0bb113c6e645a6dc556458bca69c92", "git_blob_sha": "22ff692143fb63c85f33965a3c514b61dba1dd82", "sha256": actual, "data_rows": populated - 1, "columns": len(header), "header": header, "unnamed_index_is_sequential": indices == [str(i) for i in range(populated - 1)], "labeled_grouping_or_identity_columns": matches, "observed_property_labels": [name for name in ("UTS", "Ef") if name in header], "feature_timing_requires_evidence": [name for name in ("nodularity rate", "pearlite fraction") if name in header], "independent_new_heat_qualification": "NOT_ESTABLISHED_BY_THIS_PUBLIC_EXPORT", "interpretation": "The public export has no labeled heat/lot grouping. This does not establish absence of traceability in the authors' original MES. Do not invent groups from row order or treat microstructure as a known pre-production input without evidence.", "next_needed": "Independent production-unit provenance, decision-time input availability/control, and intended complete-product acceptance measurements.", "model_training_or_new_financial_account": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--base64", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw = args.dataset.read_bytes()
    result = inspect(base64.b64decode(raw) if args.base64 else raw)
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        with args.output.open("x") as stream:
            stream.write(encoded)
    print(encoded)
