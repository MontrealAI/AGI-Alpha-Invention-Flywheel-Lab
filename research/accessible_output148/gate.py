"""Offline source-first structural accessibility gate for authored AI-output fixtures.

This deliberately does NOT certify WCAG, PDF/UA, screen-reader experience, model
identity, semantic correctness, or a buyer. No calls to providers or native finance.
"""
from __future__ import annotations

import argparse
import hashlib
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

RECORD_SCHEMA = "agi-alpha/accessibility148/record-v1"
RECEIPT_SCHEMA = "agi-alpha/accessibility148/structural-receipt-v1"
SAFE_TAGS = {"html", "head", "meta", "title", "body", "header", "h1",
             "main", "h2", "h3", "p", "a", "figure", "img",
             "figcaption", "table", "caption", "thead", "tbody",
             "tr", "th", "td"}
VOID_TAGS = {"meta", "img"}
GENERIC_ALT = {"image", "photo", "picture", "graphic", "chart", "figure",
               "illustration", "decorative", "alt text", "placeholder"}
GENERIC_LINK = {"here", "click here", "link", "read more", "more"}
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
LANG_PATTERN = re.compile(r"(en|fr)(-(CA|US))?\Z")


def canonical(obj: object) -> bytes:
    return (json.dumps(obj, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _object_pairs(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("DUPLICATE_JSON_KEY")
        d[k] = v
    return d


def strict_load(raw: bytes):
    def bad_constant(value):
        raise ValueError("NONFINITE_JSON_NUMBER")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=_object_pairs,
                      parse_constant=bad_constant)


def fields(obj, required, scope):
    if not isinstance(obj, dict) or set(obj) != set(required):
        raise ValueError("INVALID_FIELDS_" + scope)


def text(value, scope, maxlen=10000):
    if not isinstance(value, str) or not value.strip() or len(value) > maxlen:
        raise ValueError("INVALID_TEXT_" + scope)
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise ValueError("CONTROL_CHARACTER_" + scope)
    return value


def ident(value, scope):
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError("INVALID_ID_" + scope)
    return value


def web_url(value):
    text(value, "URL", 2048)
    if any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError("INVALID_URL_WHITESPACE")
    u = urlsplit(value)
    if u.scheme != "https" or not u.netloc or u.username or u.password or not u.hostname:
        raise ValueError("UNSAFE_URL")
    if u.port is not None and not 1 <= u.port <= 65535:
        raise ValueError("UNSAFE_PORT")
    return value


def content_fingerprint(record):
    """No model or system authentication is implied by a user-declared label."""
    return sha(canonical(record))


def validate(record):
    fields(record, ("schema", "document_id", "model_label", "lang", "title", "blocks"),
           "RECORD")
    if record["schema"] != RECORD_SCHEMA:
        raise ValueError("RECORD_SCHEMA_CHANGED")
    ident(record["document_id"], "DOCUMENT")
    ident(record["model_label"], "DECLARED_MODEL")
    if not isinstance(record["lang"], str) or not LANG_PATTERN.fullmatch(record["lang"]):
        raise ValueError("INVALID_LANGUAGE")
    text(record["title"], "TITLE", 250)
    blocks = record["blocks"]
    if not isinstance(blocks, list) or not 1 <= len(blocks) <= 150:
        raise ValueError("BOUNDED_BLOCKS_REQUIRED")
    last_heading = 1
    counts = {"heading": 0, "paragraph": 0, "link": 0, "image": 0, "table": 0}
    for i, block in enumerate(blocks):
        if not isinstance(block, dict) or type(block.get("kind")) is not str:
            raise ValueError("INVALID_BLOCK")
        kind = block["kind"]
        if kind not in counts:
            raise ValueError("UNKNOWN_BLOCK_KIND")
        counts[kind] += 1
        if kind == "heading":
            fields(block, ("kind", "level", "text"), "HEADING")
            if type(block["level"]) is not int or block["level"] not in (2, 3):
                raise ValueError("INVALID_HEADING_LEVEL")
            if block["level"] > last_heading + 1:
                raise ValueError("HEADING_LEVEL_SKIPPED")
            last_heading = block["level"]
            text(block["text"], "HEADING_TEXT", 250)
        elif kind == "paragraph":
            fields(block, ("kind", "text"), "PARAGRAPH")
            text(block["text"], "PARAGRAPH")
        elif kind == "link":
            fields(block, ("kind", "label", "href"), "LINK")
            label = text(block["label"], "LINK_LABEL", 250)
            if label.casefold().strip() in GENERIC_LINK:
                raise ValueError("UNINFORMATIVE_LINK_NAME")
            web_url(block["href"])
        elif kind == "image":
            fields(block, ("kind", "src", "alt", "caption"), "IMAGE")
            web_url(block["src"])
            alt = text(block["alt"], "IMAGE_ALT", 500)
            if alt.casefold().strip().rstrip(".") in GENERIC_ALT or len(alt.strip()) < 12:
                raise ValueError("UNINFORMATIVE_IMAGE_ALT")
            text(block["caption"], "IMAGE_CAPTION", 500)
        elif kind == "table":
            fields(block, ("kind", "caption", "headers", "rows"), "TABLE")
            text(block["caption"], "TABLE_CAPTION", 500)
            headers, rows = block["headers"], block["rows"]
            if not isinstance(headers, list) or not 1 <= len(headers) <= 16:
                raise ValueError("INVALID_TABLE_HEADERS")
            for header in headers:
                text(header, "TABLE_HEADER", 250)
            if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
                raise ValueError("INVALID_TABLE_ROWS")
            for row in rows:
                if not isinstance(row, list) or len(row) != len(headers):
                    raise ValueError("TABLE_ROW_WIDTH")
                for cell in row:
                    if not isinstance(cell, str) or len(cell) > 2000:
                        raise ValueError("INVALID_TABLE_CELL")
                    if any(ord(c) < 32 and c not in "\n\t" for c in cell):
                        raise ValueError("INVALID_TABLE_CELL_CONTROL")
    return counts


def render(record):
    counts = validate(record)
    e = lambda s: escape(s, quote=True)
    out = ['<!doctype html>', '<html lang="' + e(record["lang"]) + '">',
           '<head><meta charset="utf-8"><title>' + e(record["title"]) + '</title></head>',
           '<body><header><h1>' + e(record["title"]) + '</h1></header><main>']
    for item in record["blocks"]:
        k = item["kind"]
        if k == "heading":
            tag = "h" + str(item["level"])
            out.append("<" + tag + ">" + e(item["text"]) + "</" + tag + ">")
        elif k == "paragraph":
            out.append("<p>" + e(item["text"]) + "</p>")
        elif k == "link":
            out.append('<p><a href="' + e(item["href"]) + '">' +
                       e(item["label"]) + '</a></p>')
        elif k == "image":
            out.append('<figure><img src="' + e(item["src"]) +
                       '" alt="' + e(item["alt"]) + '"><figcaption>' +
                       e(item["caption"]) + '</figcaption></figure>')
        elif k == "table":
            out.append('<table><caption>' + e(item["caption"]) +
                       '</caption><thead><tr>')
            for h in item["headers"]:
                out.append('<th scope="col">' + e(h) + '</th>')
            out.append('</tr></thead><tbody>')
            for row in item["rows"]:
                out.append('<tr>')
                for c in row:
                    out.append('<td>' + e(c) + '</td>')
                out.append('</tr>')
            out.append('</tbody></table>')
    out.append('</main></body></html>')
    return ("\n".join(out) + "\n").encode("utf-8"), counts


class _Structure(HTMLParser):
    """Independently inspect semantic structure, beyond byte identity checks."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.counts = {}
        self.doctypes = 0
        self.lang = None
        self.links = []
        self.current_link = None
        self.level = 0
        self.tables = []
        self.active_table = None

    def handle_decl(self, decl):
        if decl.lower().strip() != "doctype html":
            raise ValueError("INVALID_DOCTYPE")
        self.doctypes += 1

    def handle_comment(self, data):
        raise ValueError("UNREGISTERED_COMMENT")

    def handle_starttag(self, tag, attrs):
        if tag not in SAFE_TAGS:
            raise ValueError("DISALLOWED_HTML_TAG")
        a = dict(attrs)
        if len(a) != len(attrs):
            raise ValueError("DUPLICATE_HTML_ATTRIBUTE")
        self.counts[tag] = self.counts.get(tag, 0) + 1
        if tag == "html":
            if set(a) != {"lang"} or not LANG_PATTERN.fullmatch(a["lang"] or ""):
                raise ValueError("INVALID_HTML_LANGUAGE")
            self.lang = a["lang"]
        elif tag == "a":
            if set(a) != {"href"}:
                raise ValueError("UNBOUNDED_LINK_ATTRIBUTES")
            web_url(a["href"])
            self.current_link = ""
        elif tag == "img":
            if set(a) != {"src", "alt"}:
                raise ValueError("INVALID_IMAGE_ATTRIBUTES")
            web_url(a["src"])
            alt = text(a["alt"], "ALT", 500)
            if len(alt.strip()) < 12 or alt.casefold().strip().rstrip(".") in GENERIC_ALT:
                raise ValueError("UNINFORMATIVE_ALT")
        elif tag == "th":
            if a != {"scope": "col"}:
                raise ValueError("HEADER_SCOPE_MISSING")
        elif tag == "meta":
            if a != {"charset": "utf-8"}:
                raise ValueError("META_CONTRACT_CHANGED")
        elif a:
            raise ValueError("UNREGISTERED_HTML_ATTRIBUTES")
        if tag in {"h1", "h2", "h3"}:
            n = int(tag[1])
            if n > self.level + 1:
                raise ValueError("HEADING_SKIPPED_IN_HTML")
            self.level = n
        if tag == "table":
            self.active_table = {"caption": 0, "th": 0}
        if tag == "caption":
            if self.active_table is None:
                raise ValueError("ORPHAN_CAPTION")
            self.active_table["caption"] += 1
        if tag == "th":
            if self.active_table is None:
                raise ValueError("ORPHAN_TH")
            self.active_table["th"] += 1
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag not in VOID_TAGS:
            raise ValueError("UNEXPECTED_SELF_CLOSING_TAG")
        self.handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self.current_link is not None and "a" in self.stack:
            self.current_link += data

    def handle_endtag(self, tag):
        if tag in VOID_TAGS or not self.stack or self.stack[-1] != tag:
            raise ValueError("INVALID_HTML_NESTING")
        self.stack.pop()
        if tag == "a":
            if not self.current_link or not self.current_link.strip():
                raise ValueError("EMPTY_LINK_TEXT")
            self.links.append(self.current_link)
            self.current_link = None
        if tag == "table":
            if not self.active_table or self.active_table["caption"] != 1 or not self.active_table["th"]:
                raise ValueError("TABLE_STRUCTURE_INCOMPLETE")
            self.tables.append(self.active_table)
            self.active_table = None


def inspect_html(raw):
    p = _Structure()
    p.feed(raw.decode("utf-8"))
    p.close()
    if p.stack or p.doctypes != 1:
        raise ValueError("INCOMPLETE_HTML_DOCUMENT")
    for tag, expected in {"html": 1, "head": 1, "body": 1, "main": 1,
                          "header": 1, "h1": 1, "title": 1}.items():
        if p.counts.get(tag, 0) != expected:
            raise ValueError("MISSING_OR_DUPLICATE_LANDMARK_" + tag)
    return {"lang": p.lang, "h1": p.counts.get("h1", 0),
            "h2": p.counts.get("h2", 0), "h3": p.counts.get("h3", 0),
            "links": len(p.links), "images": p.counts.get("img", 0),
            "tables": len(p.tables)}


def generate_receipt(record, html_raw, counts):
    return {"schema": RECEIPT_SCHEMA, "document_id": record["document_id"],
            "declared_model_label_unverified": record["model_label"],
            "record_sha256": content_fingerprint(record),
            "html_sha256": sha(html_raw),
            "block_counts": counts,
            "claim": "source_bound_structural_invariants_only",
            "wcag_conformance": "NOT_ASSESSED",
            "assistive_technology_testing": "NOT_PERFORMED",
            "model_identity_authentication": "NOT_PROVIDED",
            "customer_acceptance": "NOT_ESTABLISHED",
            "paid_commerce": "NONE"}


def compile_bytes(record_raw):
    record = strict_load(record_raw)
    html_raw, counts = render(record)
    inspected = inspect_html(html_raw)
    if inspected["lang"] != record["lang"]:
        raise ValueError("LANG_MISMATCH")
    return html_raw, canonical(generate_receipt(record, html_raw, counts))


def audit_bytes(record_raw, html_raw, receipt_raw):
    record = strict_load(record_raw)
    receipt = strict_load(receipt_raw)
    expected_html, counts = render(record)
    if html_raw != expected_html or sha(html_raw) != sha(expected_html):
        raise ValueError("HTML_SOURCE_BINDING_FAILED")
    inspected = inspect_html(html_raw)
    if inspected["lang"] != record["lang"]:
        raise ValueError("DOCUMENT_LANGUAGE_CHANGED")
    expected = generate_receipt(record, html_raw, counts)
    if receipt != expected or canonical(receipt) != receipt_raw:
        raise ValueError("RECEIPT_SOURCE_BINDING_FAILED")
    return {"accepted": True, "claim": expected["claim"],
            "record_sha256": expected["record_sha256"],
            "html_sha256": expected["html_sha256"],
            "document_id": record["document_id"], "counts": counts,
            "structure": inspected, "limitations":
                ["no_wcag_conformance", "no_human_testing",
                 "no_model_authentication", "no_paid_commerce"]}


def compare_bytes(baseline, candidate):
    """Read-only fail-closed release comparison; no automated semantic sign-off."""
    first = audit_bytes(*baseline)
    second = audit_bytes(*candidate)
    if first["document_id"] != second["document_id"]:
        raise ValueError("DOCUMENT_IDENTITY_CHANGED")
    for kind in ("heading", "paragraph", "link", "image", "table"):
        if second["counts"][kind] < first["counts"][kind]:
            raise ValueError("STRUCTURAL_ROLE_COUNT_REGRESSED_" + kind.upper())
    return {"accepted": True, "verdict": "PASS_STRUCTURAL_ONLY",
            "changed_html": first["html_sha256"] != second["html_sha256"],
            "baseline": first["html_sha256"], "candidate": second["html_sha256"],
            "requires_semantic_and_assistive_technology_review": True,
            "commercial_verdict": "NOT_ESTABLISHED"}


def _read_triplet(base):
    folder = Path(base)
    return tuple((folder / n).read_bytes() for n in
                 ("RECORD.json", "DOCUMENT.html", "RECEIPT.json"))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("compile", "audit", "compare"))
    p.add_argument("--record")
    p.add_argument("--output")
    p.add_argument("--baseline")
    p.add_argument("--candidate")
    args = p.parse_args(argv)
    if args.command == "compile":
        if not args.record or not args.output:
            p.error("compile requires --record and --output")
        record_raw = Path(args.record).read_bytes()
        html_raw, receipt_raw = compile_bytes(record_raw)
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=False)
        (out / "RECORD.json").write_bytes(canonical(strict_load(record_raw)))
        (out / "DOCUMENT.html").write_bytes(html_raw)
        (out / "RECEIPT.json").write_bytes(receipt_raw)
        result = audit_bytes(*_read_triplet(out))
    elif args.command == "audit":
        if not args.output:
            p.error("audit requires --output")
        result = audit_bytes(*_read_triplet(args.output))
    else:
        if not args.baseline or not args.candidate:
            p.error("compare requires --baseline and --candidate")
        result = compare_bytes(_read_triplet(args.baseline),
                               _read_triplet(args.candidate))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
