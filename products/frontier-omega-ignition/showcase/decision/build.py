"""Build the standalone public decision exhibit from registered and rechecked public evidence."""
import argparse
import base64
import io
import json
from pathlib import Path
import sys
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parents[1]
sys.path.insert(0, str(PRODUCT))
from showcase.build import csp_hash, sha
from endpoint_lab.decide import decide
from endpoint_study.reference import MANIFEST, connect, selection, verify

LAB = PRODUCT / "endpoint_lab"
STUDY = PRODUCT / "endpoint_study"
NUMERIC = PRODUCT / "numeric_study"


def json_file(path):
    return json.loads(path.read_bytes())


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()


def sensitivity(contracts, observation):
    recorded = observation["rate_sensitivity"]
    rows = []
    distinct = {}
    with connect() as db:
        for rate in range(1, recorded["rate_count"] + 1):
            loads = []
            for metric in ["reported_tps_per_user", "inverse_p90_tpot"]:
                contract = dict(contracts["interactive_deepseek"], rate_metric=metric, min_tps_per_user=str(rate))
                matches = selection(contract, db)["selected"]
                eligible_loads = {point["concurrency"] for point in matches}
                if len(eligible_loads) > 1:
                    raise ValueError("Highest supported load is ambiguous.")
                loads.append(next(iter(eligible_loads), None))
            rows.append(loads)
            if loads[0] != loads[1]:
                distinct[rate] = loads
    declared = {rate: [next(iter(r["reported_concurrency"]), None), next(iter(r["inverse_p90_concurrency"]), None)]
                for r in recorded["intervals"] for rate in range(r["start_tok_s"], r["end_tok_s"] + 1)}
    if (distinct != declared or len(distinct) != recorded["thresholds_with_different_choice"]
            or not observation["pass"] or recorded["disagreements"] or recorded["candidate_sql_comparisons"] != 2 * len(rows)):
        raise ValueError("Sensitivity replay differs from the registered observation.")
    return {"rows": rows, "different": len(distinct), "comparisons": recorded["candidate_sql_comparisons"]}


def assemble():
    public = json_file(LAB / "evidence/public.json")
    if public["reports_sha256"] != sha((LAB / "reports.json").read_bytes()):
        raise ValueError("Source projection differs from recorded decisions.")
    if public["sources"] != json_file(LAB / "reports.json")["sources"]:
        raise ValueError("Publication changed the measurements.")
    contracts = json_file(STUDY / "contracts.json")
    if list(contracts) != [s["id"] for s in public["scenarios"]]:
        raise ValueError("Registered scenario set differs.")
    files = {p.name:p.read_bytes() for p in
             [LAB/"decide.py", LAB/"reports.json", LAB/"README.md", STUDY/"contracts.json",
              STUDY/"reference.py", STUDY/"REGISTRATION.md", STUDY/"SENSITIVITY.md"]}
    observed = json_file(STUDY / "OBSERVATION.json")
    public["sensitivity"] = sensitivity(contracts, observed)
    model_file = NUMERIC / "model_observation/observation.json"
    numeric = json_file(NUMERIC / "RESULTS.json")
    if sha(model_file.read_bytes()) != numeric["model_observation_sha256"]:
        raise ValueError("Model observation identity changed.")
    public["execution"] = {"endpoint": observed["execution"], "numeric_model": json_file(model_file)}
    files["ND02-MODEL-CALLS.json"] = model_file.read_bytes()
    files["PRESENT.md"] = (HERE / "PRESENT.md").read_bytes()
    files["EP01-OBSERVATION.json"] = (STUDY / "OBSERVATION.json").read_bytes()
    for source, name in [(NUMERIC / "RESULTS.json", "ND02-RESULTS.json"),
                         (NUMERIC / "AUDIT.json", "ND02-AUDIT.json"),
                         (NUMERIC / "RECOVERY.json", "ND02-RECOVERY.json"),
                         (PRODUCT / "reader_trial/QUALIFICATION.json", "RR02-QUALIFICATION.json"),
                         (PRODUCT / "opportunity_field/field.json", "OPPORTUNITIES.json")]:
        files[name] = source.read_bytes()
    source_dir = STUDY / "sources"
    manifest = (source_dir / "manifest.json").read_bytes()
    if sha(manifest) != MANIFEST:
        raise ValueError("Registered full-table manifest changed.")
    files["sources/manifest.json"] = manifest
    for report in json.loads(manifest):
        name = report["table_file"]
        if name != report["id"] + ".csv" or Path(name).name != name:
            raise ValueError("Unexpected source-table filename.")
        raw = (source_dir / name).read_bytes()
        if sha(raw) != report["table_sha256"]:
            raise ValueError("Registered source table changed.")
        files["sources/" + name] = raw
    files["observations/independent-sql.json"] = encoded({
        key: case["reference"] for key, case in observed["cases"].items()
    })
    previous = PRODUCT.parents[1] / "docs/frontier-omega-ignition/continuation"
    for name in ["FRONTIER_IGNITION.html", "PAIRING_LAB.html"]:
        files[name] = (previous / name).read_bytes()
    for sc in public["scenarios"]:
        key = sc["id"]
        contract = contracts[key]
        receipt = decide(contract)
        verify(contract, receipt)
        summary = sc["result"]
        if (sc["requirement"] != contract or summary["eligible_count"] != len(receipt["eligible"])
                or summary["excluded_count"] != len(receipt["excluded"])
                or any(v != receipt[k] for k,v in summary.items() if k not in {"eligible_count","excluded_count"})):
            raise ValueError("Public outcome no longer matches its replay: " + key)
        files[f"cases/{key}.json"] = encoded(contract)
        files[f"observations/{key}.json"] = encoded(receipt)
    files["REPRODUCE.txt"] = (
        "FRONTIER Ω IGNITION | Endpoint Lab\n"
        "Python 3, standard library only. From this directory, use a fresh output path.\n"
        "Python 3 et sa bibliothèque standard. Depuis ce dossier, choisissez un nouveau fichier de sortie.\n\n"
        "python3 decide.py --contract cases/interactive_gpt.json --output new-decision.json\n"
        "python3 reference.py --contract cases/interactive_gpt.json --receipt new-decision.json\n\n"
        "Select another case from cases/, or edit a copy. Each receipt records the exact contract and reports.\n"
        "Choisissez un autre dossier d’essai dans cases/ ou modifiez une copie des exigences.\n"
        "Each selected point is a published observation. An actual deployment requires separate evidence.\n"
        "Chaque point retenu est une observation publiée. Une mise en service exige des preuves distinctes.\n"
    ).encode()
    buffer = io.BytesIO()
    with ZipFile(buffer,"w",compression=ZIP_DEFLATED,compresslevel=9) as z:
        for name,content in sorted(files.items()):
            item = ZipInfo(name,(2026,11,17,0,0,0))
            item.compress_type=ZIP_DEFLATED
            item.external_attr=0o100644 << 16
            item.create_system=3
            z.writestr(item,content,compresslevel=9)
    blob=buffer.getvalue()
    return public, {"bytes":base64.b64encode(blob).decode("ascii"), "sha256":sha(blob)}


