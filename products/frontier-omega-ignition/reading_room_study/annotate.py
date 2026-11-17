"""Attach verified physical-page citations to one of two pinned public author editions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from lxml import etree


HERE = Path(__file__).resolve().parent
PRODUCER = HERE.parent / "reading_room" / "edition.py"
PRODUCER_SHA = "f4d38a94174896d6330c4559de13e6ae105cf72c1df456cd3968f02b0437d9bc"
PAPERS = {
    "237e73a6dfb99ddfaf4d2d184e8783c87ba0332e77e1fb655dce1a3557facd71":
    "4c303bc5a9c4cafbbb11b4d84a0fb4ceb8f7b95822fbdf935c6560f658807c01",
    "cf1b5583aa251226cecc9fae991061c783fd5ff6088710b94db9183b02260738":
    "816f02210ffae281aac747af57aa59f02a79db2d4e36c639808527269b6ad662",
}
XHTML = "{http://www.w3.org/1999/xhtml}"
BLOCKS = {XHTML + tag for tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6")}
MARK = "data-rr-added"
CSP = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_markup(data):
    return etree.fromstring(data, parser=etree.XMLParser(no_network=True, resolve_entities=False))


def anchors(markup, mapping):
    """A pure renderer over the allowlisted, inactive author markup."""
    root = read_markup(markup)
    policy = etree.Element(XHTML + "meta", attrib={"http-equiv": "Content-Security-Policy",
                                                  "content": CSP, MARK: "policy"})
    root.find(XHTML + "head").insert(0, policy)
    elements = [e for e in root.find(XHTML + "body").iter() if e.tag in BLOCKS]
    if len(elements) != len(mapping):
        raise ValueError("Receipt does not cover the author manuscript.")
    for index, (element, block) in enumerate(zip(elements, mapping), 1):
        original = " ".join("".join(element.itertext()).split())
        if block["index"] != index or " ".join(block["text"].split()) != original:
            raise ValueError(f"Receipt passage {index} differs from the author manuscript.")
        if block["page"] is not None:
            n = block["page"]
            link = etree.Element(XHTML + "a", attrib={MARK: str(index), "href": f"source.pdf#page={n}",
                                 "aria-label": f"Passage {index}, source PDF page {n}"})
            link.text = f"[PDF p. {n}]"
            element.addnext(link)
    return etree.tostring(root, encoding="UTF-8", doctype="<!DOCTYPE html>", method="xml")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edition", required=True, type=Path, help="completed offline recipient directory")
    directory = parser.parse_args().edition.resolve()
    dest = directory / "annotated-author.html"
    if dest.exists():
        parser.error("The optional annotated edition already exists.")
    manuscript, pdf = directory/"manuscript.original.txt", directory/"source.pdf"
    markup = manuscript.read_bytes()
    if PAPERS.get(sha(markup)) != sha(pdf.read_bytes()) or sha(PRODUCER.read_bytes()) != PRODUCER_SHA:
        parser.error("Publication or instrument identity differs from the permitted public editions.")
    # Validate the entire supplied receipt against new local execution, without any page key.
    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp)/"replay"
        subprocess.run([sys.executable, str(PRODUCER), "--source", str(manuscript), "--source-format", "html",
                        "--pdf", str(pdf), "--output", str(fresh)], check=True, stdout=subprocess.DEVNULL)
        recorded = json.loads((directory/"receipt.json").read_text())
        if recorded != json.loads((fresh/"receipt.json").read_text()):
            parser.error("Received evidence differs from a fresh execution on identical source inputs.")
    payload = anchors(markup, recorded["blocks"])
    with tempfile.NamedTemporaryFile(dir=directory) as stage:
        stage.write(payload)
        stage.flush()
        os.link(stage.name, dest)
    print(dest.name, sha(payload))


if __name__ == "__main__":
    main()
