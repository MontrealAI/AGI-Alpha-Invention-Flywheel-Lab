"""Eligibility audit of the author-linked GRASP implementation, not a GRASP run.

Only metadata and original compatibility observations are retained here. No
third-party algorithm source, binary, instance, or modified derivative is bundled.
The inspection did not change the frozen production060 model or held-out plans.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil


REPOSITORY = "https://github.com/aliousmane/concrete-delivery-problem"
COMMIT = "1de9fdea499817bd4020e3459d29752bf3a12b26"
PAPER = "https://doi.org/10.1016/j.cor.2024.106818"


def _file(path: str, blob_sha: str) -> dict:
    return {"path": path, "git_blob_sha1": blob_sha,
            "url": f"{REPOSITORY}/blob/{COMMIT}/{path}"}


_INSPECTION = {
    "schema_version": "production060-grasp-eligibility-v1",
    "inspection_date": "2026-11-01",
    "repository": REPOSITORY,
    "commit": COMMIT,
    "paper": {"title": "A GRASP algorithm for the concrete delivery problem",
              "authors": ["Ousmane Ali", "Jean-François Côté", "Leandro C. Coelho"],
              "year": 2024, "doi": "10.1016/j.cor.2024.106818",
              "primary_publication_url": "https://www.sciencedirect.com/science/article/pii/S0305054824002909"},
    "status": "not_executed_licensing_build_and_model_gaps",
    "third_party_execution_attempted": False,
    "third_party_code_vendored": False,
    "benchmark_comparison_available": False,
    "performance_verdict": None,
    "strongest_existing_method_claim": False,
    "license_observations": {
        "github_repository_license_metadata": None,
        "root_license_or_copying_file_found": False,
        "algorithm_subtree_license_or_copying_file_found": False,
        "source_subtrees_inspected": ["codeCDP", "codeCQ"],
        "root_readme_license_grant_found": False,
        "bundled_library_readme": "codeCDP/lib/README.TXT asserts open-source status for that library; it supplies no named license and does not establish an algorithm-wide license grant",
        "conclusion": "No explicit applicable algorithm license was verified; public visibility alone was not treated as a reusable open-source license.",
        "primary_policy_reference": "https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository",
    },
    "build_observations": {
        "provided_targets": ["codeCDP", "codeCQ"],
        "language_standard": "C++23",
        "unconditional_prescribed_dependencies": ["IBM CPLEX/Concert", "Gurobi", "LEMON"],
        "proprietary_headers_in_prescribed_target": ["ilcplex/ilocplex.h", "gurobi_c++.h"],
        "hardcoded_author_installation_paths": True,
        "free_solver_only_build_target_verified": False,
        "conclusion": "The supplied CMake targets require proprietary solver headers and libraries even for the named executable; no tested solver-free build route was established.",
        "limitation": "This is a source inspection, not proof that a licensed heuristic-only build could never be constructed.",
    },
    "variant_observations": {
        "codeCDP": "README identifies the Kinable et al. 2014 variant",
        "codeCQ": "README identifies the Ali et al. 2024 variant",
        "published_method": "GRASP with randomized greedy construction and local search, with a separate exact model",
        "published_scope": "driver working shifts, minimum work and overtime, multiple customer concrete orders, heterogeneous fleet and plant scheduling",
        "scope_limit": "A relevant published specialist method; no performance ranking against the production060 model was executed.",
    },
    "compatibility_gaps": [
        {"topic": "driver inputs", "author_code": "CQ text reader expects driver identifiers, truck number, rank, depot, capacity and shift start",
         "production060": "public normalized fleet supplies anonymized id, capacity and home plant; no driver shift starts or ranks",
         "required_resolution": "independently justified shift inputs and compatible declared shift model"},
        {"topic": "travel and distance", "author_code": "CQ reader loads separate global time and distance matrices and divides time entries by60",
         "production060": "order-to-plant and plant-to-plant truck minutes; no road-distance matrix or matching CQ global distance IDs",
         "required_resolution": "explicit matrix-ID adapter without inventing road distances or applying the truck multiplier twice"},
        {"topic": "loading and unloading", "author_code": "CQ duration functions use60 times quantity divided by depot rate and an unloading rate; CQ defaults unloading30m3/hour",
         "production060": "source plant-rate units unspecified; frozen fixed10min loading and10min unloading",
         "required_resolution": "obtain supported units or deliberately port GRASP construction to the same fixed-duration acceptance model"},
        {"topic": "load splitting and plant choice", "author_code": "CQ creates a capacity-based delivery-node range and reads an assigned depot per order",
         "production060": "exact client positive split maximum or7.5m3 fallback, exact terminal partial, loading plant selected by dispatcher",
         "required_resolution": "preserve the production060 exact accepted load set and permitted plant choices in any adapter"},
        {"topic": "working and time windows", "author_code": "CQ defaults include600min max working,120min overtime,180min minimum work,480min normal work,120min travel threshold and derived customer windows",
         "production060": "source15min break plus30min meal before every reused trip;240min continuous block and720min span review flags; soft requested-load lateness; no invented concrete-lifetime limit",
         "required_resolution": "freeze one common model; do not compare objective values under conflicting feasibility assumptions"},
        {"topic": "objective", "author_code": "CQ Cost comparison is lexicographic over undelivered demand, first-delivery cost, travel, waiting, overtime and underwork",
         "production060": "all required quantity delivered; weighted120 per activated truck plus1 per travel minute plus10 per late minute",
         "required_resolution": "use common accepted schedules and recomputed common objective; changing the heuristic's selection rule would be a disclosed adaptation"},
    ],
    "next_eligible_comparison": [
        "Verify an applicable license or obtain explicit reuse permission for the algorithm and necessary dependencies.",
        "Establish an authorized free local build or a lawfully available existing licensed build, with source and dependency bindings.",
        "Freeze a transparent adapter and one common model before fresh evaluation; original published and adapted variants must remain distinguishable.",
        "Run development correctness and independent acceptance checks, then use prospectively held-out instances with matched information and measured complete runtime.",
    ],
    "claim_boundary": "The CP-SAT/best-fit implementation is an executed ordinary open-source baseline within its declared restricted search. It is not established as globally strongest, optimal for the day, or better than the published GRASP.",
    "source_evidence": [
        _file("README.md", "f5dc34ff86faac85adbfdd21e69f36bd6c2fa1a6"),
        _file("codeCQ/CMakeLists.txt", "4822a60d677f9ba5c518910062227abbe0c85ba4"),
        _file("codeCDP/CMakeLists.txt", "095921409b7cf29e319d30f8cab94afc48e8d40e"),
        _file("codeCQ/Data.cpp", "bc0dd5b4285082492f549f10a0d56b0fce54fd27"),
        _file("codeCQ/Data.h", "d2339370a8d52115cf10290558fea49520432898"),
        _file("codeCQ/Parameters.cpp", "eac6398eaddea5d7c295643cef8fd940cbab57bf"),
        _file("codeCQ/Cost.cpp", "dd30f1834e671d76d25cde282fde6b1fdf9a49f4"),
        _file("codeCQ/model/cplex/cplexSolver.h", "f77ec82a3c0dec0ec1184d09aaa7017d5554e5c9"),
        _file("codeCQ/model/gurobi/gurobiSolver.h", "b3b041601a01f216a6caf14ebe637c74e23f8089"),
        _file("codeCDP/lib/README.TXT", "512cf862d0a7c41bbb1ca03f1cecc5bf7ff83460"),
    ],
    "metadata_evidence": [
        "https://api.github.com/repos/aliousmane/concrete-delivery-problem",
        f"https://api.github.com/repos/aliousmane/concrete-delivery-problem/contents?ref={COMMIT}",
        "https://api.github.com/repos/aliousmane/concrete-delivery-problem/git/trees/3bc42d137aedfff549f822cc045670b177aef0d9?recursive=1",
        "https://api.github.com/repos/aliousmane/concrete-delivery-problem/git/trees/b491995d55f606fc6d1ce67fab325ee719a53f5f?recursive=1",
    ],
}


def comparison_eligibility() -> dict:
    """Return the pinned inspection; no external code or build command is run."""
    result = copy.deepcopy(_INSPECTION)
    result["local_tool_presence"] = {name: shutil.which(name) is not None for name in ("g++", "cmake")}
    result["local_tool_presence"]["note"] = "Compiler presence does not establish an applicable code license or proprietary solver license."
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = comparison_eligibility()
    payload = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload)
        print(json.dumps({"output": str(args.output), "status": result["status"],
                          "third_party_execution_attempted": False}))
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
