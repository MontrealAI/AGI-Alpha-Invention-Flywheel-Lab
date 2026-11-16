"""Exact exposed-source calibration witnesses; not physical certification or finance."""
from __future__ import annotations
from decimal import Decimal, localcontext
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
SOURCE_REL="research/blue_sky064/public_calibration.json"
REG_REL="campaign/blue-sky-064/friction-probe/MIXED_REGISTRATION.json"
SOURCE_SHA256="7aedc8e4c3e7181e381055d3815378b3f5bfe7b5b9386fd5748803d495ab1ced"
REG_SHA256="6eece869fb53ed7d6977a88b01ce0ba78af6a5d6931aea9df99c51b4c6f348fa"
PROTOCOL="5db6e21a3cc17eabe392ff9aebba4749a75cc6d9"
SCHEMA="agi-alpha/blue-sky190-calibration-witness/v1"

class Refused(ValueError):
    pass

def unique(pairs):
    out={}
    for k,v in pairs:
        if k in out: raise Refused("DUPLICATE_JSON_KEY:"+k)
        out[k]=v
    return out

def pinned_json(path,sha):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>200000:
        raise Refused("BOUNDED_REGULAR_SOURCE_REQUIRED")
    raw=p.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=sha:
        raise Refused("PINNED_SOURCE_BYTES_CHANGED")
    try:
        return json.loads(raw,parse_float=Decimal,object_pairs_hook=unique)
    except (ValueError,UnicodeError,TypeError) as e:
        raise Refused("INVALID_SOURCE_JSON") from e

def decimal(x):
    if isinstance(x,bool) or not isinstance(x,(int,Decimal)):
        raise Refused("FINITE_DECIMAL_REQUIRED")
    d=Decimal(x)
    if not d.is_finite(): raise Refused("FINITE_DECIMAL_REQUIRED")
    return d

def rows_intervals(rows):
    if not isinstance(rows,(list,tuple)) or not 2<=len(rows)<=1000:
        raise Refused("BOUNDED_ROWS_REQUIRED")
    out=[]
    for index,row in enumerate(rows):
        if not isinstance(row,(list,tuple)) or len(row)!=4:
            raise Refused("FOUR_COLUMN_ROW_REQUIRED")
        a,ea,f,ef=map(decimal,row)
        if a<=0 or f<=0 or not(0<=ea<a) or ef<0:
            raise Refused("POSITIVE_AREA_FORCE_AND_VALID_ERRORS_REQUIRED")
        out.append(dict(index=index,a=a,ea=ea,f=f,ef=ef,
                        lo=max(Decimal(0),(f-ef)/(a+ea)),
                        hi=(f+ef)/(a-ea)))
    return out

def feasible(rows,q):
    q=decimal(q)
    if q<0: raise Refused("NONNEGATIVE_EXTRA_DISCREPANCY_REQUIRED")
    return (max(max(Decimal(0),(r["f"]-r["ef"]-q*r["f"])/(r["a"]+r["ea"])) for r in rows)
            <=min((r["f"]+r["ef"]+q*r["f"])/(r["a"]-r["ea"]) for r in rows))

def calculate(rows):
    with localcontext() as ctx:
        ctx.prec=60
        vals=rows_intervals(rows)
        lower=max(vals,key=lambda r:r["lo"])
        upper=min(vals,key=lambda r:r["hi"])
        q=Decimal(0)
        active=None
        for i in vals:
            for j in vals:
                numerator=(i["f"]-i["ef"])/(i["a"]+i["ea"])-(j["f"]+j["ef"])/(j["a"]-j["ea"])
                denominator=i["f"]/(i["a"]+i["ea"])+j["f"]/(j["a"]-j["ea"])
                candidate=numerator/denominator
                if candidate>q:
                    q,active=candidate,(i["index"],j["index"])
        conflict=lower["lo"]>upper["hi"]
        if conflict!=(q>0): raise Refused("ANALYTIC_CONFLICT_MISMATCH")
        if q>0 and not feasible(vals,q+Decimal("1e-50")):
            raise Refused("ANALYTIC_BOUNDARY_NOT_VERIFIED")
        return {
            "source_row_count":len(vals),
            "coefficient_intersection":[str(lower["lo"]),str(upper["hi"])],
            "origin_linear_constant_supported_by_authored_boxes":not conflict,
            "conflicting_row_pair":({
                "max_lower_row_zero_based":lower["index"],
                "min_upper_row_zero_based":upper["index"],
                "gap":str(lower["lo"]-upper["hi"])
            } if conflict else None),
            "minimal_extra_relative_force_error_q":str(q),
            "active_q_pair_zero_based":list(active) if active else None,
            "q_is_hypothetical_not_physical_confidence":True
        }

