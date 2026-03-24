"""Sweep arithmetic operations: op x n => T-count, qubits, breakdown.

Outputs:
  results/sweeps/sweep_arithmetic.csv
  results/charts/arithmetic_scaling.png
  results/charts/arithmetic_breakdown.png
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

from _style import (
    FIG_DUAL,
    FIG_TALL,
    PALETTE,
    apply_theme,
    light_grid,
    savefig,
)
from ftprims.algorithms import registry
from ftprims.breakdown import extract_structural_breakdown, summarize_breakdown


# ModAdd cost extraction is very slow for large n in Qualtran,
# so we cap it separately.
BITSIZES: dict[str, list[int]] = {
    "add": [8, 16, 32, 64, 128, 256, 512],
    "add_oop": [8, 16, 32, 64, 128, 256, 512],
    "leq": [8, 16, 32, 64, 128, 256, 512],
    "mul": [8, 16, 32, 64, 128, 256, 512],
    "modadd": [8, 16, 32],
}

COLORS = {
    "add": PALETTE["blue"],
    "add_oop": PALETTE["green"],
    "leq": PALETTE["orange"],
    "mul": PALETTE["red"],
    "modadd": PALETTE["purple"],
}


def collect(bench) -> list[dict]:
    rows: list[dict] = []
    for op, bitsizes in BITSIZES.items():
        for n in bitsizes:
            bloq = bench.build_bloq(n=n, op=op)
            costs = bench.logical_costs(bloq)
            items = extract_structural_breakdown(bloq)
            summary = summarize_breakdown(items)

            def _ftqc(component: str) -> int:
                return sum(i.est_t_ftqc for i in items if i.component == component)

            rows.append(
                {
                    "op": op,
                    "n": n,
                    "logical_qubits_estimate": costs.logical_qubits_estimate,
                    "t_count_direct": costs.t_count_direct,
                    "t_count_ftqc": costs.t_count_ftqc,
                    "rotation_count": costs.rotation_count,
                    "clifford_count": costs.clifford_count,
                    "dominant_component": summary.get("dominant_component", ""),
                    "dominant_share": round(summary.get("dominant_share", 0), 3),
                    "arithmetic_core_ftqc": _ftqc("arithmetic_core"),
                    "controlled_nonclifford_ftqc": _ftqc("controlled_nonclifford"),
                }
            )
            print(
                f"{op:10s}  n={n:4d}  "
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
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    for op in BITSIZES:
        color = COLORS[op]
        ts_positive = [r for r in rows if r["op"] == op and r["t_count_ftqc"] > 0]
        qs_positive = [
            r for r in rows if r["op"] == op and r["logical_qubits_estimate"] > 0
        ]

        if ts_positive:
            ax1.loglog(
                [r["n"] for r in ts_positive],
                [r["t_count_ftqc"] for r in ts_positive],
                "o-",
                color=color,
                label=op,
            )

        if qs_positive:
            ax2.loglog(
                [r["n"] for r in qs_positive],
                [r["logical_qubits_estimate"] for r in qs_positive],
                "o-",
                color=color,
                label=op,
            )

    ax1.set_xlabel("Bitsize (n)")
    ax1.set_ylabel("FTQC T-count")
    ax1.set_title("Arithmetic: T-gate Scaling")
    ax1.legend(fontsize=9)
    light_grid(ax1, which="both")

    ax2.set_xlabel("Bitsize (n)")
    ax2.set_ylabel("Logical qubits (estimate)")
    ax2.set_title("Arithmetic: Qubit Scaling")
    ax2.legend(fontsize=9)
    light_grid(ax2, which="both")

    plt.tight_layout()
    savefig(fig, path)


def plot_breakdown(rows: list[dict], path: Path) -> None:
    """Grouped bar: gate-type breakdown per op at n=16 (log scale)."""
    target_n = 16
    subset = [r for r in rows if r["n"] == target_n]
    if not subset:
        all_ns = sorted({r["n"] for r in rows})
        target_n = all_ns[0]
        subset = [r for r in rows if r["n"] == target_n]

    ops = [r["op"] for r in subset]
    t_direct = [r["t_count_direct"] for r in subset]
    cliffords = [r["clifford_count"] for r in subset]

    x = range(len(ops))
    w = 0.35

    fig, ax = plt.subplots(figsize=FIG_TALL)
    bars_t = ax.bar(
        [i - w / 2 for i in x],
        t_direct,
        w,
        label="T-gates (direct)",
        color=PALETTE["red"],
        alpha=0.85,
    )
    bars_c = ax.bar(
        [i + w / 2 for i in x],
        cliffords,
        w,
        label="Clifford gates",
        color=PALETTE["gray"],
        alpha=0.7,
    )

    # Log scale so mul doesn't crush add/add_oop
    ax.set_yscale("log")

    # Value labels
    for bar, val in zip(list(bars_t) + list(bars_c), t_direct + cliffords):
        if val > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                val * 1.15,
                str(val),
                ha="center",
                va="bottom",
                fontsize=7.5,
            )

    ax.set_xticks(list(x))
    ax.set_xticklabels(ops)
    ax.set_xlabel("Operation")
    ax.set_ylabel("Gate count")
    ax.set_title(f"Arithmetic: Gate-Type Breakdown (n={target_n})")
    ax.legend(fontsize=9)
    light_grid(ax, axis="y", which="both")
    plt.tight_layout()
    savefig(fig, path)


def main() -> None:
    apply_theme()

    csv_dir = Path("results/sweeps")
    chart_dir = Path("results/charts")
    csv_dir.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)

    rows = collect(registry["arithmetic"])
    save_csv(rows, csv_dir / "sweep_arithmetic.csv")
    plot_scaling(rows, chart_dir / "arithmetic_scaling.png")
    plot_breakdown(rows, chart_dir / "arithmetic_breakdown.png")


if __name__ == "__main__":
    main()
