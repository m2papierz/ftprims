"""Sweep GE19's windowed modexp over the window grid and over modulus size
(ASSUMPTIONS.md sec. 6). Writes results/sweeps/sweep_windowed_modexp.csv with
panels ``window_grid`` / ``falloff`` / ``default_window``."""

from __future__ import annotations

import csv
import math
from pathlib import Path

from qrepro.algorithms.windowed_factoring import (
    ge19_exponent_bitsize,
    make_ge19_windowed_modexp,
    windowed_term_breakdown,
)
from qrepro.references.ge19_windowed import WINDOW_GRID, windowed_best_window
from qrepro.references.values import GE19, GE19_WINDOWED, WINDOWED_COEFFICIENT_SIZES

GRID_N = GE19["n"]  # 2048
GE19_DEFAULT_WINDOW = (GE19_WINDOWED["exp_window"], GE19_WINDOWED["mul_window"])

#: Sizes GE19 tabulates in Table 1, i.e. the sizes the reproduction reports.
TABULATED_SIZES = (1024, 2048, 3072)


def _total_ccz(n: int, we: int, wm: int) -> int:
    return windowed_term_breakdown(
        make_ge19_windowed_modexp(n, exp_window=we, mul_window=wm)
    ).total_ccz


def collect() -> tuple[list[dict], list[dict], list[dict]]:
    """Window-grid rows at n=2048, the falloff series, and the default-window
    comparison at every size GE19 tabulates."""
    grid_rows: list[dict] = []
    for we, wm in WINDOW_GRID:
        bloq = make_ge19_windowed_modexp(GRID_N, exp_window=we, mul_window=wm)
        terms = windowed_term_breakdown(bloq)
        total = terms.total_ccz
        grid_rows.append(
            dict(
                n=GRID_N,
                exp_window=we,
                mul_window=wm,
                lookup_bits=we + wm,
                table_entries=2 ** (we + wm),
                total_ccz=total,
                adder_ccz=terms.adder_ccz,
                lookup_ccz=terms.lookup_ccz,
                unlookup_ccz=terms.unlookup_ccz,
                adder_share=round(terms.adder_ccz / total, 4),
                lookup_share=round(terms.lookup_ccz / total, 4),
                unlookup_share=round(terms.unlookup_ccz / total, 4),
                bridged_ccz=terms.adder_bridged_total_ccz,
                ratio_vs_table1=round(
                    total / (GE19["table1_toffoli_billions"]["n2048"] * 1e9), 4
                ),
            )
        )

    falloff_rows: list[dict] = []
    for n in WINDOWED_COEFFICIENT_SIZES:
        we, wm = windowed_best_window(n)
        ne = ge19_exponent_bitsize(n)
        total = windowed_term_breakdown(
            make_ge19_windowed_modexp(n, exp_window=we, mul_window=wm)
        ).total_ccz
        coeff = total / (ne * n**2)
        falloff_rows.append(
            dict(
                n=n,
                exp_bitsize=ne,
                best_exp_window=we,
                best_mul_window=wm,
                total_ccz=total,
                coefficient=round(coeff, 6),
                coefficient_times_lg2n=round(coeff * math.log2(n) ** 2, 4),
            )
        )

    default_rows: list[dict] = []
    for n in TABULATED_SIZES:
        table1 = GE19["table1_toffoli_billions"][f"n{n}"] * 1e9
        best_we, best_wm = windowed_best_window(n)
        argmin_total = _total_ccz(n, best_we, best_wm)
        default_total = _total_ccz(n, *GE19_DEFAULT_WINDOW)
        default_rows.append(
            dict(
                n=n,
                exp_window=GE19_DEFAULT_WINDOW[0],
                mul_window=GE19_DEFAULT_WINDOW[1],
                total_ccz=default_total,
                ratio_vs_table1=round(default_total / table1, 4),
                best_exp_window=best_we,
                best_mul_window=best_wm,
                argmin_total_ccz=argmin_total,
                argmin_ratio_vs_table1=round(argmin_total / table1, 4),
            )
        )
    return grid_rows, falloff_rows, default_rows


def write_csv(
    grid_rows: list[dict],
    falloff_rows: list[dict],
    default_rows: list[dict],
    path: Path,
) -> None:
    """One CSV holding all three panels, tagged by a `panel` column."""
    every = grid_rows + falloff_rows + default_rows
    fields = sorted({k for r in every for k in r} | {"panel"})
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in grid_rows:
            writer.writerow({**row, "panel": "window_grid"})
        for row in falloff_rows:
            writer.writerow({**row, "panel": "falloff"})
        for row in default_rows:
            writer.writerow({**row, "panel": "default_window"})
    print(f"Saved {path}")


def main() -> None:
    results = Path("results")
    (results / "sweeps").mkdir(parents=True, exist_ok=True)

    grid_rows, falloff_rows, default_rows = collect()
    write_csv(
        grid_rows,
        falloff_rows,
        default_rows,
        results / "sweeps" / "sweep_windowed_modexp.csv",
    )

    best = min(grid_rows, key=lambda r: r["total_ccz"])
    print(
        f"\nCost minimum at n={GRID_N}: "
        f"(w_e, w_m) = ({best['exp_window']}, {best['mul_window']}), "
        f"{best['total_ccz'] / 1e9:.4f}e9 CCZ"
    )
    print(f"GE19 published default (L690): {GE19_DEFAULT_WINDOW}")

    print("\nargmin window vs GE19's published (5, 5), per tabulated n:")
    for row in default_rows:
        print(
            f"  n={row['n']:5d}  argmin ({row['best_exp_window']}, "
            f"{row['best_mul_window']}) = {row['argmin_ratio_vs_table1']:.4f} x Table 1"
            f"   |   (5, 5) = {row['ratio_vs_table1']:.4f} x Table 1"
        )


if __name__ == "__main__":
    main()
