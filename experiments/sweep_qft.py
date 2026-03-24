"""Sweep QFT parameters: n x variant => T-count, qubits, cost breakdown.

Outputs:
  results/sweeps/sweep_qft.csv
  results/charts/qft_scaling.png
  results/charts/qft_breakdown.png
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

from _style import (
    FIG_DUAL,
    PALETTE,
    apply_theme,
    light_grid,
    savefig,
)
from ftprims.algorithms import registry
from ftprims.breakdown import extract_structural_breakdown, summarize_breakdown


BITSIZES = [4, 8, 16, 32, 64, 128]
VARIANTS = ["textbook", "approx"]


def collect(bench) -> list[dict]:
    rows: list[dict] = []
    for n in BITSIZES:
        for variant in VARIANTS:
            bloq = bench.build_bloq(n=n, variant=variant)
            costs = bench.logical_costs(bloq)
            items = extract_structural_breakdown(bloq)
            summary = summarize_breakdown(items)
            rows.append(
                {
                    "n": n,
                    "variant": variant,
                    "logical_qubits_estimate": costs.logical_qubits_estimate,
                    "t_count_direct": costs.t_count_direct,
                    "t_count_ftqc": costs.t_count_ftqc,
                    "clifford_count": costs.clifford_count,
                    "rotation_count": costs.rotation_count,
                    "dominant_component": summary.get("dominant_component", ""),
                    "dominant_share": round(summary.get("dominant_share", 0), 3),
                    "rotations_ftqc": sum(
                        i.est_t_ftqc for i in items if i.component == "rotations"
                    ),
                    "clifford_scaffolding_ftqc": sum(
                        i.est_t_ftqc
                        for i in items
                        if i.component == "clifford_scaffolding"
                    ),
                }
            )
            print(
                f"n={n:4d}  {variant:10s}  "
                f"T_direct={costs.t_count_direct:>8,}  "
                f"T_ftqc={costs.t_count_ftqc:>10,}  "
                f"dom={summary.get('dominant_component', '')}"
            )
    return rows


def save_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {path}")


def plot_scaling(rows: list[dict], path: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIG_DUAL)

    styles = {
        "textbook": (PALETTE["red"], "o", "textbook"),
        "approx": (PALETTE["blue"], "s", "approx"),
    }

    # Left panel: FTQC T-count (both variants)
    for variant, (color, marker, label) in styles.items():
        subset = [r for r in rows if r["variant"] == variant and r["t_count_ftqc"] > 0]
        if not subset:
            continue
        ns = [r["n"] for r in subset]
        ts = [r["t_count_ftqc"] for r in subset]
        ax1.semilogy(ns, ts, f"{marker}-", color=color, label=label)

    ax1.set_xlabel("Bitsize (n)")
    ax1.set_ylabel("FTQC T-count")
    ax1.set_title("QFT: Non-Clifford Cost Scaling")
    ax1.legend()
    light_grid(ax1, which="both")

    # Right panel: savings ratio if both have T-count, else Clifford comparison.
    tb = {r["n"]: r["t_count_ftqc"] for r in rows if r["variant"] == "textbook"}
    ap = {r["n"]: r["t_count_ftqc"] for r in rows if r["variant"] == "approx"}
    ns_ratio = sorted(n for n in tb if ap.get(n, 0) > 0 and tb[n] > 0)

    if ns_ratio:
        ratios = [tb[n] / ap[n] for n in ns_ratio]
        ax2.plot(ns_ratio, ratios, "o-", color=PALETTE["green"])
        for x, y in zip(ns_ratio, ratios):
            ax2.annotate(
                f"{y:.1f}\u00d7",
                (x, y),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=9,
                color=PALETTE["green"],
                fontweight="bold",
            )
        ax2.axhline(y=1, color=PALETTE["gray"], linestyle="--", alpha=0.5)
        ax2.set_ylabel("Textbook / Approximate")
        ax2.set_title("FTQC T-count Savings")
    else:
        for variant, (color, marker, label) in styles.items():
            subset = [r for r in rows if r["variant"] == variant]
            cs = [r["clifford_count"] for r in subset]
            ns = [r["n"] for r in subset]
            if any(c > 0 for c in cs):
                ax2.semilogy(ns, cs, f"{marker}-", color=color, label=label)
        ax2.set_ylabel("Clifford gate count")
        ax2.set_title("QFT: Clifford Cost Comparison")
        ax2.legend()

    ax2.set_xlabel("Bitsize (n)")
    light_grid(ax2, which="both")

    plt.tight_layout()
    savefig(fig, path)


def plot_breakdown(rows: list[dict], path: Path) -> None:
    """Two-panel breakdown for textbook QFT."""
    subset = [r for r in rows if r["variant"] == "textbook"]
    ns = [str(r["n"]) for r in subset]
    rot_ftqc = [r["rotations_ftqc"] for r in subset]
    rot_count = [r["rotation_count"] for r in subset]
    cliff_count = [r["clifford_count"] for r in subset]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIG_DUAL)

    # Left: synthesised T-cost (log scale to handle 126..428k range)
    bars = ax1.bar(
        ns,
        rot_ftqc,
        color=PALETTE["red"],
        alpha=0.85,
        label="rotations (synthesised T-cost)",
    )
    ax1.set_yscale("log")
    ax1.set_xlabel("Bitsize (n)")
    ax1.set_ylabel("Estimated FTQC T-cost")
    ax1.set_title("QFT Textbook: Non-Clifford Cost")
    ax1.legend(fontsize=9)
    light_grid(ax1, axis="y", which="both")
    for bar, val in zip(bars, rot_ftqc):
        if val > 0:
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                val * 1.4,
                f"{val:,}",
                ha="center",
                va="bottom",
                fontsize=7.5,
                color=PALETTE["red"],
            )

    # Right: gate counts by type
    x = range(len(ns))
    w = 0.35
    ax2.bar(
        [i - w / 2 for i in x],
        rot_count,
        w,
        label="rotation gates",
        color=PALETTE["red"],
        alpha=0.85,
    )
    ax2.bar(
        [i + w / 2 for i in x],
        cliff_count,
        w,
        label="Clifford gates",
        color=PALETTE["gray"],
        alpha=0.7,
    )
    ax2.set_xticks(list(x))
    ax2.set_xticklabels(ns)
    ax2.set_xlabel("Bitsize (n)")
    ax2.set_ylabel("Gate count")
    ax2.set_title("QFT Textbook: Gate Counts by Type")
    ax2.legend(fontsize=9)
    light_grid(ax2, axis="y")

    plt.tight_layout()
    savefig(fig, path)


def main() -> None:
    apply_theme()

    csv_dir = Path("results/sweeps")
    chart_dir = Path("results/charts")
    csv_dir.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)

    rows = collect(registry["qft"])
    save_csv(rows, csv_dir / "sweep_qft.csv")
    plot_scaling(rows, chart_dir / "qft_scaling.png")
    plot_breakdown(rows, chart_dir / "qft_breakdown.png")


if __name__ == "__main__":
    main()
