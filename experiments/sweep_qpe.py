"""Sweep QPE precision: m → T-count, qubits.

Outputs:
  results/sweep_qpe.csv
  results/chart_qpe_scaling.png
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

from ftprims.algorithms import registry


PRECISIONS = [4, 6, 8, 10, 12]
PHI = 0.25


def collect(bench) -> list[dict]:
    rows: list[dict] = []
    for m in PRECISIONS:
        bloq = bench.build_bloq(m=m, phi=PHI)
        costs = bench.logical_costs(bloq)
        rows.append(
            {
                "m": m,
                "phi": PHI,
                "logical_qubits_estimate": costs.qubits,
                "t_count_direct": costs.t_count_direct,
                "t_count_ftqc": costs.t_count_ftqc,
                "raw_t": costs.raw_t,
                "ccz_count": costs.ccz_count,
                "clifford_count": costs.clifford_count,
                "rotation_count": costs.rotation_count,
            }
        )
        print(
            f"m={m:3d}  T_ftqc={costs.t_count_ftqc:>8,}  "
            f"q={costs.qubits}  rot={costs.rotation_count}"
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

    ms = [r["m"] for r in rows]
    ts = [r["t_count_ftqc"] for r in rows]
    qs = [r["logical_qubits_estimate"] for r in rows]

    ax1.semilogy(ms, ts, "o-", color="#e74c3c", linewidth=2, markersize=8)
    ax1.set_xlabel("Precision bits (m)")
    ax1.set_ylabel("T-count (FTQC, incl. rotation synthesis)")
    ax1.set_title("QPE: Non-Clifford Cost vs Precision")
    ax1.grid(True, alpha=0.3, which="both")

    ax2.plot(ms, qs, "s-", color="#3498db", linewidth=2, markersize=8)
    ax2.set_xlabel("Precision bits (m)")
    ax2.set_ylabel("Logical qubits (estimate)")
    ax2.set_title("QPE: Qubit Count vs Precision")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved {path}")


def main() -> None:
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)

    rows = collect(registry["qpe"])
    save_csv(rows, out_dir / "sweep_qpe.csv")
    plot_scaling(rows, out_dir / "chart_qpe_scaling.png")


if __name__ == "__main__":
    main()
