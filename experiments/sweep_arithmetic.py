"""Sweep arithmetic operations: op x n => T-count, qubits.

Outputs:
  results/sweep_arithmetic.csv
  results/chart_arithmetic_scaling.png
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

from ftprims.algorithms._base import registry


# ModAdd cost extraction is very slow for large n in Qualtran,
# so we cap it separately.
_BITSIZES: dict[str, list[int]] = {
    "add": [8, 16, 32, 64, 128, 256, 512],
    "add_oop": [8, 16, 32, 64, 128, 256, 512],
    "leq": [8, 16, 32, 64, 128, 256, 512],
    "mul": [8, 16, 32, 64, 128, 256, 512],
    "modadd": [8, 16, 32],
}


def main() -> None:
    bench = registry["arithmetic"]
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)

    rows: list[dict] = []
    for op, bitsizes in _BITSIZES.items():
        for n in bitsizes:
            bloq = bench.build_bloq(n=n, op=op)
            costs = bench.logical_costs(bloq)
            row = {
                "op": op,
                "n": n,
                "qubits": costs.qubits,
                "t_count": costs.t_count,
            }
            rows.append(row)
            print(f"{op:10s}  n={n:4d}  T={costs.t_count:>10,}  q={costs.qubits}")

    # ── CSV ──────────────────────────────────────────────────────────
    csv_path = out_dir / "sweep_arithmetic.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {csv_path}")

    # ── Chart ────────────────────────────────────────────────────────
    colors = {
        "add": "#3498db",
        "add_oop": "#2ecc71",
        "leq": "#e67e22",
        "mul": "#e74c3c",
        "modadd": "#9b59b6",
    }

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    for op in _BITSIZES:
        subset = [r for r in rows if r["op"] == op]
        ns = [r["n"] for r in subset]
        ts = [r["t_count"] for r in subset]
        qs = [r["qubits"] for r in subset]
        ax1.loglog(ns, ts, "o-", color=colors[op], linewidth=2, markersize=7, label=op)
        ax2.loglog(ns, qs, "o-", color=colors[op], linewidth=2, markersize=7, label=op)

    ax1.set_xlabel("Bitsize (n)")
    ax1.set_ylabel("T-equivalent count")
    ax1.set_title("Arithmetic: T-gate Scaling")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3, which="both")

    ax2.set_xlabel("Bitsize (n)")
    ax2.set_ylabel("Logical qubits")
    ax2.set_title("Arithmetic: Qubit Scaling")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3, which="both")

    plt.tight_layout()
    chart_path = out_dir / "chart_arithmetic_scaling.png"
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    print(f"Saved {chart_path}")


if __name__ == "__main__":
    main()
