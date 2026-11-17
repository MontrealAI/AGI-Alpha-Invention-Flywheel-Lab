"""Build an offline, page-linked reading edition from a PDF and a semantic manuscript."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from html import escape
from html.parser import HTMLParser
from pathlib import Path


HEADINGS = {f"h{number}" for number in range(1, 7)}
VOID = set("area base br col embed hr img input link meta param source track wbr".split())
MUTED = set("script style template nav footer noscript button select dialog".split())
LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"})


def whitespace(text):
    return " ".join(text.split())


def normalized(text):
    return whitespace(unicodedata.normalize("NFC", text.translate(LIGATURES)))


def language(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", value):
        return "und"
    return value


class SemanticHTML(HTMLParser):
    """Read text only. Never execute markup or follow links in a manuscript."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.rows = []
        self.active = None
        self.title_parts = []
        self.scopes = set()
        self.lang = "und"

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.active and tag in HEADINGS | {"p", "section", "article", "main", "div"}:
            self.finish_block()
        muted = ((self.stack and self.stack[-1][1]) or tag in MUTED
                 or "hidden" in attrs or "inert" in attrs
                 or (attrs.get("aria-hidden") or "").lower() == "true")
        if tag not in VOID:
            self.stack.append((tag, bool(muted)))
        if muted:
            return
        if tag == "html":
            self.lang = language(attrs.get("lang") or attrs.get("xml:lang"))
        if tag in {"main", "article"}:
            self.scopes.add(tag)
        if tag in HEADINGS or tag == "p":
            tags = {name for name, _ in self.stack}
            scope = "main" if "main" in tags else "article" if "article" in tags else "body"
            self.active = {"tag": tag, "scope": scope, "parts": [], "embedded": []}
        elif self.active:
            if tag == "br":
                self.active["parts"].append(" ")
            elif tag in {"img", "svg", "math", "canvas", "object", "video", "audio", "iframe", "embed"}:
                self.active["embedded"].append(tag)

    def handle_data(self, data):
        if self.stack and self.stack[-1][1]:
            return
        if self.stack and self.stack[-1][0] == "title" and not self.active:
            self.title_parts.append(data)
        elif self.active:
            self.active["parts"].append(data)

    def finish_block(self):
        if self.active:
            row = self.active
            value = whitespace("".join(row["parts"]))
            if value or row["embedded"]:
                block = {"kind": "paragraph", "text": value}
                if row["tag"] in HEADINGS:
                    block.update(kind="heading", level=int(row["tag"][1:]))
                if row["embedded"]:
                    block["embedded"] = sorted(set(row["embedded"]))
                self.rows.append((row["scope"], block))
        self.active = None

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                if self.active and any(name == self.active["tag"] for name, _ in self.stack[index:]):
                    self.finish_block()
                del self.stack[index:]
                return

    def manuscript(self):
        self.finish_block()
        scope = "main" if "main" in self.scopes else "article" if "article" in self.scopes else "body"
        blocks = [block for group, block in self.rows if group == scope]
        title = whitespace("".join(self.title_parts)) or next(
            (block["text"] for block in blocks if block["kind"] == "heading"), "Reading edition")
        return {"title": title, "language": self.lang, "blocks": blocks}, {
            "scope": scope, "embedded_blocks": sum("embedded" in block for block in blocks)}


