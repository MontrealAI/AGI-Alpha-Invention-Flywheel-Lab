"""Public metadata-only workload upper envelope. No serving, buyer, or finance."""
import argparse
from collections import Counter
from datetime import datetime, timedelta
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import resource
import shutil
import tarfile
import tempfile
import time
import urllib.request
import unittest

DATES = ("2026-06-01", "2026-06-07")
URL = "https://github.com/Azure/AzurePublicDataset/releases/download/ghcp-coding-agent-2026/date.{}.tar.gz"
CLASSES = ("first", "ambiguous", "same", "switch")


def timestamp(call):
    try:
        start = datetime.fromisoformat(call["timestamp"].replace("Z", "+00:00"))
        if start.tzinfo is None:
            return None, None
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
        return None, None
    try:
        duration = call["duration_ms"]
        if type(duration) not in (float, int) or duration < 0:
            return start, None
        return start, start + timedelta(milliseconds=duration)
    except (KeyError, TypeError, ValueError, OverflowError):
        return start, None


def valid_model(x):
    return isinstance(x, str) and bool(x.strip())


def classify(calls):
    intervals = [(timestamp(c), c) for c in calls]
    if any(start is None for (start, _), _ in intervals):
        return [("ambiguous", c) for c in calls]
    intervals.sort(key=lambda x: x[0][0])
    starts = Counter(start for (start, _), _ in intervals)
    out = []
    max_end = None
    unknown_end = False
    previous = None
    for (start, end), call in intervals:
        model = call.get("model")
        if (end is None or not valid_model(model) or starts[start] > 1
                or unknown_end or (max_end is not None and max_end > start)):
            kind = "ambiguous"
        elif previous is None:
            kind = "first"
        elif starts[previous[0]] > 1 or not valid_model(previous[1]):
            kind = "ambiguous"
        else:
            kind = "same" if model == previous[1] else "switch"
        out.append((kind, call))
        previous = (start, model)
        if end is None:
            unknown_end = True
        elif max_end is None or end > max_end:
            max_end = end
    return out


def tokens(call):
    t = call.get("tokens")
    if not isinstance(t, dict):
        return None
    p, c, o = (t.get(k) for k in ("prompt", "cached", "completion"))
    if any(type(x) is not int or x < 0 for x in (p, c, o)) or c > p:
        return None
    if "total" in t and (type(t["total"]) is not int or t["total"] != p + o):
        return None
    return p, c, o


def tally(rows, date):
    counts = {k: Counter(calls=0, prompt=0, cached=0, output=0, miss=0) for k in CLASSES}
    denominators = Counter(sessions=0, turns=0, calls=0, malformed_tokens=0)
    for row in rows:
        if not isinstance(row, dict) or row.get("date") != date or not isinstance(row.get("turns"), list):
            raise ValueError("UNEXPECTED_SESSION_SCHEMA_OR_DATE")
        denominators["sessions"] += 1
        for turn in row["turns"]:
            if not isinstance(turn, dict) or not isinstance(turn.get("llm_calls"), list):
                raise ValueError("UNEXPECTED_TURN_SCHEMA")
            calls = turn["llm_calls"]
            if any(not isinstance(c, dict) for c in calls):
                raise ValueError("UNEXPECTED_CALL_SCHEMA")
            denominators["turns"] += 1
            denominators["calls"] += len(calls)
            for kind, call in classify(calls):
                x = tokens(call)
                if x is None:
                    denominators["malformed_tokens"] += 1
                    continue
                p, c, o = x
                counts[kind].update(calls=1, prompt=p, cached=c, output=o, miss=p-c)
    total = sum(counts.values(), Counter())
    if total["calls"] + denominators["malformed_tokens"] != denominators["calls"]:
        raise AssertionError("CALL_CONSERVATION")
    if total["prompt"] != total["cached"] + total["miss"]:
        raise AssertionError("TOKEN_CONSERVATION")
    return {"denominators": dict(denominators), "classes": {k: dict(v) for k,v in counts.items()},
            "all": {k:total[k] for k in ("calls","prompt","cached","output","miss")}}


def envelope(aggregate):
    a, switch = aggregate["all"], aggregate["classes"]["switch"]
    out = []
    for q in (Fraction(0), Fraction(1,10), Fraction(1,2), Fraction(1)):
        for r in (1,4,10):
            baseline = a["miss"] + q*a["cached"] + r*a["output"]
            def ratio(m):
                x = (1-q)*m/baseline if baseline else None
                return None if x is None else {"exact": str(x), "decimal": float(x)}
            out.append({"q":str(q),"r":r,"switch_bound":ratio(switch["miss"]),
                        "all_call_bound":ratio(a["miss"])})
    return out


def download(date, path):
    request = urllib.request.Request(URL.format(date), headers={"User-Agent":"public-metadata-research/1"})
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(request, timeout=120) as src, path.open("xb") as dst:
        advertised = src.headers.get("Content-Length")
        if advertised and int(advertised) >= shutil.disk_usage(path.parent).free:
            raise OSError("DATASET_EXCEEDS_ACTUAL_FREE_DISK")
        while block := src.read(1024*1024):
            digest.update(block)
            dst.write(block)
            size += len(block)
    if advertised and size != int(advertised):
        raise ValueError("INCOMPLETE_DOWNLOAD")
    return {"bytes":size, "sha256":digest.hexdigest()}


