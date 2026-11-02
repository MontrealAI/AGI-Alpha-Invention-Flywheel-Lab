"""Plot recorded retrospective reveal events, with an exact source-hash receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

import numpy as np

from .freeze import validate_freeze


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="New figure directory")
    args = parser.parse_args(argv)
    bound = validate_freeze(Path(__file__).resolve().parents[1])
    if args.output.exists():
        raise ValueError("Figure directory already exists; preserve the previous attempt")
    source = args.attempt / "results.json"
    raw = source.read_bytes()
    result = json.loads(raw)
    curves = {
        name: [0] + [row["cumulative_discoveries_after_seal"] for row in rows]
        for name, rows in result["receipts"].items()
    }
    budget = result["query_budget"]
    if any(len(values) != budget + 1 for values in curves.values()):
        raise ValueError("Incomplete registered curve; do not omit failed control records")
    hashes = np.asarray([curves[f"hash_{i:02d}"] for i in range(32)], dtype=float)
    x = list(range(budget + 1))
    counts = result["full_profile_cost_counts"]
    source_receipt = {
        "scope": "Retrospective selections on published condition means, not newly executed assays",
        "source_results_sha256": hashlib.sha256(raw).hexdigest(),
        "source_public_freeze_commit": result["public_freeze_commit"],
        "source_execution_kind": result.get("execution_kind"),
        "plot_source_freeze_sha256": bound["freeze_document_sha256"],
        "x_additional_double_queries": x,
        "curves_discovered_targets": curves,
        "hash_control_mean": hashes.mean(axis=0).tolist(),
        "hash_control_min": hashes.min(axis=0).tolist(),
        "hash_control_max": hashes.max(axis=0).tolist(),
        "hash_summary_semantics": "Finite range and mean across 32 registered hash policies; not uncertainty on biology",
        "initial_and_total_profile_counts": counts,
        "confirmation_target_count": result["target_count"],
        "interpolation": "None: markers and range bars at integer recorded query counts only",
    }
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "next072-matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(12, 7.5))
    mean, low, high = hashes.mean(axis=0), hashes.min(axis=0), hashes.max(axis=0)
    ax.errorbar(x, mean, yerr=[mean - low, high - mean], fmt=".", color="#a5a5a5",
                ecolor="#d5d5d5", elinewidth=4, capsize=0,
                label="32 hash controls: mean and finite min–max range", zorder=1)
    styles = [
        ("probability_of_hit", "Probability of Hit (primary)", "#175c9c", "o"),
        ("ordinary_equal_content", "Equal-content conventional reuse", "#1b998b", "+"),
        ("static_probability_of_hit", "Static Probability of Hit", "#a64d79", "s"),
        ("sequential_kernel", "UCB kernel control", "#226c71", "P"),
        ("static_kernel", "Static UCB kernel", "#996f45", "h"),
        ("kernel_exploitation", "Kernel exploitation", "#d48725", "^"),
        ("linear_ridge", "Conventional linear ridge", "#453781", "D"),
        ("additive_magnitude", "Additive-effect magnitude", "#617d3b", "v"),
        ("diversity", "Feature diversity", "#b64443", "x"),
        ("constant_features", "Constant-feature ablation", "#6b655c", "1"),
    ]
    for name, label, color, marker in styles:
        ax.plot(x, curves[name], linestyle="none", marker=marker, markersize=5.8,
                color=color, markerfacecolor="none" if marker not in ("+", "x", "1") else color,
                markeredgewidth=1.3, label=label, zorder=3)
    threshold = math.ceil(0.5 * result["target_count"])
    ax.axhline(threshold, color="#303030", linestyle="--", linewidth=.9,
               label=f"Registered boundary: at least {threshold}/{result['target_count']} targets")
    ax.set_title("Budgeted discovery on published perturbation means", loc="left", fontsize=16, pad=14)
    ax.set_xlabel("Additional double-perturbation outcomes revealed")
    ax.set_ylabel("Declared confirmation targets discovered")
    ax.set_xlim(-.5, budget + .5)
    ax.set_ylim(-.5, max(result["target_count"], high.max()) + .8)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(axis="y", alpha=.2)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.02), frameon=False, fontsize=9.2)
    footer = (
        f"All policies start with {result['reference_pairs']} double-pair references, "
        f"{counts['unique_single_profiles']} single profiles and one control. "
        f"{result['confirmation_pairs']} candidate pairs; {result['target_count']} targets.\n"
        "Markers are recorded integer-query events. Grey bars summarize the 32 fixed hash policies; "
        "they are not biological confidence intervals.\n"
        f"Source results SHA256: {source_receipt['source_results_sha256']}"
    )
    fig.text(.08, .025, footer, fontsize=8.4, va="bottom", color="#404040")
    fig.subplots_adjust(left=.08, right=.65, bottom=.20, top=.90)
    args.output.mkdir(parents=True)
    fig.savefig(args.output / "discovery_by_query.png", dpi=180)
    fig.savefig(args.output / "discovery_by_query.svg", metadata={"Date": None})
    plt.close(fig)
    (args.output / "chart_source.json").write_text(json.dumps(source_receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "RECORDED_SERIES_PLOTTED", "source_results_sha256": source_receipt["source_results_sha256"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
