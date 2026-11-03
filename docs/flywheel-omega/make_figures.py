"""Regenerate the vector figure from the exact authored companion, not a forecast."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from companion import staged_arrangement

ROOT = Path(__file__).resolve().parent


def main():
    data = staged_arrangement()
    names = ("ordinary_monolithic", "staging_alone", "connector_alone", "connector_and_staging")
    needs = [data["routes"][name]["minimum_opening_cash"] for name in names]
    path = data["routes"][names[-1]]["notional_cash_path"]
    assert needs == [9, 7, 9, 5] and path == [6, 4, 1, 7, 3, 9]
    colors = {"ink": "#151224", "violet": "#6842A2", "mint": "#176E68", "gold": "#B18740"}
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "axes.labelcolor": colors["ink"], "text.color": colors["ink"],
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.spines.left": False, "axes.spines.bottom": False,
                         "xtick.color": "#61596E", "ytick.color": "#61596E"})
    fig, (left, right) = plt.subplots(1, 2, figsize=(8.0, 3.25), gridspec_kw={"width_ratios": [1, 1.15]})
    fig.patch.set_facecolor("white")
    labels = ["Ordinary\nfinal payment", "Staging\nalone", "Connector\nalone", "Connector\n+ staging"]
    left.barh(range(4), needs, height=.58, color=["#C9C1D6"]*3+[colors["mint"]])
    left.set_yticks(range(4), labels)
    left.invert_yaxis()
    left.axvline(6, color=colors["gold"], linestyle=(0, (3, 3)), lw=1.2)
    left.set_xlim(0, 10.3)
    left.set_xticks([0, 3, 6, 9])
    left.set_xlabel("Minimum opening cash / illustrative units", labelpad=9)
    left.set_title("A. A joint construction crosses the threshold", loc="left", pad=16, fontsize=9.5, fontweight="bold")
    for y, val in enumerate(needs):
        left.text(val+.2, y, str(val), va="center", fontsize=10, fontweight="bold")
    left.tick_params(axis="both", length=0)
    right.step(range(6), path, where="post", lw=1.8, color=colors["violet"])
    right.scatter(range(6), path, s=28, color=[colors["violet"]]*3+[colors["mint"], colors["violet"], colors["mint"]], zorder=3)
    right.axhline(6, color=colors["gold"], linestyle=(0, (3, 3)), lw=1.2)
    right.set_ylim(0, 10.3)
    right.set_xlim(-.25, 5.3)
    right.set_yticks([0, 3, 6, 9])
    right.set_xticks(range(6), ["Start", "Build\n−2", "Produce A\n−3", "Accept A\n+6", "Produce B\n−4", "Accept B\n+6"], fontsize=7.2)
    right.set_title("B. Useful accepted work finances continuation", loc="left", pad=16, fontsize=9.5, fontweight="bold")
    right.set_ylabel("Available cash / illustrative units")
    right.set_xlabel("Each receipt follows acceptance", labelpad=8)
    right.grid(axis="y", color="#E8E2EE", lw=.6)
    right.set_axisbelow(True)
    right.tick_params(axis="both", length=0)
    for x, val in enumerate(path):
        offset = (8, 7) if x in (1, 2, 4) else (0, 7)
        right.annotate(str(val), (x, val), xytext=offset, textcoords="offset points", ha="center", fontsize=9, fontweight="bold", bbox={"facecolor": "white", "edgecolor": "none", "pad": .3})
    fig.tight_layout(w_pad=2)
    directory = ROOT / "figures"
    directory.mkdir(exist_ok=True)
    fig.savefig(directory / "construction.pdf", bbox_inches="tight", metadata={"CreationDate": None, "ModDate": None, "Title": "An authored staged-production liquidity witness"})
    fig.savefig(directory / "construction.png", dpi=190, bbox_inches="tight")
    plt.close(fig)
    print("Regenerated exact staged-construction figure.")


if __name__ == "__main__":
    main()
