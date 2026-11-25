"""Conventional source-native checks for the registered Atlas questions."""

import argparse
from datetime import datetime
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
from subprocess import check_output
from time import perf_counter, process_time

ROOT = Path(__file__).resolve().parent
CUTOFF = "2026-11-24T23:59:59Z"


def primary(name):
    return (ROOT / f"con-{name}.raw").read_bytes()


def within(value):
    return datetime.fromisoformat(value) <= datetime.fromisoformat(CUTOFF)


def normalized(parts):
    return " ".join("".join(parts).split())


class Tables(HTMLParser):
    def __init__(self, raw):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None
        self.feed(raw.decode())

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, text):
        if self.cell is not None:
            self.cell.append(text)

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append(normalized(self.cell))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def freecad():
    release = json.loads(primary("fc-tag"))
    tag = "26.3rc2"
    artifact_name = f"FreeCAD_{tag}-Linux-aarch64.AppImage"
    assert release["tag_name"] == tag and release["draft"] is False
    assert within(release["published_at"])
    db = sqlite3.connect(":memory:")
    with db:
        db.execute("CREATE TABLE assets(name TEXT PRIMARY KEY, status TEXT, created TEXT, digest TEXT)")
        db.executemany("INSERT INTO assets VALUES (?,?,?,?)", (
            (a["name"], a["state"], a["created_at"], a["digest"]) for a in release["assets"]
        ))
        asset, created, digest = db.execute(
            "SELECT name,created,digest FROM assets WHERE name=? AND status='uploaded' AND created<=?",
            (artifact_name,CUTOFF),
        ).fetchone()
    assert re.fullmatch(r"sha256:[0-9a-f]{64}",digest)
    return {"id":"fc-263rc2-arm", "verdict":"DOCUMENTED",
            "first_party_date_utc":release["published_at"][:10],
            "exact_scope_facts":{"tag":tag, "release_published_utc":release["published_at"],
              "channel":"prerelease / release candidate" if release["prerelease"] else "stable",
              "artifact":asset, "artifact_state":"uploaded", "artifact_created_utc":created,
              "artifact_declared_sha256":digest.removeprefix("sha256:")},
            "source_urls":[release["html_url"],release["url"]],
            "unsupported_claims":["Stable production release", "Installed or tested binary", "Artifact existed when the release was first published"],
            "action":"TEST"}


def e4s():
    pdf = check_output(["pdftotext", "-layout", str(ROOT/"con-e4s-pdf.raw"), "-"]).decode()
    text = " ".join(pdf.split())
    day = datetime.strptime(re.search(r"OR\., (\w+ \d+, \d{4})", text)[1], "%B %d, %Y").date().isoformat()
    version = re.search(r"GPU support is updated to CUDA (\d+\.\d+)", text)[1]
    named = re.search(r"NVIDIA CUDA \(([^)]+)\)", text)[1].replace(", and ", ", ").split(", ")
    assert day <= CUTOFF[:10] and "E4S 26.11 container images are now available for Ubuntu 24.04 LTS" in text
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE catalog(variant TEXT, machine TEXT, distro TEXT, source_ref TEXT)")
    db.execute("CREATE TABLE registry(tag TEXT, status TEXT, os TEXT, cpu TEXT, pushed TEXT, digest TEXT)")
    with db:
        db.executemany("INSERT INTO catalog VALUES (?,?,?,?)", (
            tuple(row[:4]) for row in Tables(primary("e4s-container")).rows if len(row) == 8
        ))
        for arch in ("80", "90", "120"):
            metadata = json.loads(primary("cuda"+arch))
            db.executemany("INSERT INTO registry VALUES (?,?,?,?,?,?)", (
                (metadata["name"], i["status"], i["os"], i["architecture"], i["last_pushed"], i["digest"])
                for i in metadata["images"]
            ))
        matches = db.execute("""SELECT variant, source_ref, pushed, digest FROM catalog
            JOIN registry ON source_ref = 'ecpe4s/e4s-cuda:' || tag
            WHERE machine='x86_64' AND distro='Ubuntu' AND os='linux' AND cpu='amd64'
            AND variant LIKE 'CUDA (%' AND status='active' AND pushed<=?
        """, (CUTOFF,)).fetchall()
    tags = {re.match(r"CUDA \((\w+),", variant)[1]: ref for variant, ref, _, _ in matches}
    assert set(tags) == set(named)
    return {"id":"e4s-2611-cuda24", "verdict":"DOCUMENTED", "first_party_date_utc":day,
            "exact_scope_facts":{"product":"E4S 26.11", "os":"Ubuntu 24.04 LTS",
              "cpu_architecture":"x86_64 (OCI linux/amd64)", "cuda_version":version,
              "named_nvidia_architectures":named,"exact_image_tags":tags,
              "linux_amd64_manifest_sha256":{ref.split(":")[1]:digest.removeprefix("sha256:") for _,ref,_,digest in matches},
              "registry_last_push_date_utc": max(pushed[:10] for _,_,pushed,_ in matches)},
            "source_urls":["https://e4s.io/news/NEWS_RELEASE_E4S_26.11.pdf","https://e4s.io/container-download/",
              *("https://hub.docker.com/v2/namespaces/ecpe4s/repositories/e4s-cuda/tags/" + tag.split(":")[1] for tag in tags.values())],
            "unsupported_claims":["Turing support for these image variants", "Local pull, runtime operation or speed", "One tag for all GPU architectures"],
            "action":"TEST"}


def section(raw, name):
    found = re.search(fr'<section\b[^>]*\bid="{name}"[^>]*>(.*?)</section>', raw, re.S)
    if found is None:
        raise ValueError(f"Section missing: {name}")
    return found[1]