def scan(path, date):
    if date not in DATES:
        raise ValueError("UNREGISTERED_DATE")
    with tarfile.open(path, "r:gz") as archive:
        names = []
        for member in archive.getmembers():
            p = PurePosixPath(member.name)
            if p.is_absolute() or ".." in p.parts:
                raise ValueError("UNEXPECTED_ARCHIVE_PATH")
            if member.name.endswith(".jsonl.gz"):
                if not member.isfile() or f"date={date}" not in p.parts:
                    raise ValueError("UNEXPECTED_SHARD_SCHEMA")
                names.append(member.name)
        if len(names) < 2 or len(set(names)) != len(names):
            raise ValueError("MISSING_OR_DUPLICATE_SHARDS")
        selected = sorted(names)[:2]
        shards = []
        def rows():
            for name in selected:
                # No filesystem extraction and no retained raw shards.
                f = archive.extractfile(name)
                if f is None:
                    raise ValueError("UNREADABLE_SHARD")
                with f, tempfile.TemporaryFile() as scratch:
                    h = hashlib.sha256()
                    n = 0
                    while block := f.read(1024*1024):
                        scratch.write(block)
                        h.update(block)
                        n += len(block)
                    scratch.seek(0)
                    count = 0
                    with gzip.GzipFile(fileobj=scratch) as stream:
                        for line in stream:
                            count += 1
                            yield json.loads(line)
                    shards.append({"name":name,"sha256":h.hexdigest(),"bytes":n,"sessions":count})
        data = tally(rows(),date)
    return {"selected_shards":shards, "aggregate":data, "price_envelopes":envelope(data)}


class Tests(unittest.TestCase):
    def call(self, sec, duration=100, model="A", prompt=10, cached=4):
        return {"timestamp":f"2026-06-01T00:00:{sec:02d}Z","duration_ms":duration,
                "model":model,"tokens":{"prompt":prompt,"cached":cached,"completion":2}}
    def test_sequence(self):
        calls=[self.call(0),self.call(1),self.call(2,model="B"),
               self.call(3,3000),self.call(4),self.call(7),self.call(7)]
        self.assertEqual([k for k,_ in classify(calls)],
                         ["first","same","switch","switch","ambiguous","ambiguous","ambiguous"])
    def test_unknown_timestamp(self):
        self.assertEqual([k for k,_ in classify([{},self.call(0)])],["ambiguous"]*2)
    def test_missing_end(self):
        a=self.call(0);del a["duration_ms"]
        self.assertEqual([k for k,_ in classify([a,self.call(1)])],["ambiguous"]*2)
    def test_tokens(self):
        self.assertIsNone(tokens(self.call(0,cached=11)))
        self.assertIsNone(tokens(self.call(0,prompt=True)))
    def test_accounting(self):
        date=DATES[0]
        x=tally([{"date":date,"turns":[{"llm_calls":[self.call(0),self.call(1,model="B"),
                        self.call(2,cached=11)]}]}],date)
        self.assertEqual(x["denominators"]["calls"],3)
        self.assertEqual(x["denominators"]["malformed_tokens"],1)
        self.assertEqual(x["all"]["miss"],12)
        self.assertEqual(x["classes"]["switch"]["miss"],6)
        for y in envelope(x):
            self.assertLessEqual(y["switch_bound"]["decimal"],y["all_call_bound"]["decimal"])
            if y["q"]=="1": self.assertEqual(y["switch_bound"]["decimal"],0)
    def test_zero(self):
        self.assertTrue(all(y["switch_bound"] is None for y in envelope(tally([],DATES[0]))))
    def test_schema(self):
        with self.assertRaises(ValueError):tally([{"date":"wrong","turns":[]}],DATES[0])
        with self.assertRaises(ValueError):scan(Path("not-used"),"wrong")
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"empty.tar.gz"
            with tarfile.open(p,"w:gz"):pass
            with self.assertRaisesRegex(ValueError,"MISSING_OR_DUPLICATE"):scan(p,DATES[0])


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--self-test",action="store_true")
    parser.add_argument("--date",choices=DATES)
    parser.add_argument("--receipt",type=Path)
    args=parser.parse_args()
    if args.self_test:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
        return 0 if result.wasSuccessful() else 1
    if args.date is None or args.receipt is None:
        parser.error("--date and --receipt are required")
    start=time.monotonic()
    cpu=time.process_time()
    receipt={"date":args.date,"source_url":URL.format(args.date),
             "source_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             "scope":"public metadata-only optimistic homogeneous-price bound",
             "actual_billing":None,"native_profit":None,"paid_commerce":False}
    try:
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"day.tar.gz"
            receipt["archive"]=download(args.date,path)
            receipt.update(scan(path,args.date))
        receipt["status"]="PASS"
    except Exception as e:
        # No source rows, identifiers, arbitrary exception payloads or credentials.
        receipt["status"]="FAILED"
        receipt["error_type"]=type(e).__name__
        if isinstance(e,urllib.error.HTTPError):receipt["http_status"]=e.code
        elif isinstance(e,ValueError) and str(e).isupper() and len(str(e))<100:
            receipt["error_code"]=str(e)
    finally:
        receipt["wall_seconds"]=time.monotonic()-start
        receipt["process_cpu_seconds"]=time.process_time()-cpu
        receipt["max_rss_kib"]=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        args.receipt.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
        print(json.dumps({"date":args.date,"status":receipt["status"],
                          "error_type":receipt.get("error_type")},sort_keys=True))
    return 0 if receipt["status"]=="PASS" else 1

if __name__=="__main__":
    raise SystemExit(main())
