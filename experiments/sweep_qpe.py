"""Sweep QPE precision: m => T-count, qubits, breakdown.

Outputs:
  results/sweeps/sweep_qpe.csv
  results/charts/qpe_scaling.png
  results/charts/qpe_breakdown.png
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

from ftprims.algorithms import registry
from ftprims.breakdown import extract_structural_breakdown, summarize_breakdown


PRECISIONS = [4, 6, 8, 10, 12]
PHI = 0.25


def collect(bench) -> list[dict]:
    rows: list[dict] = []
    for m in PRECISIONS:
        bloq = bench.build_bloq(m=m, phi=PHI)
        costs = bench.logical_costs(bloq)
        items = extract_structural_breakdown(bloq)
        summary = summarize_breakdown(items)

        def _ftqc(component: str) -> int:
            return sum(i.est_t_ftqc for i in items if i.component == component)

        rows.append(
            {
                "m": m,
                "phi": PHI,
                "logical_qubits_estimate": costs.logical_qubits_estimate,
                "t_count_direct": costs.t_count_direct,
                "t_count_ftqc": costs.t_count_ftqc,
                "rotation_count": costs.rotation_count,
                "dominant_component": summary.get("dominant_component", ""),
                "dominant_share": round(summary.get("dominant_share", 0), 3),
                "qft_qpe_core_ftqc": _ftqc("qft_qpe_core"),
                "rotations_ftqc": _ftqc("rotations"),
                "controlled_nonclifford_ftqc": _ftqc("controlled_nonclifford"),
            }
        )
        print(
            f"m={m:3d}  T_ftqc={costs.t_count_ftqc:>8,}  "
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


def plot_breakdown(rows: list[dict], path: Path) -> None:
    """Stacked bar: qft_qpe_core vs controlled_nonclifford vs rotations."""
    ms = [str(r["m"]) for r in rows]
    qft = [r["qft_qpe_core_ftqc"] for r in rows]
    ctrl = [r["controlled_nonclifford_ftqc"] for r in rows]
    rot = [r["rotations_ftqc"] for r in rows]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(ms, qft, label="qft_qpe_core", color="#3498db")
    ax.bar(ms, ctrl, bottom=qft, label="controlled_nonclifford", color="#e74c3c")
    bottoms = [q + c for q, c in zip(qft, ctrl)]
    ax.bar(ms, rot, bottom=bottoms, label="rotations", color="#f39c12")
    ax.set_xlabel("Precision bits (m)")
    ax.set_ylabel("Estimated FTQC T-cost")
    ax.set_title("QPE: Cost Breakdown by Component")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved {path}")


def main() -> None:
    csv_dir = Path("results/sweeps")
    chart_dir = Path("results/charts")
    csv_dir.mkdir(parents=True, exist_ok=True)
    chart_dir.mkdir(parents=True, exist_ok=True)

    rows = collect(registry["qpe"])
    save_csv(rows, csv_dir / "sweep_qpe.csv")
    plot_scaling(rows, chart_dir / "qpe_scaling.png")
    plot_breakdown(rows, chart_dir / "qpe_breakdown.png")


if __name__ == "__main__":
    main()
