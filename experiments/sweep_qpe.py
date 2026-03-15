"""Sweep QPE precision: m => T-count, qubits.

Outputs:
  results/sweep_qpe.csv
  results/chart_qpe_scaling.png
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

from ftprims.algorithms import registry


def main() -> None:
    bench = registry["qpe"]
    precisions = [4, 6, 8, 10, 12]
    phi = 0.25
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)

    rows: list[dict] = []
    for m in precisions:
        bloq = bench.build_bloq(m=m, phi=phi)
        costs = bench.logical_costs(bloq)
        row = {
            "m": m,
            "phi": phi,
            "qubits": costs.qubits,
            "t_count": costs.t_count,
            "rotation_count": costs.rotation_count,
        }
        rows.append(row)
        print(
            f"m={m:3d}  T={costs.t_count:>8,}  q={costs.qubits}  rot={costs.rotation_count}"
        )

    # ── CSV ──────────────────────────────────────────────────────────
    csv_path = out_dir / "sweep_qpe.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {csv_path}")

    # ── Chart ────────────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    ms = [r["m"] for r in rows]
    ts = [r["t_count"] for r in rows]
    qs = [r["qubits"] for r in rows]

    ax1.semilogy(ms, ts, "o-", color="#e74c3c", linewidth=2, markersize=8)
    ax1.set_xlabel("Precision bits (m)")
    ax1.set_ylabel("T-equivalent count")
    ax1.set_title("QPE: Non-Clifford Cost vs Precision")
    ax1.grid(True, alpha=0.3, which="both")

    ax2.plot(ms, qs, "s-", color="#3498db", linewidth=2, markersize=8)
    ax2.set_xlabel("Precision bits (m)")
    ax2.set_ylabel("Logical qubits")
    ax2.set_title("QPE: Qubit Count vs Precision")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    chart_path = out_dir / "chart_qpe_scaling.png"
    plt.savefig(chart_path, dpi=150, bbox_inches="tight")
    print(f"Saved {chart_path}")


if __name__ == "__main__":
    main()
