"""Opt-in GitHub release radar for FRONTIER Ω, as investigation triggers only.

Reads bounded public metadata from the constructed GitHub API endpoint. A release
never proves newly feasible economics, credible buyers, verified tasks or earnings.
"""
from __future__ import annotations
import argparse
from datetime import date,datetime,timezone
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler

OWNER=re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z")
REPOSITORY=re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")
TAG=re.compile(r"[a-z][a-z0-9-]{1,63}\Z")


def validate_config(config):
    if type(config) is not dict or set(config)!={"schema","repositories"} or config["schema"]!="frontier-omega/github-release-sources/v1":
        raise ValueError("EXACT_PUBLIC_RELEASE_SOURCE_CONFIG_REQUIRED")
    repos=config["repositories"]
    if type(repos) is not list or not 1<=len(repos)<=32:
        raise ValueError("BOUNDED_ALLOWLISTED_REPOSITORIES_REQUIRED")
    seen=set()
    for item in repos:
        if type(item) is not dict or set(item)!={"repository","tags"}:
            raise ValueError("EXACT_REPOSITORY_AND_CAPABILITY_TAGS_REQUIRED")
        target=item["repository"]
        if type(target) is not str:
            raise ValueError("REPOSITORY_IDENTIFIER_REQUIRED")
        parts=target.split("/")
        if len(parts)!=2 or not OWNER.fullmatch(parts[0]) or not REPOSITORY.fullmatch(parts[1]) or target in seen:
            raise ValueError("SAFE_UNIQUE_GITHUB_REPOSITORY_REQUIRED")
        seen.add(target)
        tags=item["tags"]
        if type(tags) is not list or not 1<=len(tags)<=20 or len(tags)!=len(set(map(str,tags))) or any(type(t) is not str or not TAG.fullmatch(t) for t in tags):
            raise ValueError("FINITE_UNIQUE_CAPABILITY_TAGS_REQUIRED")
    return config


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError("RELEASE_REDIRECT_REFUSED")


def _fetch(endpoint):
    if not endpoint.startswith("https://api.github.com/repos/") or not endpoint.endswith("/releases/latest"):
        raise ValueError("PINNED_PUBLIC_GITHUB_ENDPOINT_REQUIRED")
    request=Request(endpoint,headers={"Accept":"application/vnd.github+json",
       "User-Agent":"FrontierOmega-OpportunitySensor/1"})
    with build_opener(_NoRedirect()).open(request,timeout=15) as response:
        if int(response.status)!=200:raise ValueError("RELEASE_SOURCE_HTTP_ERROR")
        raw=response.read(200001)
        if len(raw)>200000:raise ValueError("RELEASE_RECORD_TOO_LARGE")
    return json.loads(raw)


def poll(reservoir,config,*,fetch=None,as_of=None):
    validate_config(config)
    if as_of is None:as_of=datetime.now(timezone.utc).date().isoformat()
    if type(as_of) is not str or date.fromisoformat(as_of).isoformat()!=as_of:
        raise ValueError("EXACT_OBSERVATION_DAY_REQUIRED")
    fetch=fetch or _fetch
    # Preserve the first observed date through subsequent daily polls.
    known={row["id"]:row for row in reservoir.rows("frontiers")}
    records=[]
    for entry in config["repositories"]:
        repository=entry["repository"]
        endpoint="https://api.github.com/repos/"+repository+"/releases/latest"
        try:
            data=fetch(endpoint)
            if type(data) is not dict:
                raise ValueError("RELEASE_JSON_OBJECT_REQUIRED")
            tag=data.get("tag_name")
            link=data.get("html_url")
            if type(tag) is not str or not 0<len(tag)<=160 or type(link) is not str or not link.startswith("https://github.com/"+repository+"/releases/"):
                raise ValueError("RELEASE_REPOSITORY_PROVENANCE_MISMATCH")
            name=data.get("name") or tag
            body=data.get("body") or ""
            if type(name) is not str or type(body) is not str:
                raise ValueError("RELEASE_METADATA_TEXT_REQUIRED")
            fingerprint=hashlib.sha256(json.dumps(
               [repository,tag,name,body,link],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            ident="github-release-"+fingerprint[:36]
            observation={"schema":"frontier-omega/capability/v1",
               "id":ident,"title":("GitHub release: "+repository+" "+tag)[:1600],
               "observed_on":known[ident]["observed_on"] if ident in known else as_of,
               "description":("Release metadata observed; claimed capabilities NOT independently benchmarked. "+name+" "+body)[:1600],
               "tags":entry["tags"],
               "source_urls":[link,endpoint],
               "availability":"REPORTED"}
            receipt=reservoir.add(observation)
            known[ident]=observation
            records.append({"repository":repository,"release":tag,"added":receipt["added"],
                 "retests_queued":receipt["retests_queued"],"id":ident})
        except (ValueError,TypeError,KeyError,OSError,TimeoutError,ConnectionError) as error:
            records.append({"repository":repository,"status":"NO_CLAIM_NO_TRIGGER",
                            "error_type":type(error).__name__})
    return {"sources_checked":len(config["repositories"]),"receipts":records,
            "scope":"RELEASE_METADATA_ONLY_NO_TECHNICAL_OR_ECONOMIC_FEASIBILITY_ESTABLISHED",
            "financial_effects":0,"market_outreach":0}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--once",action="store_true")
    parser.add_argument("--poll-seconds",type=float,default=3600)
    args=parser.parse_args(argv)
    if not args.once and not 300<=args.poll_seconds<=86400:
        parser.error("Watch interval must be between five minutes and one day")
    from .core import Reservoir,load_file
    sources=validate_config(load_file(args.config))
    inventory=Reservoir(args.root)
    with inventory.lock():
        while True:
            # One writer owns BOTH inbox intake and source monitoring, avoiding
            # competing perpetual locks from two separate watch processes.
            inbox_receipts=inventory.ingest_inbox()
            report=poll(inventory,sources)
            report['inbox_processed']=len(inbox_receipts)
            print(json.dumps(report,sort_keys=True,ensure_ascii=False),flush=True)
            if args.once:break
            time.sleep(args.poll_seconds)


if __name__=="__main__":main()
