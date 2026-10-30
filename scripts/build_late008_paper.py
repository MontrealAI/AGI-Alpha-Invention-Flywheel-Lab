"""Append-only late-results supplement from one exact published source freeze.

This document builder reads Git objects and compiles a paper. It performs no
scientific/data experiment and does not modify either earlier paper.
"""
import argparse
import datetime as dt
import hashlib
import html
import json
from pathlib import Path
import re
import resource
import subprocess
import time

BASE = "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"
PRIOR_MEASURED_PAPER_CPU = 15.462157


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tex(value):
    return "".join({"\\":r"\textbackslash{}", "&":r"\&", "%":r"\%", "$":r"\$", "#":r"\#", "_":r"\_", "{":r"\{", "}":r"\}", "~":r"\textasciitilde{}", "^":r"\textasciicircum{}"}.get(c,c) for c in str(value))


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True,type=Path)
    p.add_argument("--source-ref",required=True)
    p.add_argument("--inputs",required=True)
    p.add_argument("--self-path",required=True)
    p.add_argument("--output",required=True,type=Path)
    args=p.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}",args.source_ref):
        raise ValueError("Exact public source commit required")
    resource.setrlimit(resource.RLIMIT_CPU,(580,580))
    resource.setrlimit(resource.RLIMIT_AS,(2147483648,2147483648))
    start=time.monotonic();started=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    root,out=args.repo.resolve(),args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    consumed={}
    def raw(path):
        r=subprocess.run(["git","show",args.source_ref+":"+path],cwd=root,capture_output=True)
        if r.returncode:raise ValueError("Absent frozen input: "+path)
        consumed[path]={"sha256":sha(r.stdout),"bytes":len(r.stdout)}
        return r.stdout
    if raw(args.self_path)!=Path(__file__).read_bytes():raise ValueError("Executing builder differs from public source")
    cfg=json.loads(raw(args.inputs));paths=cfg["records"]
    data={k:json.loads(raw(v)) for k,v in paths.items()}
    for path in cfg["support"]:raw(path)
    for path in cfg["earlier_papers"]:raw(path)
    ref=args.source_ref;link=lambda path:BASE+"/blob/"+ref+"/"+path
    ids={k:"R"+str(i+1) for i,k in enumerate(paths)}
    original=data["coordinate_result"];review=data["coordinate_review"]
    fresh=data["downloaded_numerical"];field=data["field_reproduction"]
    aliases=data["alias_result"];cost=data["cost_snapshot"];ledger=data["cost_journal"]
    outer=data["downloaded_receipt"];allocation=data["allocation"]
    assert review["all_checks_passed"] and fresh["separate_review"]["all_checks_passed"]
    assert fresh["restored"]["all_original_hashes_match"] and fresh["source_bytes_unchanged"]
    assert all(r["same_bytes"] for r in field)
    assert aliases["all_records_retained"] and all(r["duplicate_pairs"]==0 and r["conflicting_label_groups"]==0 for r in aliases["results"].values())
    assert cost["qualified_simulated_commercial_earnings_microUSD"]==0
    pages=[]
    def page(title):b=[];pages.append((title,b));return b
    def para(b,text,*refs):b.append(("p",text,refs))
    def table(b,heads,rows):b.append(("table",(heads,rows),[]))
    def code(b,text):b.append(("code",text,[]))

    b=page("Coordinate repair: computation fixed, useful feature claim still fails")
    para(b,"This append-only supplement extends the historical and progress papers without rewriting them. It reports completed late constructions and public-package execution. MISSION NOT COMPLETE at this source freeze; the original overnight window ends "+allocation["end_utc"]+". No final-window closeout, new scientific confirmation or budget reset is claimed.","allocation")
    manifest=data["coordinate_manifest"]
    para(b,"The frozen coordinate package has "+str(len(manifest["files"]))+" manifest entries. Its repair source is "+original["source_sha256"][:12]+", and its independent checker is "+review["verifier_source_sha256"][:12]+". Explicit source/target sample centers replace endpoint-aligned zoom, while the complete old affine map retains its original centroids. Both faces and three arms remain: old field transported to corrected physical centers, fixed old affine evaluated there, and the unchanged ordinary registration routine refitted. This is developer-written conventional repair on exposed data.","coordinate_manifest","coordinate_result","coordinate_review")
    ramp=max(r["repaired_max_error_mm"] for r in original["ramps"])
    para(b,"Physical-coordinate ramps now match the declared target centers to %.4g mm numerical discrepancy. This proves processing-grid consistency, not physical instrument accuracy. The table compares mean absolute height disagreement in mm on identical corrected physical points; no index-only or changing-mask gain is substituted."%ramp,"coordinate_result")
    rows=[]
    for row in original["rows"]:
        q=row["common_physical_grid"]
        rows.append([row["side"],str(q["refit"]["overlap_n"]),"%.9f"%q["old_transported"]["mae_mm"],"%.9f"%q["fixed_old_transform"]["mae_mm"],"%.9f"%q["refit"]["mae_mm"],"%.9f"%q["refit"]["zero_plane_mae_mm_same_overlap"]])
    table(b,["Face","Common n","Old transported","Fixed old affine","Refit","Zero plane"],rows)
    maximum=next(r for r in original["rows"] if r["side"]=="max")
    own=maximum["refit_metrics"];deep=own["strata"][0]
    para(b,"The max-face refit is slightly worse on the common cohort and the featureless plane still wins. On its own overlap, refit MAE is %.9f mm at %d/%d coverage; the below-minus0.1 mm diagnostic retains only %d/%d = %.2f%%. That depth group is not a true pore mask or a newly accepted customer cohort. Corrected reference locations/missingness differ from old ones; interpolation order and refitting cannot be isolated as physical accuracy gains."%(own["mae_mm"],own["overlap_n"],own["reference_n"],deep["overlap_n"],deep["reference_n"],100*deep["coverage"]),"coordinate_result","coordinate_review")
    para(b,"The reviewer reconstructs coordinates, full affine maps, fields, masks and arithmetic without candidate imports or registration reoptimization. Same host/model family/libraries mean procedural separation, not external certification. Independent calibration, pore truth, internal geometry and unseen specimens remain missing.","coordinate_review")

    b=page("All 828 recorded inputs and actual downloaded numerical qualification")
    para(b,"The paired fuel-cell diagnostic retains all %d released records. One view follows the published nine-channel/final100-sample recipe; the other retains all ten channels and180 samples. Only signed zero is canonicalized. Hash groups require exact value equality before label comparison; no rounding, nearest-neighbor equivalence, fitted residual or favorable cohort is used. No predictor is trained and no downloaded model is deserialized."%aliases["cohort_records"],"alias_protocol","alias_result")
    table(b,["Frozen input view","Records / unique groups","Duplicate pairs","Conflicting groups"],[[label,str(r["records"])+" / "+str(r["unique_input_groups"]),str(r["duplicate_pairs"]),str(r["conflicting_label_groups"])] for key,label in [("published9x100","Published9x100"),("all10x180","All10x180")] for r in [aliases["results"][key]]])
    para(b,"No exact recorded-input alias witness is found. This does not prove physical identification: continuous noisy inputs can all be distinct while unobserved ambiguities remain. Source row pairing is not independent acquisition-clock validation. Raw records expose different cell/stack targets, incomplete row mapping, and time-recording/spectral examples from different dates; they cannot be manufactured into same-system repeats or a noise bound. The physical gate remains a clock/site/frequency map plus independently characterized same-system repeatability.","alias_result","alias_gate")
    archive=data["archive_integrity"]
    para(b,"The earlier downloaded data-archive check at "+archive["source_commit"][:12]+" verifies Git blobs and lossless field assembly only; it is not numerical runtime qualification. The later run downloads source "+fresh["source_commit"][:12]+" ("+str(fresh["source_files"])+" files) and data "+fresh["data_commit"][:12]+" ("+str(fresh["data_files"])+" files), verifies every Git blob first, restores all "+str(fresh["restored"]["restored_original_files"])+" original hashes, then actually executes the coordinate repair and separate fixed checker. Those numerical checks pass with source bytes unchanged.","archive_integrity","downloaded_numerical")
    para(b,"Fresh min/max field NPZ hashes equal the archived repaired fields. Full RESULT files are not byte-identical: the original "+consumed[paths["coordinate_result"]]["sha256"][:12]+" and fresh "+consumed[paths["fresh_coordinate_result"]]["sha256"][:12]+" include different actual timestamps/resource measurements. Identical source/checker/input identity and independently checked numerical outcomes must not be confused with identical receipt bytes.","field_reproduction","coordinate_result","fresh_coordinate_result")
    para(b,"The enclosing replay receipt records %.6f waited-child CPU-seconds and %.9f supervisor CPU-seconds; nested restore/repair/check phases are not added again. They remain inside the existing300-second reservation with no refund. The wrapper is a trusted-command resource receipt, not an exact full-process-group meter, arbitrary native sandbox, physical validation or commercial qualification."%(outer["waited_cpu_seconds"],outer["supervisor_cpu_seconds"]),"downloaded_receipt","cost_snapshot")
    if "ci" in data:
        ci=data["ci"]
        para(b,"The recorded "+str(len(ci["workflows"]))+" exact-head workflows at "+ci["source_ref"][:12]+" report "+", ".join(w["conclusion"] for w in ci["workflows"])+". The earlier56dc legacy SIGINT startup failure remains preserved and is not a demonstrated source fix merely because a later timing-sensitive probe passes.","ci","legacy_ci")
    else:
        para(b,"The known56dc overall legacy SIGINT-startup qualification failure remains preserved. Separate successful construction checks do not erase it. This supplement makes no unstated all-green claim or claim that unchanged legacy code was repaired.","legacy_ci")

    b=page("Complete-cost boundary, mission links and the next evidence gate")
    reserved=cost["conservative_reserved_CPU_seconds"]
    para(b,"The latest included journal has %d events and reserves %d experiment / %d verification-publication CPU-seconds against the original %d / %d ceilings. These are conservative accounting charges, not observed complete CPU or money. All %d lifecycle monetary categories lack measured finite upper bounds; complete profit, deployment cost recovery and investment NPV remain unknown. Supported buyer participation includes q=0. Posted substitute prices are not demand, avoided cost or our revenue."%(ledger["events"],reserved["experiment"],reserved["verification_publication"],ledger["original_CPU_ceilings"]["experiment"],ledger["original_CPU_ceilings"]["verification_publication"],len(cost["all9_complete_cost_categories"])),"cost_journal","cost_snapshot")
    table(b,["Mission link","Decision within the recorded scope"],[
        ["Enabling capability","NOT ESTABLISHED: processing and finite-model instruments execute; consequential new means unproved."],
        ["Technical advantage","NOT ESTABLISHED: known methods tie/provide the lever; plane and full-view witnesses defeat proxies."],
        ["Complete-cost profitability","NOT ESTABLISHED: no admitted same-cohort negative-to-positive complete-cost result."],
        ["Investment attractiveness","NOT ESTABLISHED: full incremental NPV unknown versus strongest outside option/non-entry."],
        ["AGI ALPHA value capture","CONDITIONAL: service scenario only; no independently calibrated purchase or enforceable revenue."],
        ["Unrestricted simulated earnings","VERIFIED: ZERO qualified earned funds; deposits/reserve releases are not earnings."],
        ["Earned-funded construction","NOT ESTABLISHED: current construction uses original authorized resources."],
        ["Fresh successor advantage","NOT ESTABLISHED: actual retained biological use ties ordinary reuse/reset; no attributable fresh benefit."],
    ])
    para(b,"Earlier failures remain: biological plans and all64 geothermal designs tie strong ordinary routes; native rotational CAD remains unqualified; pair-separating XCT views fail the feature-range consequence, and a full120 feasible pair defeats the fixed0.005 target under its declared model. Existing dynamic EIS already supplies the broad operando lever. No later repair turns those results into invention, physical qualification or commercial success.")
    para(b,"The next executable evidence gate is a fixed consequential feature/response obligation, reconstructed same-system acquisition timing/site/frequency mapping and independent calibration/repetition bounds. Only then can equal-input strong complete alternatives be challenged and a distinguishing active intervention or orthogonal measurement be admitted. More threshold tuning, nearest-input grouping or a synthetic world cannot supply the missing physical reference. All cases remain exposed development; no protected confirmation, real commerce, paid use or error-budget reset is claimed.","alias_gate","cost_snapshot")
    b.append(("refs",None,[]))
    code(b,"\n".join(["python3 scripts/build_late008_paper.py --repo . --source-ref "+ref+" \\",
        "  --inputs docs/overnight008-late/SOURCE_INPUTS.json \\",
        "  --self-path scripts/build_late008_paper.py --output /tmp/late-paper-NEW"]))

    snapshot=sha(json.dumps(consumed,sort_keys=True,separators=(",",":")).encode())
    source_time=subprocess.run(["git","show","-s","--format=%cI",ref],cwd=root,capture_output=True,check=True).stdout.decode().strip()
    manifest={"schema":"agi-alpha/late008-source-manifest/v1","source_ref":ref,"source_commit_time":source_time,"created_utc":started,"consumed_files":len(consumed),"snapshot_sha256":snapshot,"executing_builder_matches_source":True,"all_inputs_read_from_exact_git_objects":True,"files":dict(sorted(consumed.items())),"excludes":"Generated document outputs are excluded to avoid recursion.","scope":"Append-only ongoing supplement, not final night closeout or numerical rerun."}
    (out/"SOURCE_SHA256.json").write_text(json.dumps(manifest,indent=2)+"\n")
    title="Late Results Supplement / AGI ALPHA Overnight008"
    metadata="Source freeze "+ref+"; commit time "+source_time
    tb=[r"\documentclass[10pt,letterpaper]{article}",r"\usepackage[margin=.72in]{geometry}",r"\usepackage[T1]{fontenc}",r"\usepackage{lmodern,microtype,booktabs,longtable,array,xurl,listings,fancyhdr}",r"\usepackage[breaklinks=true,colorlinks=true,urlcolor=blue!55!black,linkcolor=black]{hyperref}",r"\pagestyle{fancy}\fancyhf{}\fancyhead[L]{\small AGI ALPHA / append-only late results}\fancyfoot[C]{\thepage}\setlength{\headheight}{14pt}",r"\setlength{\parindent}{0pt}\setlength{\parskip}{.38em}\setlength{\emergencystretch}{2em}\setlength{\tabcolsep}{4pt}\renewcommand{\arraystretch}{1.12}",r"\lstset{basicstyle=\ttfamily\scriptsize,breaklines=true,columns=fullflexible,keepspaces=true,showstringspaces=false}",r"\begin{document}",r"{\Large\bfseries "+tex(title)+r"}\par",r"\footnotesize "+tex(metadata)+r"\par",r"Snapshot SHA256: \texttt{"+snapshot+r"}\par\normalsize",r"\textbf{Ongoing source-bound checkpoint. MISSION NOT COMPLETE.}\par"]
    md=["# "+title,"","**Ongoing source-bound checkpoint. MISSION NOT COMPLETE.**","",metadata,"","Snapshot SHA256: `"+snapshot+"`",""]
    hb=['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>body{font:17px/1.55 system-ui,sans-serif;color:#17243a;background:#f3f6fa;margin:0}main{max-width:1050px;background:white;margin:28px auto;padding:36px 44px;border-top:5px solid #284f84}h1{line-height:1.15}h2{margin-top:2em}a{color:#284f84;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%;font-size:.86rem}th,td{text-align:left;vertical-align:top;padding:8px;border-bottom:1px solid #d5deea}.scroll{overflow-x:auto}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf2fa;padding:14px;font-size:.8rem}.meta{font-size:.8rem}.status{padding:12px;background:#fff0df}@media(max-width:700px){main{margin:0;padding:24px}}</style></head><body><main><h1>'+html.escape(title)+'</h1><p class="status"><strong>Ongoing checkpoint. MISSION NOT COMPLETE.</strong></p><p class="meta">'+html.escape(metadata)+'<br>Snapshot SHA256: '+snapshot+'</p>']
    for page_index,(heading,blocks) in enumerate(pages):
        if page_index:tb.append(r"\newpage")
        tb.append(r"\section*{"+tex(heading)+"}");md += ["## "+heading,""];hb.append("<h2>"+html.escape(heading)+"</h2>")
        for kind,value,refs in blocks:
            if kind=="p":
                rs=lambda k:"["+ids[k]+"]"
                tb.append(tex(value)+" "+" ".join(r"\href{"+link(paths[k])+"}{"+rs(k)+"}" for k in refs)+r"\par")
                md += [value+" "+" ".join(rs(k)+"("+link(paths[k])+")" for k in refs),""]
                hb.append("<p>"+html.escape(value)+" "+" ".join('<a href="'+html.escape(link(paths[k]),quote=True)+'">'+rs(k)+'</a>' for k in refs)+"</p>")
            elif kind=="table":
                heads,rows=value
                widths={2:[.27,.68],4:[.27,.29,.17,.18],6:[.065,.11,.18,.18,.18,.14]}[len(heads)]
                tb += [r"\begingroup\small\begin{longtable}{"+"".join(r">{\raggedright\arraybackslash}p{"+str(w)+r"\linewidth}" for w in widths)+r"}\toprule"," & ".join(r"\textbf{"+tex(x)+"}" for x in heads)+r"\\\midrule\endhead"]
                tb += [" & ".join(tex(x) for x in row)+r"\\" for row in rows];tb.append(r"\bottomrule\end{longtable}\endgroup")
                md += ["| "+" | ".join(heads)+" |","| "+" | ".join("---" for _ in heads)+" |"]+["| "+" | ".join(str(x) for x in row)+" |" for row in rows]+[""]
                hb.append('<div class="scroll"><table><thead><tr>'+"".join("<th>"+html.escape(x)+"</th>" for x in heads)+'</tr></thead><tbody>'+"".join("<tr>"+"".join("<td>"+html.escape(str(x))+"</td>" for x in row)+"</tr>" for row in rows)+"</tbody></table></div>")
            elif kind=="refs":
                tb.append(r"\small\textbf{Selected exact-source links.} "+"; ".join(r"\href{"+link(paths[k])+"}{["+ids[k]+"] "+tex(label)+"}" for k,label in cfg["selected_references"])+r"\par\normalsize")
                md += ["### Exact-source evidence",""]+["- ["+ids[k]+": "+label+"]("+link(paths[k])+")" for k,label in cfg["selected_references"]]+[""]
                hb.append("<p><strong>Exact-source evidence.</strong> "+"; ".join('<a href="'+html.escape(link(paths[k]),quote=True)+'">['+ids[k]+'] '+html.escape(label)+'</a>' for k,label in cfg["selected_references"])+"</p>")
            elif kind=="code":
                tb.append("\\begin{lstlisting}\n"+value+"\n\\end{lstlisting}");md += ["```sh",value,"```",""];hb.append("<pre>"+html.escape(value)+"</pre>")
    tb.append(r"\end{document}");hb.append("</main></body></html>")
    texfile=out/"AGI_ALPHA_Late_008.tex";texfile.write_text("\n".join(tb)+"\n")
    (out/"REPORT.md").write_text("\n".join(md)+"\n");(out/"index.html").write_text("\n".join(hb)+"\n")
    command=["pdflatex","-interaction=nonstopmode","-halt-on-error","-output-directory",str(out),str(texfile)]
    for i in range(2):
        r=subprocess.run(command,cwd=out,capture_output=True);(out/("BUILD_PASS_"+str(i+1)+".log")).write_bytes(r.stdout+b"\n"+r.stderr)
        if r.returncode:raise RuntimeError("LaTeX build failed")
    own,child=resource.getrusage(resource.RUSAGE_SELF),resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt={"operation":"LATE_PAPER_GENERATION_NOT_SCIENCE","source_ref":ref,"start_utc":started,"end_utc":dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),"wall_seconds":time.monotonic()-start,"cpu_seconds_self_plus_waited_children":own.ru_utime+own.ru_stime+child.ru_utime+child.ru_stime,"peak_self_rss_kib":own.ru_maxrss,"peak_child_rss_kib":child.ru_maxrss,"prior_measured_paper_CPU_seconds":PRIOR_MEASURED_PAPER_CPU,"original_paper_reservation_CPU_seconds":600,"current_process_CPU_limit_seconds":580,"memory_bytes_per_process":2147483648,"complete_monetary_cost":"UNKNOWN","scope":"Generation only; no numerical/data experiment or new allocation. Rendering/inference/orchestration remain separate or unknown."}
    (out/"BUILD_RECEIPT.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps({"source_ref":ref,"consumed_files":len(consumed),"snapshot_sha256":snapshot,"output":str(out),"receipt":receipt}))


if __name__=="__main__":main()