def render():
    public, archive = assemble()
    numeric = json_file(NUMERIC / "RESULTS.json")
    audit = json_file(NUMERIC / "AUDIT.json")
    primary = numeric["tables"]["publication"]["model"]
    if (not primary["accepted"] or primary["correct_cells"] != audit["publication"]["model"]["independently_matched_cells"]):
        raise ValueError("Numerical publication and independent audit disagree.")
    reader = json_file(PRODUCT / "reader_trial/QUALIFICATION.json")
    if reader["actual_participants"] != 0 or reader["reader_time"] is not None:
        raise ValueError("New beneficiary observations require updating the public claim.")
    field=json_file(PRODUCT / "opportunity_field/field.json")
    if (len(field["opportunities"]) != 6 or sum(c["selected"] for c in field["opportunities"]) != 1
            or sum(c["overlooked"] for c in field["opportunities"]) != 1):
        raise ValueError("Invalid opportunity field.")
    recovery = json_file(NUMERIC / "RECOVERY.json")
    if (not recovery["accepted"] or not recovery["footnotes_match"] or recovery["additional_model_calls"] != 0
            or recovery["original_results_sha256"] != sha((NUMERIC / "RESULTS.json").read_bytes())):
        raise ValueError("Numerical recovery differs from its registered observation.")
    data = dict(public, archive=archive, field=field, numeric=numeric, recovery=recovery,
                reader_count=reader["actual_participants"], numeric_audit=audit, copy=json_file(HERE/"copy.json"))
    raw=json.dumps(data,ensure_ascii=False,allow_nan=False,separators=(",",":")).replace("<","\\u003c")
    css=(HERE/"style.css").read_text()
    script=(HERE/"app.js").read_text()
    csp=("default-src 'none'; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; "
         "script-src "+csp_hash(script)+"; style-src "+csp_hash(css))
    page=(HERE/"index.html").read_text()
    for token,value in [("@@CSS@@",css),("@@DATA@@",raw),("@@APP@@",script),("@@POLICY@@",csp)]:
        if page.count(token)!=1: raise ValueError("Invalid template: "+token)
        page=page.replace(token,value)
    return page


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    args=parser.parse_args()
    data=render().encode()
    args.output.write_bytes(data)
    print(sha(data),args.output)
