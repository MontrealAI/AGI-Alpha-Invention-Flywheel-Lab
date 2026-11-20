"""Read only fixed first-party feeds; keep durable, untrusted observations."""
from __future__ import annotations
from contextlib import contextmanager
import datetime as dt
import email.utils
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from types import MappingProxyType
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SOURCES = MappingProxyType({
    "openai-news": "https://openai.com/news/rss.xml",
    "openai-python": "https://github.com/openai/openai-python/releases.atom",
    "anthropic-python": "https://github.com/anthropics/anthropic-sdk-python/releases.atom",
    "vllm": "https://github.com/vllm-project/vllm/releases.atom",
})
MAX_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 2500
FETCH_SECONDS = 12
ATTEMPT_SECONDS = 7
UTC = dt.timezone.utc

def _format(t):
    if not isinstance(t, dt.datetime) or t.tzinfo is None:
        raise ValueError("now must be an aware datetime")
    return t.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

def _date(s):
    try:
        value = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        try:
            value = email.utils.parsedate_to_datetime(s)
        except (ValueError, TypeError, OverflowError):
            return None
    if value is None or value.tzinfo is None:
        return None
    try:
        return _format(value)
    except (ValueError, OverflowError):
        return None

def _sha(data):
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

def _canonical_url(value, source_id):
    # Only registry-owned HTTPS origins are accepted as display citations.
    # Never follow these URLs or use them as future acquisition targets.
    host = urllib.parse.urlsplit(SOURCES[source_id]).hostname
    if not value or len(value) > 2048 or re.search(r"[\x00-\x20\\]", value):
        return None
    try:
        p = urllib.parse.urlsplit(value)
    except ValueError:
        return None
    if p.scheme != "https" or p.netloc != host or not p.path.startswith("/"):
        return None
    if host == "github.com":
        repo = urllib.parse.urlsplit(SOURCES[source_id]).path.rsplit("/releases.atom", 1)[0]
        if not p.path.startswith(repo + "/releases/tag/"):
            return None
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "", ""))

class _Plain(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)

def _plain(text, bound):
    parser = _Plain()
    parser.feed(text)
    parser.close()
    return " ".join(" ".join(parser.parts).split())[:bound]

def _text(item, tag):
    child = item.find(tag)
    return "".join(child.itertext()) if child is not None else ""

def parse_feed(source_id, body, *, stats=None):
    if source_id not in SOURCES or not isinstance(body, bytes) or len(body) > MAX_BYTES:
        raise ValueError("invalid source or feed exceeds byte limit")
    # Strict UTF-8 path constrains the parser; forbid declarations of any DTD/entity.
    xml = body.decode("utf-8-sig", errors="strict")
    if "\x00" in xml or re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", xml, re.I):
        raise ValueError("DTD/entity declarations are unsupported")
    root = ET.fromstring(xml)
    atom = "{http://www.w3.org/2005/Atom}"
    if root.tag == atom + "feed":
        children = root.findall(atom + "entry")
        is_atom = True
    elif root.tag == "rss" and root.find("channel") is not None:
        children = root.findall("channel/item")
        is_atom = False
    else:
        raise ValueError("unsupported XML feed root")
    if len(children) > MAX_ENTRIES:
        raise ValueError("feed exceeds entry limit")
    items = {}
    conflicts = set()
    for entry in children:
        if is_atom:
            link = next((a.get("href", "") for a in entry.findall(atom+"link") if a.get("rel", "alternate") == "alternate"), "")
            title = _text(entry, atom+"title")
            summary = _text(entry, atom+"summary") or _text(entry, atom+"content")
            # Atom 'updated' is not a publication claim.
            published = _text(entry, atom+"published")
        else:
            link = _text(entry, "link")
            title = _text(entry, "title")
            summary = _text(entry, "description")
            published = _text(entry, "pubDate")
        url = _canonical_url(link.strip(), source_id)
        if not url or not title.strip():
            continue
        data = dict(source_id=source_id, title=_plain(title, 300), url=url,
                    published_at=_date(published.strip()) if published.strip() else None,
                    summary=_plain(summary, 1000))
        if not data["title"]:
            continue
        ident = _sha(source_id + "\n" + url)
        data["id"] = ident
        data["content_sha256"] = _sha(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",",":")))
        if ident in conflicts:
            continue
        if ident in items and items[ident] != data:
            # Don't choose between conflicting representations of one identity.
            del items[ident]
            conflicts.add(ident)
            continue
        items[ident] = data
    if children and not items:
        raise ValueError("no valid first-party entries in nonempty feed")
    if stats is not None:
        stats.update(feed_entries=len(children), duplicate_conflicts=len(conflicts))
    return list(items.values())

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def _header(v):
    return v if isinstance(v, str) and len(v) < 512 and not re.search(r"[\r\n\x00]", v) else ""