def read_source(data, fmt):
    if fmt == "html":
        parser = SemanticHTML()
        parser.feed(data)
        parser.close()
        manuscript, selection = parser.manuscript()
    else:
        manuscript = json.loads(data)
        selection = {"scope": "supplied_blocks"}
    if not isinstance(manuscript, dict) or not isinstance(manuscript.get("title"), str) or not manuscript["title"].strip():
        raise ValueError("A manuscript needs a nonempty title.")
    rows = manuscript.get("blocks")
    if not isinstance(rows, list) or not rows:
        raise ValueError("The manuscript contains no eligible headings or paragraphs.")
    blocks = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or row.get("kind") not in ("heading", "paragraph"):
            raise ValueError(f"Block {index} needs kind heading or paragraph.")
        embedded = row.get("embedded") if fmt == "html" else None
        if not isinstance(row.get("text"), str) or (not row["text"].strip() and not embedded):
            raise ValueError(f"Block {index} needs nonempty text.")
        block = {"index": index, "kind": row["kind"], "text": row["text"]}
        if embedded:
            block["embedded"] = embedded
        if row["kind"] == "heading":
            level = row.get("level", 1)
            if type(level) is not int or not 1 <= level <= 6:
                raise ValueError(f"Heading {index} needs an integer level from 1 to 6.")
            block["level"] = level
        blocks.append(block)
    return manuscript["title"], language(manuscript.get("language")), blocks, selection


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def extract_pages(pdf):
    command = ["pdftotext", "-enc", "UTF-8", str(pdf), "-"]
    result = subprocess.run(command, capture_output=True, check=True)
    pages = result.stdout.decode("utf-8").split("\f")
    if pages[-1] == "":
        pages.pop()
    if not pages:
        raise ValueError("Poppler did not emit a PDF page.")
    version = subprocess.run(["pdftotext", "-v"], capture_output=True, text=True, check=True)
    return [normalized(page) for page in pages], (version.stderr or version.stdout).splitlines()[0]


def locate(block, pages):
    if block.get("embedded"):
        return {**block, "status": "missing", "candidate_pages": [], "page": None,
                "reason": "embedded_content_requires_review"}
    value = normalized(block["text"])
    # Match token boundaries, including decimal fragments. Keep case, numerical
    # signs, punctuation and wording intact. Never force a best-looking page.
    left = r"(?<!\w)" if value[0].isalnum() else ""
    right = r"(?!\w)" if value[-1].isalnum() else ""
    if value[0].isdigit():
        left += r"(?<!\d[.,])(?<![+\-−])"
    if value[-1].isdigit():
        right += r"(?![.,]\d)(?![%‰])"
    elif len(value) >= 2 and value[-2].isdigit() and value[-1] in ".,":
        right += r"(?!\d)"
    pattern = re.compile(left + re.escape(value) + right)
    candidates = [n for n, page in enumerate(pages, 1) if pattern.search(page)]
    status = ("matched" if len(candidates) == 1 else "ambiguous" if candidates else "missing")
    return {**block, "status": status, "candidate_pages": candidates,
            "page": candidates[0] if status == "matched" else None}


LABELS = {
    "en": {"edition": "Reading edition", "skip": "Skip to manuscript", "contents": "Contents",
           "source": "Original PDF", "receipt": "Evidence receipt", "page": "PDF page",
           "coverage": "{matched} of {total} passages link to one PDF page.",
           "reason": "Links identify text found on one page in the PDF text layer. The manuscript supplies the reading order.",
           "ambiguous": "Multiple candidate pages", "missing": "No unique source located",
           "embedded": "Embedded content requires source review", "passages": "Manuscript"},
    "fr": {"edition": "Édition de lecture", "skip": "Aller au manuscrit", "contents": "Sommaire",
           "source": "PDF original", "receipt": "Relevé de vérification", "page": "Page du PDF",
           "coverage": "{matched} passages sur {total} renvoient à une seule page du PDF.",
           "reason": "Les liens indiquent où le texte a été retrouvé sur une seule page du PDF. L’ordre de lecture provient du manuscrit.",
           "ambiguous": "Plusieurs pages possibles", "missing": "Passage introuvable dans le texte du PDF",
           "embedded": "Contenu intégré à vérifier dans le document source", "passages": "Manuscrit"},
}

STYLE = """
:root{color-scheme:light dark;font:1.05rem/1.65 Georgia,serif;background:#fbf8f2;color:#22182e}
*{box-sizing:border-box}body{max-width:52rem;margin:auto;padding:clamp(1.2rem,5vw,3.5rem)}
h1,h2,h3,h4,h5,h6{line-height:1.18;text-wrap:balance}h1{font-size:clamp(2rem,6vw,3.8rem)}
a{color:#492a78;text-underline-offset:.18em}a:focus-visible{outline:3px solid #9a6200;outline-offset:4px}
header{border-bottom:1px solid #aaa1b0;padding-bottom:1rem}nav ul{padding-left:1.4rem}
.passage{margin:1.6rem 0;overflow-wrap:anywhere}.passage>*{margin:.25rem 0}
small,.eyebrow,.resources{font: .9rem/1.5 system-ui,sans-serif}.status{color:#694500}
.skip{position:absolute;left:-10000px}.skip:focus{position:static}
@media(prefers-color-scheme:dark){:root{background:#15121e;color:#f5f0e8}a{color:#d8c2ff}.status{color:#ebcb89}}
@media print{.skip,nav,.resources{display:none}body{max-width:none}}
"""


