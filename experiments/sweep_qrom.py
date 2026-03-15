"""Sweep QROM parameters: data_size x variant, plus Pareto trade-off for SelectSwapQROM.

Outputs:
  results/sweep_qrom.csv
  results/chart_qrom_scaling.png
  results/chart_qrom_pareto.png
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt

from ftprims.algorithms import registry


def main() -> None:
    bench = registry["qrom"]
    data_sizes = [16, 32, 64, 128, 256, 512, 1024]
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)

    # ── Part 1: QROM vs SelectSwapQROM scaling ──────────────────────
    rows: list[dict] = []
    for data_size in data_sizes:
        for variant in ["basic", "selectswap"]:
            bloq = bench.build_bloq(data_size=data_size, variant=variant)
            costs = bench.logical_costs(bloq)
            row = {
                "data_size": data_size,
                "variant": variant,
                "logical_qubits_estimate": costs.qubits,
                "t_count_direct": costs.t_count_direct,
                "t_count_ftqc": costs.t_count_ftqc,
                "raw_t": costs.raw_t,
                "ccz_count": costs.ccz_count,
                "clifford_count": costs.clifford_count,
                "rotation_count": costs.rotation_count,
            }
            rows.append(row)
            print(
                f"N={data_size:5d}  {variant:12s}  "
                f"T_ftqc={costs.t_count_ftqc:>8,}  "
                f"q={costs.qubits}"
            )

    csv_path = out_dir / "sweep_qrom.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {csv_path}")

    # ── Chart: scaling ───────────────────────────────────────────────
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
            ns, ts, f"{marker}-", color=color, linewidth=2, markersize=8, label=variant
        )
        ax2.loglog(
            ns, qs, f"{marker}-", color=color, linewidth=2, markersize=8, label=variant
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
    chart_path = out_dir / "chart_qrom_scaling.png"
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    print(f"Saved {chart_path}")

    # ── Part 2: Pareto sweep of log_block_sizes ──────────────────────
    pareto_data_size = 256
    sel_bits = int(math.log2(pareto_data_size))
    pareto_rows: list[dict] = []

    print(f"\nPareto sweep: SelectSwapQROM N={pareto_data_size}")
    for k in range(1, sel_bits):
        bloq = bench.build_bloq(
            data_size=pareto_data_size, variant="selectswap", log_block_sizes=k
        )
        costs = bench.logical_costs(bloq)
        pareto_rows.append(
            {
                "k": k,
                "logical_qubits_estimate": costs.qubits,
                "t_count_ftqc": costs.t_count_ftqc,
            }
        )
        print(f"  k={k}  T_ftqc={costs.t_count_ftqc:>8,}  q={costs.qubits}")

    fig, ax = plt.subplots(figsize=(8, 5))
    qs = [r["logical_qubits_estimate"] for r in pareto_rows]
    ts = [r["t_count_ftqc"] for r in pareto_rows]
    ks = [r["k"] for r in pareto_rows]

    ax.plot(qs, ts, "o-", color="#8e44ad", linewidth=2, markersize=10)
    for q, t, k in zip(qs, ts, ks):
        ax.annotate(
            f"k={k}", (q, t), textcoords="offset points", xytext=(8, 4), fontsize=9
        )

    ax.set_xlabel("Logical qubits (ancilla)")
    ax.set_ylabel("T-count (FTQC)")
    ax.set_title(f"SelectSwapQROM Pareto: T-gates vs Qubits (N={pareto_data_size})")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    pareto_path = out_dir / "chart_qrom_pareto.png"
    plt.savefig(pareto_path, dpi=150, bbox_inches="tight")
    print(f"Saved {pareto_path}")


if __name__ == "__main__":
    main()