def _direct_worker(source_id, etag, modified):
    url = SOURCES[source_id]
    hdr = {"User-Agent":"MontrealAI-FrontierRadar/1.0",
           "Accept":"application/atom+xml, application/rss+xml, application/xml, text/xml",
           "Accept-Encoding":"identity"}
    if etag: hdr["If-None-Match"] = _header(etag)
    if modified: hdr["If-Modified-Since"] = _header(modified)
    request = urllib.request.Request(url, headers=hdr, method="GET")
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        response = opener.open(request, timeout=ATTEMPT_SECONDS)
    except urllib.error.HTTPError as e:
        with e:
            return dict(status=e.code,retry_after=_header(e.headers.get("Retry-After"))), b""
    with response:
        if response.geturl() != url:
            raise ValueError("unexpected final URL")
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("compressed response unsupported")
        if response.headers.get_content_type() not in {
            "application/atom+xml","application/rss+xml","application/xml","text/xml"
        }:
            raise ValueError("unexpected response content type")
        if response.length is not None and response.length > MAX_BYTES:
            raise ValueError("feed exceeds byte limit")
        body = response.read(MAX_BYTES+1)
        if len(body) > MAX_BYTES:
            raise ValueError("feed exceeds byte limit")
        return dict(status=response.status,etag=_header(response.headers.get("ETag")),
                    modified=_header(response.headers.get("Last-Modified"))), body

def _fetch(source_id, etag, modified):
    # Process timeout bounds all stages including DNS, TLS and slow body reads.
    # No shell, no dynamic destination, no inherited process credentials sent.
    cmd = [sys.executable, "-I", str(Path(__file__).resolve()), "_fetch", source_id]
    # Keep platform-managed HTTPS egress/CA configuration, not arbitrary secrets.
    permitted = {"https_proxy", "no_proxy", "ssl_cert_file", "ssl_cert_dir", "systemroot"}
    env = {k:v for k,v in os.environ.items() if k.lower() in permitted}
    proc = subprocess.run(cmd, input=json.dumps([etag, modified]).encode(),
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                          timeout=FETCH_SECONDS, check=False, env=env)
    if proc.returncode != 0:
        raise ValueError("feed transport failed")
    head, sep, body = proc.stdout.partition(b"\n")
    if not sep or len(head)>2048 or len(body)>MAX_BYTES:
        raise ValueError("invalid transport envelope")
    return json.loads(head), body

_SCHEMA = """
CREATE TABLE IF NOT EXISTS radar_source_health (
 source_id TEXT PRIMARY KEY, status TEXT NOT NULL, last_attempt TEXT NOT NULL,
 last_success TEXT, failures INTEGER NOT NULL, next_attempt TEXT, etag TEXT,
 modified TEXT, detail TEXT, item_count INTEGER
);
CREATE TABLE IF NOT EXISTS radar_observations (
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL,
 published_at TEXT, summary TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
 content_sha256 TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS radar_observations_recent ON radar_observations(first_seen DESC,id ASC);
CREATE TABLE IF NOT EXISTS radar_observation_versions (
 id TEXT NOT NULL, content_sha256 TEXT NOT NULL, first_seen TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(id,content_sha256)
);
"""

