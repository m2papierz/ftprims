"""Sweep QFT parameters: n x variant => T-count, qubits, cost breakdown.

Outputs:
  results/sweep_qft.csv
  results/chart_qft_scaling.png
  results/chart_qft_breakdown.png
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

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
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    for variant, color, marker in [
        ("textbook", "#e74c3c", "o"),
        ("approx", "#3498db", "s"),
    ]:
        subset = [r for r in rows if r["variant"] == variant]
        ns = [r["n"] for r in subset]
        ts = [r["t_count_ftqc"] for r in subset]
        ax1.semilogy(
            ns, ts, f"{marker}-", color=color, linewidth=2, markersize=8, label=variant
        )

    ax1.set_xlabel("Bitsize (n)")
    ax1.set_ylabel("T-count (FTQC, incl. rotation synthesis)")
    ax1.set_title("QFT: Non-Clifford Cost Scaling")
    ax1.legend()
    ax1.grid(True, alpha=0.3, which="both")

    # Savings ratio
    tb = {r["n"]: r["t_count_ftqc"] for r in rows if r["variant"] == "textbook"}
    ap = {r["n"]: r["t_count_ftqc"] for r in rows if r["variant"] == "approx"}
    ns_ratio = [n for n in sorted(tb) if ap[n] > 0]
    ratios = [tb[n] / ap[n] for n in ns_ratio]

    ax2.plot(ns_ratio, ratios, "o-", color="#2ecc71", linewidth=2, markersize=8)
    ax2.axhline(y=1, color="gray", linestyle="--", alpha=0.5)
    ax2.set_xlabel("Bitsize (n)")
    ax2.set_ylabel("Textbook / Approximate")
    ax2.set_title("FTQC T-count Savings from Approximation")
    ax2.grid(True, alpha=0.3)

    for x, y in zip(ns_ratio, ratios):
        ax2.annotate(
            f"{y:.1f}×",
            (x, y),
            textcoords="offset points",
            xytext=(0, -16),
            ha="center",
        )

    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved {path}")


def plot_breakdown(rows: list[dict], path: Path) -> None:
    """Stacked bar: rotations vs clifford_scaffolding for textbook QFT."""
    subset = [r for r in rows if r["variant"] == "textbook"]
    ns = [str(r["n"]) for r in subset]
    rot = [r["rotations_ftqc"] for r in subset]
    cliff = [r["clifford_scaffolding_ftqc"] for r in subset]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(ns, rot, label="rotations", color="#e74c3c")
    ax.bar(ns, cliff, bottom=rot, label="clifford_scaffolding", color="#95a5a6")
    ax.set_xlabel("Bitsize (n)")
    ax.set_ylabel("Estimated FTQC T-cost")
    ax.set_title("QFT Textbook: Cost Breakdown by Component")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved {path}")


def main() -> None:
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)

    rows = collect(registry["qft"])
    save_csv(rows, out_dir / "sweep_qft.csv")
    plot_scaling(rows, out_dir / "chart_qft_scaling.png")
    plot_breakdown(rows, out_dir / "chart_qft_breakdown.png")


if __name__ == "__main__":
    main()
