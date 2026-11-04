"""Regenerate the public checkpoint, then append a labeled recovery supplement.

No campaign files are written. The public frozen builder remains unchanged.
"""
import argparse
import datetime as dt
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import platform
import re
import resource
import subprocess
import sys
import time

REF = "3360acaffa088ca4e9cc595412026210cb4952b2"
CUTOFF = "2026-10-30T06:13:57Z"
BASE = "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"
REVIEW_URL = BASE + "/pull/12#issuecomment-6516456134"
INTERRUPTION_URL = BASE + "/pull/12#issuecomment-6517268753"
BUILDER_SHA = "136a72c2f0a3f818e395efe39813045258437549269cf881b1856585c4524107"
EXTRA = ["evidence/overnight-008/xct-independent-v1/" + p for p in
         ["REVIEW.md", "INDEPENDENT_RESULT.json", "independent_review.py", "SHA256.json"]]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    repo, out = args.repo.resolve(), args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    resource.setrlimit(resource.RLIMIT_CPU, (600, 600))
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    start = time.monotonic()
    start_utc = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    raw_builder = (repo / "scripts/build_overnight008_paper.py").read_bytes()
    if digest(raw_builder) != BUILDER_SHA:
        raise ValueError("Frozen public builder SHA mismatch")
    spec = importlib.util.spec_from_file_location("frozen_public_builder", repo / "scripts/build_overnight008_paper.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.OUT = out
    sys.argv = [str(repo / "scripts/build_overnight008_paper.py"), "--source-ref", REF,
                "--cutoff-utc", CUTOFF, "--no-compile"]
    module.main()
    manifest = json.loads((out / "SOURCE_SHA256.json").read_text())
    extra_files = {}
    for path in EXTRA:
        raw = subprocess.run(["git", "show", REF + ":" + path], cwd=repo,
                             capture_output=True, check=True).stdout
        extra_files[path] = digest(raw)
    reviews_path = Path(__file__).resolve().parent / "PUBLIC_REVIEWS.json"
    reviews = json.loads(reviews_path.read_text())
    if {c["id"] for c in reviews["comments"]} != {6516456134, 6517268753}:
        raise ValueError("Missing public prior-review/interruption source")
    if reviews_path.resolve() != (out / "PUBLIC_REVIEWS.json").resolve():
        (out / "PUBLIC_REVIEWS.json").write_bytes(reviews_path.read_bytes())

    notice = ("Recovered historical checkpoint. The main text describes public source " + REF[:12] +
              " at " + CUTOFF + ". The recovery supplement distinguishes later public reports, "
              "missing artifacts and current regeneration. No uninterrupted execution or new experiment is claimed.")
    paragraphs = [
        ("Interruption and scope", "At 07:21 UTC on 30 October 2026 the integration owner publicly reported a replacement environment lacking the prior checkout and private source/evidence. This recovery regenerates the historical manuscript from the recloned public commit " + REF + ", using its unchanged builder and source guard. The original six-hour allocation and its 11:07:44 UTC endpoint do not reset. The paper is an executed publication recovery, not evidence of a completed invention or commercial flywheel. The previously lost private PDF is not represented as a surviving file; these outputs are newly generated."),
        ("What the public v1 XCT record supports", "The source-bound v1 review reports feasible initial, selected and uniform region-of-interest widths of approximately 0.17440665865456, equal within 1e-10. A selected 75-degree measured view rejects the original pair but replacement images retain the same feature extrema. Its two full120 LP attempts timed out without primal solutions; full-view uncertainty was UNKNOWN in that record. The review preserves actual wall times 60.53 and 54.76 seconds and total 116.258 CPU-seconds despite configured lower limits. These values are preserved historical receipts, not newly measured recovery runs."),
        ("Later full120 result: prior public review, not replayed here", "The 06:24:57 UTC public review in PR comment 6516456134 reports a separate Fraction check of two then-private arrays against all 19,680 original ray inequalities and nonnegativity. It reports the exact ROI gap 3987691518115482796552877142434739 / 664613997892457936451903530140172288 (approximately 0.006000011331029378), exceeding the authored development target 1/200 = 0.005. If that reported feasible pair is valid, it survives every subset, so angle selection alone cannot meet that target under the unchanged model. This is a reported digital feasible-set obstruction, not measured physical material ambiguity, an industrial tolerance or a buyer obligation."),
        ("Lost replay closure and limits of this edition", "The later checker, constructor, original data-dependent witness arrays and private receipt are absent from the recovered public source closure. Their hashes and narrative in a public comment do not replace those bytes. No full120 numerical construction or exact witness verification was executed by the paper-recovery task. The old v1 reviewer also requires scratch paths absent from the public tree. Therefore the later result is attributed to its prior public review and is not labeled a newly independently replayed proof. The owner must publish a complete fresh source/data-reference/array/checker closure and actual receipts before making that recovery claim."),
        ("Economics and incomplete costs", "No qualified earning or customer purchase is introduced by recovery. Prior inference, failed search, lost artifact reconstruction, data, integration, verification, publication, support and terminal obligations remain part of complete acquisition cost. Missing monetary bills and lost detailed resource records remain UNKNOWN, rather than zero or forgiven sunk costs. This task has a prospective 600 CPU-second and 2 GiB process-memory ceiling within the original allocation; its measured build receipt covers this reconstruction process only, excluding prior work, model inference and separately recorded rendering. No new spending or paid API use was initiated."),
        ("Source identity and current execution", "The historical builder checks all 119 consumed code/data/evidence files against the exact public commit before emitting the manuscript. RECOVERY_PROVENANCE.json adds SHA256 identities for the four public v1 review files and captured public comments used by this supplement. Source identity proves bytes, not truth. Only manuscript regeneration, compilation and page-level visual QA are claimed by this recovery. Old sandbox qualification is historical and must be executed on the replacement host before new generated programs run. A public clone build is also distinct from final downloaded release-package qualification."),
    ]
    tex_path = out / "AGI_ALPHA_Overnight_008.tex"
    tex_source = tex_path.read_text()
    base_tex_sha = digest(tex_source.encode())
    first_section = r"\section{Purpose, public continuity and present decision}"
    tex_source = tex_source.replace(first_section, r"\textbf{" + module.tex(notice) + r"}\par" + "\n" + first_section, 1)
    # Keep each source label and its URL on the same page.
    tex_source = re.sub(r"(\\small\\textbf\{\[(?:E|P)\d+\]\}.*?\\normalsize)",
                        lambda m: "\\begin{samepage}\n" + m.group(1) + "\n\\end{samepage}",
                        tex_source, flags=re.DOTALL)
    supplement = [r"\clearpage\appendix\section{Recovery, interruption and later public review}"]
    for title, text in paragraphs:
        supplement += [r"\subsection*{" + module.tex(title) + "}", module.tex(text) + r"\par"]
    supplement += [r"\textbf{Prior public review:} \url{" + REVIEW_URL + r"}\par",
                   r"\textbf{Interruption record:} \url{" + INTERRUPTION_URL + r"}\par",
                   r"\textbf{Source-bound v1 result:} \url{" + BASE + "/blob/" + REF + "/" + EXTRA[1] + r"}\par"]
    tex_path.write_text(tex_source.replace(r"\end{document}", "\n".join(supplement) + "\n" + r"\end{document}"))
    html_path = out / "index.html"
    h = html_path.read_text()
    h = h.replace('<div class="abstract">', '<div class="status">' + html.escape(notice) + '</div><div class="abstract">', 1)
    hs = "<h2>Recovery, interruption and later public review</h2>" + "".join("<h3>" + html.escape(title) + "</h3><p>" + html.escape(text) + "</p>" for title, text in paragraphs)
    hs += '<p><a href="' + REVIEW_URL + '">Prior public full120 review</a> | <a href="' + INTERRUPTION_URL + '">Interruption record</a></p>'
    html_path.write_text(h.replace("</main>", hs + "</main>"))
    md = ["# AGI ALPHA overnight 008: recovered research checkpoint", "", "**MISSION NOT COMPLETE.**", "", notice, "",
          "[Compiled paper](AGI_ALPHA_Overnight_008.pdf) · [LaTeX](AGI_ALPHA_Overnight_008.tex) · [HTML report](index.html) · [Source hashes](SOURCE_SHA256.json) · [Recovery provenance](RECOVERY_PROVENANCE.json)", "",
          "| Mission link | Decision at the public checkpoint |", "| --- | --- |",
          "| Enabling capability | NOT ESTABLISHED: bounded instruments execute; consequential new work unproved. |",
          "| Technical advantage | NOT ESTABLISHED: ordinary basis methods and robust thermal design tie. |",
          "| Complete-cost profitability | NOT ESTABLISHED: no admitted loss cohort, positive demand floor or bounded lifecycle cost. |",
          "| Investment attractiveness | NOT ESTABLISHED: complete incremental NPV unknown; non-entry remains available. |",
          "| AGI ALPHA value capture | CONDITIONAL: a fixed-fee delivery is modeled; no observed purchase. |",
          "| Unrestricted simulated earnings | VERIFIED: ZERO qualified earnings. |",
          "| Earned-funded construction | NOT ESTABLISHED: construction uses original allocation. |",
          "| Fresh successor advantage | NOT ESTABLISHED: actual Crauste retrieval ties ordinary reuse/reset. |", "",
          "## Executed historical constructions", "",
          "The real Elowitz model has three detected scale ambiguities. The constructed calibrated-observation plan ties both ordinary weighted greedy and the exhaustive three-observation minimum. Actual confined plan execution, separate verifier acceptance and memory retrieval run, but Crauste correctly needs zero added observations in every matched arm. No inheritance edge is established.", "",
          "A bounded source-forcing producer is repaired after real Boehm counterexamples, including an e-notation decoding error of a factor ten million. It replays Elowitz, Crauste and Boehm numerical references with 3/0/0 detected directions. This is developer-directed source fidelity, not scientific superiority or autonomous invention.", "",
          "All 64 geothermal reduced-model interventions are executed. Constructed and ordinary robust OED select the same constant-cold design; field calibration remains missing. Real CAD data readiness is checked, but native rotation-capable execution is blocked; no weakened baseline substitutes for it.", "",
          "All cases remain DEVELOPMENT. No protected scientific superiority confirmation or campaign-wide error-budget reset is claimed. Separate roles share models, libraries and host; this is not external certification.", ""]
    for title, text in paragraphs:
        md += ["## " + title, "", text, ""]
    md += ["## Public evidence and reproduction", "", "- [PR #12](" + BASE + "/pull/12)",
           "- [Exact public source](" + BASE + "/tree/" + REF + ")",
           "- [Public builder](" + BASE + "/blob/" + REF + "/scripts/build_overnight008_paper.py)",
           "- [Source-bound v1 XCT review](" + BASE + "/blob/" + REF + "/" + EXTRA[0] + ")",
           "- [Later full120 public review](" + REVIEW_URL + ")",
           "- [Interruption and takeover](" + INTERRUPTION_URL + ")", "",
           "Run the unmodified public builder for the historical base, or this recovery wrapper for the labeled supplement:", "",
           "```sh", "python3 scripts/build_overnight008_paper.py --source-ref " + REF,
           "python3 PATH_TO_RECOVERY/build_recovery.py --repo PATH_TO_PUBLIC_CHECKOUT --output NEW_RECOVERY_OUTPUT", "```", "",
           "The wrapper requires PUBLIC_REVIEWS.json beside itself. Visual QA and hashes refer to the compiled recovered edition; no new numerical experiment is performed by it.", ""]
    (out / "REPORT.md").write_text("\n".join(md))
    (out / "RECOVERY_PROVENANCE.json").write_text(json.dumps({
        "source_ref": REF, "base_consumed_files": len(manifest["files"]),
        "base_source_snapshot_sha256": manifest["snapshot_sha256"], "base_tex_before_recovery_annotation_sha256": base_tex_sha,
        "unchanged_public_builder_sha256": BUILDER_SHA, "additional_public_source_files": extra_files,
        "public_comments_file_sha256": digest((out / "PUBLIC_REVIEWS.json").read_bytes()),
        "public_comment_urls": [REVIEW_URL, INTERRUPTION_URL],
        "recovery_wrapper_sha256": digest(Path(__file__).read_bytes()),
        "numeric_experiments_in_this_recovery": "NONE; historical results are attributed, not newly replayed",
        "claims": "SHA identities establish byte provenance only; no experiment truth or mission success inferred"
    }, indent=2) + "\n")
    command = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "-output-directory", str(out), str(tex_path)]
    for i in range(2):
        result = subprocess.run(command, cwd=repo, capture_output=True)
        (out / ("BUILD_PASS_" + str(i + 1) + ".log")).write_bytes(result.stdout + b"\n" + result.stderr)
        if result.returncode:
            raise RuntimeError("LATEX_BUILD_FAILED")
    own = resource.getrusage(resource.RUSAGE_SELF)
    child = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = own.ru_utime + own.ru_stime + child.ru_utime + child.ru_stime
    receipt = {"operation": "PUBLIC_SOURCE_PAPER_RECOVERY_NOT_NUMERICAL_EXPERIMENT", "source_ref": REF,
               "start_utc": start_utc, "end_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "wall_seconds": time.monotonic() - start, "cpu_seconds_self_plus_waited_children": cpu,
               "peak_self_rss_kib": own.ru_maxrss, "peak_waited_child_rss_kib": child.ru_maxrss,
               "cpu_ceiling_seconds": 600, "address_space_ceiling_bytes_per_process": 2 * 1024**3,
               "python": platform.python_version(), "complete_monetary_cost": "UNKNOWN",
               "excluded_resources": ["prior lost work", "model inference", "separately executed rendering/QA", "all previous campaign costs"]}
    if cpu >= 600:
        raise RuntimeError("Recovery cumulative CPU ceiling reached")
    (out / "BUILD_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