def analyze(fixture,reg):
    if fixture.get("schema")!="blue-sky064/public-calibration-fixture/v1" or fixture.get("license")!="CC-BY-4.0":
        raise Refused("ATTRIBUTED_PUBLIC_FIXTURE_REQUIRED")
    if reg.get("schema")!="friction064/mixed-hold-slide-probe/v1" or reg.get("families")!=["Batch1_R496","Batch2_R1543"] or decimal(reg["necessary_construction_target"]["increase_in_static_dynamic_ratio_at_least"])!=Decimal("0.05"):
        raise Refused("FROZEN_GEOMETRY_OR_TARGET_CHANGED")
    fams=fixture.get("calibration")
    if not isinstance(fams,list) or len(fams)!=3:
        raise Refused("ALL_SIX_SOURCE_BLOCKS_REQUIRED")
    blocks=[]
    for fam in fams:
        if set(fam.get("phases",{}))!={"s","d"}:
            raise Refused("SOURCE_PHASES_CHANGED")
        for phase in ("s","d"):
            group=fam["phases"][phase]
            forces,areas=group["force_rows"],group["area_rows"]
            if len(forces)!=len(areas):
                raise Refused("SOURCE_ROW_COUNT_MISMATCH")
            for f,a in zip(forces,areas):
                if len(f)!=4 or len(a)!=4 or f[:2]!=a[2:]:
                    raise Refused("SOURCE_PAIRED_ROW_MISMATCH")
            blocks.append({"family":fam["id"],"phase":phase,**calculate(forces)})
    if set(b["family"] for b in blocks)!={"Batch1_R496","Batch2_R507","Batch2_R1543"}:
        raise Refused("SOURCE_FAMILIES_CHANGED")
    unresolved=[b["family"]+"/"+b["phase"] for b in blocks if b["family"] in reg["families"] and not b["origin_linear_constant_supported_by_authored_boxes"]]
    return dict(schema=SCHEMA,protocol_commit=PROTOCOL,
                source_fixture_sha256=SOURCE_SHA256,
                source_registration_sha256=REG_SHA256,blocks=blocks,
                unresolved_selected_blocks=unresolved,
                decision="HOLD_INCONSISTENT_CALIBRATION_BOXES" if unresolved else "HOLD_UNVALIDATED_MIXED_TRANSFER",
                next_required_observation="Repeat conflicting source load rows under a single calibrated reference apparatus, quantify joint static/dynamic coverage, then validate manufactured mixed interface at withheld loads, speeds and wear against capable passive and active controls.",
                scope="Exposed publisher numerical rows and a hypothetical origin-linear law, not a joint confidence region or physically validated friction ratio; q is NOT permission to inflate measurements.",
                new_physical_instrument_qualified=False,real_paid_commerce=False,
                trailing_365_profit_usd=None,whole_campaign_model_host_billing_usd=None)

def run(output,root=ROOT):
    p=Path(output)
    if not p.is_absolute() or p.exists() or p.is_symlink():
        raise Refused("CREATE_ONLY_ABSOLUTE_OUTPUT_REQUIRED")
    wall,cpu=time.perf_counter(),time.process_time()
    result=analyze(pinned_json(root/SOURCE_REL,SOURCE_SHA256),pinned_json(root/REG_REL,REG_SHA256))
    result["wall_seconds"]=round(time.perf_counter()-wall,6)
    result["self_cpu_seconds"]=round(time.process_time()-cpu,6)
    p.parent.mkdir(parents=True,exist_ok=True)
    with os.fdopen(os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o644),"w") as fp:
        json.dump(result,fp,indent=2,sort_keys=True,allow_nan=False)
        fp.write("\n");fp.flush();os.fsync(fp.fileno())
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",required=True,type=Path)
    r=run(p.parse_args().output)
    print(json.dumps({"decision":r["decision"],"unresolved":r["unresolved_selected_blocks"]},sort_keys=True))
    return 0

if __name__=="__main__":
    sys.exit(main())
