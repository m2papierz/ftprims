"""Sweep QROM parameters: data_size x variant, plus Pareto trade-off.

Outputs:
  results/sweep_qrom.csv
  results/chart_qrom_scaling.png
  results/chart_qrom_pareto.png
  results/chart_qrom_breakdown.png
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt

from ftprims.algorithms import registry
from ftprims.breakdown import extract_structural_breakdown, summarize_breakdown


DATA_SIZES = [16, 32, 64, 128, 256, 512, 1024]
PARETO_DATA_SIZE = 256


def collect_scaling(bench) -> list[dict]:
    rows: list[dict] = []
    for data_size in DATA_SIZES:
        for variant in ["basic", "selectswap"]:
            bloq = bench.build_bloq(data_size=data_size, variant=variant)
            costs = bench.logical_costs(bloq)
            items = extract_structural_breakdown(bloq)
            summary = summarize_breakdown(items)

            def _ftqc(component: str) -> int:
                return sum(i.est_t_ftqc for i in items if i.component == component)

            rows.append(
                {
                    "data_size": data_size,
                    "variant": variant,
                    "logical_qubits_estimate": costs.logical_qubits_estimate,
                    "t_count_direct": costs.t_count_direct,
                    "t_count_ftqc": costs.t_count_ftqc,
                    "rotation_count": costs.rotation_count,
                    "clifford_count": costs.clifford_count,
                    "dominant_component": summary.get("dominant_component", ""),
                    "dominant_share": round(summary.get("dominant_share", 0), 3),
                    "qrom_core_ftqc": _ftqc("qrom_core"),
                    "arithmetic_core_ftqc": _ftqc("arithmetic_core"),
                    "controlled_nonclifford_ftqc": _ftqc("controlled_nonclifford"),
                }
            )
            print(
                f"N={data_size:5d}  {variant:12s}  "
                f"T_ftqc={costs.t_count_ftqc:>8,}  "
                f"dom={summary.get('dominant_component', '')}"
            )
    return rows


def collect_pareto(bench, data_size: int = PARETO_DATA_SIZE) -> list[dict]:
    sel_bits = int(math.log2(data_size))
    rows: list[dict] = []

    print(f"\nPareto sweep: SelectSwapQROM N={data_size}")
    for k in range(1, sel_bits):
        bloq = bench.build_bloq(
            data_size=data_size,
            variant="selectswap",
            log_block_sizes=k,
        )
        costs = bench.logical_costs(bloq)
        rows.append(
            {
                "k": k,
                "logical_qubits_estimate": costs.logical_qubits_estimate,
                "t_count_ftqc": costs.t_count_ftqc,
            }
        )
        print(
            f"  k={k}  T_ftqc={costs.t_count_ftqc:>8,}  q={costs.logical_qubits_estimate}"
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
        ("basic", "#e74c3c", "o"),
        ("selectswap", "#3498db", "s"),
    ]:
        subset = [r for r in rows if r["variant"] == variant]
        ns = [r["data_size"] for r in subset]
        ts = [r["t_count_ftqc"] for r in subset]
        qs = [r["logical_qubits_estimate"] for r in subset]
        ax1.loglog(
            ns,
            ts,
            f"{marker}-",
            color=color,
            linewidth=2,
            markersize=8,
            label=variant,
        )
        ax2.loglog(
            ns,
            qs,
            f"{marker}-",
            color=color,
            linewidth=2,
            markersize=8,
            label=variant,
        )

    ax1.set_xlabel("Data size (N)")
    ax1.set_ylabel("T-count (FTQC)")
    ax1.set_title("QROM: T-gate Scaling")
    ax1.legend()
    ax1.grid(True, alpha=0.3, which="both")

    ax2.set_xlabel("Data size (N)")
    ax2.set_ylabel("Logical qubits (estimate)")
    ax2.set_title("QROM: Qubit Scaling")
    ax2.legend()
    ax2.grid(True, alpha=0.3, which="both")

    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved {path}")


def plot_pareto(rows: list[dict], data_size: int, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))

    qs = [r["logical_qubits_estimate"] for r in rows]
    ts = [r["t_count_ftqc"] for r in rows]
    ks = [r["k"] for r in rows]

    # Compute actual Pareto frontier: keep only non-dominated points.
    # A point is dominated if another point has both fewer qubits AND fewer T-gates.
    frontier_idx = []
    for i in range(len(qs)):
        dominated = False
        for j in range(len(qs)):
            if i == j:
                continue
            if qs[j] <= qs[i] and ts[j] <= ts[i] and (qs[j] < qs[i] or ts[j] < ts[i]):
                dominated = True
                break
        if not dominated:
            frontier_idx.append(i)

    # Plot all points as light markers.
    ax.plot(qs, ts, "o", color="#d5d5d5", markersize=8, zorder=1)
    for q, t, k in zip(qs, ts, ks):
        ax.annotate(
            f"k={k}",
            (q, t),
            textcoords="offset points",
            xytext=(8, 4),
            fontsize=9,
            color="#999999",
        )

    # Highlight Pareto-optimal points.
    frontier = sorted(frontier_idx, key=lambda i: qs[i])
    fq = [qs[i] for i in frontier]
    ft = [ts[i] for i in frontier]
    fk = [ks[i] for i in frontier]
    ax.plot(fq, ft, "o-", color="#8e44ad", linewidth=2, markersize=10, zorder=2)
    for q, t, k in zip(fq, ft, fk):
        ax.annotate(
            f"k={k}",
            (q, t),
            textcoords="offset points",
            xytext=(8, 4),
            fontsize=9,
            fontweight="bold",
            color="#8e44ad",
        )

    ax.set_xlabel("Total logical qubits")
    ax.set_ylabel("T-count (FTQC)")
    ax.set_title(f"SelectSwapQROM: T-gates vs Qubits Pareto Frontier (N={data_size})")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved {path}")


def plot_breakdown(rows: list[dict], path: Path) -> None:
    """Grouped bar: gate-type breakdown (T-direct, Cliffords) for selectswap."""
    subset = [r for r in rows if r["variant"] == "selectswap"]
    ns = [str(r["data_size"]) for r in subset]
    t_direct = [r["t_count_direct"] for r in subset]
    cliffords = [r["clifford_count"] for r in subset]

    x = range(len(ns))
    w = 0.35

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(
        [i - w / 2 for i in x], t_direct, w, label="T-gates (direct)", color="#e74c3c"
    )
    ax.bar(
        [i + w / 2 for i in x], cliffords, w, label="Clifford gates", color="#95a5a6"
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(ns)
    ax.set_xlabel("Data size (N)")
    ax.set_ylabel("Gate count")
    ax.set_title("SelectSwapQROM: Gate-Type Breakdown")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved {path}")


def main() -> None:
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)
    bench = registry["qrom"]

    scaling_rows = collect_scaling(bench)
    save_csv(scaling_rows, out_dir / "sweep_qrom.csv")
    plot_scaling(scaling_rows, out_dir / "chart_qrom_scaling.png")
    plot_breakdown(scaling_rows, out_dir / "chart_qrom_breakdown.png")

    pareto_rows = collect_pareto(bench, PARETO_DATA_SIZE)
    plot_pareto(pareto_rows, PARETO_DATA_SIZE, out_dir / "chart_qrom_pareto.png")


if __name__ == "__main__":
    main()
