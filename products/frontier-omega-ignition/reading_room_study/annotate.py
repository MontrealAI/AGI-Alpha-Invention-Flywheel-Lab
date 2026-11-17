"""Attach verified physical-page citations to one of two pinned public author editions."""
import argparse
import hashlib
from html import escape
from html.parser import HTMLParser
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


class InsertionPoints(HTMLParser):
    """Find the original character offsets without serializing or changing author tags."""

    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.lines = [0]
        for index, char in enumerate(source):
            if char == "\n":
                self.lines.append(index + 1)
        self.head_end = None
        self.block_ends = []

    def position(self):
        line, column = self.getpos()
        return self.lines[line - 1] + column

    def handle_starttag(self, tag, attrs):
        if tag == "head":
            self.head_end = self.position() + len(self.get_starttag_text())

    def handle_endtag(self, tag):
        if XHTML + tag in BLOCKS:
            self.block_ends.append(self.source.index(">", self.position()) + 1)


def anchors(markup, mapping):
    """Insert only trusted local links into the original, exact allowlisted UTF-8 bytes."""
    if sha(markup) not in PAPERS:
        raise ValueError("Unknown publication markup.")
    root = read_markup(markup)
    elements = [e for e in root.find(XHTML + "body").iter() if e.tag in BLOCKS]
    source = markup.decode("utf-8")
    points = InsertionPoints(source)
    points.feed(source)
    points.close()
    if points.head_end is None or len(elements) != len(mapping) or len(points.block_ends) != len(mapping):
        raise ValueError("Receipt does not cover the author manuscript.")
    policy = (f'<meta {MARK}="policy" http-equiv="Content-Security-Policy" '
              f'content="{escape(CSP, quote=True)}" />')
    inserts = [(points.head_end, policy)]
    for index, (element, block, end) in enumerate(zip(elements, mapping, points.block_ends), 1):
        original = " ".join("".join(element.itertext()).split())
        if block["index"] != index or " ".join(block["text"].split()) != original:
            raise ValueError(f"Receipt passage {index} differs from the author manuscript.")
        if block["page"] is not None:
            n = block["page"]
            if type(n) is not int or n < 1:
                raise ValueError("Invalid physical page.")
            inserts.append((end, f'<a {MARK}="{index}" href="source.pdf#page={n}" '
                                 f'aria-label="Passage {index}, source PDF page {n}">[PDF p. {n}]</a>'))
    chunks = []
    start = 0
    for pos, insertion in sorted(inserts):
        # Preserve the original parent or sibling whitespace tail when a DOM
        # consumer removes our marker element.
        while pos < len(source) and source[pos].isspace():
            pos += 1
        chunks.extend([source[start:pos], insertion])
        start = pos
    chunks.append(source[start:])
    return "".join(chunks).encode("utf-8")

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