def render(receipt):
    lang = receipt["language"]
    ui = "fr" if lang.split("-")[0].lower() == "fr" else "en"
    lab = LABELS[ui]
    title = escape(receipt["title"])
    rows = receipt["blocks"]
    headings = [r for r in rows if r["kind"] == "heading"]
    nav = ""
    named_headings = [row for row in headings if row["text"]]
    if named_headings:
        links = "".join(f'<li><a href="#passage-{r["index"]}">{escape(r["text"])}</a></li>' for r in named_headings)
        nav = f'<nav aria-label="{lab["contents"]}"><h2>{lab["contents"]}</h2><ul>{links}</ul></nav>'
    fragments = []
    top = min((r["level"] for r in headings), default=1)
    previous_level = 1
    for row in rows:
        tag = "p"
        if row["kind"] == "heading":
            level = min(6, previous_level + 1, row["level"] - top + 2)
            previous_level = level
            tag = f"h{level}"
        if row["status"] == "matched":
            page = row["page"]
            evidence = f'<a href="source.pdf#page={page}">{lab["page"]} {page}</a>'
        else:
            evidence = lab["embedded"] if row.get("embedded") else lab[row["status"]]
            if row["candidate_pages"]:
                evidence += " · " + ", ".join(map(str, row["candidate_pages"]))
        fragments.append(f'<div class="passage" id="passage-{row["index"]}" data-index="{row["index"]}" '
                         f'data-status="{row["status"]}"><{tag}>{escape(row["text"])}</{tag}>'
                         f'<small class="status" lang="{ui}">{evidence}</small></div>')
    summary = lab["coverage"].format(**receipt["summary"])
    return f"""<!doctype html>
<html lang="{ui}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>{title} — {lab["edition"]}</title><style>{STYLE}</style></head><body>
<a class="skip" href="#manuscript">{lab["skip"]}</a><header><p class="eyebrow">{lab["edition"]}</p>
<h1 lang="{escape(lang)}">{title}</h1><p>{summary} {lab["reason"]}</p><p class="resources">
<a href="source.pdf">{lab["source"]}</a> · <a href="receipt.json">{lab["receipt"]}</a></p></header>
{nav}<main id="manuscript" lang="{escape(lang)}" aria-label="{lab["passages"]}">{''.join(fragments)}</main></body></html>
"""


def build(pdf, source, destination, fmt=None):
    if fmt is None:
        suffix = source.suffix.lower()
        if suffix not in {".json", ".html", ".htm", ".xhtml"}:
            raise ValueError("Specify --source-format json or html for this manuscript extension.")
        fmt = "json" if suffix == ".json" else "html"
    if destination.is_symlink() or (destination.exists() and
            (not destination.is_dir() or any(destination.iterdir()))):
        raise ValueError("The output must be a new or empty directory.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        stage = Path(temp) / "edition"
        stage.mkdir()
        local_pdf = stage / "source.pdf"
        local_source = stage / "manuscript.original.txt"
        shutil.copyfile(pdf, local_pdf)
        shutil.copyfile(source, local_source)
        title, lang, blocks, selection = read_source(local_source.read_text(encoding="utf-8-sig"), fmt)
        pages, version = extract_pages(local_pdf)
        rows = [locate(block, pages) for block in blocks]
        summary = {status: sum(r["status"] == status for r in rows)
                   for status in ("matched", "ambiguous", "missing")}
        summary["total"] = len(rows)
        receipt = {"schema": "frontier-reading-edition/1", "title": title, "language": lang,
                   "pdf_sha256": digest(local_pdf), "source_sha256": digest(local_source),
                   "source_format": fmt, "instrument_sha256": digest(Path(__file__)), "extractor": version,
                   "page_count": len(pages), "selection": selection, "summary": summary, "blocks": rows}
        (stage / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (stage / "index.html").write_text(render(receipt), encoding="utf-8")
        stage.rename(destination)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-format", choices=("json", "html"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(args.pdf, args.source, args.output, args.source_format)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Reading edition: {error}\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
