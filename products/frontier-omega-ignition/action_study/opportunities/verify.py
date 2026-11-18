"""Check the bilingual decision and, when supplied, the original publisher pages."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = False

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip = True

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        return " ".join(" ".join(self.parts).split())


def check_page(row, capture_dir):
    record = {"id": row["id"], "exact_http_body": None, "registered_excerpt_present": None}
    try:
        if capture_dir is not None:
            raw = (capture_dir / (row["id"] + ".html")).read_bytes()
        else:
            request = Request(row["url"], headers={"User-Agent": "FRONTIER-Omega public source qualification"})
            with urlopen(request, timeout=25) as response:
                record["landed_url"] = response.geturl()
                if urlsplit(record["landed_url"]).netloc != urlsplit(row["acquisition"]["landed_url"]).netloc:
                    raise ValueError("Publisher host changed since registration")
                raw = response.read(2_500_001)
                if len(raw) > 2_500_000:
                    raise ValueError("Response exceeded this reader's 2.5 MB inspection budget")
        parser = VisibleText()
        parser.feed(raw.decode("utf-8"))
        parser.close()
        record["exact_http_body"] = digest(raw) == row["acquisition"]["sha256"]
        record["registered_excerpt_present"] = row["excerpt"] in parser.text()
    except (OSError, ValueError) as error:
        record["unavailable"] = str(error)
    return record


def check(capture_dir=None, refresh=False):
    choices = json.loads((HERE / "choices.json").read_text(encoding="utf-8"))
    rows = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))["sources"]
    sources = {row["id"]: row for row in rows}
    cards = choices["opportunities"]
    ids = {card["id"] for card in cards}
    if len(sources) != len(rows) or len(ids) != len(cards) or len(cards) != 5 or choices["next_build"] not in ids:
        raise ValueError("Duplicate or missing source or opportunity identity")
    used = set()
    for card in cards:
        links = [sources[key]["url"] for key in card["source_ids"]]
        if urlsplit(card["url"]).scheme != "https" or card["url"] not in links:
            raise ValueError(f"Unattributed opportunity {card['id']}")
        used.update(card["source_ids"])
        for lang in ("en", "fr"):
            if not all(card[lang][key].strip() for key in ("title", "finding", "limit", "test")):
                raise ValueError(f"Missing {lang} copy for {card['id']}")
    if used != set(sources):
        raise ValueError("Unreferenced publisher record")
    for row in rows:
        if row["excerpt_sha256"] != digest(row["excerpt"].encode()):
            raise ValueError(f"Changed registered excerpt {row['id']}")
    captures = []
    if capture_dir is not None or refresh:
        with ThreadPoolExecutor(max_workers=3) as pool:
            captures = list(pool.map(lambda row: check_page(row, capture_dir), rows))
    return {"opportunities": len(cards), "registered_sources": len(sources), "checked_publisher_pages": captures}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    mode = cli.add_mutually_exclusive_group()
    mode.add_argument("--capture-dir", type=Path, help="Read each original publisher response as <source ID>.html")
    mode.add_argument("--refresh", action="store_true", help="Read the registered public publisher pages")
    args = cli.parse_args()
    result = check(args.capture_dir, args.refresh)
    print(json.dumps(result, indent=2))
    sys.exit(int(any(not row["registered_excerpt_present"] for row in result["checked_publisher_pages"])))