def rocm():
    raw = primary("rocm-pinned")
    html = raw.decode()
    added = section(html, "expanded-amd-gpu-support")
    new_processors = re.findall(r">AMD (Ryzen [3579] (?:PRO )?\d+)\s*</a>", added)
    header = html.split('id="rocm-docs-core-article-info"',1)[1].split("These release notes",1)[0]
    day = re.search(r"\b(20\d{2}-\d\d-\d\d)\b",header)[1]
    assert "Applies to Linux and Windows" in header
    architecture = "gfx1103"
    apu_model = r"Ryzen [3579] (?:PRO )?\d+"
    hardware, framework = [], []
    for row in Tables(raw).rows:
        if len(row) >= 3 and architecture in row[2]:
            hardware.extend(re.findall(apu_model, row[1]))
        if len(row) == 4 and row[0] == "vLLM" and architecture in row[1]:
            framework.append(tuple(row))
    db = sqlite3.connect(":memory:")
    with db:
        db.execute("CREATE TABLE expanded(model TEXT PRIMARY KEY)")
        db.execute("CREATE TABLE gfx1103(model TEXT PRIMARY KEY)")
        db.execute("CREATE TABLE runtimes(framework TEXT, version TEXT, os TEXT, python TEXT)")
        db.executemany("INSERT INTO expanded VALUES (?)",[(key,) for key in new_processors])
        db.executemany("INSERT OR IGNORE INTO gfx1103 VALUES (?)",[(key,) for key in hardware])
        db.executemany("INSERT INTO runtimes VALUES (?,?,?,?)",framework)
        confirmed = [row[0] for row in db.execute("SELECT expanded.model FROM expanded JOIN gfx1103 USING(model) ORDER BY model")]
        versions = db.execute("SELECT version,os,python FROM runtimes WHERE framework='vLLM'").fetchall()
    assert day <= CUTOFF[:10] and confirmed == sorted(set(new_processors))
    version, platform, dependencies = versions[0]
    assert len(versions) == 1 and platform == "Linux"
    return {"id":"rocm-102-gfx1103", "verdict":"DOCUMENTED", "first_party_date_utc":day,
            "exact_scope_facts":{"product":"ROCm Core SDK 10.2.0","architecture":architecture,
              "new_ryzen_apus_count":len(confirmed),"new_amd_devices_count":len(confirmed)+len(re.findall(r">AMD Radeon PRO \w+\s*</a>",added)),
              "new_models":confirmed,"release_notes_operating_systems":["Windows","Linux"],
              "vllm_version":re.match(r"\d+\.\d+(?:\.\d+)?",version)[0],"vllm_row_os":platform,
              "vllm_row_requirements":dependencies,
              "host_condition":"Confirm model and OS, supported kernel, driver, Python/PyTorch and package matrix, then obtain an observed run."},
            "source_urls":["https://rocm.docs.amd.com/en/docs-10.2.0/about/release-notes.html",
              "https://rocm.docs.amd.com/en/docs-10.2.0/compatibility/compatibility-matrix.html"],
            "unsupported_claims":["All named models support every Linux distro or Windows release", "Native Windows vLLM from the Linux table", "Performance or operation on a specific host"],
            "action":"TEST"}


def nvidia():
    raw = primary("nvidia")
    html = raw.decode()
    day = datetime.strptime(re.search(r"Linux driver release date: (\d+/\d+/\d+)",html)[1],"%m/%d/%Y").date().isoformat()
    assert "620.70.10" in html and day <= CUTOFF[:10]
    db = sqlite3.connect(":memory:")
    with db:
        db.execute("CREATE TABLE boards(family_or_model TEXT, listed_model_or_family TEXT)")
        db.executemany("INSERT INTO boards VALUES (?,?)",(tuple(row) for row in Tables(raw).rows if len(row)==2))
        named = db.execute("SELECT listed_model_or_family FROM boards WHERE family_or_model='NVIDIA Turing'").fetchone()[0]
        other = [row[0] for row in db.execute("SELECT family_or_model FROM boards WHERE listed_model_or_family='NVIDIA Turing'")]
        titan = db.execute("""SELECT count(*) FROM boards
            WHERE upper(family_or_model) LIKE '%TITAN RTX%' OR upper(listed_model_or_family) LIKE '%TITAN RTX%'""").fetchone()[0]
    assert "titan rtx" not in html.casefold() and titan == 0
    return {"id":"nv-r620-titan", "verdict":"ABSTAIN", "first_party_date_utc":day,
            "exact_scope_facts":{"driver":"620.70.10","release_type":"Linux Data Center",
              "turing_boards":[name.strip() for name in named.split(",")],
              "other_turing_product_table_rows":other,
              "target_model_hits":titan,"host_operation_observed":False},
            "source_urls":["https://docs.nvidia.com/datacenter/tesla/tesla-release-notes-620-70-10/index.html",
              "https://www.nvidia.com/en-us/drivers/details/285695/"],
            "unsupported_claims":["TITAN RTX support inferred from Turing family membership", "Owner workstation driver operation", "General TITAN RTX incompatibility based on this omission"],
            "action":"HOLD"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cycle", type=int, choices=(1,2), required=True)
    cycle = parser.parse_args().cycle
    start, cpu = perf_counter(), process_time()
    rows = [freecad(), e4s()] if cycle == 1 else [rocm(), nvidia()]
    print(json.dumps({"rows":rows,"verification_runtime_wall_s":perf_counter()-start,
                      "python_cpu_s":process_time()-cpu},indent=2,sort_keys=True))
