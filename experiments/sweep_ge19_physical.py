"""Sweep the GE19 physical reproduction over error_budget x n_factories;
deviations use matched conventions (ASSUMPTIONS.md sec. 3). Writes
results/sweeps/sweep_ge19_physical.csv."""

from __future__ import annotations

import csv
from pathlib import Path

from qrepro.physical import estimate_physical_grid_search
from qrepro.references.ge19 import ge19_formula_logical_costs
from qrepro.references.values import GE19

ERROR_BUDGETS = [0.1, 0.2, 0.31, 0.4, 0.5]
FACTORY_COUNTS = [1, 2, 4, 8, 14, 16, 20, 28, 32]


# GE19 publishes a comparable row only at these factory counts (Table 2).
# Rows without a paper counterpart leave their deviation columns blank.
GE19_ROWS = {
    1: dict(name="1 factory", qubits_M=16, hr_per_run=None, hr_expected=6.0 * 24),
    14: dict(name="1 thread", qubits_M=19, hr_per_run=None, hr_expected=0.36 * 24),
    28: dict(name="parallel", qubits_M=20, hr_per_run=5.1, hr_expected=0.31 * 24),
}


def _dev(value: float, target: float | None) -> float | str:
    return "" if target is None else round(value / target - 1, 4)


def collect() -> list[dict]:
    logical = ge19_formula_logical_costs()
    retry = GE19["physical_rows"]["table3_authoritative"]["retry"]

    rows: list[dict] = []
    for eb in ERROR_BUDGETS:
        for nf in FACTORY_COUNTS:
            r = estimate_physical_grid_search(
                logical,
                n_factories=nf,
                error_budget=eb,
                phys_err=GE19["phys_err"],
                cycle_time_us=GE19["cycle_us"],
            )
            qubits_M = r.physical_qubits / 1e6
            hr_per_run = r.wall_time_us / 3.6e9
            hr_expected = hr_per_run / (1 - retry)
            ref = GE19_ROWS.get(nf)
            rows.append(
                {
                    "error_budget": eb,
                    "n_factories": nf,
                    "ge19_row": ref["name"] if ref else "",
                    "physical_qubits_M": round(qubits_M, 4),
                    "runtime_hr_per_run": round(hr_per_run, 4),
                    "runtime_hr_expected": round(hr_expected, 4),
                    "data_code_distance": r.code_distance,
                    "factory_l1_d": r.factory_l1_d,
                    "factory_l2_d": r.factory_l2_d,
                    "failure_prob": round(r.failure_prob, 5),
                    "budget_satisfied": r.budget_satisfied,
                    "dev_qubits_vs_tbl2": (
                        _dev(qubits_M, ref["qubits_M"]) if ref else ""
                    ),
                    "dev_runtime_per_run_vs_tbl3": (
                        _dev(hr_per_run, ref["hr_per_run"]) if ref else ""
                    ),
                    "dev_runtime_expected_vs_tbl2": (
                        _dev(hr_expected, ref["hr_expected"]) if ref else ""
                    ),
                }
            )
            dq = rows[-1]["dev_qubits_vs_tbl2"]
            dt = rows[-1]["dev_runtime_expected_vs_tbl2"]
            print(
                f"eb={eb:<5} nf={nf:3d} {rows[-1]['ge19_row']:>10s}: "
                f"{qubits_M:7.3f}M  {hr_per_run:8.3f}hr/run  "
                f"d={r.code_distance:2d} d1={r.factory_l1_d} d2={r.factory_l2_d}  "
                f"fail={r.failure_prob:.3f}  "
                f"dQ={dq if dq == '' else format(dq, '+.1%'):>7s} "
                f"dT_exp={dt if dt == '' else format(dt, '+.1%'):>7s}"
            )
    return rows


def save_csv(rows: list[dict], path: Path) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {path}")


def main() -> None:
    csv_dir = Path("results/sweeps")
    csv_dir.mkdir(parents=True, exist_ok=True)

    rows = collect()
    save_csv(rows, csv_dir / "sweep_ge19_physical.csv")


if __name__ == "__main__":
    main()
