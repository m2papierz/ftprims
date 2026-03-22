"""Sweep arithmetic operations: op x n => T-count, qubits, breakdown.

Outputs:
  results/sweep_arithmetic.csv
  results/chart_arithmetic_scaling.png
  results/chart_arithmetic_breakdown.png
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt

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
    "add": "#3498db",
    "add_oop": "#2ecc71",
    "leq": "#e67e22",
    "mul": "#e74c3c",
    "modadd": "#9b59b6",
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
        subset = [r for r in rows if r["op"] == op]
        ns = [r["n"] for r in subset]
        ts = [r["t_count_ftqc"] for r in subset]
        qs = [r["logical_qubits_estimate"] for r in subset]
        ax1.loglog(ns, ts, "o-", color=COLORS[op], linewidth=2, markersize=7, label=op)
        ax2.loglog(ns, qs, "o-", color=COLORS[op], linewidth=2, markersize=7, label=op)

    ax1.set_xlabel("Bitsize (n)")
    ax1.set_ylabel("T-count (FTQC)")
    ax1.set_title("Arithmetic: T-gate Scaling")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3, which="both")

    ax2.set_xlabel("Bitsize (n)")
    ax2.set_ylabel("Logical qubits (estimate)")
    ax2.set_title("Arithmetic: Qubit Scaling")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3, which="both")

    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved {path}")


def plot_breakdown(rows: list[dict], path: Path) -> None:
    """Stacked bar: arithmetic_core vs controlled_nonclifford for add at various n."""
    subset = [r for r in rows if r["op"] == "add"]
    ns = [str(r["n"]) for r in subset]
    arith = [r["arithmetic_core_ftqc"] for r in subset]
    ctrl = [r["controlled_nonclifford_ftqc"] for r in subset]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(ns, arith, label="arithmetic_core", color="#3498db")
    ax.bar(ns, ctrl, bottom=arith, label="controlled_nonclifford", color="#e74c3c")
    ax.set_xlabel("Bitsize (n)")
    ax.set_ylabel("Estimated FTQC T-cost")
    ax.set_title("Arithmetic (add): Cost Breakdown by Component")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(path, dpi=150, bbox_inches="tight")
    print(f"Saved {path}")


def main() -> None:
    out_dir = Path("results")
    out_dir.mkdir(exist_ok=True)

    rows = collect(registry["arithmetic"])
    save_csv(rows, out_dir / "sweep_arithmetic.csv")
    plot_scaling(rows, out_dir / "chart_arithmetic_scaling.png")
    plot_breakdown(rows, out_dir / "chart_arithmetic_breakdown.png")


if __name__ == "__main__":
    main()
