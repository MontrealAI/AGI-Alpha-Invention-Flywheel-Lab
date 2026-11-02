import hashlib
import json
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import StrMethodFormatter


HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
INPUTS = {"water": CAMPAIGN / "n1/ORIGINAL_W1.json", "model": CAMPAIGN / "n3/RESULT_001.json"}
records = {k: json.loads(p.read_text()) for k, p in INPUTS.items()}
identities = {k: {"path": str(p.relative_to(CAMPAIGN)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for k, p in INPUTS.items()}
water = records["water"]["dates"]
spatial = records["model"]["spatial_cases"]
groups = list(dict.fromkeys(tuple(r["halfwidths_mm"]) for r in spatial))
means = [r["uniform_average_max_abs_mpa"] for r in spatial]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.titleweight": "bold", "axes.labelcolor": "#334155", "text.color": "#17243b", "xtick.color": "#475569", "ytick.color": "#475569", "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#cbd5e1", "svg.fonttype": "none", "savefig.facecolor": "white"})
fig, (left, right) = plt.subplots(1, 2, figsize=(14.5, 7.3), gridspec_kw={"width_ratios": [1.12, 1]})
fig.subplots_adjust(left=0.115, right=0.965, top=0.74, bottom=0.25, wspace=0.48)
fig.suptitle("Recorded quantities and the remaining observation gap", x=0.06, y=0.965, ha="left", fontsize=20, weight="bold")
fig.text(0.06, 0.91, "Historical water inputs and a separate authored manufacturing model", fontsize=12, color="#64748b")

left.set_title("A  Historical water counters", loc="left", fontsize=13, pad=37)
left.text(0, 1.045, "Seven frozen W1 dates; no fresh N1 measurements", transform=left.transAxes, fontsize=10, color="#64748b")
left.text(1.035, 1.045, "Quality", transform=left.transAxes, fontsize=9, weight="bold", ha="center")
for i, row in enumerate(water):
    amount = row["observed_counter_increment_l"]
    if amount is None:
        left.axhspan(i - 0.32, i + 0.32, color="#f1f5f9", zorder=0)
        left.text(120, i, "Missing: three-byte file", va="center", fontsize=9.5, color="#64748b")
    else:
        if amount > 0:
            left.barh(i, amount, height=0.53, color="#4c7895", zorder=3)
        else:
            left.scatter([0], [i], s=34, marker="o", facecolors="white", edgecolors="#4c7895", clip_on=False, zorder=4)
        left.text(amount + 110, i, f"{amount:,.0f}", va="center", fontsize=10, color="#334155")
    left.text(1.035, i, row["quality_status"], transform=left.get_yaxis_transform(), ha="center", va="center", fontsize=9, color="#9a640c", weight="bold", clip_on=False)
left.set_yticks(range(len(water)), [date.fromisoformat(r["date"]).strftime("%d %b %Y") for r in water])
left.set_ylim(len(water) - 0.5, -0.5)
left.set_xlim(0, 6300)
left.set_xticks([0, 2000, 4000, 6000])
left.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
left.grid(axis="x", color="#e2e8f0", linewidth=0.7, zorder=0)
left.tick_params(axis="y", length=0, pad=10)
left.spines["left"].set_visible(False)
left.set_xlabel("Observed counter increment (L)", labelpad=12)
left.text(0, -0.28, "Quality-qualified delivery remains unknown for all seven dates.\nThe two observed zeros retain unresolved causes.", transform=left.transAxes, va="top", fontsize=9.5, color="#64748b", linespacing=1.5)

right.set_title("B  Opposite local stresses, similar averages", loc="left", fontsize=13, pad=37)
right.text(0, 1.045, "Authored compact eigenstrain model; six registered fields", transform=right.transAxes, fontsize=10, color="#64748b")
right.axhline(0, color="#94a3b8", linewidth=1, linestyle="--", zorder=1)
for x, widths in enumerate(groups):
    pair = [r for r in spatial if tuple(r["halfwidths_mm"]) == widths]
    right.vlines(x, min(r["center_xx_mpa"] for r in pair), max(r["center_xx_mpa"] for r in pair), color="#cbd5e1", linewidth=1, zorder=1)
    for row in pair:
        sign = 1 if row["center_xx_mpa"] >= 0 else -1
        dx = 0.055 * sign
        right.scatter(x + dx, row["center_xx_mpa"], marker="^" if sign > 0 else "v", s=100, color="#b4524e" if sign > 0 else "#476d99", zorder=4)
        right.scatter(x + dx, row["uniform_average_max_abs_mpa"], marker="o", s=35, facecolors="white", edgecolors="#17243b", linewidth=1.2, zorder=5)
right.set_xticks(range(len(groups)), [" × ".join(f"{v:g}" for v in g) for g in groups])
right.set_xlim(-0.5, len(groups) - 0.5)
right.set_ylim(-130, 130)
right.set_yticks([-100, -50, 0, 50, 100])
right.set_ylabel("Stress (MPa)", labelpad=8)
right.set_xlabel("Registered support halfwidths (mm)", labelpad=12)
right.grid(axis="y", color="#e2e8f0", linewidth=0.7, zorder=0)
right.tick_params(axis="x", length=0, pad=8)
right.legend(handles=[Line2D([], [], marker="^", color="none", markerfacecolor="#b4524e", markeredgecolor="#b4524e", label="Positive field: center σxx", markersize=7), Line2D([], [], marker="v", color="none", markerfacecolor="#476d99", markeredgecolor="#476d99", label="Negative field: center σxx", markersize=7), Line2D([], [], marker="o", color="none", markerfacecolor="white", markeredgecolor="#17243b", label="Max |uniform mean component|", markersize=6)], loc="upper center", bbox_to_anchor=(0.5, -0.19), frameon=False, fontsize=9, ncol=1, handletextpad=0.6, labelspacing=0.65)
right.text(0.5, 0.57, f"Largest mean magnitude ≈ {max(means):.2e} MPa", transform=right.transAxes, ha="center", fontsize=9, color="#475569", bbox={"facecolor": "white", "edgecolor": "none", "pad": 3})
fig.text(0.06, 0.055, "Evidence limits: no physical or commercial admission. Panel B is a mathematical witness, not a NIST gauge measurement or fabricated part.", fontsize=9, color="#64748b")
fig.text(0.06, 0.027, "Sources: n1/ORIGINAL_W1.json (immutable W1 history) and n3/RESULT_001.json (registered authored-model output).", fontsize=8.5, color="#64748b")
fig.savefig(HERE / "recorded_evidence.svg", metadata={"Title": "Recorded quantities and the remaining observation gap", "Description": "Display-only rendering of recorded historical W1 quantities and authored N3 spatial stress witnesses."})
fig.savefig(HERE / "recorded_evidence.png", dpi=160)
plt.close(fig)
chart_data = {"role": "DISPLAY_ONLY_NO_EXPERIMENT_EXECUTION", "input_identities": identities, "panel_a": {"scope": records["water"]["scope"], "source_commit": records["water"]["commit"], "rows": [{k: r[k] for k in ["date", "observed_counter_increment_l", "quality_status", "quantity_1000_l_day", "qualified_delivered_volume_l"]} for r in water]}, "panel_b": {"scope": "authored compact eigenstrain model, not NIST gauge or part", "registered_spatial_case_denominator": records["model"]["denominators"]["spatial_cases"], "rows": [{"source_spatial_case_index": i, **{k: r[k] for k in ["halfwidths_mm", "center_xx_mpa", "uniform_average_max_abs_mpa", "scope"]}} for i, r in enumerate(spatial)], "uniform_mean_display": "Stored maximum absolute uniform-average component, not an invented signed scalar mean. Both members of each pair are plotted."}, "transformations": ["Date labels formatted for display; all seven source dates retained.", "Missing quantity retained as null and displayed without a bar or zero marker.", "Six recorded spatial cases grouped by exact halfwidth triple; no additional field calculations.", "Annotation gives maximum of the six stored uniform_average_max_abs_mpa values."]}
(HERE / "chart_data.json").write_text(json.dumps(chart_data, indent=2) + "\n")
caption = f"""# Recorded-evidence figure

![Historical water quantities and authored stress witnesses](recorded_evidence.svg)

**Panel A:** Historical W1 daily counter increments retained in `n1/ORIGINAL_W1.json` at predecessor `{records['water']['commit']}`. All seven dates remain visible. February 15 is a three-byte missing source file, not zero production. January and March contain observed zero increments with unresolved causes. Every date remains quality HOLD. The plotted quantity is an archive counter increment; it is not independently qualified water delivery, a new N1 measurement or a seasonal-reliability estimate. The original three conditional quantity passes concern a separate stock calculation with cyclic storage.

**Panel B:** The six already-recorded spatial witnesses in `n3/RESULT_001.json`, grouped into three registered support-halfwidth triples. Filled triangles show the center sigma_xx values of the two authored fields, approximately -100 and +100 MPa. Open circles show each result's stored maximum absolute uniform-average stress component, approximately zero on this scale. The thin connector groups a pair; it is not a confidence interval. The largest stored mean magnitude is `{max(means):.17g}` MPa. These are authored compact eigenstrain-model results, not NIST gauge readings, empirical manufacturing errors or validation of a fabricated component.

The script reads the two existing JSON artifacts and renders their data. It imports no experiment constructor or runner, retrieves no new source and generates no test outcome. The display preserves the distinction between measured-input history and authored-model output. It claims no physical or commercial admission.

## Input identities

| Input | SHA256 |
|---|---|
| `{identities['water']['path']}` | `{identities['water']['sha256']}` |
| `{identities['model']['path']}` | `{identities['model']['sha256']}` |

`chart_data.json` retains the exact plotted values, source row indices, input identities and display transformations. No missing observation is interpolated.

## Reproduce the display

```sh
python3 experiments/next_series_20261102_365c3d6c/charts/chart.py
```

Outputs: `recorded_evidence.svg` for the repository, `recorded_evidence.png` for visual inspection, and `chart_data.json` for exact data provenance. Python and matplotlib are required. Running this command regenerates only display artifacts in this directory.
"""
(HERE / "CAPTION.md").write_text(caption)
print(json.dumps({"outputs": ["recorded_evidence.svg", "recorded_evidence.png", "chart_data.json", "CAPTION.md"], "input_identities": identities, "historical_dates": len(water), "authored_spatial_cases": len(spatial)}))
