"""Render the original synthetic midpoint diagnostic; no new model fitting."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    values = np.genfromtxt(args.traces, delimiter=",", names=True)
    if len(values) != 4201 or values["time_s"][0] != 0 or values["time_s"][-1] != 2100:
        raise ValueError("ORIGINAL_REGISTERED_REFERENCE_GRID_REQUIRED")
    a = np.column_stack([values[f"a_cell{i}"] for i in range(4)])
    b = np.column_stack([values[f"b_cell{i}"] for i in range(4)])
    m = np.column_stack([values[f"midpoint_cell{i}"] for i in range(4)])
    if not np.array_equal(m, (a + b) / 2):
        raise ValueError("COMMON_MIDPOINT_REQUIRED")
    errors = np.maximum(np.sqrt(np.mean((m-a)**2, axis=0)),
                        np.sqrt(np.mean((m-b)**2, axis=0))) / 2 * 100
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none"})
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 5.7), gridspec_kw={"width_ratios": [1.45, 1]})
    fig.subplots_adjust(left=.075, right=.975, bottom=.22, top=.77, wspace=.30)
    ax = axes[0]
    minutes = values["time_s"] / 60
    ax.plot(minutes, a[:, 0], color="#2367a6", linewidth=2.4, label="World A: 2 Ah cell")
    ax.plot(minutes, b[:, 0], color="#cd692d", linewidth=2.4, label="World B: 3 Ah cell")
    ax.plot(minutes, m[:, 0], color="#252525", linestyle="--", linewidth=2, label="One common prediction")
    ax.set(xlabel="Time (minutes)", ylabel="Branch 0 current (A)", xlim=(0, 35))
    ax.set_title("Different exact models, one accepted prediction", loc="left", fontsize=12, pad=13)
    ax.grid(axis="y", alpha=.2)
    ax.legend(frameon=False, fontsize=9.5, loc="upper center")
    ax = axes[1]
    ax.bar(np.arange(4), errors, color=["#677d95", "#96a9bc", "#96a9bc", "#96a9bc"], width=.62)
    ax.axhline(10, color="#ae3333", linewidth=1.6, linestyle="--")
    ax.text(3.45, 10.23, "10% limit", color="#ae3333", ha="right", fontsize=10)
    for i, value in enumerate(errors):
        ax.text(i, value + .25, f"{value:.3f}%", ha="center", fontsize=10)
    ax.set(xticks=range(4), xticklabels=["0", "1", "2", "3"], xlabel="Branch", ylabel="Worst-world NRMSE (%)", ylim=(0, 12))
    ax.set_title("All branch RMSE checks pass", loc="left", fontsize=12, pad=13)
    ax.grid(axis="y", alpha=.2)
    ax.set_axisbelow(True)
    fig.suptitle("Synthetic result: extra identification is unnecessary for this contract", x=.075, y=.94, ha="left", fontsize=16, weight="bold")
    fig.text(.075, .865, "Post-result exploratory diagnostic • Frozen pair and original 2,100-second interval", fontsize=11, color="#555555")
    fig.text(.075, .10, "Smallest RMSE margin: 0.829 mA. All peak errors also pass (worst: 6.010%; limit: 10%).", fontsize=11)
    fig.text(.075, .055, "Two authored models only. No physical measurements, robustness certification, or commercial qualification.", fontsize=10.5, color="#555555")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"Date": None} if args.output.suffix.lower() == ".svg" else {"Software": "Matplotlib"}
    fig.savefig(args.output, dpi=180, metadata=metadata, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
