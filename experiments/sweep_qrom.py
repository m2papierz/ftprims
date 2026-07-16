"""Sweep QROM parameters: data_size x variant, plus Pareto trade-off.

Outputs:
  results/sweeps/sweep_qrom.csv
  results/charts/qrom_scaling.png
  results/charts/qrom_pareto.png
  results/charts/qrom_breakdown.png
"""

from __future__ import annotations

import csv
import math
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
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=FIG_DUAL)

    styles = {
        "basic": (PALETTE["red"], "o"),
        "selectswap": (PALETTE["blue"], "s"),
    }

    for variant, (color, marker) in styles.items():
        subset = [r for r in rows if r["variant"] == variant]
        ns = [r["data_size"] for r in subset]
        ts = [r["t_count_ftqc"] for r in subset]
        qs = [r["logical_qubits_estimate"] for r in subset]
        ax1.loglog(ns, ts, f"{marker}-", color=color, label=variant)
        ax2.loglog(ns, qs, f"{marker}-", color=color, label=variant)

    # Annotate crossover region on T-count panel
    basic_t = {
        r["data_size"]: r["t_count_ftqc"] for r in rows if r["variant"] == "basic"
    }
    swap_t = {
        r["data_size"]: r["t_count_ftqc"] for r in rows if r["variant"] == "selectswap"
    }
    prev_diff = None
    for n in sorted(basic_t):
        if n not in swap_t:
            continue
        diff = basic_t[n] - swap_t[n]
        if prev_diff is not None and prev_diff <= 0 < diff:
            ax1.axvline(x=n, color=PALETTE["gray"], linestyle=":", alpha=0.6)
            ax1.annotate(
                f"crossover \u2248N={n}",
                xy=(n, basic_t[n]),
                xytext=(15, -20),
                textcoords="offset points",
                fontsize=8,
                color=PALETTE["gray"],
                arrowprops=dict(arrowstyle="->", color=PALETTE["gray"], lw=0.8),
            )
        prev_diff = diff

    ax1.set_xlabel("Data size (N)")
    ax1.set_ylabel("FTQC T-count")
    ax1.set_title("QROM: T-gate Scaling")
    ax1.legend()
    light_grid(ax1, which="both")

    ax2.set_xlabel("Data size (N)")
    ax2.set_ylabel("Logical qubits (estimate)")
    ax2.set_title("QROM: Qubit Scaling")
    ax2.legend()
    light_grid(ax2, which="both")

    plt.tight_layout()
    savefig(fig, path)


def plot_pareto(rows: list[dict], data_size: int, path: Path) -> None:
    """Trade-off curve: all k values labeled, Pareto frontier highlighted."""
    fig, ax = plt.subplots(figsize=FIG_TALL)

    qs = [r["logical_qubits_estimate"] for r in rows]
    ts = [r["t_count_ftqc"] for r in rows]
    ks = [r["k"] for r in rows]

    # Compute Pareto frontier.
    frontier_idx = []
    for i in range(len(qs)):
        dominated = any(
            qs[j] <= qs[i] and ts[j] <= ts[i] and (qs[j] < qs[i] or ts[j] < ts[i])
            for j in range(len(qs))
            if j != i
        )
        if not dominated:
            frontier_idx.append(i)
    frontier_set = set(frontier_idx)

    # Draw full trade-off curve (all k connected, sorted by k).
    order = sorted(range(len(ks)), key=lambda i: ks[i])
    ax.plot(
        [qs[i] for i in order],
        [ts[i] for i in order],
        "o--",
        color="#D1D5DB",
        markersize=9,
        zorder=1,
        linewidth=1.2,
    )

    # Highlight frontier points.
    frontier = sorted(frontier_idx, key=lambda i: qs[i])
    fq = [qs[i] for i in frontier]
    ft = [ts[i] for i in frontier]
    ax.plot(
        fq, ft, "o-", color=PALETTE["purple"], markersize=12, zorder=2, linewidth=2.5
    )

    # Label every point.
    for i in order:
        is_front = i in frontier_set
        color = PALETTE["purple"] if is_front else PALETTE["gray"]
        weight = "bold" if is_front else "normal"
        vert = 12 if ks[i] % 2 != 0 else -16
        label = f"k={ks[i]}"
        if is_front:
            label += " \u2605"
        ax.annotate(
            label,
            (qs[i], ts[i]),
            textcoords="offset points",
            xytext=(10, vert),
            fontsize=9,
            fontweight=weight,
            color=color,
        )

    ax.set_xlabel("Total logical qubits")
    ax.set_ylabel("FTQC T-count")
    ax.set_title(f"SelectSwapQROM: Qubits vs T-gates Trade-off (N={data_size})")
    light_grid(ax)

    plt.tight_layout()
    savefig(fig, path)


def plot_breakdown(rows: list[dict], path: Path) -> None:
    """Grouped bar: gate-type breakdown (T-direct, Cliffords) for selectswap."""
    subset = [r for r in rows if r["variant"] == "selectswap"]
    ns = [str(r["data_size"]) for r in subset]
    t_direct = [r["t_count_direct"] for r in subset]
    cliffords = [r["clifford_count"] for r in subset]

    x = range(len(ns))
    w = 0.35

    fig, ax = plt.subplots(figsize=FIG_TALL)
    ax.bar(
        [i - w / 2 for i in x],
        t_direct,
        w,
        label="T-gates (direct)",
        color=PALETTE["red"],
        alpha=0.85,
    )
    ax.bar(
        [i + w / 2 for i in x],
        cliffords,
        w,
        label="Clifford gates",
        color=PALETTE["gray"],
        alpha=0.7,
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(ns)
    ax.set_xlabel("Data size (N)")
    ax.set_ylabel("Gate count")
    ax.set_title("SelectSwapQROM: Gate-Type Breakdown")
    ax.legend(fontsize=9)
    light_grid(ax, axis="y")
    plt.tight_layout()
    savefig(fig, path)


def main() -> None:
    apply_theme()

    csv_dir = Path("results/sweeps")
    chart_dir = Path("results/charts")
    csv_dir.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)
    bench = registry["qrom"]

    scaling_rows = collect_scaling(bench)
    save_csv(scaling_rows, csv_dir / "sweep_qrom.csv")
    plot_scaling(scaling_rows, chart_dir / "qrom_scaling.png")
    plot_breakdown(scaling_rows, chart_dir / "qrom_breakdown.png")

    pareto_rows = collect_pareto(bench, PARETO_DATA_SIZE)
    plot_pareto(pareto_rows, PARETO_DATA_SIZE, chart_dir / "qrom_pareto.png")


if __name__ == "__main__":
    main()
