#!/usr/bin/env python3
"""Check exact localized numeric claims against named production evidence."""

import argparse
from decimal import Decimal
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re


LANGUAGES = {"en": "index.html", "fr": "fr.html"}
VOID_TAGS = frozenset("area base br col embed hr img input link meta param source track wbr".split())
WORDS = {"en": {"four": 4, "six": 6}, "fr": {"quatre": 4, "six": 6}}
NUMBER = {
    "en": r"[−+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|[A-Za-z]+",
    "fr": r"[−+-]?(?:\d{1,3}(?: \d{3})+|\d+)(?:,\d+)?|[A-Za-z]+",
}
SCHEMA = "frontier/production-claim-plan-v1"


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def normalized(text):
    return " ".join(text.split()).casefold()


def load_blob(directory, name, max_bytes=2_000_000):
    relative = Path(name)
    if len(relative.parts) != 1 or relative.name != name or relative.suffix not in {".html", ".json"}:
        raise ValueError("invalid approved input name")
    path = directory / name
    if path.is_symlink():
        raise ValueError("input symlink is outside the evidence contract")
    with path.open("rb") as document:
        body = document.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ValueError("approved input exceeds byte limit")
    return body


class Fragments(HTMLParser):
    def __init__(self, selectors):
        super().__init__(convert_charrefs=True)
        self.selectors = selectors
        self.matches = {key: [] for key in selectors}
        self.active = None
        self.language = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "html":
            self.language = attributes.get("lang")
        if self.active is not None:
            if tag not in VOID_TAGS:
                self.active[2].append(tag)
            return
        for name, selector in self.selectors.items():
            if tag == selector["tag"] and attributes.get(selector["attribute"]) == selector["value"]:
                self.active = (name, [], [tag])
                return

    def handle_endtag(self, tag):
        if self.active is None:
            return
        name, chunks, stack = self.active
        if stack[-1] != tag:
            raise ValueError("ambiguous or incomplete claim fragment")
        stack.pop()
        if not stack:
            self.matches[name].append("".join(chunks))
            self.active = None

    def handle_data(self, data):
        if self.active is not None:
            self.active[1].append(data)

    def result(self, language):
        if self.active is not None or self.language != language:
            raise ValueError("unclosed claim fragment or unexpected language")
        output = {}
        for name, fragments in self.matches.items():
            if len(fragments) != 1:
                raise ValueError(f"{name} does not identify exactly one source fragment")
            fragment = fragments[0]
            selector = self.selectors[name]
            if "mission" in selector:
                template = json.loads(fragment)
                missions = [row for row in template if row["capability"]["id"] == selector["mission"]]
                if len(missions) != 1:
                    raise ValueError(f"{name} does not identify exactly one mission")
                fragment = missions[0][language]
            output[name] = fragment
        return output


def follow(item, path):
    for part in path:
        item = item[part]
    return item


def scalar(source, expression):
    value = follow(source, expression["path"])
    if "max" in expression:
        value = max(follow(row, expression["max"]) for row in value)
    elif expression.get("count", False):
        value = len(value)
    elif expression.get("sum", False):
        value = sum(value.values())
    elif "denominator" in expression:
        value = Decimal(value) / Decimal(follow(source, expression["denominator"]))
    return Decimal(value)


def parse_number(value, language):
    if value in WORDS[language]:
        return Decimal(WORDS[language][value])
    value = value.replace("−", "-")
    if language == "en":
        return Decimal(value.replace(",", ""))
    return Decimal(value.replace(" ", "").replace(",", "."))


def find_claim(fragment, anchors, language):
    prefix, suffix = (part.casefold() for part in anchors)
    pattern = re.escape(prefix) + f"(?P<quantity>{NUMBER[language]})" + re.escape(suffix)
    matches = list(re.finditer(pattern, normalized(fragment)))
    if len(matches) != 1:
        return None
    witness = matches[0]
    return parse_number(witness["quantity"], language), witness[0]


def check(plan, directory):
    if plan["schema"] != SCHEMA or not plan["claims"]:
        raise ValueError("unexpected or empty claim plan")
    raw_pages = {language: load_blob(directory, name) for language, name in LANGUAGES.items()}
    sources = {}
    for filename, registered in plan["evidence_sha256"].items():
        raw = load_blob(directory, filename)
        if sha256(raw) != registered:
            raise ValueError(f"source receipt mismatch for {filename}")
        sources[filename] = json.loads(raw)
    fragments = {}
    for language, source in raw_pages.items():
        parser = Fragments(plan["selectors"])
        parser.feed(source.decode("utf-8"))
        parser.close()
        fragments[language] = parser.result(language)
    claims = []
    for rule in plan["claims"]:
        expected = scalar(sources[rule["source"]], rule["expected"])
        for language in LANGUAGES:
            found = find_claim(fragments[language][rule["selector"]], rule[language], language)
            claims.append({
                "id": rule["id"], "language": language,
                "expected": str(expected), "found": str(found[0]) if found else None,
                "evidence": rule["source"], "receipt_locator": rule["expected"],
                "rendered_witness": found[1] if found else None,
                "decision": "PASS" if found and found[0] == expected else "HOLD",
            })
    return {
        "schema": "frontier/production-claim-evidence-v1",
        "job": plan["job"], "decision": "PASS" if all(row["decision"] == "PASS" for row in claims) else "HOLD",
        "page_sha256": {language: sha256(source) for language, source in raw_pages.items()},
        "evidence_sha256": plan["evidence_sha256"], "claims": claims,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("evidence_directory", type=Path)
    args = parser.parse_args()
    try:
        plan_blob = args.plan.read_bytes()
        report = check(json.loads(plan_blob), args.evidence_directory)
        report["plan_sha256"] = sha256(plan_blob)
    except (ValueError, TypeError, KeyError, IndexError, ArithmeticError, OSError) as error:
        report = {"decision": "HOLD", "reason": str(error)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report["decision"] != "PASS"


if __name__ == "__main__":
    raise SystemExit(main())