@contextmanager
def _db(path):
    con = sqlite3.connect(path, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        con.executescript(_SCHEMA)
        with con:
            yield con
    finally:
        con.close()

def observations(db_path, *, limit=1000):
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError("invalid observation limit")
    with _db(db_path) as con:
        return [dict(r) for r in con.execute(
            "SELECT * FROM radar_observations ORDER BY first_seen DESC,id LIMIT ?", (limit,))]

def health(db_path):
    with _db(db_path) as con:
        return [dict(r) for r in con.execute("SELECT * FROM radar_source_health ORDER BY source_id")]

def _retry_at(now, failures, value):
    seconds = min(14400, 60 * 2 ** min(failures-1, 8))
    val = _header(value)
    if val.isascii() and val.isdecimal() and len(val) <= 8:
        seconds = max(seconds, min(int(val),86400))
    elif val:
        end = _date(val)
        if end:
            seconds = max(seconds, min(86400,(dt.datetime.fromisoformat(end)-now).total_seconds()))
    return _format(now+dt.timedelta(seconds=seconds))

def run(db_path, source_ids=None, *, now=None, transport=None):
    sources = list(SOURCES) if source_ids is None else list(source_ids)
    if len(sources) != len(set(sources)) or any(s not in SOURCES for s in sources):
        raise ValueError("unregistered or duplicate source")
    started = now if now is not None else dt.datetime.now(UTC)
    report = {"started_at":_format(started),"sources":[],"new_observations":[]}
    transfer = _fetch if transport is None else transport
    for source in sources:
        attempt = now if now is not None else dt.datetime.now(UTC)
        stamp = _format(attempt)
        with _db(db_path) as con:
            existing = con.execute("SELECT * FROM radar_source_health WHERE source_id=?", (source,)).fetchone()
        p = dict(existing) if existing else {}
        if p.get("next_attempt") and stamp < p["next_attempt"]:
            report["sources"].append({**p,"recorded_status":p["status"],"status":"backoff"})
            continue
        d = {"source_id":source,"last_attempt":stamp,"last_success":p.get("last_success"),
             "etag":p.get("etag"),"modified":p.get("modified"),"detail":None,"item_count":p.get("item_count")}
        items=[]; retry=None
        try:
            metadata, body = transfer(source,p.get("etag") or "",p.get("modified") or "")
            code=metadata["status"]
            retry=metadata.get("retry_after")
            if code == 304 and p.get("last_success"):
                d.update(status="not_modified",last_success=stamp,failures=0,next_attempt=None)
            elif code == 200:
                stats={}
                items=parse_feed(source, body, stats=stats)
                if stats["duplicate_conflicts"]:
                    d["detail"]=f'excluded {stats["duplicate_conflicts"]} conflicting duplicate identities'
                d.update(status="ok",last_success=stamp,failures=0,next_attempt=None,
                         etag=_header(metadata.get("etag")),modified=_header(metadata.get("modified")),
                         item_count=len(items))
            else:
                raise ValueError("unexpected HTTP status " + str(code) if type(code) is int else "invalid HTTP status")
        except (ValueError, ET.ParseError, OSError, subprocess.TimeoutExpired, KeyError, TypeError) as e:
            # Persist stable diagnostics, never feed content, URL params or raw exception messages.
            if isinstance(e, subprocess.TimeoutExpired):
                detail="hard transport deadline exceeded"
            elif isinstance(e, ValueError) and str(e).startswith("unexpected HTTP status ") and re.fullmatch(r"unexpected HTTP status [0-9]{3}",str(e)):
                detail=str(e)
            else:
                detail="bounded fetch or feed validation failed"
            fails=p.get("failures",0)+1
            d.update(status="error",failures=fails,next_attempt=_retry_at(attempt,fails,retry),detail=detail)
        with _db(db_path) as con:
            con.execute("BEGIN IMMEDIATE")
            previous=con.execute("SELECT last_attempt FROM radar_source_health WHERE source_id=?", (source,)).fetchone()
            if previous and previous["last_attempt"] > stamp:
                report["sources"].append({"source_id":source,"status":"superseded","last_attempt":stamp})
                continue
            con.execute("""INSERT OR REPLACE INTO radar_source_health VALUES
                (:source_id,:status,:last_attempt,:last_success,:failures,:next_attempt,:etag,:modified,:detail,:item_count)""",d)
            additions=[]
            for item in items:
                old=con.execute("SELECT first_seen,content_sha256 FROM radar_observations WHERE id=?", (item["id"],)).fetchone()
                row={**item,"first_seen":old["first_seen"] if old else stamp,"last_seen":stamp}
                con.execute("""INSERT OR REPLACE INTO radar_observations VALUES
                    (:id,:source_id,:title,:url,:published_at,:summary,:first_seen,:last_seen,:content_sha256)""",row)
                con.execute("INSERT OR IGNORE INTO radar_observation_versions VALUES (?,?,?,?)",
                            (item["id"],item["content_sha256"],stamp,json.dumps(item,sort_keys=True,ensure_ascii=False)))
                if not old or old["content_sha256"]!=item["content_sha256"]:
                    additions.append(row)
        report["new_observations"].extend(additions)
        report["sources"].append(d)
    return report

if __name__ == "__main__" and len(sys.argv)==3 and sys.argv[1]=="_fetch":
    try:
        etag,modified=json.loads(sys.stdin.buffer.read(2048))
        metadata, response=_direct_worker(sys.argv[2],etag,modified)
        sys.stdout.buffer.write(json.dumps(metadata).encode("ascii")+b"\n"+response)
    except Exception:
        sys.exit(1)
