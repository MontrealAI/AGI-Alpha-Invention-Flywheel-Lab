"""Compare an independently supplied primary HTML/text response with one frozen passage."""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path

from . import evaluate


class BodyText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def visible(text):
    return " ".join(text.split())


def check(source, path):
    record = evaluate.sources()[source]
    raw = path.read_bytes()
    parser = BodyText()
    parser.feed(raw.decode("utf-8"))
    body = visible(" ".join(parser.parts))
    return {"source": source, "registered_url": record["url"], "observed_file_sha256": hashlib.sha256(raw).hexdigest(),
            "observed_bytes": len(raw), "exact_normalized_passage_present": visible(record["excerpt"]) in body,
            "source_identity": "caller supplies the publisher response; matching words alone do not authenticate origin"}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("source", choices=evaluate.sources())
    p.add_argument("file", type=Path)
    args = p.parse_args()
    result = check(args.source, args.file)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["exact_normalized_passage_present"] else 1)
