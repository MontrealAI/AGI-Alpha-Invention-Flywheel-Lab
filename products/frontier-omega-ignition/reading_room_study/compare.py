"""Independent complete comparator for the registered public XHTML/PDF pair."""

import argparse
import json
from pathlib import Path
import shutil
import unicodedata

from lxml import etree
import pymupdf


XHTML = "http://www.w3.org/1999/xhtml"
BLOCKS = {"p", "h1", "h2", "h3", "h4", "h5", "h6"}
LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
                           "ﬅ": "st", "ﬆ": "st"})


def tokens(text):
    return " ".join(unicodedata.normalize("NFC", text).translate(LIGATURES).split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir()
    reader = etree.parse(str(args.source), etree.XMLParser(no_network=True, resolve_entities=False))
    body = reader.find(f"{{{XHTML}}}body")
    elements = [element for element in body.iter() if isinstance(element.tag, str)
                and element.tag in {f"{{{XHTML}}}{name}" for name in BLOCKS}]
    with pymupdf.open(args.pdf) as doc:
        pages = [" " + tokens(page.get_text(sort=True)) + " " for page in doc]
    results = []
    for idx, element in enumerate(elements, 1):
        needle = tokens("".join(element.itertext()))
        ids = [i for i, page in enumerate(pages, 1) if f" {needle} " in page]
        link = ids[0] if len(ids) == 1 else None
        results.append({"index": idx, "page": link})
        if link:
            anchor = etree.SubElement(element, f"{{{XHTML}}}a", href=f"source.pdf#page={link}")
            anchor.set("aria-label", f"Open source PDF at page {link}")
            anchor.text = f" [PDF p. {link}]"
    reader.write(str(args.output / "index.html"), encoding="UTF-8", method="xml",
                 doctype="<!DOCTYPE html>")
    shutil.copyfile(args.pdf, args.output / "source.pdf")
    (args.output / "links.json").write_text(json.dumps(results), encoding="utf-8")


if __name__ == "__main__":
    main()
